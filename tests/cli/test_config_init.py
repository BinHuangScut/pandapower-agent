from __future__ import annotations

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
    monkeypatch.setattr("pandapower_agent.cli.commands.config_init.console.print", lambda msg: None)

    rc = main(["config", "init", "--non-interactive", "--provider", "openai", "--skip-check"])

    assert rc == 1
    assert not (tmp_path / ".env").exists()


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
