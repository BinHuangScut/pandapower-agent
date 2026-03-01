from __future__ import annotations

from pandapower_agent.agent.render import render_tool_result
from pandapower_agent.config import settings
from pandapower_agent.power.executor import ToolExecutor


def run_plot_command(
    executor: ToolExecutor,
    path: str,
    source_tool: str | None,
    metric: str | None,
    chart: str,
    top_n: int,
) -> int:
    result = executor.execute(
        "plot_analysis_result",
        {"path": path, "source_tool": source_tool, "metric": metric, "chart": chart, "top_n": top_n},
    )
    render_tool_result(result)
    return 0 if result.ok else 1


def run_plot_network_command(
    executor: ToolExecutor,
    path: str,
    library: str,
    bus_size: float,
    line_width: float,
    show_bus_labels: bool,
    label_font_size: float,
    plot_loads: bool,
    plot_gens: bool,
    plot_sgens: bool,
    respect_switches: bool,
) -> int:
    if not executor.state.has_net():
        bootstrap = executor.execute("load_builtin_network", {"case_name": settings.default_network})
        if not bootstrap.ok:
            render_tool_result(bootstrap)
            return 1

    result = executor.execute(
        "plot_network_layout",
        {
            "path": path,
            "library": library,
            "bus_size": bus_size,
            "line_width": line_width,
            "show_bus_labels": show_bus_labels,
            "label_font_size": label_font_size,
            "plot_loads": plot_loads,
            "plot_gens": plot_gens,
            "plot_sgens": plot_sgens,
            "respect_switches": respect_switches,
        },
    )
    render_tool_result(result)
    return 0 if result.ok else 1
