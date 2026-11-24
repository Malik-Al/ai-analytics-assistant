import pytest
from pydantic import ValidationError

from olist_mcp.config import Settings


def test_settings_requires_postgres_db(monkeypatch):
    monkeypatch.delenv("POSTGRES_DB")
    with pytest.raises(ValidationError):
        Settings()
