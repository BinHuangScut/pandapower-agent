from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from pandapower_agent.power.state import SessionState
from pandapower_agent.power.executor import ToolExecutor


class FakePP:
    def __init__(self):
        self._ids = {"load": 10, "sgen": 20, "line": 30, "trafo": 40}

    def create_load(self, net, bus, p_mw, q_mvar, name=None):
        idx = self._ids["load"]
        self._ids["load"] += 1
        net.load.loc[idx] = {"bus": bus, "p_mw": p_mw, "q_mvar": q_mvar, "name": name}
        return idx

    def create_sgen(self, net, bus, p_mw, q_mvar=0.0, vm_pu=1.0, name=None):
        idx = self._ids["sgen"]
        self._ids["sgen"] += 1
        net.sgen.loc[idx] = {"bus": bus, "p_mw": p_mw, "q_mvar": q_mvar, "vm_pu": vm_pu, "name": name}
        return idx

    def create_line_from_parameters(
        self, net, from_bus, to_bus, length_km, r_ohm_per_km, x_ohm_per_km, c_nf_per_km, max_i_ka, name=None
    ):
        idx = self._ids["line"]
        self._ids["line"] += 1
        net.line.loc[idx] = {"from_bus": from_bus, "to_bus": to_bus, "in_service": True, "name": name}
        return idx

    def create_transformer_from_parameters(
        self,
        net,
        hv_bus,
        lv_bus,
        sn_mva,
        vn_hv_kv,
        vn_lv_kv,
        vk_percent,
        vkr_percent,
        pfe_kw,
        i0_percent,
        shift_degree=0.0,
        name=None,
    ):
        idx = self._ids["trafo"]
        self._ids["trafo"] += 1
        net.trafo.loc[idx] = {"hv_bus": hv_bus, "lv_bus": lv_bus, "in_service": True, "name": name}
        return idx


def _make_net():
    return SimpleNamespace(
        name="fake",
        bus=pd.DataFrame(index=[0, 1, 2]),
        load=pd.DataFrame(columns=["bus", "p_mw", "q_mvar", "name"]),
        sgen=pd.DataFrame(columns=["bus", "p_mw", "q_mvar", "vm_pu", "name"]),
        line=pd.DataFrame(columns=["from_bus", "to_bus", "in_service", "name"]),
        trafo=pd.DataFrame(columns=["hv_bus", "lv_bus", "in_service", "name"]),
        gen=pd.DataFrame(columns=["bus", "in_service"]),
        ext_grid=pd.DataFrame(columns=["bus", "in_service"]),
    )


def test_create_and_update_elements(monkeypatch) -> None:
    state = SessionState()
    state.working_net = _make_net()
    state.scenarios["current"] = state.working_net
    executor = ToolExecutor(state)

    monkeypatch.setattr("pandapower_agent.power.handlers.mutation.import_pp", lambda: FakePP())

    load_result = executor.execute("create_load", {"bus_id": 1, "p_mw": 5.0, "q_mvar": 1.0, "name": "L1"})
    sgen_result = executor.execute("create_sgen", {"bus_id": 2, "p_mw": 3.0, "q_mvar": 0.0, "name": "DG1"})
    line_result = executor.execute(
        "create_line_from_parameters",
        {
            "from_bus": 0,
            "to_bus": 1,
            "length_km": 1.0,
            "r_ohm_per_km": 0.1,
            "x_ohm_per_km": 0.1,
            "c_nf_per_km": 1.0,
            "max_i_ka": 0.4,
            "name": "line-x",
        },
    )
    trafo_result = executor.execute(
        "create_transformer_from_parameters",
        {
            "hv_bus": 0,
            "lv_bus": 2,
            "sn_mva": 10.0,
            "vn_hv_kv": 110.0,
            "vn_lv_kv": 20.0,
            "vk_percent": 10.0,
            "vkr_percent": 0.5,
            "pfe_kw": 5.0,
            "i0_percent": 0.1,
            "shift_degree": 0.0,
            "name": "T1",
        },
    )

    assert load_result.ok
    assert sgen_result.ok
    assert line_result.ok
    assert trafo_result.ok


def test_update_element_params_and_toggle() -> None:
    state = SessionState()
    net = _make_net()
    net.line.loc[3] = {"from_bus": 0, "to_bus": 1, "in_service": True, "name": "line3"}
    state.working_net = net
    state.scenarios["current"] = net
    executor = ToolExecutor(state)

    upd = executor.execute(
        "update_element_params", {"element_type": "line", "element_id": 3, "fields": {"name": "line3-new"}}
    )
    tog = executor.execute("toggle_element", {"element_type": "line", "element_id": 3, "in_service": False})
    assert upd.ok
    assert tog.ok
    assert bool(state.working_net.line.at[3, "in_service"]) is False


def test_update_element_params_allows_dynamic_short_circuit_fields_for_ext_grid() -> None:
    state = SessionState()
    net = _make_net()
    net.ext_grid.loc[0] = {"bus": 0, "in_service": True}
    state.working_net = net
    state.scenarios["current"] = net
    executor = ToolExecutor(state)

    upd = executor.execute(
        "update_element_params",
        {
            "element_type": "ext_grid",
            "element_id": 0,
            "fields": {"s_sc_max_mva": 1000.0, "rx_max": 0.1},
        },
    )
    assert upd.ok
    assert "added_fields" in upd.data
    assert float(state.working_net.ext_grid.at[0, "s_sc_max_mva"]) == 1000.0
    assert float(state.working_net.ext_grid.at[0, "rx_max"]) == 0.1
