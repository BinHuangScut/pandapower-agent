from __future__ import annotations

from types import SimpleNamespace

from pandapower_agent.cli.chat import apply_admin_key, chat_loop, run_single


class _DummyState:
    def __init__(self) -> None:
        self.reset_called = False

    def reset(self) -> None:
        self.reset_called = True


class _DummyRuntime:
    def __init__(self) -> None:
        self.admin_mode = False
        self.executor = SimpleNamespace(state=_DummyState())
        self.turn_inputs: list[str] = []
        self.reset_called = False

    def set_admin_mode(self, enabled: bool) -> None:
        self.admin_mode = enabled

    def reset_conversation(self) -> None:
        self.reset_called = True

    def run_turn(self, user_message: str):
        self.turn_inputs.append(user_message)
        return {
            "final_text": "done",
            "tool_traces": [{"tool": "run_power_flow", "ok": True, "args": {"algorithm": "nr"}, "message": "ok"}],
            "history": [],
        }


def test_apply_admin_key_requires_correct_password(monkeypatch) -> None:
    runtime = _DummyRuntime()
    outputs: list[str] = []
    monkeypatch.setenv("ADMIN_DEBUG_KEY", "525400")
    monkeypatch.setattr("pandapower_agent.cli.chat.console.print", lambda msg: outputs.append(str(msg)))

    ok = apply_admin_key(runtime, "bad-key")

    assert not ok
    assert runtime.admin_mode is False
    assert "Invalid admin key." in outputs[-1]


def test_apply_admin_key_enables_admin_mode(monkeypatch) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setenv("ADMIN_DEBUG_KEY", "525400")
    monkeypatch.setattr("pandapower_agent.cli.chat.console.print", lambda msg: None)

    ok = apply_admin_key(runtime, "525400")

    assert ok
    assert runtime.admin_mode is True


def test_run_single_hides_traces_when_not_admin(monkeypatch) -> None:
    runtime = _DummyRuntime()
    traces: list[list[dict[str, object]]] = []
    replies: list[str] = []
    monkeypatch.setattr("pandapower_agent.cli.chat.render_agent_reply", lambda text: replies.append(text))
    monkeypatch.setattr("pandapower_agent.cli.chat.render_tool_traces", lambda rows: traces.append(rows))

    rc = run_single(runtime, "run flow")

    assert rc == 0
    assert replies == ["done"]
    assert traces == []


def test_chat_loop_unlock_admin_mode_with_hidden_command(monkeypatch) -> None:
    runtime = _DummyRuntime()
    replies: list[str] = []
    traces: list[list[dict[str, object]]] = []
    monkeypatch.setenv("ADMIN_DEBUG_KEY", "525400")

    inputs = iter(["/admin unlock 525400", "run flow", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    monkeypatch.setattr("pandapower_agent.cli.chat.print_startup_network_preview", lambda executor: None)
    monkeypatch.setattr("pandapower_agent.cli.chat.render_agent_reply", lambda text: replies.append(text))
    monkeypatch.setattr("pandapower_agent.cli.chat.render_tool_traces", lambda rows: traces.append(rows))
    monkeypatch.setattr("pandapower_agent.cli.chat.console.print", lambda msg: None)

    rc = chat_loop(runtime)

    assert rc == 0
    assert runtime.admin_mode is True
    assert replies == ["done"]
    assert len(traces) == 1


def test_apply_admin_key_requires_config(monkeypatch) -> None:
    runtime = _DummyRuntime()
    outputs: list[str] = []
    monkeypatch.delenv("ADMIN_DEBUG_KEY", raising=False)
    monkeypatch.setattr("pandapower_agent.cli.chat.console.print", lambda msg: outputs.append(str(msg)))

    ok = apply_admin_key(runtime, "525400")

    assert not ok
    assert runtime.admin_mode is False
    assert "Admin debug mode is not configured." in outputs[-1]


def test_chat_loop_reset_clears_state_and_conversation(monkeypatch) -> None:
    runtime = _DummyRuntime()

    inputs = iter(["/reset", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    monkeypatch.setattr("pandapower_agent.cli.chat.print_startup_network_preview", lambda executor: None)
    monkeypatch.setattr("pandapower_agent.cli.chat.console.print", lambda msg: None)

    rc = chat_loop(runtime)

    assert rc == 0
    assert runtime.executor.state.reset_called is True
    assert runtime.reset_called is True


def test_chat_loop_plotnet_command(monkeypatch) -> None:
    runtime = _DummyRuntime()
    calls: list[dict[str, object]] = []

    inputs = iter(["/plotnet ./outputs/net.png", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    monkeypatch.setattr("pandapower_agent.cli.chat.print_startup_network_preview", lambda executor: None)
    monkeypatch.setattr("pandapower_agent.cli.chat.console.print", lambda msg: None)
    monkeypatch.setattr(
        "pandapower_agent.cli.chat.run_plot_network_command",
        lambda executor, **kwargs: calls.append(kwargs) or 0,
    )

    rc = chat_loop(runtime)

    assert rc == 0
    assert calls and calls[0]["path"] == "./outputs/net.png"
    assert calls[0]["library"] == "networkx"
