"""Shared pydantic models for the olist-mcp package."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class TableInfo(BaseModel):
    table_name: str
    description: str | None


class ColumnInfo(BaseModel):
    column_name: str
    data_type: str
    description: str | None


class TableDetails(BaseModel):
    table_name: str
    description: str | None
    columns: list[ColumnInfo]


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
    truncated: bool  # True if the query returned more than max_rows rows


class DocChunk(BaseModel):
    source: str
    title: str
    content: str
    score: float  # cosine similarity, higher is more relevant
