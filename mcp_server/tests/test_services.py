import datetime as dt
from decimal import Decimal

import pytest

from olist_mcp.domain.errors import EmbeddingError, QueryExecutionError, UnknownTableError
from olist_mcp.domain.models import ColumnInfo, DocChunk, TableInfo
from olist_mcp.domain.sql_guard import UnsafeSqlError
from olist_mcp.services import KnowledgeService, WarehouseService
from tests.fakes import FakeCatalog, FakeEmbedder, FakeKnowledgeStore, FakeQueryRunner

TABLES = [
    TableInfo(table_name="dim_customers", description="One row per real customer."),
    TableInfo(table_name="fct_orders", description=None),
]
COLUMNS = [ColumnInfo(column_name="order_id", data_type="text", description="Order key.")]


def make_service(runner=None, max_rows=3):
    return WarehouseService(
        FakeCatalog(TABLES, COLUMNS),
        runner or FakeQueryRunner(),
        max_rows=max_rows,
        timeout_ms=1000,
    )


def test_describe_table_returns_columns():
    details = make_service().describe_table("fct_orders")
    assert details.description is None
    assert details.columns == COLUMNS


def test_describe_table_unknown_table():
    with pytest.raises(UnknownTableError) as exc:
        make_service().describe_table("orders")
    assert exc.value.available == ["dim_customers", "fct_orders"]


def test_run_sql_truncates_to_max_rows():
    result = make_service(max_rows=3).run_sql("select 1 as n from fct_orders")
    assert result.rows == [[0], [1], [2]]
    assert result.row_count == 3
    assert result.truncated is True


def test_run_sql_rejects_unsafe_sql_before_reaching_the_database():
    runner = FakeQueryRunner()
    with pytest.raises(UnsafeSqlError):
        make_service(runner).run_sql("delete from fct_orders")
    assert runner.executed == []


def test_run_sql_propagates_database_errors():
    runner = FakeQueryRunner(error='column "nope" does not exist')
    with pytest.raises(QueryExecutionError, match="nope"):
        make_service(runner).run_sql("select nope from fct_orders")


def test_run_sql_converts_values_to_json_scalars():
    class OneRow(FakeQueryRunner):
        def run(self, sql, max_rows, timeout_ms):
            return ["revenue", "month"], [(Decimal("24.99"), dt.date(2017, 1, 1))]

    result = make_service(OneRow()).run_sql("select 1 from fct_orders")
    assert result.rows == [[24.99, "2017-01-01"]]
    assert result.truncated is False


CHUNKS = [
    DocChunk(source="metrics.md", title="Revenue", content="Revenue = sum(price).", score=0.9),
    DocChunk(source="metrics.md", title="AOV", content="AOV = revenue / orders.", score=0.5),
]


def test_search_embeds_the_question_and_filters_by_model():
    store, embedder = FakeKnowledgeStore(CHUNKS), FakeEmbedder()
    result = KnowledgeService(store, embedder).search("what is revenue", top_k=1)
    assert result == CHUNKS[:1]
    assert embedder.embedded_texts == ["what is revenue"]
    assert store.searched_models == ["fake-model"]


def test_search_propagates_embedding_errors():
    service = KnowledgeService(FakeKnowledgeStore(CHUNKS), FakeEmbedder(error="quota exceeded"))
    with pytest.raises(EmbeddingError, match="quota"):
        service.search("revenue", top_k=3)
