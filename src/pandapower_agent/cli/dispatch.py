from __future__ import annotations

import argparse

from pandapower_agent.agent.render import console
from pandapower_agent.cli.chat import apply_admin_key, chat_loop, run_single
from pandapower_agent.cli.commands.config_init import run_config_init_command
from pandapower_agent.cli.commands.doctor import run_doctor_command
from pandapower_agent.cli.commands.export import run_export_command
from pandapower_agent.cli.commands.network import run_networks_command, run_use_command
from pandapower_agent.cli.commands.plot import run_plot_command, run_plot_network_command
from pandapower_agent.cli.commands.scenario import run_scenarios_command, run_undo_command
from pandapower_agent.cli.commands.tools import run_tools_command
from pandapower_agent.config import settings
from pandapower_agent.power.executor import ToolExecutor
from pandapower_agent.power.state import SessionState


def require_api_key() -> None:
    key = settings.active_api_key
    if not key:
        if settings.provider == "google":
            raise RuntimeError(
                "GOOGLE_API_KEY is required for LLM_PROVIDER=google "
                "(fallback OPENAI_API_KEY is also supported; set it in project .env/.env.example or export it in shell)"
            )
        raise RuntimeError("OPENAI_API_KEY is required (set it in project .env/.env.example or export it in shell)")


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> int:
    state = SessionState()
    executor = ToolExecutor(state)

    if args.cmd == "reset":
        state.reset()
        console.print("Session reset")
        return 0
    if args.cmd == "undo":
        return run_undo_command(executor)
    if args.cmd == "networks":
        return run_networks_command(executor, query=args.query, max_results=args.max_results, output_format=args.format)
    if args.cmd == "use":
        return run_use_command(executor, case_name=args.case_name)
    if args.cmd == "tools":
        return run_tools_command(output_format=args.format)
    if args.cmd == "doctor":
        return run_doctor_command(executor, case_name=args.case_name, output_format=args.format)
    if args.cmd == "scenarios":
        return run_scenarios_command(executor, output_format=args.format)
    if args.cmd == "export":
        return run_export_command(state, export_type=args.export_type, path=args.path)
    if args.cmd == "plot":
        return run_plot_command(
            executor,
            path=args.path,
            source_tool=args.source_tool,
            metric=args.metric,
            chart=args.chart,
            top_n=args.top_n,
        )
    if args.cmd == "plot-network":
        return run_plot_network_command(
            executor,
            path=args.path,
            library=args.library,
            bus_size=args.bus_size,
            line_width=args.line_width,
            show_bus_labels=not args.hide_bus_labels,
            label_font_size=args.label_font_size,
            plot_loads=args.plot_loads,
            plot_gens=args.plot_gens,
            plot_sgens=args.plot_sgens,
            respect_switches=not args.ignore_switches,
        )
    if args.cmd == "config":
        if args.config_cmd == "init":
            return run_config_init_command(args)
        console.print("Unknown config command.")
        return 1

    require_api_key()
    from pandapower_agent.agent.runtime import AgentRuntime

    runtime = AgentRuntime(executor=executor)
    if not apply_admin_key(runtime, getattr(args, "admin_key", None)):
        return 1

    if args.cmd == "run":
        return run_single(runtime, args.instruction)
    if args.cmd == "chat":
        return chat_loop(runtime)

    if parser is not None:
        parser.print_help()
    return 1
