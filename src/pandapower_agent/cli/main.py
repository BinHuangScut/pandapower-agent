from __future__ import annotations

import argparse
import getpass
import json
import os
import shlex
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.agent.render import (
    console,
    render_agent_reply,
    render_json,
    render_table,
    render_tool_result,
    render_tool_traces,
)
from app.config import _normalize_api_key, _normalize_base_url, settings
from app.power.state import SessionState
from app.power.tools import TOOL_SPECS, ToolExecutor

if TYPE_CHECKING:
    from app.agent.loop import AgentRuntime


def _package_version() -> str:
    try:
        return version("pandapower-agent")
    except PackageNotFoundError:
        return "0.1.0-dev"


def _validate_admin_key(candidate: str) -> tuple[bool, str]:
    expected = os.getenv("ADMIN_DEBUG_KEY", "").strip()
    if not expected:
        return False, "Admin debug mode is not configured."
    if candidate != expected:
        return False, "Invalid admin key."
    return True, ""


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


def require_api_key() -> None:
    key = settings.active_api_key
    if not key:
        if settings.provider == "google":
            raise RuntimeError(
                "GOOGLE_API_KEY is required for LLM_PROVIDER=google "
                "(fallback OPENAI_API_KEY is also supported; set it in project .env/.env.example or export it in shell)"
            )
        raise RuntimeError("OPENAI_API_KEY is required (set it in project .env/.env.example or export it in shell)")


def _read_existing_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            data[key.strip()] = value.strip()
    except OSError:
        return {}
    return data


def _prompt_with_default(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def _prompt_secret(prompt: str) -> str:
    return getpass.getpass(prompt).strip()


def _verify_llm_config(provider: str, api_key: str, model: str, base_url: str) -> tuple[bool, str]:
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)

    try:
        if provider == "google":
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
        else:
            client.responses.create(
                model=model,
                input="ping",
                max_output_tokens=8,
            )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, "Connectivity check passed."


