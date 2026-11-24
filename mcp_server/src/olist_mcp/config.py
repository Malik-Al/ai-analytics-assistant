"""Centralised settings for the olist-mcp package (pydantic-settings)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# This file lives at mcp_server/src/olist_mcp/config.py.
# parents[3] == repo root (olist_mcp/ -> src/ -> mcp_server/ -> repo)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DOCS_DIR = _REPO_ROOT / "docs" / "knowledge"


class Settings(BaseSettings):
    # env vars are matched case-insensitively: postgres_host <- POSTGRES_HOST
    model_config = SettingsConfigDict(extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str  # required: fail fast at startup if missing
    # owner role is used only by the indexer (it writes); the MCP server never needs it
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    mcp_reader_user: str
    mcp_reader_password: SecretStr
    mcp_schema: str = "marts"
    mcp_max_rows: int = Field(200, gt=0)
    mcp_query_timeout_ms: int = Field(5000, gt=0)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    knowledge_docs_dir: Path = _DEFAULT_DOCS_DIR


@cache
def get_settings() -> Settings:
    return Settings()
