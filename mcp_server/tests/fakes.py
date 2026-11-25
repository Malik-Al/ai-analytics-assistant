"""In-memory implementations of the ports for tests. No database, no network."""

from __future__ import annotations

from olist_mcp.domain.errors import EmbeddingError, QueryExecutionError
from olist_mcp.domain.models import ColumnInfo, DocChunk, TableInfo


class FakeCatalog:
    def __init__(self, tables: list[TableInfo], columns: list[ColumnInfo]) -> None:
        self.tables = tables
        self.columns = columns

    def list_tables(self) -> list[TableInfo]:
        return self.tables

    def list_columns(self, table_name: str) -> list[ColumnInfo]:
        return self.columns


class FakeQueryRunner:
    """Returns max_rows + 1 rows so truncation is always exercised; records the SQL it got."""

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.executed: list[str] = []

    def run(self, sql: str, max_rows: int, timeout_ms: int) -> tuple[list[str], list[tuple]]:
        self.executed.append(sql)
        if self.error:
            raise QueryExecutionError(self.error)
        return ["n"], [(i,) for i in range(max_rows + 1)]


class FakeKnowledgeStore:
    """Returns the first top_k chunks; records the model it was asked for."""

    def __init__(self, chunks: list[DocChunk]) -> None:
        self.chunks = chunks
        self.searched_models: list[str] = []

    def search(self, query_vector: list[float], model: str, top_k: int) -> list[DocChunk]:
        self.searched_models.append(model)
        return self.chunks[:top_k]


class FakeEmbedder:
    """Deterministic 3-dimensional vectors; counts how many texts it embedded."""

    model = "fake-model"
    dimensions = 3

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.embedded_texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.error:
            raise EmbeddingError(self.error)
        self.embedded_texts.extend(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]
