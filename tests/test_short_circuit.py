from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from app.power.state import SessionState
from app.power.tools import ToolExecutor


def test_run_short_circuit(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace()
    executor = ToolExecutor(state)

    monkeypatch.setattr(
        "app.power.tools.short_circuit_analysis",
        lambda net, case, fault, bus_ids: {
            "case": case,
            "fault": fault,
            "rows": [{"bus": 1, "ikss_ka": 8.0, "ip_ka": 12.0, "ith_ka": 7.0}],
            "machine_summary": {"max_ikss_ka": 8.0, "min_ikss_ka": 8.0, "rows": 1},
        },
    )

    result = executor.execute("run_short_circuit", {"case": "max", "fault": "3ph", "bus_ids": [1]})
    assert result.ok
    assert result.data["machine_summary"]["max_ikss_ka"] == 8.0
    assert result.tables


def test_run_short_circuit_auto_fills_ext_grid_defaults(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace(ext_grid=pd.DataFrame({"bus": [0], "in_service": [True]}))
    executor = ToolExecutor(state)

    calls = {"n": 0}

    def _fake_short_circuit(net, case, fault, bus_ids):
        _ = bus_ids
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("short circuit apparent power s_sc_max_mva needs to be specified for external grid")
        assert case == "max"
        assert fault == "3ph"
        assert float(net.ext_grid.at[0, "s_sc_max_mva"]) == 1000.0
        assert float(net.ext_grid.at[0, "rx_max"]) == 0.1
        return {
            "case": case,
            "fault": fault,
            "rows": [{"bus": 1, "ikss_ka": 8.0, "ip_ka": 12.0, "ith_ka": 7.0}],
            "machine_summary": {"max_ikss_ka": 8.0, "min_ikss_ka": 8.0, "rows": 1},
        }

    monkeypatch.setattr("app.power.tools.short_circuit_analysis", _fake_short_circuit)

    result = executor.execute("run_short_circuit", {"case": "max", "fault": "3ph"})
    assert result.ok
    assert result.data["auto_filled_ext_grid_fields"]


def test_run_short_circuit_reports_zero_sequence_missing(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace(ext_grid=pd.DataFrame({"bus": [0], "in_service": [True]}))
    executor = ToolExecutor(state)

    calls = {"n": 0}

    def _fake_short_circuit(net, case, fault, bus_ids):
        _ = net, case, fault, bus_ids
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("short circuit apparent power s_sc_max_mva needs to be specified for external grid")
        raise KeyError("r0_ohm_per_km")

    monkeypatch.setattr("app.power.tools.short_circuit_analysis", _fake_short_circuit)

    result = executor.execute("run_short_circuit", {"case": "max", "fault": "1ph"})
    assert not result.ok
    assert "zero-sequence" in result.message
    assert result.data["missing_prerequisites"]


def test_run_short_circuit_falls_back_with_generators_excluded(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace(
        ext_grid=pd.DataFrame({"bus": [0], "in_service": [True]}),
        gen=pd.DataFrame({"bus": [1], "in_service": [True]}),
    )
    executor = ToolExecutor(state)

    calls = {"n": 0}

    def _fake_short_circuit(net, case, fault, bus_ids):
        _ = case, fault, bus_ids
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("short circuit apparent power s_sc_max_mva needs to be specified for external grid")
        if calls["n"] == 2:
            raise AttributeError("'DataFrame' object has no attribute 'vn_kv'")
        assert bool(net.gen.at[0, "in_service"]) is False
        return {
            "case": "max",
            "fault": "1ph",
            "rows": [{"bus": 1, "ikss_ka": 4.0, "ip_ka": 6.0, "ith_ka": 3.5}],
            "machine_summary": {"max_ikss_ka": 4.0, "min_ikss_ka": 4.0, "rows": 1},
        }

    monkeypatch.setattr("app.power.tools.short_circuit_analysis", _fake_short_circuit)

    result = executor.execute("run_short_circuit", {"case": "max", "fault": "1ph"})
    assert result.ok
    assert any("generators excluded" in note for note in result.data.get("notes", []))
    assert result.data["fallback"]["excluded_generators"] == 1
    assert bool(state.working_net.gen.at[0, "in_service"]) is True


def test_run_short_circuit_reports_zero_sequence_after_generator_fallback_failure(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace(
        ext_grid=pd.DataFrame({"bus": [0], "in_service": [True]}),
        gen=pd.DataFrame({"bus": [1], "in_service": [True]}),
    )
    executor = ToolExecutor(state)

    calls = {"n": 0}

    def _fake_short_circuit(net, case, fault, bus_ids):
        _ = net, case, fault, bus_ids
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("short circuit apparent power s_sc_max_mva needs to be specified for external grid")
        if calls["n"] == 2:
            raise AttributeError("'DataFrame' object has no attribute 'vn_kv'")
        raise KeyError("r0_ohm_per_km")

    monkeypatch.setattr("app.power.tools.short_circuit_analysis", _fake_short_circuit)

    result = executor.execute("run_short_circuit", {"case": "max", "fault": "1ph"})
    assert not result.ok
    assert "zero-sequence" in result.message


def test_run_short_circuit_hides_raw_generator_error(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace(
        ext_grid=pd.DataFrame({"bus": [0], "in_service": [True]}),
        gen=pd.DataFrame({"bus": [1], "in_service": [True]}),
    )
    executor = ToolExecutor(state)

    def _fake_short_circuit(net, case, fault, bus_ids):
        _ = net, case, fault, bus_ids
        raise AttributeError("'DataFrame' object has no attribute 'vn_kv'")

    monkeypatch.setattr("app.power.tools.short_circuit_analysis", _fake_short_circuit)

    result = executor.execute("run_short_circuit", {"case": "max", "fault": "3ph"})
    assert not result.ok
    assert "Generator short-circuit parameters are missing" in result.message
    assert "raw_error" not in result.data
