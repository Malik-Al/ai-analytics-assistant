"""Agent settings (pydantic-settings), read from environment variables."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# This file lives at agent/src/olist_agent/config.py.
# parents[3] == repo root (olist_agent/ -> src/ -> agent/ -> repo)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MCP_SERVER_DIR = _REPO_ROOT / "mcp_server"


class Settings(BaseSettings):
    # env vars are matched case-insensitively: agent_model <- AGENT_MODEL
    model_config = SettingsConfigDict(extra="ignore")

    agent_model: str = "gpt-4o-mini"
    agent_max_steps: int = Field(10, gt=0)
    mcp_server_dir: Path = _DEFAULT_MCP_SERVER_DIR


@cache
def get_settings() -> Settings:
    return Settings()
