from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from pandapower_agent.power.state import SessionState
from pandapower_agent.power.executor import ToolExecutor


def _net_with_load() -> SimpleNamespace:
    return SimpleNamespace(
        bus=pd.DataFrame(index=[1]),
        load=pd.DataFrame({"bus": [1], "p_mw": [10.0], "q_mvar": [2.0]}, index=[0]),
        sgen=pd.DataFrame(columns=["bus", "p_mw"]),
        line=pd.DataFrame(columns=["in_service"]),
        trafo=pd.DataFrame(columns=["in_service"]),
        gen=pd.DataFrame(columns=["in_service"]),
        ext_grid=pd.DataFrame(columns=["in_service"]),
    )


def test_undo_last_mutation_for_set_load() -> None:
    state = SessionState()
    state.working_net = _net_with_load()
    state.scenarios["current"] = state.working_net
    executor = ToolExecutor(state)

    before = float(state.working_net.load.at[0, "p_mw"])
    changed = executor.execute("set_load", {"p_mw_delta": 5.0})
    assert changed.ok
    assert float(state.working_net.load.at[0, "p_mw"]) == before + 5.0

    undone = executor.execute("undo_last_mutation", {})
    assert undone.ok
    assert float(state.working_net.load.at[0, "p_mw"]) == before


def test_list_and_delete_scenarios() -> None:
    state = SessionState()
    state.working_net = _net_with_load()
    state.scenarios["base"] = _net_with_load()
    state.scenarios["current"] = _net_with_load()
    state.scenarios["custom_a"] = _net_with_load()
    executor = ToolExecutor(state)

    listed = executor.execute("list_scenarios", {})
    assert listed.ok
    assert "custom_a" in listed.data["scenario_catalog"]

    deleted = executor.execute("delete_scenario", {"name": "custom_a"})
    assert deleted.ok
    listed2 = executor.execute("list_scenarios", {})
    assert "custom_a" not in listed2.data["scenario_catalog"]
