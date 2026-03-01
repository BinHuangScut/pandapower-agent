from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from openai import OpenAI

from pandapower_agent.agent.prompts import build_system_prompt
from pandapower_agent.config import settings
from pandapower_agent.power.executor import ToolExecutor, default_bootstrap_if_needed
from pandapower_agent.schema.types import ToolResult

if TYPE_CHECKING:
    from pandapower_agent.power.state import SessionState


class AgentRuntime:
    MAX_IDENTICAL_TOOL_FAILURE_STREAK = 2

    def __init__(self, executor: ToolExecutor, client: Any | None = None, admin_mode: bool = False):
        self.executor = executor
        self.client = client or self._build_client()
        self.admin_mode = admin_mode
        self.turn_history: list[dict[str, str]] = []
        self.max_history_messages = 20

    def _build_client(self) -> OpenAI:
        kwargs: dict[str, Any] = {"api_key": settings.active_api_key}
        if settings.active_base_url:
            kwargs["base_url"] = settings.active_base_url
        return OpenAI(**kwargs)

    def set_admin_mode(self, enabled: bool) -> None:
        self.admin_mode = enabled

    def reset_conversation(self) -> None:
        self.turn_history.clear()

    def _build_turn_input(self, user_message: str) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": build_system_prompt(admin_mode=self.admin_mode)},
            {"role": "system", "content": self._session_context_message()},
            *self.turn_history,
            {"role": "user", "content": user_message},
        ]

    def _append_turn_history(self, user_message: str, assistant_message: str) -> None:
        self.turn_history.append({"role": "user", "content": user_message})
        self.turn_history.append({"role": "assistant", "content": assistant_message})
        if len(self.turn_history) > self.max_history_messages:
            self.turn_history = self.turn_history[-self.max_history_messages :]

    def _safe_count(self, state: "SessionState", table_name: str) -> int:
        if not state.has_net():
            return 0
        table = getattr(state.working_net, table_name, None)
        if table is None:
            return 0
        try:
            return int(len(table.index))
        except Exception:
            try:
                return int(len(table))
            except Exception:
                return 0

    def _session_context_message(self) -> str:
        state = self.executor.state
        if not state.has_net():
            return "Session context: no network loaded yet."

        net = state.working_net
        net_name = state.current_network_name or getattr(net, "name", None) or "unknown"
        return (
            "Session context: "
            f"network_loaded=true, current_network={net_name}, "
            f"bus_count={self._safe_count(state, 'bus')}, "
            f"line_count={self._safe_count(state, 'line')}, "
            f"load_count={self._safe_count(state, 'load')}, "
            f"sgen_count={self._safe_count(state, 'sgen')}, "
            f"gen_count={self._safe_count(state, 'gen')}."
        )

    def _extract_text_from_responses(self, response: Any) -> str:
        if getattr(response, "output_text", None):
            return response.output_text

        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") == "message":
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", "") in {"output_text", "text"} and getattr(c, "text", None):
                        parts.append(c.text)
        return "\n".join(parts).strip()

    def _extract_text_from_chat_message(self, message: Any | None) -> str:
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                item_type = str(item.get("type", ""))
                text = item.get("text", "")
            else:
                item_type = str(getattr(item, "type", ""))
                text = getattr(item, "text", "")

            if item_type not in {"text", "output_text"}:
                continue
            if isinstance(text, dict):
                text = text.get("value") or text.get("text") or ""
            if text:
                parts.append(str(text))
        return "\n".join(part.strip() for part in parts if str(part).strip()).strip()

    def _collect_response_tool_calls(self, response: Any) -> list[Any]:
        calls: list[Any] = []
        for item in getattr(response, "output", []) or []:
            typ = getattr(item, "type", "")
            if typ in {"function_call", "tool_call"}:
                calls.append(item)
        return calls

    def _collect_chat_tool_calls(self, message: Any | None) -> list[Any]:
        if message is None:
            return []
        calls = getattr(message, "tool_calls", None)
        if not calls:
            return []
        return list(calls)

    def _first_chat_message(self, response: Any) -> Any | None:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        return getattr(choices[0], "message", None)

    def _args_preview(self, arguments: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(arguments, str):
            if not arguments:
                return {}
            try:
                parsed = json.loads(arguments)
                return parsed if isinstance(parsed, dict) else {"_raw": arguments}
            except json.JSONDecodeError:
                return {"_raw": arguments}
        return arguments

    def _tool_call_signature(self, tool_name: str, arguments: str | dict[str, Any]) -> str:
        payload = self._args_preview(arguments)
        try:
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            canonical = str(payload)
        return f"{tool_name}:{canonical}"

    def _blocked_repeated_failure(self, tool_name: str, streak: int) -> ToolResult:
        return ToolResult(
            ok=False,
            message=f"Blocked repeated failing tool call: {tool_name}",
            data={
                "reason": "repeated_identical_failure",
                "consecutive_failures": streak,
                "next_action": "Adjust arguments or change approach before retrying the same tool call.",
            },
        )

    def _execute_guarded_tool_call(
        self,
        tool_name: str,
        arguments: str | dict[str, Any],
        last_failed_signature: str | None,
        identical_failure_streak: int,
    ) -> tuple[ToolResult, bool, str | None, int]:
        signature = self._tool_call_signature(tool_name, arguments)
        blocked_repeat = (
            signature == last_failed_signature and identical_failure_streak >= self.MAX_IDENTICAL_TOOL_FAILURE_STREAK
        )
        if blocked_repeat:
            result = self._blocked_repeated_failure(tool_name, identical_failure_streak + 1)
        else:
            result = self.executor.execute(tool_name, arguments)

        if result.ok:
            return result, blocked_repeat, None, 0
        if signature == last_failed_signature:
            return result, blocked_repeat, last_failed_signature, identical_failure_streak + 1
        return result, blocked_repeat, signature, 1

    def _run_turn_with_responses(self, user_message: str, tool_traces: list[dict[str, Any]]) -> tuple[str, bool]:
        response = self.client.responses.create(
            model=settings.active_model,
            tools=self.executor.responses_tools,
            input=self._build_turn_input(user_message),
        )

        steps = 0
        reached_limit = False
        last_failed_signature: str | None = None
        identical_failure_streak = 0
        while steps < settings.max_tool_calls_per_turn:
            steps += 1
            calls = self._collect_response_tool_calls(response)
            if not calls:
                break

            tool_outputs: list[dict[str, Any]] = []
            for call in calls:
                name = getattr(call, "name", "")
                function = getattr(call, "function", None)
                if not name and isinstance(function, dict):
                    name = function.get("name", "")
                if not name and function is not None:
                    name = getattr(function, "name", "")

                arguments = getattr(call, "arguments", None)
                if arguments is None and isinstance(function, dict):
                    arguments = function.get("arguments", "{}")
                if arguments is None and function is not None:
                    arguments = getattr(function, "arguments", "{}")
                if arguments is None:
                    arguments = "{}"
                call_id = getattr(call, "call_id", None) or getattr(call, "id", None)

                result, blocked_repeat, last_failed_signature, identical_failure_streak = (
                    self._execute_guarded_tool_call(
                        name,
                        arguments,
                        last_failed_signature,
                        identical_failure_streak,
                    )
                )

                tool_traces.append(
                    {
                        "tool": name,
                        "args": self._args_preview(arguments),
                        "ok": result.ok,
                        "message": result.message,
                        "blocked_repeat": blocked_repeat,
                    }
                )

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result.model_dump_json(),
                    }
                )

            response = self.client.responses.create(
                model=settings.active_model,
                tools=self.executor.responses_tools,
                previous_response_id=response.id,
                input=tool_outputs,
            )
        else:
            reached_limit = True

        return self._extract_text_from_responses(response), reached_limit

    def _normalize_chat_tool_calls(self, calls: list[Any]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for idx, call in enumerate(calls):
            function = getattr(call, "function", None)
            name = getattr(function, "name", "")
            arguments = getattr(function, "arguments", "{}") or "{}"
            call_id = getattr(call, "id", None) or f"call_{idx + 1}"
            normalized.append({"id": call_id, "name": name, "arguments": arguments})
        return normalized

    def _assistant_message_payload_for_chat(self, message: Any, calls: list[dict[str, str]]) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": "assistant"}
        content = self._extract_text_from_chat_message(message)
        if content:
            payload["content"] = content
        payload["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
            }
            for call in calls
        ]
        return payload

    def _run_turn_with_chat_completions(self, user_message: str, tool_traces: list[dict[str, Any]]) -> tuple[str, bool]:
        messages = self._build_turn_input(user_message)
        response = self.client.chat.completions.create(
            model=settings.active_model,
            tools=self.executor.chat_tools,
            messages=messages,
            tool_choice="auto",
        )

        steps = 0
        reached_limit = False
        last_failed_signature: str | None = None
        identical_failure_streak = 0
        while steps < settings.max_tool_calls_per_turn:
            steps += 1
            message = self._first_chat_message(response)
            calls = self._collect_chat_tool_calls(message)
            if not calls:
                break

            normalized_calls = self._normalize_chat_tool_calls(calls)
            messages.append(self._assistant_message_payload_for_chat(message, normalized_calls))

            for call in normalized_calls:
                result, blocked_repeat, last_failed_signature, identical_failure_streak = (
                    self._execute_guarded_tool_call(
                        call["name"],
                        call["arguments"],
                        last_failed_signature,
                        identical_failure_streak,
                    )
                )
                tool_traces.append(
                    {
                        "tool": call["name"],
                        "args": self._args_preview(call["arguments"]),
                        "ok": result.ok,
                        "message": result.message,
                        "blocked_repeat": blocked_repeat,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result.model_dump_json(),
                    }
                )

            response = self.client.chat.completions.create(
                model=settings.active_model,
                tools=self.executor.chat_tools,
                messages=messages,
                tool_choice="auto",
            )
        else:
            reached_limit = True

        return self._extract_text_from_chat_message(self._first_chat_message(response)), reached_limit

    def run_turn(self, user_message: str) -> dict[str, Any]:
        bootstrap_result = default_bootstrap_if_needed(self.executor)
        tool_traces: list[dict[str, Any]] = []
        if bootstrap_result is not None:
            tool_traces.append(
                {
                    "tool": "load_builtin_network",
                    "ok": bootstrap_result.ok,
                    "message": bootstrap_result.message,
                }
            )

        if settings.use_chat_completions:
            final_text, reached_limit = self._run_turn_with_chat_completions(user_message, tool_traces)
        else:
            final_text, reached_limit = self._run_turn_with_responses(user_message, tool_traces)

        if not final_text:
            final_text = "No final text response generated."
        if reached_limit:
            final_text = (
                f"{final_text}\n\n[Notice] Reached max tool calls in this turn ({settings.max_tool_calls_per_turn})."
            )
        self._append_turn_history(user_message, final_text)

        return {
            "final_text": final_text,
            "tool_traces": tool_traces,
            "history": self.executor.state.history[-20:],
        }
