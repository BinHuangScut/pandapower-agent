from __future__ import annotations

import pytest

from pandapower_agent.cli.main import main
from pandapower_agent.schema.types import ToolResult


def test_main_networks_invokes_list_tool(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        if tool_name == "list_builtin_networks":
            return ToolResult(ok=True, message="ok", data={"network_catalog": [{"name": "case14"}]})
        return ToolResult(ok=True, message="ok")

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.network.render_tool_result", lambda result: None)

    rc = main(["networks", "--query", "118", "--max", "5"])
    assert rc == 0
    assert calls[0][0] == "list_builtin_networks"
    assert calls[0][1]["query"] == "118"
    assert calls[0][1]["max_results"] == 5


def test_main_use_invokes_load_and_info(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        if tool_name == "load_builtin_network":
            return ToolResult(ok=True, message="loaded", data={"case_name": raw_args["case_name"]})
        if tool_name == "get_current_network_info":
            return ToolResult(ok=True, message="info", data={"current_network": {"name": "case14"}})
        return ToolResult(ok=True, message="ok")

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.network.render_tool_result", lambda result: None)

    rc = main(["use", "case14"])
    assert rc == 0
    assert [c[0] for c in calls] == ["load_builtin_network", "get_current_network_info"]


def test_main_use_returns_nonzero_on_load_failure(monkeypatch) -> None:
    def fake_execute(self, tool_name, raw_args):
        _ = raw_args
        if tool_name == "load_builtin_network":
            return ToolResult(ok=False, message="bad network", data={"suggestions": ["case14"]})
        return ToolResult(ok=True, message="ok")

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.network.render_tool_result", lambda result: None)

    rc = main(["use", "wrong_name"])
    assert rc == 1


def test_main_tools_json(monkeypatch) -> None:
    outputs = []
    monkeypatch.setattr("pandapower_agent.cli.commands.tools.render_json", lambda data: outputs.append(data))
    rc = main(["tools", "--format", "json"])
    assert rc == 0
    assert outputs


def test_main_doctor_runs_health_checks(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        return ToolResult(ok=True, message="ok")

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.doctor.render_table", lambda title, columns, rows: None)
    monkeypatch.setattr("pandapower_agent.cli.commands.doctor.console.print", lambda msg: None)

    rc = main(["doctor", "--case-name", "case14"])
    assert rc == 0
    assert [name for name, _ in calls] == [
        "load_builtin_network",
        "get_current_network_info",
        "run_power_flow",
        "run_topology_analysis",
        "get_line_loading_violations",
    ]


def test_main_doctor_returns_nonzero_when_required_check_fails(monkeypatch) -> None:
    def fake_execute(self, tool_name, raw_args):
        _ = raw_args
        if tool_name == "run_power_flow":
            return ToolResult(ok=False, message="power flow failed")
        return ToolResult(ok=True, message="ok")

    payloads = []
    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.doctor.render_json", lambda data: payloads.append(data))

    rc = main(["doctor", "--format", "json"])
    assert rc == 1
    assert payloads and payloads[0]["ok"] is False


def test_main_scenarios_calls_list_scenarios(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        return ToolResult(ok=True, message="ok", data={"scenario_catalog": ["base", "current"]})

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.scenario.render_tool_result", lambda result: None)
    rc = main(["scenarios"])
    assert rc == 0
    assert calls[0][0] == "list_scenarios"


def test_main_undo_calls_undo_tool(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        return ToolResult(ok=True, message="ok", data={"current_network": {"name": "case14"}})

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.scenario.render_tool_result", lambda result: None)
    rc = main(["undo"])
    assert rc == 0
    assert calls[0][0] == "undo_last_mutation"


def test_main_export_without_results_returns_nonzero(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["export", "--type", "summary", "--path", "/tmp/pandapower-agent-empty.json"])
    assert rc == 1


def test_main_plot_invokes_plot_tool(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        return ToolResult(ok=True, message="plot ok", data={"plot_path": raw_args["path"]})

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.plot.render_tool_result", lambda result: None)

    rc = main(
        [
            "plot",
            "--path",
            "/tmp/analysis_plot.png",
            "--tool",
            "run_power_flow",
            "--metric",
            "max_line_loading_pct",
            "--chart",
            "bar",
            "--top-n",
            "10",
        ]
    )
    assert rc == 0
    assert calls[0][0] == "plot_analysis_result"
    assert calls[0][1]["source_tool"] == "run_power_flow"


def test_main_plot_network_invokes_network_plot_tool(monkeypatch) -> None:
    calls = []

    def fake_execute(self, tool_name, raw_args):
        calls.append((tool_name, raw_args))
        if tool_name == "load_builtin_network":
            return ToolResult(ok=True, message="loaded", data={"case_name": raw_args["case_name"]})
        return ToolResult(ok=True, message="plot ok", data={"plot_path": raw_args["path"]})

    monkeypatch.setattr("pandapower_agent.power.executor.ToolExecutor.execute", fake_execute)
    monkeypatch.setattr("pandapower_agent.cli.commands.plot.render_tool_result", lambda result: None)

    rc = main(
        [
            "plot-network",
            "--path",
            "/tmp/network_plot.png",
            "--library",
            "networkx",
            "--bus-size",
            "1.5",
            "--line-width",
            "2.0",
            "--plot-loads",
            "--ignore-switches",
        ]
    )
    assert rc == 0
    assert calls[0][0] == "load_builtin_network"
    assert calls[1][0] == "plot_network_layout"
    assert calls[1][1]["path"] == "/tmp/network_plot.png"
    assert calls[1][1]["library"] == "networkx"
    assert calls[1][1]["show_bus_labels"] is True
    assert calls[1][1]["label_font_size"] == 8.0
    assert calls[1][1]["plot_loads"] is True
    assert calls[1][1]["respect_switches"] is False


def test_main_version_option(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("agent ")
