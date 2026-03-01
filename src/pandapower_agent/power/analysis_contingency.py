from __future__ import annotations

import copy
from typing import Any

from pandapower_agent.power.metrics import summarize_network_metrics


def _import_pp():
    import pandapower as pp  # type: ignore

    return pp


def _voltage_violations(net: Any, vm_min_pu: float, vm_max_pu: float) -> int:
    if not hasattr(net, "res_bus") or net.res_bus.empty or "vm_pu" not in net.res_bus:
        return 0
    ser = net.res_bus["vm_pu"]
    bad = ser[(ser < vm_min_pu) | (ser > vm_max_pu)]
    return int(len(bad))


def _line_loading_violations(net: Any, loading_threshold: float) -> int:
    if not hasattr(net, "res_line") or net.res_line.empty or "loading_percent" not in net.res_line:
        return 0
    bad = net.res_line[net.res_line["loading_percent"] >= loading_threshold]
    return int(len(bad))


def run_contingency_screening(
    net: Any,
    element_types: list[str] | None = None,
    top_k: int = 10,
    max_outages: int = 20,
    loading_threshold: float = 100.0,
    vm_min_pu: float = 0.95,
    vm_max_pu: float = 1.05,
) -> dict[str, Any]:
    pp = _import_pp()
    targets = element_types or ["line", "trafo"]
    ranking: list[dict[str, Any]] = []
    scanned = 0
    truncated = False

    for element_type in targets:
        table = getattr(net, element_type, None)
        if table is None or len(table.index) == 0:
            continue
        for element_id in list(table.index):
            if scanned >= max_outages:
                truncated = True
                break
            scanned += 1
            sim_net = copy.deepcopy(net)
            sim_table = getattr(sim_net, element_type)
            sim_table.at[element_id, "in_service"] = False

            item: dict[str, Any] = {"element_type": element_type, "element_id": int(element_id)}
            try:
                pp.runpp(sim_net)
                summary = summarize_network_metrics(sim_net)
                line_bad = _line_loading_violations(sim_net, loading_threshold=loading_threshold)
                vm_bad = _voltage_violations(sim_net, vm_min_pu=vm_min_pu, vm_max_pu=vm_max_pu)
                max_loading = summary.get("max_line_loading_pct") or 0.0
                severity = float(max_loading) + 10.0 * (line_bad + vm_bad)
                item.update(
                    {
                        "ok": True,
                        "severity": severity,
                        "line_violations": line_bad,
                        "voltage_violations": vm_bad,
                        "max_line_loading_pct": summary.get("max_line_loading_pct"),
                        "min_bus_vm_pu": summary.get("min_bus_vm_pu"),
                    }
                )
            except Exception as exc:
                _ = exc
                item.update({"ok": False, "severity": 1e9, "error": "contingency_case_failed"})
            ranking.append(item)
        if truncated:
            break

    ranking.sort(key=lambda x: float(x.get("severity", 0.0)), reverse=True)
    return {
        "contingency_ranking": ranking[:top_k],
        "machine_summary": {
            "scanned_outages": scanned,
            "returned": min(top_k, len(ranking)),
            "truncated": truncated,
        },
    }