def _write_dotenv(path: Path, values: dict[str, str]) -> None:
    ordered_keys = [
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "GOOGLE_API_KEY",
        "GOOGLE_MODEL",
        "GOOGLE_BASE_URL",
        "DEFAULT_NETWORK",
        "MAX_TOOL_CALLS_PER_TURN",
        "LANGUAGE_AUTO",
        "STARTUP_SHOW_NETWORKS",
        "STARTUP_NETWORK_PREVIEW_COUNT",
    ]
    lines = [f"{key}={values.get(key, '')}" for key in ordered_keys]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_config_init_command(args: argparse.Namespace) -> int:
    env_path = Path(args.path).expanduser()
    existing = _read_existing_dotenv(env_path)
    interactive = not args.non_interactive

    if env_path.exists() and not args.force and interactive:
        answer = input(f"{env_path} already exists. Overwrite it? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            console.print("Aborted by user.")
            return 1
    elif env_path.exists() and not args.force and not interactive:
        console.print(f"{env_path} already exists. Re-run with --force to overwrite in non-interactive mode.")
        return 1

    provider = args.provider or settings.provider
    if interactive and args.provider is None:
        provider = _prompt_with_default("Provider (openai/google)", settings.provider).strip().lower()
    if provider not in {"openai", "google"}:
        console.print("Provider must be one of: openai, google.")
        return 1

    openai_model = args.openai_model or existing.get("OPENAI_MODEL", settings.openai_model)
    google_model = args.google_model or existing.get("GOOGLE_MODEL", settings.google_model)
    openai_base_url = args.openai_base_url
    if openai_base_url is None:
        openai_base_url = existing.get("OPENAI_BASE_URL", settings.openai_base_url)
    google_base_url = args.google_base_url
    if google_base_url is None:
        google_base_url = existing.get("GOOGLE_BASE_URL", settings.google_base_url)
    default_network = args.default_network or existing.get("DEFAULT_NETWORK", settings.default_network)
    try:
        max_tool_calls = args.max_tool_calls_per_turn or int(
            existing.get("MAX_TOOL_CALLS_PER_TURN", str(settings.max_tool_calls_per_turn))
        )
    except ValueError:
        console.print("MAX_TOOL_CALLS_PER_TURN must be an integer.")
        return 1

    openai_key = args.openai_api_key
    if openai_key is None:
        openai_key = existing.get("OPENAI_API_KEY", settings.openai_api_key)
    google_key = args.google_api_key
    if google_key is None:
        google_key = existing.get("GOOGLE_API_KEY", settings.google_api_key)

    if interactive and args.openai_api_key is None:
        openai_candidate = _prompt_secret("OPENAI_API_KEY (hidden; leave empty to keep current): ")
        if openai_candidate:
            openai_key = openai_candidate
    if interactive and args.google_api_key is None:
        google_candidate = _prompt_secret("GOOGLE_API_KEY (hidden; leave empty to keep current): ")
        if google_candidate:
            google_key = google_candidate

    normalized_openai_key = _normalize_api_key(openai_key or "")
    normalized_google_key = _normalize_api_key(google_key or "")
    if provider == "openai" and not normalized_openai_key:
        console.print("OPENAI_API_KEY is required for provider=openai.")
        return 1
    if provider == "google" and not normalized_google_key and not normalized_openai_key:
        console.print("GOOGLE_API_KEY (or fallback OPENAI_API_KEY) is required for provider=google.")
        return 1

    try:
        normalized_openai_base_url = _normalize_base_url(
            (openai_base_url or "").strip() or "https://api.openai.com/v1",
            env_name="OPENAI_BASE_URL",
        )
        normalized_google_base_url = _normalize_base_url(
            (google_base_url or "").strip() or "https://generativelanguage.googleapis.com/v1beta/openai/",
            env_name="GOOGLE_BASE_URL",
        )
    except RuntimeError as exc:
        console.print(str(exc))
        return 1

    if not args.skip_check:
        active_model = google_model if provider == "google" else openai_model
        active_base_url = normalized_google_base_url if provider == "google" else normalized_openai_base_url
        if provider == "google":
            active_key = normalized_google_key or normalized_openai_key
        else:
            active_key = normalized_openai_key
        ok, message = _verify_llm_config(provider=provider, api_key=active_key, model=active_model, base_url=active_base_url)
        if not ok:
            console.print(f"Connectivity check failed: {message}")
            console.print("Use --skip-check to save config without validation.")
            return 1
        console.print(message)

    values = {
        "LLM_PROVIDER": provider,
        "OPENAI_API_KEY": openai_key or "",
        "OPENAI_MODEL": openai_model,
        "OPENAI_BASE_URL": openai_base_url or "",
        "GOOGLE_API_KEY": google_key or "",
        "GOOGLE_MODEL": google_model,
        "GOOGLE_BASE_URL": google_base_url or "",
        "DEFAULT_NETWORK": default_network,
        "MAX_TOOL_CALLS_PER_TURN": str(max_tool_calls),
        "LANGUAGE_AUTO": str(settings.language_auto).lower(),
        "STARTUP_SHOW_NETWORKS": str(settings.startup_show_networks).lower(),
        "STARTUP_NETWORK_PREVIEW_COUNT": str(settings.startup_network_preview_count),
    }
    _write_dotenv(env_path, values)
    console.print(f"Configuration written to {env_path}")
    return 0


def _print_startup_network_preview(executor: ToolExecutor) -> None:
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


def _run_networks_command(executor: ToolExecutor, query: str | None, max_results: int, output_format: str) -> int:
    result = executor.execute("list_builtin_networks", {"query": query, "max_results": max_results})
    if output_format == "json":
        render_json(result.model_dump())
    else:
        render_tool_result(result)
    return 0 if result.ok else 1


def _run_use_command(executor: ToolExecutor, case_name: str) -> int:
    result = executor.execute("load_builtin_network", {"case_name": case_name})
    render_tool_result(result)
    if not result.ok:
        return 1
    info_result = executor.execute("get_current_network_info", {})
    render_tool_result(info_result)
    return 0 if info_result.ok else 1


def _run_scenarios_command(executor: ToolExecutor, output_format: str) -> int:
    result = executor.execute("list_scenarios", {})
    if output_format == "json":
        render_json(result.model_dump())
    else:
        render_tool_result(result)
    return 0 if result.ok else 1


def _run_undo_command(executor: ToolExecutor) -> int:
    result = executor.execute("undo_last_mutation", {})
    render_tool_result(result)
    return 0 if result.ok else 1


def _build_summary_payload(last_results: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for tool_name, payload in last_results.items():
        data = payload.get("data", {})
        if isinstance(data, dict) and "machine_summary" in data:
            summary[tool_name] = data["machine_summary"]
    if not summary:
        summary["note"] = "No machine_summary found in last results."
    return summary


def _run_export_command(state: SessionState, export_type: str, path: str) -> int:
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


def _run_plot_command(
    executor: ToolExecutor,
    path: str,
    source_tool: str | None,
    metric: str | None,
    chart: str,
    top_n: int,
) -> int:
    result = executor.execute(
        "plot_analysis_result",
        {"path": path, "source_tool": source_tool, "metric": metric, "chart": chart, "top_n": top_n},
    )
    render_tool_result(result)
    return 0 if result.ok else 1


def _run_plot_network_command(
    executor: ToolExecutor,
    path: str,
    library: str,
    bus_size: float,
    line_width: float,
    show_bus_labels: bool,
    label_font_size: float,
    plot_loads: bool,
    plot_gens: bool,
    plot_sgens: bool,
    respect_switches: bool,
) -> int:
    if not executor.state.has_net():
        bootstrap = executor.execute("load_builtin_network", {"case_name": settings.default_network})
        if not bootstrap.ok:
            render_tool_result(bootstrap)
            return 1

    result = executor.execute(
        "plot_network_layout",
        {
            "path": path,
            "library": library,
            "bus_size": bus_size,
            "line_width": line_width,
            "show_bus_labels": show_bus_labels,
            "label_font_size": label_font_size,
            "plot_loads": plot_loads,
            "plot_gens": plot_gens,
            "plot_sgens": plot_sgens,
            "respect_switches": respect_switches,
        },
    )
    render_tool_result(result)
    return 0 if result.ok else 1


def _tool_schema_keys(schema: dict[str, Any]) -> str:
    props = schema.get("properties", {})
    keys = list(props.keys())
    return ", ".join(keys) if keys else "-"


def _run_tools_command(output_format: str) -> int:
    items: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        schema = spec.args_model.model_json_schema()
        items.append(
            {
                "name": spec.name,
                "description": spec.description,
                "args": list(schema.get("properties", {}).keys()),
                "zh_example": spec.zh_example,
                "en_example": spec.en_example,
            }
        )

    if output_format == "json":
        render_json({"tools": items})
        return 0

    rows = []
    for spec in TOOL_SPECS:
        schema = spec.args_model.model_json_schema()
        rows.append([spec.name, spec.description, _tool_schema_keys(schema), spec.zh_example, spec.en_example])
    render_table("Tool Catalog", ["tool", "description", "key_args", "zh_example", "en_example"], rows)
    return 0


def _run_doctor_command(executor: ToolExecutor, case_name: str, output_format: str) -> int:
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


def _apply_admin_key(runtime: AgentRuntime, admin_key: str | None) -> bool:
    if admin_key is None:
        return True
    ok, message = _validate_admin_key(admin_key)
    if not ok:
        console.print(message)
        return False
    runtime.set_admin_mode(True)
    console.print("Admin debug mode enabled.")
    return True


def _handle_hidden_admin_command(runtime: AgentRuntime, line: str) -> bool:
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


def run_single(runtime: AgentRuntime, instruction: str) -> int:
    out = runtime.run_turn(instruction)
    render_agent_reply(out["final_text"])
    if runtime.admin_mode:
        render_tool_traces(out["tool_traces"])
    return 0


def chat_loop(runtime: AgentRuntime) -> int:
    console.print(
        "Type questions directly. Commands: /networks /use <case_name> /scenarios /undo /plot <path> [tool] [metric] [chart] /plotnet <path> /export <summary|results> <path> /reset /exit"
    )
    _print_startup_network_preview(runtime.executor)

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
            _run_networks_command(runtime.executor, query=None, max_results=settings.startup_network_preview_count, output_format="table")
            continue
        if line.lower() == "/scenarios":
            _run_scenarios_command(runtime.executor, output_format="table")
            continue
        if line.lower() == "/undo":
            _run_undo_command(runtime.executor)
            continue
        if line.lower().startswith("/use "):
            case_name = line[5:].strip()
            if not case_name:
                console.print("Usage: /use <case_name>")
                continue
            _run_use_command(runtime.executor, case_name)
            continue
        if line.lower() == "/tools":
            _run_tools_command("table")
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
            _run_export_command(runtime.executor.state, export_type=export_type, path=export_path)
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
                _run_plot_network_command(
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
            _run_plot_command(
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    state = SessionState()
    executor = ToolExecutor(state)

    if args.cmd == "reset":
        state.reset()
        console.print("Session reset")
        return 0
    if args.cmd == "undo":
        return _run_undo_command(executor)
    if args.cmd == "networks":
        return _run_networks_command(executor, query=args.query, max_results=args.max_results, output_format=args.format)
    if args.cmd == "use":
        return _run_use_command(executor, case_name=args.case_name)
    if args.cmd == "tools":
        return _run_tools_command(output_format=args.format)
    if args.cmd == "doctor":
        return _run_doctor_command(executor, case_name=args.case_name, output_format=args.format)
    if args.cmd == "scenarios":
        return _run_scenarios_command(executor, output_format=args.format)
    if args.cmd == "export":
        return _run_export_command(state, export_type=args.export_type, path=args.path)
    if args.cmd == "plot":
        return _run_plot_command(
            executor,
            path=args.path,
            source_tool=args.source_tool,
            metric=args.metric,
            chart=args.chart,
            top_n=args.top_n,
        )
    if args.cmd == "plot-network":
        return _run_plot_network_command(
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
            return _run_config_init_command(args)
        console.print("Unknown config command.")
        return 1

    require_api_key()
    from app.agent.loop import AgentRuntime

    runtime = AgentRuntime(executor=executor)
    if not _apply_admin_key(runtime, getattr(args, "admin_key", None)):
        return 1

    if args.cmd == "run":
        return run_single(runtime, args.instruction)
    if args.cmd == "chat":
        return chat_loop(runtime)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
