from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

from pandapower_agent.agent.render import console, render_agent_reply, render_tool_traces
from pandapower_agent.cli.commands.export import run_export_command
from pandapower_agent.cli.commands.network import print_startup_network_preview, run_networks_command, run_use_command
from pandapower_agent.cli.commands.plot import run_plot_command, run_plot_network_command
from pandapower_agent.cli.commands.scenario import run_scenarios_command, run_undo_command
from pandapower_agent.cli.commands.tools import run_tools_command
from pandapower_agent.config import settings

if TYPE_CHECKING:
    from pandapower_agent.agent.runtime import AgentRuntime


def _validate_admin_key(candidate: str) -> tuple[bool, str]:
    expected = os.getenv("ADMIN_DEBUG_KEY", "").strip()
    if not expected:
        return False, "Admin debug mode is not configured."
    if candidate != expected:
        return False, "Invalid admin key."
    return True, ""


def apply_admin_key(runtime: "AgentRuntime", admin_key: str | None) -> bool:
    if admin_key is None:
        return True
    ok, message = _validate_admin_key(admin_key)
    if not ok:
        console.print(message)
        return False
    runtime.set_admin_mode(True)
    console.print("Admin debug mode enabled.")
    return True


def _handle_hidden_admin_command(runtime: "AgentRuntime", line: str) -> bool:
    normalized = line.strip()
    lowered = normalized.lower()
    if lowered == "/admin off":
        runtime.set_admin_mode(False)
        console.print("Admin debug mode disabled.")
        return True

    if lowered.startswith("/admin unlock "):
        key = normalized[len("/admin unlock ") :].strip()
        ok, message = _validate_admin_key(key)
        if ok:
            runtime.set_admin_mode(True)
            console.print("Admin debug mode enabled.")
        else:
            console.print(message)
        return True

    return False


def run_single(runtime: "AgentRuntime", instruction: str) -> int:
    out = runtime.run_turn(instruction)
    render_agent_reply(out["final_text"])
    if runtime.admin_mode:
        render_tool_traces(out["tool_traces"])
    return 0


def chat_loop(runtime: "AgentRuntime") -> int:
    console.print(
        "Type questions directly. Commands: /networks /use <case_name> /scenarios /undo /plot <path> [tool] [metric] [chart] /plotnet <path> /export <summary|results> <path> /reset /exit"
    )
    print_startup_network_preview(runtime.executor)

    while True:
        try:
            line = input("you> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if _handle_hidden_admin_command(runtime, line):
            continue
        if line.lower() in {"exit", "quit"}:
            break
        if line.lower() == "/reset":
            runtime.executor.state.reset()
            runtime.reset_conversation()
            console.print("Session reset")
            continue
        if line.lower() == "/networks":
            run_networks_command(runtime.executor, query=None, max_results=settings.startup_network_preview_count, output_format="table")
            continue
        if line.lower() == "/scenarios":
            run_scenarios_command(runtime.executor, output_format="table")
            continue
        if line.lower() == "/undo":
            run_undo_command(runtime.executor)
            continue
        if line.lower().startswith("/use "):
            case_name = line[5:].strip()
            if not case_name:
                console.print("Usage: /use <case_name>")
                continue
            run_use_command(runtime.executor, case_name)
            continue
        if line.lower() == "/tools":
            run_tools_command("table")
            continue
        if line.lower().startswith("/export "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                console.print("Usage: /export <summary|results> <path>")
                continue
            export_type = parts[1].strip().lower()
            export_path = parts[2].strip()
            if export_type not in {"summary", "results"}:
                console.print("Export type must be 'summary' or 'results'")
                continue
            run_export_command(runtime.executor.state, export_type=export_type, path=export_path)
            continue
        if line.lower().startswith("/plot"):
            if line.lower().startswith("/plotnet"):
                try:
                    parts = shlex.split(line)
                except ValueError:
                    console.print("Usage: /plotnet <path>")
                    continue
                if len(parts) < 2:
                    console.print("Usage: /plotnet <path>")
                    continue
                run_plot_network_command(
                    runtime.executor,
                    path=parts[1].strip(),
                    library="networkx",
                    bus_size=1.0,
                    line_width=1.0,
                    show_bus_labels=True,
                    label_font_size=8.0,
                    plot_loads=False,
                    plot_gens=False,
                    plot_sgens=False,
                    respect_switches=True,
                )
                continue
            try:
                parts = shlex.split(line)
            except ValueError:
                console.print("Usage: /plot <path> [tool_name] [metric] [auto|bar|line]")
                continue
            if len(parts) < 2:
                console.print("Usage: /plot <path> [tool_name] [metric] [auto|bar|line]")
                continue
            plot_path = parts[1].strip()
            source_tool = parts[2].strip() if len(parts) >= 3 else None
            metric = parts[3].strip() if len(parts) >= 4 else None
            chart = parts[4].strip().lower() if len(parts) >= 5 else "auto"
            if chart not in {"auto", "bar", "line"}:
                console.print("Chart must be one of auto/bar/line")
                continue
            run_plot_command(
                runtime.executor,
                path=plot_path,
                source_tool=source_tool,
                metric=metric,
                chart=chart,
                top_n=20,
            )
            continue

        out = runtime.run_turn(line)
        render_agent_reply(out["final_text"])
        if runtime.admin_mode:
            render_tool_traces(out["tool_traces"])
    return 0
