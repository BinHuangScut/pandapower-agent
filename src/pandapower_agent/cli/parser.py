from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version

from pandapower_agent.config import settings


def _package_version() -> str:
    try:
        return version("pandapower-agent")
    except PackageNotFoundError:
        return "0.1.0-dev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Pandapower AI Agent CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run single instruction")
    run_p.add_argument("instruction", type=str)
    run_p.add_argument("--admin-key", type=str, default=None, help=argparse.SUPPRESS)

    chat_p = sub.add_parser("chat", help="Start chat session")
    chat_p.add_argument("--admin-key", type=str, default=None, help=argparse.SUPPRESS)
    sub.add_parser("reset", help="Reset in-memory session")
    sub.add_parser("undo", help="Undo last mutating action")

    networks_p = sub.add_parser("networks", help="List selectable pandapower built-in networks")
    networks_p.add_argument("--query", type=str, default=None, help="Optional keyword filter")
    networks_p.add_argument("--max", dest="max_results", type=int, default=20, help="Maximum result size")
    networks_p.add_argument("--format", choices=["table", "json"], default="table")

    use_p = sub.add_parser("use", help="Switch to a built-in network")
    use_p.add_argument("case_name", type=str)

    tools_p = sub.add_parser("tools", help="Show tool catalog and usage examples")
    tools_p.add_argument("--format", choices=["table", "json"], default="table")

    doctor_p = sub.add_parser("doctor", help="Run built-in toolchain health check")
    doctor_p.add_argument("--case-name", type=str, default=settings.default_network, help="Network used for health checks")
    doctor_p.add_argument("--format", choices=["table", "json"], default="table")

    scenarios_p = sub.add_parser("scenarios", help="List saved scenarios")
    scenarios_p.add_argument("--format", choices=["table", "json"], default="table")

    export_p = sub.add_parser("export", help="Export latest results to JSON")
    export_p.add_argument("--type", dest="export_type", choices=["summary", "results"], default="summary")
    export_p.add_argument("--path", required=True, type=str)

    plot_p = sub.add_parser("plot", help="Plot latest analysis result to image")
    plot_p.add_argument("--path", type=str, default="./outputs/analysis_plot.png")
    plot_p.add_argument("--tool", dest="source_tool", type=str, default=None)
    plot_p.add_argument("--metric", type=str, default=None)
    plot_p.add_argument("--chart", choices=["auto", "bar", "line"], default="auto")
    plot_p.add_argument("--top-n", type=int, default=20)

    plot_net_p = sub.add_parser("plot-network", help="Plot current network layout to image")
    plot_net_p.add_argument("--path", type=str, default="./outputs/network_plot.png")
    plot_net_p.add_argument("--library", choices=["networkx", "igraph"], default="networkx")
    plot_net_p.add_argument("--bus-size", type=float, default=1.0)
    plot_net_p.add_argument("--line-width", type=float, default=1.0)
    plot_net_p.add_argument("--label-font-size", type=float, default=8.0)
    plot_net_p.add_argument("--hide-bus-labels", action="store_true")
    plot_net_p.add_argument("--plot-loads", action="store_true")
    plot_net_p.add_argument("--plot-gens", action="store_true")
    plot_net_p.add_argument("--plot-sgens", action="store_true")
    plot_net_p.add_argument("--ignore-switches", action="store_true")

    config_p = sub.add_parser("config", help="Configure provider and API keys")
    config_sub = config_p.add_subparsers(dest="config_cmd", required=True)
    config_init_p = config_sub.add_parser("init", help="Interactive setup wizard for .env")
    config_init_p.add_argument("--path", type=str, default=".env", help="Target dotenv file path")
    config_init_p.add_argument("--provider", choices=["openai", "google"], default=None)
    config_init_p.add_argument("--openai-api-key", type=str, default=None)
    config_init_p.add_argument("--google-api-key", type=str, default=None)
    config_init_p.add_argument("--openai-model", type=str, default=None)
    config_init_p.add_argument("--google-model", type=str, default=None)
    config_init_p.add_argument("--openai-base-url", type=str, default=None)
    config_init_p.add_argument("--google-base-url", type=str, default=None)
    config_init_p.add_argument("--default-network", type=str, default=None)
    config_init_p.add_argument("--max-tool-calls-per-turn", type=int, default=None)
    config_init_p.add_argument("--skip-check", action="store_true", help="Skip live API connectivity check")
    config_init_p.add_argument("--force", action="store_true", help="Overwrite existing dotenv file without prompt")
    config_init_p.add_argument("--non-interactive", action="store_true", help="Do not prompt for input")

    return parser
