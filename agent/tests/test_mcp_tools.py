from pathlib import Path

from olist_agent.config import Settings
from olist_agent.mcp_tools import build_connection


def test_connection_runs_server_from_its_directory():
    settings = Settings(mcp_server_dir=Path("/repo/mcp_server"))
    conn = build_connection(settings, environ={})
    assert conn["transport"] == "stdio"
    assert conn["command"] == "uv"
    assert conn["args"] == ["run", "--directory", str(Path("/repo/mcp_server")), "olist-mcp"]


def test_connection_passes_env_without_virtual_env():
    environ = {"POSTGRES_DB": "dwh", "VIRTUAL_ENV": "/repo/agent/.venv"}
    conn = build_connection(Settings(), environ=environ)
    assert conn["env"] == {"POSTGRES_DB": "dwh"}
    assert "VIRTUAL_ENV" in environ  # the caller's dict is not mutated
