from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from pandapower_agent.power.state import SessionState
from pandapower_agent.power.executor import ToolExecutor


class FakePP:
    def runopp(self, net):
        net.res_cost = 123.45

    def runpp(self, net):
        _ = net

    def create_measurement(self, net, meas_type, element_type, value, std_dev, element):
        _ = (meas_type, element_type, value, std_dev, element)
        if not hasattr(net, "measurement"):
            net.measurement = pd.DataFrame(columns=["dummy"])
        net.measurement.loc[len(net.measurement)] = {"dummy": 1}


def _net_for_estimation():
    return SimpleNamespace(
        bus=pd.DataFrame(index=[0, 1]),
        res_bus=pd.DataFrame({"vm_pu": [1.0, 0.99]}, index=[0, 1]),
        measurement=pd.DataFrame(columns=["dummy"]),
    )


def test_run_opf(monkeypatch) -> None:
    state = SessionState()
    state.working_net = _net_for_estimation()
    executor = ToolExecutor(state)
    monkeypatch.setattr("pandapower_agent.power.handlers.analysis.import_pp", lambda: FakePP())

    result = executor.execute("run_opf", {"objective": "min_cost"})
    assert result.ok
    assert result.data["machine_summary"]["opf_objective"] == 123.45


def test_run_state_estimation(monkeypatch) -> None:
    state = SessionState()
    state.working_net = _net_for_estimation()
    executor = ToolExecutor(state)
    monkeypatch.setattr("pandapower_agent.power.handlers.analysis.import_pp", lambda: FakePP())

    fake_est = SimpleNamespace(estimate=lambda net, init: True)
    monkeypatch.setitem(sys.modules, "pandapower.estimation", fake_est)

    result = executor.execute("run_state_estimation", {"measurement_set": "synthetic", "init": "flat"})
    assert result.ok
    assert result.data["machine_summary"]["state_estimation_converged"] is True
