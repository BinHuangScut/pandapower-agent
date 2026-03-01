from __future__ import annotations

from types import SimpleNamespace

from app.power.state import SessionState
from app.power.tools import ToolExecutor


def test_run_topology_analysis(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace()
    executor = ToolExecutor(state)

    monkeypatch.setattr(
        "app.power.tools.topology_analysis",
        lambda net, respect_switches: {
            "topology_summary": {"connected_components": 2, "component_sizes": [10, 4], "unsupplied_buses": [12]}
        },
    )

    result = executor.execute("run_topology_analysis", {"respect_switches": True})
    assert result.ok
    assert result.data["topology_summary"]["connected_components"] == 2
