"""MCP server exposing the Olist data warehouse (marts schema) to LLM agents."""

from __future__ import annotations

from mcp.server import MCPServer
from pydantic import BaseModel

import db

mcp = MCPServer(
    name="olist-dwh",
    instructions=(
        "Tools for the Olist e-commerce data warehouse (Postgres, star schema in `marts`). "
        "Start with list_tables to see what data exists."
    ),
)


class TableInfo(BaseModel):
    table_name: str
    description: str | None


@mcp.tool()
def list_tables() -> list[TableInfo]:
    """List tables in the analytics warehouse with their descriptions.

    Call this first to find which fact and dimension tables can answer the question.
    """
    return [TableInfo(**row) for row in db.fetch_tables()]


if __name__ == "__main__":
    mcp.run()  # stdio transport: the client starts this process and talks over stdin/stdout
