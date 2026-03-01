from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from pandapower_agent.config import settings
from pandapower_agent.power.handlers.common import public_error_message, tool_error
from pandapower_agent.power.registry import TOOL_INDEX, TOOL_SPECS
from pandapower_agent.power.runtime_guard import silence_library_output, suppressed_runtime_metadata
from pandapower_agent.schema.types import ToolResult


def _store_result(state, key: str, result: ToolResult) -> None:
    state.record_result(key, result.model_dump())
    try:
        Path(".agent_last_results.json").write_text(json.dumps(state.last_results, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class ToolExecutor:
    def __init__(self, state):
        self.state = state

    @property
    def responses_tools(self) -> list[dict[str, Any]]:
        return [spec.to_responses_tool() for spec in TOOL_SPECS]

    @property
    def chat_tools(self) -> list[dict[str, Any]]:
        return [spec.to_chat_tool() for spec in TOOL_SPECS]

    def execute(self, tool_name: str, raw_args: str | dict[str, Any]) -> ToolResult:
        if tool_name not in TOOL_INDEX:
            return tool_error(f"Tool '{tool_name}' is not allowed")

        spec = TOOL_INDEX[tool_name]
        parsed: dict[str, Any] = {}
        suppressed_meta: dict[str, object] = {}
        captured = None
        try:
            if isinstance(raw_args, str):
                parsed = json.loads(raw_args) if raw_args else {}
            else:
                parsed = copy.deepcopy(raw_args)
            args_model = spec.args_model.model_validate(parsed)

            if spec.mutating:
                self.state.push_mutation_snapshot(tool_name)

            with silence_library_output() as capture:
                captured = capture
                result = spec.handler(self.state, args_model)
            if captured is not None:
                suppressed_meta = suppressed_runtime_metadata(captured)

            if spec.mutating and not result.ok:
                self.state.undo_last_mutation()
            _store_result(self.state, tool_name, result)
            history_entry: dict[str, Any] = {"tool": tool_name, "args": parsed, "ok": result.ok, "message": result.message}
            if suppressed_meta:
                history_entry["suppressed_runtime"] = suppressed_meta
            self.state.history.append(history_entry)
            return result
        except Exception as exc:
            if spec.mutating:
                self.state.undo_last_mutation()
            if captured is not None and not suppressed_meta:
                suppressed_meta = suppressed_runtime_metadata(captured)
            public_message, next_action = public_error_message(exc)
            err = tool_error(public_message, next_action=next_action)
            _store_result(self.state, tool_name, err)
            history_entry = {
                "tool": tool_name,
                "args": parsed,
                "ok": False,
                "message": err.message,
                "internal_error": f"{exc.__class__.__name__}: {exc}",
            }
            if suppressed_meta:
                history_entry["suppressed_runtime"] = suppressed_meta
            self.state.history.append(history_entry)
            return err


def default_bootstrap_if_needed(executor: ToolExecutor) -> ToolResult | None:
    if executor.state.has_net():
        return None
    return executor.execute("load_builtin_network", {"case_name": settings.default_network})
