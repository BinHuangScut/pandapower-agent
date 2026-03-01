from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pandapower_agent.power.plotting import PLOTTABLE_SOURCE_TOOLS
from pandapower_agent.power.runtime_guard import is_pandapower_related_exception
from pandapower_agent.schema.types import ToolResult


def import_pp():
    import pandapower as pp  # type: ignore

    return pp


def tool_error(message: str, *, data: dict[str, Any] | None = None, next_action: str | None = None) -> ToolResult:
    payload = data.copy() if data else {}
    if next_action:
        payload["next_action"] = next_action
    return ToolResult(ok=False, message=message, data=payload)


def public_error_message(exc: Exception) -> tuple[str, str]:
    if is_pandapower_related_exception(exc):
        return (
            "Power-system calculation failed in pandapower. Detailed error is hidden from user output.",
            "Check network prerequisites/parameters and retry.",
        )
    return str(exc), "Check tool args and current network state."


def ensure_net(state: Any) -> None:
    if not state.has_net():
        raise ValueError("No network loaded. Call load_builtin_network first.")


def safe_count(net: Any, table_name: str) -> int:
    table = getattr(net, table_name, None)
    if table is None:
        return 0
    try:
        return int(len(table.index))
    except Exception:
        try:
            return int(len(table))
        except Exception:
            return 0


def current_network_info(net: Any, fallback_name: str | None = None) -> dict[str, Any]:
    name = None
    if hasattr(net, "name"):
        name = getattr(net, "name")
    if not name:
        try:
            name = net.get("name")
        except Exception:
            name = None
    if not name:
        try:
            name = net["name"]
        except Exception:
            name = None
    if not name:
        name = fallback_name

    return {
        "name": name,
        "bus_count": safe_count(net, "bus"),
        "line_count": safe_count(net, "line"),
        "load_count": safe_count(net, "load"),
        "sgen_count": safe_count(net, "sgen"),
        "gen_count": safe_count(net, "gen"),
    }


def ensure_bus_exists(net: Any, bus_id: int) -> None:
    if bus_id not in list(net.bus.index):
        raise ValueError(f"bus_id {bus_id} not found. Available bus IDs: {list(net.bus.index)[:20]}")


def import_plotting_backend():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    return sns, plt


def import_pandapower_plotting_backend():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandapower.plotting as ppplot  # type: ignore

    return ppplot, plt


def extract_bus_label_positions(net: Any) -> list[tuple[int, float, float]]:
    bus_table = getattr(net, "bus", None)
    if bus_table is None or not hasattr(bus_table, "index") or "geo" not in getattr(bus_table, "columns", []):
        return []

    positions: list[tuple[int, float, float]] = []
    for bus_id in list(bus_table.index):
        try:
            raw_geo = bus_table.at[bus_id, "geo"]
        except Exception:
            continue
        if raw_geo is None:
            continue

        try:
            payload = json.loads(raw_geo) if isinstance(raw_geo, str) else raw_geo
            if not isinstance(payload, dict):
                continue
            coords = payload.get("coordinates")
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                continue
            positions.append((int(bus_id), float(coords[0]), float(coords[1])))
        except Exception:
            continue
    return positions


def load_cached_results() -> dict[str, Any]:
    cache_file = Path(".agent_last_results.json")
    if not cache_file.exists():
        return {}
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def resolve_plot_source(
    source_results: dict[str, Any],
    requested_source: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    if requested_source:
        if requested_source not in PLOTTABLE_SOURCE_TOOLS:
            return None, None
        candidate = source_results.get(requested_source)
        if not isinstance(candidate, dict):
            return None, None
        return requested_source, candidate

    keys = list(source_results.keys())
    for tool_name in reversed(keys):
        if tool_name not in PLOTTABLE_SOURCE_TOOLS:
            continue
        candidate = source_results.get(tool_name)
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("ok", False)):
            continue
        data = candidate.get("data")
        if isinstance(data, dict) and data:
            return tool_name, candidate
    return None, None


def render_plot_image(
    labels: list[str],
    values: list[float],
    title: str,
    x_label: str,
    y_label: str,
    chart: str,
    output_path: str,
) -> Path:
    sns, plt = import_plotting_backend()
    out_path = Path(output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width = max(8.0, min(24.0, 0.6 * max(4, len(labels))))
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(width, 5))

    if chart == "line":
        sns.lineplot(
            x=labels,
            y=values,
            marker="o",
            linewidth=1.8,
            color="#2a6f97",
            sort=False,
            ax=ax,
        )
    else:
        sns.barplot(x=labels, y=values, color="#2a6f97", edgecolor="#1d3557", ax=ax)
        if len(values) <= 20:
            if getattr(ax, "containers", None):
                ax.bar_label(ax.containers[0], labels=[f"{value:.3g}" for value in values], padding=2, fontsize=8)

    rotate = 45 if len(labels) > 8 else 0
    plt.setp(ax.get_xticklabels(), rotation=rotate, ha="right" if rotate else "center")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
