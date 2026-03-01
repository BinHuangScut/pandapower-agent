from __future__ import annotations

import pytest

from pandapower_agent.power.state import SessionState
from pandapower_agent.schema.tool_args import AddDGArgs, SaveScenarioArgs, SetLoadArgs


def test_set_load_requires_delta() -> None:
    with pytest.raises(Exception):
        SetLoadArgs()


def test_add_dg_validation() -> None:
    with pytest.raises(Exception):
        AddDGArgs(bus_id=1, p_mw=-1)


def test_save_scenario_reserved_name() -> None:
    with pytest.raises(Exception):
        SaveScenarioArgs(name="current")


def test_session_state_save_load_reset() -> None:
    state = SessionState()
    net = {"k": 1}
    state.set_base_and_current(net)
    state.save_scenario("s1")

    state.working_net["k"] = 2
    state.load_scenario("s1")
    assert state.working_net["k"] == 1

    state.reset()
    assert state.working_net is None
    assert state.scenarios == {}
