from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agent.loop import AgentRuntime
from app.power.state import SessionState
from app.power.tools import ToolExecutor
from app.schema.types import ToolResult


@pytest.fixture(autouse=True)
def _default_openai_provider(monkeypatch):
    monkeypatch.setattr("app.agent.loop.settings.llm_provider", "openai")


class FakeCall:
    type = "function_call"

    def __init__(self, name: str, arguments: str, call_id: str = "call_1"):
        self.name = name
        self.arguments = arguments
        self.call_id = call_id


class FakeMessagePart:
    type = "output_text"

    def __init__(self, text: str):
        self.text = text


class FakeMessage:
    type = "message"

    def __init__(self, text: str):
        self.content = [FakeMessagePart(text)]


class FakeResponse:
    def __init__(self, rid: str, output, output_text: str = ""):
        self.id = rid
        self.output = output
        self.output_text = output_text


class FakeResponsesAPI:
    def __init__(self, tool_name: str, arguments: str):
        self.calls = 0
        self.tool_name = tool_name
        self.arguments = arguments
        self.kwargs_history: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.kwargs_history.append(kwargs)
        self.calls += 1
        if self.calls == 1:
            return FakeResponse("r1", [FakeCall(self.tool_name, self.arguments, "call_1")])
        return FakeResponse("r2", [FakeMessage("done")], output_text="done")


class FakeClient:
    def __init__(self, tool_name: str, arguments: str):
        self.responses = FakeResponsesAPI(tool_name=tool_name, arguments=arguments)


class RepeatingFailureResponsesAPI:
    def __init__(self, tool_name: str, arguments: str):
        self.calls = 0
        self.tool_name = tool_name
        self.arguments = arguments

    def create(self, **kwargs):
        _ = kwargs
        self.calls += 1
        if self.calls <= 3:
            return FakeResponse(f"r{self.calls}", [FakeCall(self.tool_name, self.arguments, f"call_{self.calls}")])
        return FakeResponse("r4", [FakeMessage("done")], output_text="done")


class RepeatingFailureClient:
    def __init__(self, tool_name: str, arguments: str):
        self.responses = RepeatingFailureResponsesAPI(tool_name=tool_name, arguments=arguments)


class FakeChatToolCallFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class FakeChatToolCall:
    def __init__(self, name: str, arguments: str, call_id: str = "call_1"):
        self.id = call_id
        self.function = FakeChatToolCallFunction(name=name, arguments=arguments)


class FakeChatMessage:
    def __init__(self, content: str | None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeChatChoice:
    def __init__(self, message: FakeChatMessage):
        self.message = message


class FakeChatResponse:
    def __init__(self, message: FakeChatMessage):
        self.choices = [FakeChatChoice(message)]


class FakeChatCompletionsAPI:
    def __init__(self, tool_name: str, arguments: str):
        self.calls = 0
        self.tool_name = tool_name
        self.arguments = arguments
        self.kwargs_history: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.kwargs_history.append(kwargs)
        self.calls += 1
        if self.calls == 1:
            message = FakeChatMessage(content=None, tool_calls=[FakeChatToolCall(self.tool_name, self.arguments, "call_1")])
            return FakeChatResponse(message)
        return FakeChatResponse(FakeChatMessage(content="done"))


class FakeChatClient:
    def __init__(self, tool_name: str, arguments: str):
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI(tool_name=tool_name, arguments=arguments))


def _fake_network_catalog(query: str | None = None, max_results: int = 20):
    items = [
        {"name": "case14", "category": "ieee_case", "doc": "14-bus"},
        {"name": "case118", "category": "ieee_case", "doc": "118-bus"},
    ]
    if query:
        items = [item for item in items if query.lower() in item["name"].lower()]
    return items[:max_results]


def test_agent_runtime_tool_loop_with_load_builtin_network(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)

    monkeypatch.setattr("app.power.tools.list_available_networks", _fake_network_catalog)
    monkeypatch.setattr("app.power.tools.get_network_factory", lambda case_name: (lambda: {"name": case_name}))

    runtime = AgentRuntime(
        executor=executor,
        client=FakeClient(tool_name="load_builtin_network", arguments='{"case_name":"case14"}'),
    )
    out = runtime.run_turn("load and run")

    assert "done" in out["final_text"]
    assert any(trace["tool"] == "load_builtin_network" for trace in out["tool_traces"])


