"""Connect to the olist-mcp server over stdio and expose its tools as LangChain tools."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StdioConnection
from langchain_mcp_adapters.tools import load_mcp_tools

from olist_agent.config import Settings, get_settings

SERVER_NAME = "olist-dwh"


def build_connection(settings: Settings, environ: dict[str, str] | None = None) -> StdioConnection:
    """Describe how to start the MCP server as a child process.

    The child inherits our env (POSTGRES_*, MCP_READER_*, OPENAI_API_KEY).
    VIRTUAL_ENV points to the agent's .venv; drop it so `uv run` uses the server's own .venv.
    """
    env = dict(os.environ if environ is None else environ)
    env.pop("VIRTUAL_ENV", None)
    return {
        "transport": "stdio",
        "command": "uv",
        "args": ["run", "--directory", str(settings.mcp_server_dir), "olist-mcp"],
        "env": env,
    }


@asynccontextmanager
async def open_mcp_tools(settings: Settings) -> AsyncIterator[list[BaseTool]]:
    """Start the server once and keep one MCP session open for every tool call.

    Without an explicit session the adapter starts a new server process per tool call.
    """
    client = MultiServerMCPClient({SERVER_NAME: build_connection(settings)})
    async with client.session(SERVER_NAME) as session:
        yield await load_mcp_tools(session)


async def _print_tools() -> None:
    async with open_mcp_tools(get_settings()) as tools:
        for tool in tools:
            print(f"{tool.name}: {tool.description.splitlines()[0]}")


if __name__ == "__main__":
    # smoke check: uv run --env-file ../.env python -m olist_agent.mcp_tools
    asyncio.run(_print_tools())
