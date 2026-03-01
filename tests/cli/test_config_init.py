from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from pandapower_agent.cli.main import main


@pytest.fixture(autouse=True)
def _clear_settings_keys(monkeypatch) -> None:
    monkeypatch.setattr("pandapower_agent.config.settings.openai_api_key", "")
    monkeypatch.setattr("pandapower_agent.config.settings.google_api_key", "")
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.settings.openai_api_key", "")
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.settings.google_api_key", "")


def test_config_init_openai_non_interactive_writes_env(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    checks: list[dict[str, str]] = []

    def fake_verify_llm_config(*, provider: str, api_key: str, model: str, base_url: str):
        checks.append({"provider": provider, "api_key": api_key, "model": model, "base_url": base_url})
        return True, "ok"

    monkeypatch.setattr("pandapower_agent.cli.commands.config_init._verify_llm_config", fake_verify_llm_config)
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", lambda msg: None)

    rc = main(
        [
            "config",
            "init",
            "--non-interactive",
            "--provider",
            "openai",
            "--openai-api-key",
            "sk-test-key",
            "--openai-model",
            "gpt-4.1-mini",
            "--force",
        ]
    )

    assert rc == 0
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "LLM_PROVIDER=openai" in env_text
    assert "OPENAI_API_KEY=sk-test-key" in env_text
    assert checks and checks[0]["provider"] == "openai"


def test_config_init_openai_requires_key(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    messages: list[str] = []
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", messages.append)

    rc = main(["config", "init", "--non-interactive", "--provider", "openai", "--skip-check"])

    assert rc == 1
    assert not (tmp_path / ".env").exists()
    assert any("OPENAI_API_KEY is required" in msg for msg in messages)
    assert any("empty API key" in msg for msg in messages)


def test_config_init_non_interactive_requires_force_when_env_exists(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("LLM_PROVIDER=openai\n", encoding="utf-8")
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", lambda msg: None)

    rc = main(
        [
            "config",
            "init",
            "--non-interactive",
            "--provider",
            "openai",
            "--openai-api-key",
            "sk-test-key",
            "--skip-check",
        ]
    )

    assert rc == 1


def test_config_init_skip_check_avoids_live_call(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_verify(**kwargs):
        _ = kwargs
        raise AssertionError("should not be called")

    monkeypatch.setattr("pandapower_agent.cli.commands.config_init._verify_llm_config", fail_verify)
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", lambda msg: None)

    rc = main(
        [
            "config",
            "init",
            "--non-interactive",
            "--provider",
            "google",
            "--openai-api-key",
            "sk-fallback",
            "--skip-check",
            "--force",
        ]
    )

    assert rc == 0
    env_path = Path(tmp_path) / ".env"
    assert env_path.exists()
    text = env_path.read_text(encoding="utf-8")
    assert "LLM_PROVIDER=google" in text
    assert "OPENAI_API_KEY=sk-fallback" in text


def test_verify_llm_config_uses_minimum_supported_token_budget(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class _FakeResponses:
        def create(self, **kwargs):
            calls.append(("responses", kwargs))
            return {"ok": True}

    class _FakeChatCompletions:
        def create(self, **kwargs):
            calls.append(("chat", kwargs))
            return {"ok": True}

    class _FakeOpenAIClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.responses = _FakeResponses()
            self.chat = types.SimpleNamespace(completions=_FakeChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAIClient))

    from pandapower_agent.cli.commands.config_init import _verify_llm_config

    ok_openai, _ = _verify_llm_config(
        provider="openai",
        api_key="sk-test",
        model="gpt-4.1-mini",
        base_url="https://api.openai.com/v1",
    )
    ok_google, _ = _verify_llm_config(
        provider="google",
        api_key="sk-test",
        model="gemini-2.0-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    assert ok_openai is True
    assert ok_google is True

    response_call = next(kwargs for kind, kwargs in calls if kind == "responses")
    chat_call = next(kwargs for kind, kwargs in calls if kind == "chat")
    assert response_call["max_output_tokens"] == 16
    assert chat_call["max_tokens"] == 16


def test_config_init_connectivity_failure_prints_empty_key_hint(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    messages: list[str] = []

    def fake_verify_llm_config(*, provider: str, api_key: str, model: str, base_url: str):
        _ = (provider, api_key, model, base_url)
        return False, "BadRequestError: invalid key"

    monkeypatch.setattr("pandapower_agent.cli.commands.config_init._verify_llm_config", fake_verify_llm_config)
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", messages.append)

    rc = main(
        [
            "config",
            "init",
            "--non-interactive",
            "--provider",
            "openai",
            "--openai-api-key",
            "sk-test-key",
            "--force",
        ]
    )

    assert rc == 1
    assert not (tmp_path / ".env").exists()
    assert any("Connectivity check failed" in msg for msg in messages)
    assert any("empty API key" in msg for msg in messages)


def test_config_init_interactive_openai_prompts_only_openai_key(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    prompts: list[str] = []

    def fake_prompt(prompt: str) -> str:
        prompts.append(prompt)
        return "sk-openai"

    monkeypatch.setattr("pandapower_agent.cli.commands.config_init._prompt_secret", fake_prompt)
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", lambda msg: None)

    rc = main(["config", "init", "--provider", "openai", "--skip-check", "--force"])

    assert rc == 0
    assert prompts == ["OPENAI_API_KEY (hidden; leave empty to keep current): "]
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-openai" in env_text


def test_config_init_interactive_google_prompts_only_google_key(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    prompts: list[str] = []

    def fake_prompt(prompt: str) -> str:
        prompts.append(prompt)
        return "gk-google"

    monkeypatch.setattr("pandapower_agent.cli.commands.config_init._prompt_secret", fake_prompt)
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", lambda msg: None)

    rc = main(["config", "init", "--provider", "google", "--skip-check", "--force"])

    assert rc == 0
    assert prompts == ["GOOGLE_API_KEY (hidden; leave empty to keep current): "]
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY=gk-google" in env_text
