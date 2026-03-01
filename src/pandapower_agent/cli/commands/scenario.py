from __future__ import annotations

from pandapower_agent.agent.render import render_json, render_tool_result
from pandapower_agent.power.executor import ToolExecutor


def run_scenarios_command(executor: ToolExecutor, output_format: str) -> int:
    result = executor.execute("list_scenarios", {})
    if output_format == "json":
        render_json(result.model_dump())
    else:
        render_tool_result(result)
    return 0 if result.ok else 1


def run_undo_command(executor: ToolExecutor) -> int:
    result = executor.execute("undo_last_mutation", {})
    render_tool_result(result)
    return 0 if result.ok else 1
