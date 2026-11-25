"""MCP server exposing the Olist data warehouse (marts schema) to LLM agents.

Tools are thin: they call services and translate domain errors into MCP ToolError.
main() is the composition root: the only place where real adapters are created.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from olist_mcp.adapters.embeddings import build_embedder
from olist_mcp.adapters.postgres import (
    PostgresCatalog,
    PostgresKnowledgeStore,
    PostgresQueryRunner,
    create_reader_pool,
)
from olist_mcp.config import get_settings
from olist_mcp.domain.errors import EmbeddingError, QueryExecutionError, UnknownTableError
from olist_mcp.domain.models import DocChunk, QueryResult, TableDetails, TableInfo
from olist_mcp.domain.sql_guard import UnsafeSqlError
from olist_mcp.services import KnowledgeService, WarehouseService


def create_server(warehouse: WarehouseService, knowledge: KnowledgeService) -> MCPServer:
    """Build the MCP server around ready-made services (real ones in main, fakes in tests)."""
    server = MCPServer(
        name="olist-dwh",
        instructions=(
            "Tools for the Olist e-commerce data warehouse (Postgres, star schema in `marts`). "
            "Start with list_tables to see what data exists."
        ),
    )

    @server.tool()
    def list_tables() -> list[TableInfo]:
        """List tables in the analytics warehouse with their descriptions.

        Call this first to find which fact and dimension tables can answer the question.
        """
        return warehouse.list_tables()

    @server.tool()
    def describe_table(table_name: str) -> TableDetails:
        """Describe one warehouse table: its columns, data types and what each column means.

        Call this before writing SQL against a table. Column descriptions explain how to use
        the column (e.g. which one is revenue, which one is the customer key).
        """
        try:
            return warehouse.describe_table(table_name)
        except UnknownTableError as e:
            raise ToolError(str(e)) from e

    @server.tool()
    def run_readonly_sql(sql: str) -> QueryResult:
        """Run one read-only SELECT (Postgres dialect) against the marts tables.

        Use only tables from list_tables and columns from describe_table.
        Aggregate in SQL (GROUP BY, SUM, COUNT) instead of fetching raw rows:
        at most 200 rows are returned and queries are stopped after 5 seconds.
        """
        try:
            return warehouse.run_sql(sql)
        except UnsafeSqlError as e:
            raise ToolError(f"Query rejected: {e}") from e
        except QueryExecutionError as e:
            # the Postgres message (syntax error, unknown column, timeout) lets the LLM fix its SQL
            raise ToolError(f"Database error: {e}") from e

    @server.tool()
    def search_docs(
        query: str,
        top_k: Annotated[int, Field(ge=1, le=10)] = 3,
    ) -> list[DocChunk]:
        """Search the business knowledge base: metric definitions and dataset caveats.

        Use it to learn how a metric is defined (revenue, AOV, late delivery, review score)
        or which data quirks to respect (time coverage, order statuses) before writing SQL.
        """
        try:
            return knowledge.search(query, top_k)
        except EmbeddingError as e:
            raise ToolError(f"Embedding provider error: {e}") from e

    return server


def main() -> None:
    """Composition root: settings -> pool -> adapters -> services -> server."""
    settings = get_settings()
    pool = create_reader_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.mcp_reader_user,
        password=settings.mcp_reader_password.get_secret_value(),
    )
    try:
        warehouse = WarehouseService(
            PostgresCatalog(pool, settings.mcp_schema),
            PostgresQueryRunner(pool, settings.mcp_schema),
            max_rows=settings.mcp_max_rows,
            timeout_ms=settings.mcp_query_timeout_ms,
        )
        knowledge = KnowledgeService(PostgresKnowledgeStore(pool), build_embedder(settings))
        # stdio transport: the client starts this process and talks over stdin/stdout
        create_server(warehouse, knowledge).run()
    finally:
        pool.close()


if __name__ == "__main__":
    main()
