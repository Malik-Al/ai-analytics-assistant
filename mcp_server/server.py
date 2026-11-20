"""MCP server exposing the Olist data warehouse (marts schema) to LLM agents."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
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


class ColumnInfo(BaseModel):
    column_name: str
    data_type: str
    description: str | None


class TableDetails(BaseModel):
    table_name: str
    description: str | None
    columns: list[ColumnInfo]


@mcp.tool()
def describe_table(table_name: str) -> TableDetails:
    """Describe one warehouse table: its columns, data types and what each column means.

    Call this before writing SQL against a table. Column descriptions explain how to use
    the column (e.g. which one is revenue, which one is the customer key).
    """
    tables = {row["table_name"]: row["description"] for row in db.fetch_tables()}
    if table_name not in tables:
        raise ToolError(f"Unknown table {table_name!r}. Available tables: {', '.join(tables)}")

    return TableDetails(
        table_name=table_name,
        description=tables[table_name],
        columns=[ColumnInfo(**row) for row in db.fetch_columns(table_name)],
    )


if __name__ == "__main__":
    mcp.run()  # stdio transport: the client starts this process and talks over stdin/stdout
