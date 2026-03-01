from __future__ import annotations

from typing import Any


def _import_sc():
    import pandapower.shortcircuit as sc  # type: ignore

    return sc


def run_short_circuit(
    net: Any,
    case: str = "max",
    fault: str = "3ph",
    bus_ids: list[int] | None = None,
) -> dict[str, Any]:
    sc = _import_sc()
    sc.calc_sc(net, case=case, fault=fault)

    if not hasattr(net, "res_bus_sc") or net.res_bus_sc.empty:
        return {
            "case": case,
            "fault": fault,
            "rows": [],
            "machine_summary": {"max_ikss_ka": None, "min_ikss_ka": None, "rows": 0},
        }

    df = net.res_bus_sc
    if bus_ids:
        df = df[df.index.isin(bus_ids)]

    ikss_col = "ikss_ka" if "ikss_ka" in df.columns else None
    ip_col = "ip_ka" if "ip_ka" in df.columns else None
    ith_col = "ith_ka" if "ith_ka" in df.columns else None
    rows = []
    for idx, row in df.iterrows():
        rows.append(
            {
                "bus": int(idx),
                "ikss_ka": float(row[ikss_col]) if ikss_col else None,
                "ip_ka": float(row[ip_col]) if ip_col else None,
                "ith_ka": float(row[ith_col]) if ith_col else None,
            }
        )

    ikss_vals = [r["ikss_ka"] for r in rows if r["ikss_ka"] is not None]
    return {
        "case": case,
        "fault": fault,
        "rows": rows,
        "machine_summary": {
            "max_ikss_ka": max(ikss_vals) if ikss_vals else None,
            "min_ikss_ka": min(ikss_vals) if ikss_vals else None,
            "rows": len(rows),
        },
    }
