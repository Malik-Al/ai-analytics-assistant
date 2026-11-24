"""MCP server exposing the Olist data warehouse (marts schema) to LLM agents."""

from __future__ import annotations

from functools import cache
from typing import Annotated

import openai
import psycopg
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from olist_mcp.adapters import postgres
from olist_mcp.adapters.embeddings import Embedder, get_embedder
from olist_mcp.config import get_settings
from olist_mcp.domain.models import (
    ColumnInfo,
    DocChunk,
    QueryResult,
    TableDetails,
    TableInfo,
    to_cell,
)
from olist_mcp.domain.sql_guard import UnsafeSqlError, validate_sql

mcp = MCPServer(
    name="olist-dwh",
    instructions=(
        "Tools for the Olist e-commerce data warehouse (Postgres, star schema in `marts`). "
        "Start with list_tables to see what data exists."
    ),
)


@mcp.tool()
def list_tables() -> list[TableInfo]:
    """List tables in the analytics warehouse with their descriptions.

    Call this first to find which fact and dimension tables can answer the question.
    """
    return [TableInfo(**row) for row in postgres.fetch_tables()]


@mcp.tool()
def describe_table(table_name: str) -> TableDetails:
    """Describe one warehouse table: its columns, data types and what each column means.

    Call this before writing SQL against a table. Column descriptions explain how to use
    the column (e.g. which one is revenue, which one is the customer key).
    """
    tables = {row["table_name"]: row["description"] for row in postgres.fetch_tables()}
    if table_name not in tables:
        raise ToolError(f"Unknown table {table_name!r}. Available tables: {', '.join(tables)}")

    return TableDetails(
        table_name=table_name,
        description=tables[table_name],
        columns=[ColumnInfo(**row) for row in postgres.fetch_columns(table_name)],
    )


@mcp.tool()
def run_readonly_sql(sql: str) -> QueryResult:
    """Run one read-only SELECT (Postgres dialect) against the marts tables.

    Use only tables from list_tables and columns from describe_table.
    Aggregate in SQL (GROUP BY, SUM, COUNT) instead of fetching raw rows:
    at most 200 rows are returned and queries are stopped after 5 seconds.
    """
    settings = get_settings()
    max_rows = settings.mcp_max_rows
    timeout_ms = settings.mcp_query_timeout_ms
    allowed_tables = {row["table_name"] for row in postgres.fetch_tables()}
    try:
        safe_sql = validate_sql(sql, allowed_tables)
        columns, rows = postgres.run_query(safe_sql, max_rows, timeout_ms)
    except UnsafeSqlError as e:
        raise ToolError(f"Query rejected: {e}") from e
    except psycopg.Error as e:
        # the Postgres message (syntax error, unknown column, timeout) lets the LLM fix its SQL
        raise ToolError(f"Database error: {e}") from e

    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return QueryResult(
        columns=columns,
        rows=[[to_cell(value) for value in row] for row in rows],
        row_count=len(rows),
        truncated=truncated,
    )


@cache
def query_embedder() -> Embedder:
    """Created on first use and reused: one API client per server process."""
    return get_embedder()


@mcp.tool()
def search_docs(
    query: str,
    top_k: Annotated[int, Field(ge=1, le=10)] = 3,
) -> list[DocChunk]:
    """Search the business knowledge base: metric definitions and dataset caveats.

    Use it to learn how a metric is defined (revenue, AOV, late delivery, review score)
    or which data quirks to respect (time coverage, order statuses) before writing SQL.
    """
    embedder = query_embedder()
    try:
        [vector] = embedder.embed([query])
    except openai.OpenAIError as e:
        raise ToolError(f"Embedding provider error: {e}") from e
    rows = postgres.search_chunks(vector, embedder.model, top_k)
    return [DocChunk(**row) for row in rows]


def main() -> None:
    mcp.run()  # stdio transport: the client starts this process and talks over stdin/stdout


if __name__ == "__main__":
    main()
