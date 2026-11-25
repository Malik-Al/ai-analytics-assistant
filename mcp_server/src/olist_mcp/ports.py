"""Ports: what the core needs from the outside world. Adapters implement these protocols."""

from __future__ import annotations

from typing import Protocol

from olist_mcp.domain.models import ColumnInfo, DocChunk, TableInfo


class Catalog(Protocol):
    """Metadata of the tables the agent may query."""

    def list_tables(self) -> list[TableInfo]: ...

    def list_columns(self, table_name: str) -> list[ColumnInfo]: ...


class QueryRunner(Protocol):
    """Executes an already validated read-only SELECT."""

    def run(self, sql: str, max_rows: int, timeout_ms: int) -> tuple[list[str], list[tuple]]:
        """Return (column names, at most max_rows + 1 rows). Raises QueryExecutionError."""
        ...


class KnowledgeStore(Protocol):
    """Vector search over the embedded knowledge base."""

    def search(self, query_vector: list[float], model: str, top_k: int) -> list[DocChunk]: ...


class Embedder(Protocol):
    """Turns texts into vectors. Raises EmbeddingError."""

    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
