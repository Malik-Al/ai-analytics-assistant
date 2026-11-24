import pytest

from olist_mcp.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """Clear the settings cache and provide required env vars for every test."""
    get_settings.cache_clear()
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("MCP_READER_USER", "test_reader")
    monkeypatch.setenv("MCP_READER_PASSWORD", "test_password")
    yield
    get_settings.cache_clear()
