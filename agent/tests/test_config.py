import pytest
from pydantic import ValidationError

from olist_agent.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("MCP_SERVER_DIR", raising=False)
    settings = Settings()
    assert settings.agent_model == "gpt-4o-mini"
    assert settings.mcp_server_dir.name == "mcp_server"
    assert (settings.mcp_server_dir / "pyproject.toml").exists()


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("MCP_SERVER_DIR", str(tmp_path))
    settings = Settings()
    assert settings.agent_model == "gpt-4.1-mini"
    assert settings.mcp_server_dir == tmp_path


def test_max_steps_must_be_positive(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_STEPS", "0")
    with pytest.raises(ValidationError):
        Settings()
