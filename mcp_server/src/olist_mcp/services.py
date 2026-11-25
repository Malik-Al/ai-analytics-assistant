"""Use cases of the MCP server. Depend only on domain and ports, never on concrete adapters."""

from __future__ import annotations

from olist_mcp.domain.errors import UnknownTableError
from olist_mcp.domain.models import DocChunk, QueryResult, TableDetails, TableInfo, to_cell
from olist_mcp.domain.sql_guard import validate_sql
from olist_mcp.ports import Catalog, Embedder, KnowledgeStore, QueryRunner


class WarehouseService:
    """Read-only access to the analytics warehouse: metadata and validated SQL."""

    def __init__(
        self, catalog: Catalog, runner: QueryRunner, *, max_rows: int, timeout_ms: int
    ) -> None:
        self._catalog = catalog
        self._runner = runner
        self._max_rows = max_rows
        self._timeout_ms = timeout_ms

    def list_tables(self) -> list[TableInfo]:
        return self._catalog.list_tables()

    def describe_table(self, table_name: str) -> TableDetails:
        tables = {t.table_name: t for t in self._catalog.list_tables()}
        if table_name not in tables:
            raise UnknownTableError(table_name, available=list(tables))
        return TableDetails(
            table_name=table_name,
            description=tables[table_name].description,
            columns=self._catalog.list_columns(table_name),
        )

    def run_sql(self, sql: str) -> QueryResult:
        """Validate and run one SELECT. Raises UnsafeSqlError or QueryExecutionError."""
        allowed_tables = {t.table_name for t in self._catalog.list_tables()}
        safe_sql = validate_sql(sql, allowed_tables)
        columns, rows = self._runner.run(safe_sql, self._max_rows, self._timeout_ms)

        truncated = len(rows) > self._max_rows
        rows = rows[: self._max_rows]
        return QueryResult(
            columns=columns,
            rows=[[to_cell(value) for value in row] for row in rows],
            row_count=len(rows),
            truncated=truncated,
        )


class KnowledgeService:
    """Semantic search over the business knowledge base (metric definitions, dataset caveats)."""

    def __init__(self, store: KnowledgeStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def search(self, query: str, top_k: int) -> list[DocChunk]:
        """Embed the question and return the closest chunks. Raises EmbeddingError."""
        [vector] = self._embedder.embed([query])
        # only vectors of the same model are comparable, so the store filters by model
        return self._store.search(vector, self._embedder.model, top_k)
