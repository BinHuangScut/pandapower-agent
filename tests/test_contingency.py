from __future__ import annotations

from types import SimpleNamespace

from app.power.state import SessionState
from app.power.tools import ToolExecutor


def test_run_contingency_screening(monkeypatch) -> None:
    state = SessionState()
    state.working_net = SimpleNamespace()
    executor = ToolExecutor(state)

    monkeypatch.setattr(
        "app.power.tools.contingency_analysis",
        lambda net, element_types, top_k, max_outages, loading_threshold, vm_min_pu, vm_max_pu: {
            "contingency_ranking": [
                {
                    "element_type": "line",
                    "element_id": 3,
                    "severity": 123.4,
                    "line_violations": 2,
                    "voltage_violations": 1,
                    "max_line_loading_pct": 145.0,
                }
            ],
            "machine_summary": {"scanned_outages": 1, "returned": 1, "truncated": False},
        },
    )

    result = executor.execute(
        "run_contingency_screening",
        {"element_types": ["line"], "top_k": 5, "max_outages": 10, "loading_threshold": 100.0, "vm_min_pu": 0.95, "vm_max_pu": 1.05},
    )
    assert result.ok
    assert result.data["contingency_ranking"][0]["element_id"] == 3