def test_agent_runtime_tool_loop_with_list_builtin_networks(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)

    monkeypatch.setattr("app.power.tools.list_available_networks", _fake_network_catalog)
    monkeypatch.setattr("app.power.tools.get_network_factory", lambda case_name: (lambda: {"name": case_name}))

    runtime = AgentRuntime(
        executor=executor,
        client=FakeClient(tool_name="list_builtin_networks", arguments='{"query":"118","max_results":5}'),
    )
    out = runtime.run_turn("what built-in systems can I use")

    assert "done" in out["final_text"]
    assert any(trace["tool"] == "list_builtin_networks" for trace in out["tool_traces"])


def test_agent_runtime_keeps_turn_memory(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)

    monkeypatch.setattr("app.power.tools.list_available_networks", _fake_network_catalog)
    monkeypatch.setattr("app.power.tools.get_network_factory", lambda case_name: (lambda: {"name": case_name}))

    client = FakeClient(tool_name="list_builtin_networks", arguments='{"query":"case","max_results":3}')
    runtime = AgentRuntime(executor=executor, client=client)

    runtime.run_turn("first question")
    runtime.run_turn("好")

    second_turn_input = client.responses.kwargs_history[2]["input"]
    assert isinstance(second_turn_input, list)
    assert any(item.get("role") == "assistant" and item.get("content") == "done" for item in second_turn_input)


def test_agent_runtime_includes_session_context_with_loaded_network(monkeypatch) -> None:
    state = SessionState()
    state.current_network_name = "case2848rte"
    state.working_net = SimpleNamespace(bus=[0, 1], line=[0], load=[0], sgen=[], gen=[0])
    executor = ToolExecutor(state)

    monkeypatch.setattr("app.power.tools.list_available_networks", _fake_network_catalog)
    monkeypatch.setattr("app.power.tools.get_network_factory", lambda case_name: (lambda: {"name": case_name}))

    client = FakeClient(tool_name="list_builtin_networks", arguments='{"query":"case","max_results":3}')
    runtime = AgentRuntime(executor=executor, client=client)

    runtime.run_turn("短路计算")
    first_turn_input = client.responses.kwargs_history[0]["input"]
    assert isinstance(first_turn_input, list)
    assert any(
        item.get("role") == "system"
        and "network_loaded=true" in str(item.get("content"))
        and "current_network=case2848rte" in str(item.get("content"))
        for item in first_turn_input
    )


def test_agent_runtime_blocks_identical_repeated_failing_tool_calls(monkeypatch) -> None:
    state = SessionState()
    state.working_net = {"name": "loaded"}
    executor = ToolExecutor(state)
    execute_calls: list[tuple[str, object]] = []

    def fake_execute(tool_name, raw_args):
        execute_calls.append((tool_name, raw_args))
        return ToolResult(ok=False, message="boom")

    monkeypatch.setattr(executor, "execute", fake_execute)

    runtime = AgentRuntime(
        executor=executor,
        client=RepeatingFailureClient(tool_name="run_power_flow", arguments='{"algorithm":"nr","enforce_q_lims":false}'),
    )
    out = runtime.run_turn("run power flow")

    assert out["final_text"] == "done"
    assert len(execute_calls) == 2
    assert any(bool(trace.get("blocked_repeat")) for trace in out["tool_traces"])


def test_agent_runtime_google_provider_uses_chat_completions(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)

    monkeypatch.setattr("app.agent.loop.settings.llm_provider", "google")
    monkeypatch.setattr("app.power.tools.list_available_networks", _fake_network_catalog)
    monkeypatch.setattr("app.power.tools.get_network_factory", lambda case_name: (lambda: {"name": case_name}))

    client = FakeChatClient(tool_name="load_builtin_network", arguments='{"case_name":"case14"}')
    runtime = AgentRuntime(executor=executor, client=client)

    out = runtime.run_turn("load and run")

    assert "done" in out["final_text"]
    assert any(trace["tool"] == "load_builtin_network" for trace in out["tool_traces"])
    assert len(client.chat.completions.kwargs_history) == 2
