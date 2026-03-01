from __future__ import annotations

import pytest

from app.main import require_api_key, settings


def test_require_api_key_accepts_non_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    require_api_key()


def test_require_api_key_rejects_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "your_api_key")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        require_api_key()


def test_require_api_key_accepts_google_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "google")
    monkeypatch.setattr(settings, "google_api_key", "google-key")
    monkeypatch.setattr(settings, "openai_api_key", "")
    require_api_key()


def test_require_api_key_rejects_google_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "google")
    monkeypatch.setattr(settings, "google_api_key", "your_google_api_key")
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY is required"):
        require_api_key()
