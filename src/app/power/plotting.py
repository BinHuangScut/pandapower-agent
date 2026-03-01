from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PLOTTABLE_SOURCE_TOOLS = {
    "run_power_flow",
    "run_dc_power_flow",
    "run_three_phase_power_flow",
    "run_short_circuit",
    "run_topology_analysis",
    "run_contingency_screening",
    "run_opf",
    "run_state_estimation",
}


@dataclass(slots=True)
class PlotDataset:
    title: str
    x_label: str
    y_label: str
    labels: list[str]
    values: list[float]
    metric: str
    available_metrics: list[str]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _build_short_circuit_dataset(payload: dict[str, Any], metric: str | None, top_n: int) -> PlotDataset:
    rows = payload.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("run_short_circuit has no row data to plot.")
    candidates = ["ikss_ka", "ip_ka", "ith_ka"]
    chosen = metric or "ikss_ka"
    if chosen not in candidates:
        raise ValueError(f"Metric '{chosen}' is not supported. Available metrics: {', '.join(candidates)}.")

    points: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        val = row.get(chosen)
        if not _is_number(val):
            continue
        bus_id = row.get("bus")
        points.append((f"bus:{bus_id}", float(val)))
    if not points:
        raise ValueError(f"No numeric values found for metric '{chosen}' in run_short_circuit.")

    points = sorted(points, key=lambda x: x[1], reverse=True)[:top_n]
    labels = [p[0] for p in points]
    values = [p[1] for p in points]
    return PlotDataset(
        title=f"Short-Circuit Result ({chosen})",
        x_label="Bus",
        y_label=chosen,
        labels=labels,
        values=values,
        metric=chosen,
        available_metrics=candidates,
    )


def _build_contingency_dataset(payload: dict[str, Any], metric: str | None, top_n: int) -> PlotDataset:
    ranking = payload.get("contingency_ranking", [])
    if not isinstance(ranking, list) or not ranking:
        raise ValueError("run_contingency_screening has no ranking data to plot.")
    candidates = ["severity", "max_line_loading_pct", "line_violations", "voltage_violations"]
    chosen = metric or "severity"
    if chosen not in candidates:
        raise ValueError(f"Metric '{chosen}' is not supported. Available metrics: {', '.join(candidates)}.")

    points: list[tuple[str, float]] = []
    for row in ranking:
        if not isinstance(row, dict):
            continue
        val = row.get(chosen)
        if not _is_number(val):
            continue
        name = f"{row.get('element_type')}:{row.get('element_id')}"
        points.append((name, float(val)))
    if not points:
        raise ValueError(f"No numeric values found for metric '{chosen}' in run_contingency_screening.")

    points = sorted(points, key=lambda x: x[1], reverse=True)[:top_n]
    labels = [p[0] for p in points]
    values = [p[1] for p in points]
    return PlotDataset(
        title=f"N-1 Screening Ranking ({chosen})",
        x_label="Outage",
        y_label=chosen,
        labels=labels,
        values=values,
        metric=chosen,
        available_metrics=candidates,
    )


def _build_topology_dataset(payload: dict[str, Any], metric: str | None) -> PlotDataset:
    summary = payload.get("topology_summary", {})
    if not isinstance(summary, dict) or not summary:
        raise ValueError("run_topology_analysis has no topology_summary data to plot.")

    derived: dict[str, float] = {}
    components = summary.get("connected_components")
    if _is_number(components):
        derived["connected_components"] = float(components)

    comp_sizes = summary.get("component_sizes")
    if isinstance(comp_sizes, list):
        derived["largest_component_size"] = float(max(comp_sizes) if comp_sizes else 0)

    unsupplied = summary.get("unsupplied_buses")
    if isinstance(unsupplied, list):
        derived["unsupplied_bus_count"] = float(len(unsupplied))

    if not derived:
        raise ValueError("run_topology_analysis has no numeric topology summary to plot.")

    candidates = list(derived.keys())
    if metric:
        if metric not in derived:
            raise ValueError(f"Metric '{metric}' is not supported. Available metrics: {', '.join(candidates)}.")
        labels = [metric]
        values = [derived[metric]]
        chosen = metric
    else:
        labels = list(derived.keys())
        values = list(derived.values())
        chosen = "topology_summary"

    return PlotDataset(
        title="Topology Summary",
        x_label="Metric",
        y_label="Value",
        labels=labels,
        values=values,
        metric=chosen,
        available_metrics=candidates,
    )


def _build_machine_summary_dataset(source_tool: str, payload: dict[str, Any], metric: str | None, top_n: int) -> PlotDataset:
    summary = payload.get("machine_summary", {})
    if not isinstance(summary, dict) or not summary:
        raise ValueError(f"{source_tool} has no machine_summary data to plot.")

    numeric_items: list[tuple[str, float]] = []
    for key, value in summary.items():
        if _is_number(value):
            numeric_items.append((str(key), float(value)))

    if not numeric_items:
        raise ValueError(f"{source_tool} machine_summary has no numeric fields to plot.")

    available = [k for k, _ in numeric_items]
    if metric:
        selected = [(k, v) for k, v in numeric_items if k == metric]
        if not selected:
            raise ValueError(f"Metric '{metric}' is not supported. Available metrics: {', '.join(available)}.")
        chosen = metric
    else:
        selected = numeric_items[:top_n]
        chosen = "machine_summary"

    labels = [k for k, _ in selected]
    values = [v for _, v in selected]
    return PlotDataset(
        title=f"{source_tool} machine_summary",
        x_label="Metric",
        y_label="Value",
        labels=labels,
        values=values,
        metric=chosen,
        available_metrics=available,
    )


def build_plot_dataset(source_tool: str, payload: dict[str, Any], metric: str | None = None, top_n: int = 20) -> PlotDataset:
    if source_tool == "run_short_circuit":
        return _build_short_circuit_dataset(payload, metric=metric, top_n=top_n)
    if source_tool == "run_contingency_screening":
        return _build_contingency_dataset(payload, metric=metric, top_n=top_n)
    if source_tool == "run_topology_analysis":
        return _build_topology_dataset(payload, metric=metric)
    return _build_machine_summary_dataset(source_tool, payload, metric=metric, top_n=top_n)
