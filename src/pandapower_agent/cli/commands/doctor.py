from __future__ import annotations

from typing import Any

from pandapower_agent.agent.render import console, render_json, render_table
from pandapower_agent.power.executor import ToolExecutor


def run_doctor_command(executor: ToolExecutor, case_name: str, output_format: str) -> int:
    checks = [
        ("load_network", "load_builtin_network", {"case_name": case_name}, True),
        ("network_info", "get_current_network_info", {}, True),
        ("ac_power_flow", "run_power_flow", {"algorithm": "nr", "enforce_q_lims": False}, True),
        ("topology", "run_topology_analysis", {"respect_switches": True}, True),
        ("line_violations", "get_line_loading_violations", {"threshold": 100.0}, False),
    ]

    rows: list[list[str]] = []
    report: list[dict[str, Any]] = []
    overall_ok = True

    for step, tool_name, args, required in checks:
        result = executor.execute(tool_name, args)
        if result.ok:
            status = "ok"
        elif required:
            status = "error"
            overall_ok = False
        else:
            status = "warning"
        rows.append([step, tool_name, status, result.message])
        report.append(
            {
                "step": step,
                "tool": tool_name,
                "required": required,
                "ok": result.ok,
                "status": status,
                "message": result.message,
            }
        )

    payload = {"ok": overall_ok, "case_name": case_name, "checks": report}
    if output_format == "json":
        render_json(payload)
    else:
        render_table("Agent Doctor", ["step", "tool", "status", "message"], rows)
        console.print(f"Doctor status: {'PASS' if overall_ok else 'FAIL'}")
    return 0 if overall_ok else 1
