from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


PLACEHOLDER_API_KEYS = {"your_api_key", "your_google_api_key", "replace_me"}


def _normalize_api_key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if cleaned.lower() in PLACEHOLDER_API_KEYS:
        return ""
    return cleaned


def _normalize_base_url(value: str, *, env_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""

    candidate = cleaned
    if "://" not in candidate:
        if candidate.startswith("/"):
            raise RuntimeError(
                f"{env_name} must be a full URL (include http:// or https://). Got: {cleaned!r}"
            )
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(
            f"{env_name} must be a full URL (include http:// or https://). Got: {cleaned!r}"
        )
    return candidate


def _dotenv_candidates() -> list[Path]:
    candidates: list[Path] = []
    for path in (
        Path.cwd() / ".env",
        Path.cwd() / ".env.example",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[2] / ".env.example",
    ):
        if path.exists() and path not in candidates:
            candidates.append(path)
    return candidates


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].lstrip()
    if "=" not in text:
        return None

    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not key:
        return None

    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    elif " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return key, value


def _load_dotenv() -> None:
    for env_path in _dotenv_candidates():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            parsed = _parse_dotenv_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if value == "":
                continue
            os.environ.setdefault(key, value)


_load_dotenv()


@dataclass(slots=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_model: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
    google_base_url: str = os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    default_network: str = os.getenv("DEFAULT_NETWORK", "case14")
    max_tool_calls_per_turn: int = int(os.getenv("MAX_TOOL_CALLS_PER_TURN", "6"))
    language_auto: bool = os.getenv("LANGUAGE_AUTO", "true").lower() in {"1", "true", "yes", "y"}
    startup_show_networks: bool = os.getenv("STARTUP_SHOW_NETWORKS", "true").lower() in {"1", "true", "yes", "y"}
    startup_network_preview_count: int = int(os.getenv("STARTUP_NETWORK_PREVIEW_COUNT", "8"))

    @property
    def provider(self) -> str:
        normalized = self.llm_provider.strip().lower()
        if normalized in {"google", "gemini"}:
            return "google"
        return "openai"

    @property
    def active_model(self) -> str:
        if self.provider == "google":
            return self.google_model
        return self.openai_model

    @property
    def active_api_key(self) -> str:
        if self.provider == "google":
            google_key = _normalize_api_key(self.google_api_key)
            if google_key:
                return google_key
            return _normalize_api_key(self.openai_api_key)
        return _normalize_api_key(self.openai_api_key)

    @property
    def active_api_key_env_name(self) -> str:
        if self.provider == "google":
            if _normalize_api_key(self.google_api_key):
                return "GOOGLE_API_KEY"
            return "OPENAI_API_KEY"
        return "OPENAI_API_KEY"

    @property
    def active_base_url(self) -> str:
        if self.provider == "google":
            raw_google_base_url = self.google_base_url.strip() or "https://generativelanguage.googleapis.com/v1beta/openai/"
            return _normalize_base_url(raw_google_base_url, env_name="GOOGLE_BASE_URL")
        raw_openai_base_url = self.openai_base_url.strip() or "https://api.openai.com/v1"
        return _normalize_base_url(raw_openai_base_url, env_name="OPENAI_BASE_URL")

    @property
    def use_chat_completions(self) -> bool:
        return self.provider == "google"


settings = Settings()
