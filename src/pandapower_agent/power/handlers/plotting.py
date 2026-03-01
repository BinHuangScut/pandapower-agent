from __future__ import annotations

from pathlib import Path

from pandapower_agent.power.handlers.common import (
    ensure_net,
    extract_bus_label_positions,
    import_pandapower_plotting_backend,
    load_cached_results,
    render_plot_image,
    resolve_plot_source,
    safe_count,
    tool_error,
)
from pandapower_agent.power.plotting import PLOTTABLE_SOURCE_TOOLS, build_plot_dataset
from pandapower_agent.schema.tool_args import PlotAnalysisResultArgs, PlotNetworkArgs
from pandapower_agent.schema.types import TablePayload, ToolResult


def plot_analysis_result(state, args: PlotAnalysisResultArgs) -> ToolResult:
    source_results = state.last_results or load_cached_results()
    if not source_results:
        return tool_error(
            "No analysis results available to plot.",
            next_action="Run at least one analysis tool first, then call plot_analysis_result.",
        )

    source_tool, source_payload = resolve_plot_source(source_results, requested_source=args.source_tool)
    if source_tool is None or source_payload is None:
        available = sorted([name for name in source_results if name in PLOTTABLE_SOURCE_TOOLS])
        return tool_error(
            f"Requested source tool '{args.source_tool}' is unavailable for plotting." if args.source_tool else "No plottable result found.",
            data={"available_source_tools": available},
            next_action="Use one of available_source_tools or rerun a supported analysis tool.",
        )

    data = source_payload.get("data")
    if not isinstance(data, dict):
        return tool_error(
            f"Result from '{source_tool}' does not include plottable data.",
            next_action="Rerun the analysis tool to regenerate result payload.",
        )

    try:
        dataset = build_plot_dataset(source_tool, data, metric=args.metric, top_n=args.top_n)
    except ValueError as exc:
        return tool_error(str(exc))

    chart = "bar" if args.chart == "auto" else args.chart
    try:
        plot_path = render_plot_image(
            labels=dataset.labels,
            values=dataset.values,
            title=dataset.title,
            x_label=dataset.x_label,
            y_label=dataset.y_label,
            chart=chart,
            output_path=args.path,
        )
    except ModuleNotFoundError:
        return tool_error(
            "Seaborn plotting dependencies are not installed.",
            next_action="Reinstall project dependencies via `pip install -e .[dev]` and retry.",
        )
    except Exception as exc:
        return tool_error(f"Failed to render plot: {exc}")

    rows = [[label, value] for label, value in zip(dataset.labels, dataset.values)]
    preview_rows = rows[: min(20, len(rows))]
    table = TablePayload(title=f"Plot Data ({source_tool})", columns=["label", dataset.metric], rows=preview_rows)
    return ToolResult(
        ok=True,
        message=f"Plot saved to {plot_path}",
        data={
            "source_tool": source_tool,
            "metric": dataset.metric,
            "chart": chart,
            "plot_path": str(plot_path),
            "points": len(dataset.values),
            "available_metrics": dataset.available_metrics,
        },
        tables=[table],
    )


def plot_network_layout(state, args: PlotNetworkArgs) -> ToolResult:
    ensure_net(state)
    ppplot, plt = import_pandapower_plotting_backend()
    net = state.working_net

    out_path = Path(args.path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fig, ax = plt.subplots(figsize=(10, 7))
        ppplot.simple_plot(
            net,
            respect_switches=args.respect_switches,
            line_width=args.line_width,
            bus_size=args.bus_size,
            plot_loads=args.plot_loads,
            plot_gens=args.plot_gens,
            plot_sgens=args.plot_sgens,
            library=args.library,
            show_plot=False,
            ax=ax,
        )
        labels_drawn = 0
        if args.show_bus_labels:
            for bus_id, x, y in extract_bus_label_positions(net):
                ax.text(
                    x,
                    y,
                    str(bus_id),
                    fontsize=args.label_font_size,
                    color="#111111",
                    ha="center",
                    va="center",
                    zorder=30,
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.75},
                )
                labels_drawn += 1
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
    except ModuleNotFoundError:
        return tool_error(
            "Pandapower network plotting dependencies are not installed.",
            next_action="Reinstall project dependencies via `pip install -e .[dev]` and retry.",
        )
    except Exception as exc:
        return tool_error(f"Failed to plot network layout: {exc}")

    rows = [
        ["bus_count", safe_count(net, "bus")],
        ["line_count", safe_count(net, "line")],
        ["load_count", safe_count(net, "load")],
        ["sgen_count", safe_count(net, "sgen")],
        ["gen_count", safe_count(net, "gen")],
    ]
    table = TablePayload(title="Network Plot Summary", columns=["metric", "value"], rows=rows)
    return ToolResult(
        ok=True,
        message=f"Network layout plot saved to {out_path}",
        data={
            "plot_path": str(out_path),
            "library": args.library,
            "respect_switches": args.respect_switches,
            "show_bus_labels": args.show_bus_labels,
            "label_font_size": args.label_font_size,
            "bus_labels_drawn": labels_drawn,
            "plot_loads": args.plot_loads,
            "plot_gens": args.plot_gens,
            "plot_sgens": args.plot_sgens,
        },
        tables=[table],
    )
