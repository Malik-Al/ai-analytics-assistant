"""Postgres access for the MCP server. Read-only by design."""

from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row, tuple_row

SCHEMA = os.environ.get("MCP_SCHEMA", "marts")


def connect() -> psycopg.Connection:
    conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5433"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["MCP_READER_USER"],
        password=os.environ["MCP_READER_PASSWORD"],
        row_factory=dict_row,  # rows as dicts: {"table_name": ..., "description": ...}
    )
    # every transaction on this connection is READ ONLY: INSERT/UPDATE/DDL fail in Postgres
    conn.read_only = True
    return conn


LIST_TABLES_SQL = """
SELECT c.relname AS table_name,
       obj_description(c.oid, 'pg_class') AS description
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s
  AND c.relkind IN ('r', 'v', 'm')  -- table, view, materialized view
  AND has_table_privilege(c.oid, 'SELECT')  -- only what the connected role can read
ORDER BY c.relname
"""


def fetch_tables(schema: str = SCHEMA) -> list[dict[str, Any]]:
    with connect() as conn:
        return conn.execute(LIST_TABLES_SQL, (schema,)).fetchall()


LIST_COLUMNS_SQL = """
SELECT a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       col_description(c.oid, a.attnum) AS description
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = %s
  AND c.relname = %s
  AND a.attnum > 0          -- skip system columns (ctid, xmin, ...)
  AND NOT a.attisdropped    -- skip dropped columns
ORDER BY a.attnum
"""


def fetch_columns(table_name: str, schema: str = SCHEMA) -> list[dict[str, Any]]:
    with connect() as conn:
        return conn.execute(LIST_COLUMNS_SQL, (schema, table_name)).fetchall()


def run_query(sql: str, max_rows: int, timeout_ms: int) -> tuple[list[str], list[tuple]]:
    """Run an already validated SELECT. Fetches at most max_rows + 1 rows."""
    wrapped = f"SELECT * FROM ({sql}) AS q LIMIT {max_rows + 1}"
    with connect() as conn, conn.cursor(row_factory=tuple_row) as cur:
        # SET LOCAL lives until the end of this transaction only
        cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
        cur.execute("SET LOCAL search_path = marts")
        cur.execute(wrapped)
        columns = [col.name for col in cur.description]
        return columns, cur.fetchall()


SEARCH_CHUNKS_SQL = """
SELECT source,
       title,
       content,
       1 - (embedding <=> %(query)s::vector) AS score  -- cosine similarity, 1 = identical
FROM knowledge.chunks
WHERE embedding_model = %(model)s  -- vectors of different models are not comparable
ORDER BY embedding <=> %(query)s::vector
LIMIT %(top_k)s
"""


def search_chunks(query_vector: list[float], model: str, top_k: int) -> list[dict[str, Any]]:
    with connect() as conn:
        return conn.execute(
            SEARCH_CHUNKS_SQL, {"query": str(query_vector), "model": model, "top_k": top_k}
        ).fetchall()
