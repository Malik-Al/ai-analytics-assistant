"""Postgres adapters for the MCP server ports. Read-only by design."""

from __future__ import annotations

import psycopg
from psycopg import sql as pg_sql
from psycopg.rows import dict_row, tuple_row
from psycopg_pool import ConnectionPool

from olist_mcp.domain.errors import QueryExecutionError
from olist_mcp.domain.models import ColumnInfo, DocChunk, TableInfo

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


# --- Adapters implementing the ports (olist_mcp.ports) ---------------------------------


def create_reader_pool(
    *, host: str, port: int, dbname: str, user: str, password: str, max_size: int = 4
) -> ConnectionPool:
    """Pool of read-only connections for the MCP server. Opens eagerly: fails fast if DB is down."""

    def configure(conn: psycopg.Connection) -> None:
        # runs once per new physical connection: every transaction on it is READ ONLY
        conn.read_only = True

    pool = ConnectionPool(
        kwargs={
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "row_factory": dict_row,
        },
        min_size=1,
        max_size=max_size,
        configure=configure,
        open=False,
    )
    pool.open(wait=True, timeout=10)
    return pool


class PostgresCatalog:
    """Catalog port: table and column metadata (with dbt descriptions) from pg_catalog."""

    def __init__(self, pool: ConnectionPool, schema: str) -> None:
        self._pool = pool
        self._schema = schema

    def list_tables(self) -> list[TableInfo]:
        with self._pool.connection() as conn:
            rows = conn.execute(LIST_TABLES_SQL, (self._schema,)).fetchall()
        return [TableInfo(**row) for row in rows]

    def list_columns(self, table_name: str) -> list[ColumnInfo]:
        with self._pool.connection() as conn:
            rows = conn.execute(LIST_COLUMNS_SQL, (self._schema, table_name)).fetchall()
        return [ColumnInfo(**row) for row in rows]


class PostgresQueryRunner:
    """QueryRunner port: runs an already validated SELECT with a timeout and a row cap."""

    def __init__(self, pool: ConnectionPool, schema: str) -> None:
        self._pool = pool
        self._schema = schema

    def run(self, sql: str, max_rows: int, timeout_ms: int) -> tuple[list[str], list[tuple]]:
        wrapped = f"SELECT * FROM ({sql}) AS q LIMIT {max_rows + 1}"
        try:
            with self._pool.connection() as conn, conn.cursor(row_factory=tuple_row) as cur:
                # SET LOCAL lives until the end of this transaction only
                cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                cur.execute(
                    pg_sql.SQL("SET LOCAL search_path = {}").format(pg_sql.Identifier(self._schema))
                )
                cur.execute(wrapped)
                columns = [col.name for col in cur.description]
                return columns, cur.fetchall()
        except psycopg.Error as e:
            # keep the Postgres message: it lets the LLM fix its SQL
            raise QueryExecutionError(str(e)) from e


class PostgresKnowledgeStore:
    """KnowledgeStore port: cosine search in knowledge.chunks (pgvector)."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def search(self, query_vector: list[float], model: str, top_k: int) -> list[DocChunk]:
        params = {"query": str(query_vector), "model": model, "top_k": top_k}
        with self._pool.connection() as conn:
            rows = conn.execute(SEARCH_CHUNKS_SQL, params).fetchall()
        return [DocChunk(**row) for row in rows]
