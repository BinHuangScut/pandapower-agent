from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.power.state import SessionState
from app.power.tools import ToolExecutor


class _FakeFigure:
    def tight_layout(self) -> None:
        return None

    def savefig(self, path, dpi=150) -> None:
        _ = dpi
        Path(path).write_text("fake-image", encoding="utf-8")


class _FakeAxes:
    text_calls: list[tuple[object, object, object, dict[str, object]]] = []

    def __init__(self) -> None:
        self.containers = []

    def get_xticklabels(self):
        return []

    def bar_label(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def set_xlabel(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def set_ylabel(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def set_title(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def grid(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def text(self, x, y, s, **kwargs) -> None:
        _FakeAxes.text_calls.append((x, y, s, kwargs))


class _FakePlt:
    def subplots(self, figsize=(8, 5)):
        _ = figsize
        return _FakeFigure(), _FakeAxes()

    def setp(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def close(self, fig) -> None:
        _ = fig


class _FakeSns:
    def set_theme(self, *args, **kwargs) -> None:
        _ = args, kwargs

    def lineplot(self, *args, **kwargs):
        _ = args, kwargs
        return kwargs.get("ax")

    def barplot(self, *args, **kwargs):
        ax = kwargs.get("ax")
        if ax is not None:
            ax.containers = [object()]
        return ax


class _FakePPPlot:
    def simple_plot(self, *args, **kwargs):
        _ = args, kwargs


def test_plot_analysis_result_short_circuit(monkeypatch, tmp_path) -> None:
    state = SessionState()
    state.last_results = {
        "run_short_circuit": {
            "ok": True,
            "message": "ok",
            "data": {
                "rows": [
                    {"bus": 1, "ikss_ka": 8.0, "ip_ka": 11.0, "ith_ka": 7.0},
                    {"bus": 2, "ikss_ka": 6.0, "ip_ka": 9.0, "ith_ka": 5.0},
                ]
            },
        }
    }
    executor = ToolExecutor(state)
    monkeypatch.setattr("app.power.tools._import_plotting_backend", lambda: (_FakeSns(), _FakePlt()))

    out_file = tmp_path / "sc_plot.png"
    result = executor.execute(
        "plot_analysis_result",
        {"source_tool": "run_short_circuit", "metric": "ikss_ka", "path": str(out_file)},
    )
    assert result.ok
    assert result.data["source_tool"] == "run_short_circuit"
    assert result.data["metric"] == "ikss_ka"
    assert out_file.exists()


def test_plot_analysis_result_auto_source_selection(monkeypatch, tmp_path) -> None:
    state = SessionState()
    state.last_results = {
        "run_power_flow": {
            "ok": True,
            "message": "ok",
            "data": {"machine_summary": {"max_line_loading_pct": 88.0, "min_bus_vm_pu": 0.97}},
        }
    }
    executor = ToolExecutor(state)
    monkeypatch.setattr("app.power.tools._import_plotting_backend", lambda: (_FakeSns(), _FakePlt()))

    out_file = tmp_path / "pf_plot.png"
    result = executor.execute("plot_analysis_result", {"path": str(out_file)})
    assert result.ok
    assert result.data["source_tool"] == "run_power_flow"
    assert out_file.exists()


def test_plot_analysis_result_returns_error_for_invalid_metric(monkeypatch, tmp_path) -> None:
    state = SessionState()
    state.last_results = {
        "run_short_circuit": {
            "ok": True,
            "message": "ok",
            "data": {"rows": [{"bus": 1, "ikss_ka": 8.0}]},
        }
    }
    executor = ToolExecutor(state)
    monkeypatch.setattr("app.power.tools._import_plotting_backend", lambda: (_FakeSns(), _FakePlt()))

    result = executor.execute(
        "plot_analysis_result",
        {"source_tool": "run_short_circuit", "metric": "bad_metric", "path": str(tmp_path / "x.png")},
    )
    assert not result.ok
    assert "Available metrics" in result.message


def test_plot_analysis_result_without_any_results(monkeypatch) -> None:
    state = SessionState()
    executor = ToolExecutor(state)
    monkeypatch.setattr("app.power.tools._load_cached_results", lambda: {})
    result = executor.execute("plot_analysis_result", {"path": "./outputs/none.png"})
    assert not result.ok
    assert "No analysis results available to plot" in result.message


def test_plot_network_layout_uses_pandapower_builtin(monkeypatch, tmp_path) -> None:
    state = SessionState()
    state.current_network_name = "case14"
    state.working_net = SimpleNamespace(
        bus=pd.DataFrame(
            {
                "geo": [
                    json.dumps({"coordinates": [0.0, 0.0]}),
                    json.dumps({"coordinates": [1.0, 1.0]}),
                ]
            },
            index=[0, 1],
        ),
        line=pd.DataFrame(index=[0]),
        load=pd.DataFrame(index=[]),
        sgen=pd.DataFrame(index=[]),
        gen=pd.DataFrame(index=[]),
    )
    executor = ToolExecutor(state)
    monkeypatch.setattr("app.power.tools._import_pandapower_plotting_backend", lambda: (_FakePPPlot(), _FakePlt()))
    _FakeAxes.text_calls.clear()

    out_file = tmp_path / "network_plot.png"
    result = executor.execute(
        "plot_network_layout",
        {"path": str(out_file), "library": "networkx", "show_bus_labels": True, "label_font_size": 9.0},
    )

    assert result.ok
    assert result.data["plot_path"] == str(out_file.resolve())
    assert result.data["bus_labels_drawn"] == 2
    assert len(_FakeAxes.text_calls) == 2
    assert out_file.exists()
