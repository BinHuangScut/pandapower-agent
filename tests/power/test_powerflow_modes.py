from __future__ import annotations

from types import SimpleNamespace

from app.power.state import SessionState
from app.power.tools import ToolExecutor


def _fake_net():
    return SimpleNamespace()


def test_run_ac_dc_3ph_modes(monkeypatch) -> None:
    state = SessionState()
    state.working_net = _fake_net()
    executor = ToolExecutor(state)

    monkeypatch.setattr(
        "app.power.tools.analysis_run_ac_power_flow",
        lambda net, algorithm, enforce_q_lims: {"mode": "ac", "machine_summary": {"x": 1}},
    )
    monkeypatch.setattr(
        "app.power.tools.analysis_run_dc_power_flow",
        lambda net, calculate_voltage_angles: {"mode": "dc", "machine_summary": {"x": 2}},
    )
    monkeypatch.setattr(
        "app.power.tools.analysis_run_three_phase_power_flow",
        lambda net, max_iteration: {"mode": "3ph", "machine_summary": {"x": 3}},
    )

    ac = executor.execute("run_power_flow", {"algorithm": "nr", "enforce_q_lims": False})
    dc = executor.execute("run_dc_power_flow", {"calculate_voltage_angles": True})
    ph = executor.execute("run_three_phase_power_flow", {"max_iteration": 20})

    assert ac.ok and ac.data["mode"] == "ac"
    assert dc.ok and dc.data["mode"] == "dc"
    assert ph.ok and ph.data["mode"] == "3ph"
