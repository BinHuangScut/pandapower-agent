from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pandapower_agent.agent.render import console
from pandapower_agent.power.state import SessionState


def _build_summary_payload(last_results: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for tool_name, payload in last_results.items():
        data = payload.get("data", {})
        if isinstance(data, dict) and "machine_summary" in data:
            summary[tool_name] = data["machine_summary"]
    if not summary:
        summary["note"] = "No machine_summary found in last results."
    return summary


def run_export_command(state: SessionState, export_type: str, path: str) -> int:
    out_path = Path(path).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    source_results = state.last_results
    if not source_results:
        cache_file = Path(".agent_last_results.json")
        if cache_file.exists():
            try:
                source_results = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                source_results = {}
    if not source_results:
        console.print("No results available to export in current session.")
        return 1

    payload: dict[str, Any]
    if export_type == "summary":
        payload = {"type": "summary", "data": _build_summary_payload(source_results)}
    else:
        payload = {"type": "results", "data": source_results}

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"Exported {export_type} to {out_path}")
    return 0
