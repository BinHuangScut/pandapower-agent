from __future__ import annotations

from typing import Any


def _import_topology():
    import pandapower.topology as top  # type: ignore

    return top


def run_topology_analysis(net: Any, respect_switches: bool = True) -> dict[str, Any]:
    top = _import_topology()
    graph = top.create_nxgraph(net, respect_switches=respect_switches)

    try:
        import networkx as nx  # type: ignore

        n_components = int(nx.number_connected_components(graph))
        component_sizes = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    except Exception:
        n_components = 0
        component_sizes = []

    try:
        unsupplied = sorted([int(x) for x in top.unsupplied_buses(net)])
    except Exception:
        unsupplied = []

    return {
        "topology_summary": {
            "connected_components": n_components,
            "component_sizes": component_sizes,
            "unsupplied_buses": unsupplied,
        }
    }
