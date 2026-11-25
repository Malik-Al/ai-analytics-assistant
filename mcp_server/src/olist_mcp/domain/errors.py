"""Domain errors: raised by services and adapters, translated to protocol errors in entrypoints."""

from __future__ import annotations


class UnknownTableError(LookupError):
    """The requested table does not exist (or the role cannot read it)."""

    def __init__(self, table_name: str, available: list[str]) -> None:
        self.table_name = table_name
        self.available = available
        super().__init__(f"Unknown table {table_name!r}. Available tables: {', '.join(available)}")


class QueryExecutionError(RuntimeError):
    """The database rejected or failed a query (syntax error, unknown column, timeout)."""


class EmbeddingError(RuntimeError):
    """The embedding provider failed (network, auth, quota)."""
