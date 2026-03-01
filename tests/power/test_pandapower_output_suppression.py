from __future__ import annotations

import sys
import warnings
from types import SimpleNamespace

from app.power.state import SessionState
from app.power.tools import ToolExecutor


class FakePandapowerError(RuntimeError):
    __module__ = "pandapower.powerflow"


def _fake_net():
    return SimpleNamespace()


def test_tool_executor_hides_raw_pandapower_error(monkeypatch) -> None:
    state = SessionState()
    state.working_net = _fake_net()
    executor = ToolExecutor(state)

    def _raise(*_args, **_kwargs):
        raise FakePandapowerError("raw pandapower solver failure detail")

    monkeypatch.setattr("app.power.tools.analysis_run_ac_power_flow", _raise)

    result = executor.execute("run_power_flow", {"algorithm": "nr", "enforce_q_lims": False})

    assert not result.ok
    assert "pandapower" in result.message.lower()
    assert "raw pandapower solver failure detail" not in result.message
    assert state.history
    assert "internal_error" in state.history[-1]
    assert "raw pandapower solver failure detail" in str(state.history[-1]["internal_error"])


def test_tool_executor_suppresses_runtime_warning_stdout_stderr(monkeypatch) -> None:
    state = SessionState()
    state.working_net = _fake_net()
    executor = ToolExecutor(state)

    def _noisy(*_args, **_kwargs):
        warnings.warn("noisy warning from power runtime")
        print("noisy stdout from power runtime")
        print("noisy stderr from power runtime", file=sys.stderr)
        return {"mode": "ac", "machine_summary": {"x": 1}}

    monkeypatch.setattr("app.power.tools.analysis_run_ac_power_flow", _noisy)

    result = executor.execute("run_power_flow", {"algorithm": "nr", "enforce_q_lims": False})

    assert result.ok
    assert state.history
    suppressed = state.history[-1].get("suppressed_runtime", {})
    assert suppressed.get("warning_count", 0) >= 1
    assert "noisy stdout from power runtime" in str(suppressed.get("stdout_preview", ""))
    assert "noisy stderr from power runtime" in str(suppressed.get("stderr_preview", ""))
