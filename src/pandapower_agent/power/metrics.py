from __future__ import annotations

from typing import Any


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def summarize_network_metrics(net: Any) -> dict[str, float | None]:
    summary = {
        "max_line_loading_pct": None,
        "min_bus_vm_pu": None,
        "max_bus_vm_pu": None,
        "total_active_loss_mw": None,
    }

    if hasattr(net, "res_line") and getattr(net.res_line, "empty", True) is False and "loading_percent" in net.res_line:
        summary["max_line_loading_pct"] = _safe_float(net.res_line["loading_percent"].max())

    if hasattr(net, "res_bus") and getattr(net.res_bus, "empty", True) is False and "vm_pu" in net.res_bus:
        summary["min_bus_vm_pu"] = _safe_float(net.res_bus["vm_pu"].min())
        summary["max_bus_vm_pu"] = _safe_float(net.res_bus["vm_pu"].max())

    if (
        hasattr(net, "res_ext_grid")
        and getattr(net.res_ext_grid, "empty", True) is False
        and "p_mw" in net.res_ext_grid
    ):
        summary["total_active_loss_mw"] = _safe_float(net.res_ext_grid["p_mw"].sum())

    return summary


def diff_metrics(
    a: dict[str, float | None], b: dict[str, float | None], metric_keys: list[str] | None = None
) -> dict[str, dict[str, float | None]]:
    keys = metric_keys or sorted(set(a) | set(b))
    out: dict[str, dict[str, float | None]] = {}
    for k in keys:
        av = a.get(k)
        bv = b.get(k)
        dv = None
        if av is not None and bv is not None:
            dv = bv - av
        out[k] = {"a": av, "b": bv, "delta": dv}
    return out
