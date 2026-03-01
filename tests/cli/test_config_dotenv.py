from __future__ import annotations

import importlib

import pandapower_agent.config as config_module
import pytest


def test_parse_dotenv_line() -> None:
    assert config_module._parse_dotenv_line("A=1") == ("A", "1")
    assert config_module._parse_dotenv_line(" export B = 2 ") == ("B", "2")
    assert config_module._parse_dotenv_line('C="hello world"') == ("C", "hello world")
    assert config_module._parse_dotenv_line("D=abc # comment") == ("D", "abc")
    assert config_module._parse_dotenv_line("# comment") is None
    assert config_module._parse_dotenv_line("INVALID") is None


def test_load_settings_from_cwd_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=from_file",
                "OPENAI_MODEL=test-model",
                "DEFAULT_NETWORK=case9",
                "MAX_TOOL_CALLS_PER_TURN=12",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("OPENAI_API_KEY", raising=False)
        m.delenv("OPENAI_MODEL", raising=False)
        m.delenv("DEFAULT_NETWORK", raising=False)
        m.delenv("MAX_TOOL_CALLS_PER_TURN", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.openai_api_key == "from_file"
        assert config_module.settings.openai_model == "test-model"
        assert config_module.settings.default_network == "case9"
        assert config_module.settings.max_tool_calls_per_turn == 12

    importlib.reload(config_module)


def test_shell_env_overrides_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_MODEL=from_file\n", encoding="utf-8")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.setenv("OPENAI_MODEL", "from_shell")

        importlib.reload(config_module)
        assert config_module.settings.openai_model == "from_shell"

    importlib.reload(config_module)


def test_load_settings_from_dotenv_example_when_env_missing(tmp_path, monkeypatch) -> None:
    env_example_file = tmp_path / ".env.example"
    env_example_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=from_example",
                "OPENAI_MODEL=example-model",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("OPENAI_API_KEY", raising=False)
        m.delenv("OPENAI_MODEL", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.openai_api_key == "from_example"
        assert config_module.settings.openai_model == "example-model"

    importlib.reload(config_module)


def test_dotenv_has_priority_over_dotenv_example(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_example_file = tmp_path / ".env.example"
    env_file.write_text("OPENAI_MODEL=from_env\n", encoding="utf-8")
    env_example_file.write_text("OPENAI_MODEL=from_example\n", encoding="utf-8")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("OPENAI_MODEL", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.openai_model == "from_env"

    importlib.reload(config_module)


def test_google_provider_settings_and_active_values(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=google",
                "GOOGLE_API_KEY=google_key",
                "GOOGLE_MODEL=gemini-2.5-flash",
                "GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("LLM_PROVIDER", raising=False)
        m.delenv("GOOGLE_API_KEY", raising=False)
        m.delenv("GOOGLE_MODEL", raising=False)
        m.delenv("GOOGLE_BASE_URL", raising=False)
        m.delenv("OPENAI_API_KEY", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.provider == "google"
        assert config_module.settings.active_api_key == "google_key"
        assert config_module.settings.active_api_key_env_name == "GOOGLE_API_KEY"
        assert config_module.settings.active_model == "gemini-2.5-flash"
        assert config_module.settings.active_base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
        assert config_module.settings.use_chat_completions is True

    importlib.reload(config_module)


def test_google_provider_allows_openai_key_fallback(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=google",
                "OPENAI_API_KEY=fallback_openai_key",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("LLM_PROVIDER", raising=False)
        m.delenv("GOOGLE_API_KEY", raising=False)
        m.delenv("OPENAI_API_KEY", raising=False)
        m.setenv("GOOGLE_API_KEY", "")

        importlib.reload(config_module)
        assert config_module.settings.provider == "google"
        assert config_module.settings.active_api_key == "fallback_openai_key"
        assert config_module.settings.active_api_key_env_name == "OPENAI_API_KEY"

    importlib.reload(config_module)


def test_openai_base_url_without_scheme_is_normalized_to_https(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=openai",
                "OPENAI_BASE_URL=api.openai.com/v1",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("LLM_PROVIDER", raising=False)
        m.delenv("OPENAI_BASE_URL", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.provider == "openai"
        assert config_module.settings.active_base_url == "https://api.openai.com/v1"

    importlib.reload(config_module)


def test_openai_base_url_invalid_value_raises_clear_error(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=openai",
                "OPENAI_BASE_URL=/v1",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("LLM_PROVIDER", raising=False)
        m.delenv("OPENAI_BASE_URL", raising=False)

        importlib.reload(config_module)
        with pytest.raises(RuntimeError, match="OPENAI_BASE_URL must be a full URL"):
            _ = config_module.settings.active_base_url

    importlib.reload(config_module)


def test_openai_base_url_defaults_to_official_endpoint_when_unset(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_PROVIDER=openai\n", encoding="utf-8")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("LLM_PROVIDER", raising=False)
        m.delenv("OPENAI_BASE_URL", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.active_base_url == "https://api.openai.com/v1"

    importlib.reload(config_module)


def test_dotenv_empty_openai_base_url_does_not_set_process_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=openai",
                "OPENAI_BASE_URL=",
            ]
        ),
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.delenv("LLM_PROVIDER", raising=False)
        m.delenv("OPENAI_BASE_URL", raising=False)

        importlib.reload(config_module)
        assert config_module.settings.active_base_url == "https://api.openai.com/v1"
        assert "OPENAI_BASE_URL" not in config_module.os.environ

    importlib.reload(config_module)
