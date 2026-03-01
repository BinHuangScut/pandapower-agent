from __future__ import annotations

from pandapower_agent.agent.render import console, render_json, render_table, render_tool_result
from pandapower_agent.config import settings
from pandapower_agent.power.executor import ToolExecutor


def print_startup_network_preview(executor: ToolExecutor) -> None:
    if not settings.startup_show_networks:
        return
    result = executor.execute("list_builtin_networks", {"max_results": settings.startup_network_preview_count})
    if not result.ok:
        return

    console.print("[bold]Available built-in networks (preview)[/bold]")
    if result.tables:
        for table in result.tables:
            render_table(table.title, table.columns, table.rows)
    console.print("Use `agent networks --query <keyword>` to browse, or `/use <case_name>` in chat.")


def run_networks_command(executor: ToolExecutor, query: str | None, max_results: int, output_format: str) -> int:
    result = executor.execute("list_builtin_networks", {"query": query, "max_results": max_results})
    if output_format == "json":
        render_json(result.model_dump())
    else:
        render_tool_result(result)
    return 0 if result.ok else 1


def run_use_command(executor: ToolExecutor, case_name: str) -> int:
    result = executor.execute("load_builtin_network", {"case_name": case_name})
    render_tool_result(result)
    if not result.ok:
        return 1
    info_result = executor.execute("get_current_network_info", {})
    render_tool_result(info_result)
    return 0 if info_result.ok else 1
