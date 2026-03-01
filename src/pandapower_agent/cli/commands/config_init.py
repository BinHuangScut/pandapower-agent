from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Any

from pandapower_agent.agent.render import console
from pandapower_agent.config import _normalize_api_key, _normalize_base_url, settings


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


def run_config_init_command(args: argparse.Namespace) -> int:
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
