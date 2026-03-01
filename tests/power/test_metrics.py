from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from pandapower_agent.power.metrics import diff_metrics, summarize_network_metrics


def make_net(line=70.0, vmin=0.98, vmax=1.03, loss=10.0):
    return SimpleNamespace(
        res_line=pd.DataFrame({"loading_percent": [line, line - 5]}),
        res_bus=pd.DataFrame({"vm_pu": [vmin, vmax], "va_degree": [0.0, 1.0]}),
        res_ext_grid=pd.DataFrame({"p_mw": [loss]}),
    )


def test_summarize_metrics() -> None:
    net = make_net()
    s = summarize_network_metrics(net)
    assert s["max_line_loading_pct"] == 70.0
    assert s["min_bus_vm_pu"] == 0.98


def test_diff_metrics() -> None:
    a = summarize_network_metrics(make_net(line=70.0))
    b = summarize_network_metrics(make_net(line=65.0))
    d = diff_metrics(a, b)
    assert d["max_line_loading_pct"]["delta"] == -5.0
