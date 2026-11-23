"""MCP server exposing the Olist data warehouse (marts schema) to LLM agents."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from functools import cache
from typing import Annotated

import openai
import psycopg
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

import db
from embeddings import Embedder, get_embedder
from sql_guard import UnsafeSqlError, validate_sql

MAX_ROWS = 200
TIMEOUT_MS = 5000

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


# JSON scalar types only: untyped values ({} in JSON Schema) are rejected by strict LLM providers
Cell = str | int | float | bool | None


def to_cell(value: object) -> Cell:
    """Convert a Postgres value to a JSON-friendly scalar."""
    if value is None or isinstance(value, str | bool | int | float):
        return value
    if isinstance(value, Decimal):
        return float(value)  # numeric -> number; fine for analytics answers
    if isinstance(value, dt.date | dt.datetime | dt.time):
        return value.isoformat()
    return str(value)


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Cell]]
    row_count: int
    truncated: bool  # True if the query returned more than MAX_ROWS rows


@mcp.tool()
def run_readonly_sql(sql: str) -> QueryResult:
    """Run one read-only SELECT (Postgres dialect) against the marts tables.

    Use only tables from list_tables and columns from describe_table.
    Aggregate in SQL (GROUP BY, SUM, COUNT) instead of fetching raw rows:
    at most 200 rows are returned and queries are stopped after 5 seconds.
    """
    allowed_tables = {row["table_name"] for row in db.fetch_tables()}
    try:
        safe_sql = validate_sql(sql, allowed_tables)
        columns, rows = db.run_query(safe_sql, MAX_ROWS, TIMEOUT_MS)
    except UnsafeSqlError as e:
        raise ToolError(f"Query rejected: {e}") from e
    except psycopg.Error as e:
        # the Postgres message (syntax error, unknown column, timeout) lets the LLM fix its SQL
        raise ToolError(f"Database error: {e}") from e

    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
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


class DocChunk(BaseModel):
    source: str
    title: str
    content: str
    score: float  # cosine similarity, higher is more relevant


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
    rows = db.search_chunks(vector, embedder.model, top_k)
    return [DocChunk(**row) for row in rows]


if __name__ == "__main__":
    mcp.run()  # stdio transport: the client starts this process and talks over stdin/stdout
