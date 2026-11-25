import pytest
from mcp.client import Client

from olist_mcp.domain.models import ColumnInfo, DocChunk, TableInfo
from olist_mcp.entrypoints.mcp_app import create_server
from olist_mcp.services import KnowledgeService, WarehouseService
from tests.fakes import FakeCatalog, FakeEmbedder, FakeKnowledgeStore, FakeQueryRunner

FAKE_TABLES = [
    {"table_name": "dim_customers", "description": "One row per real customer."},
    {"table_name": "fct_orders", "description": None},
]
FAKE_COLUMNS = [
    {"column_name": "order_id", "data_type": "text", "description": "Order key."},
    {"column_name": "is_late", "data_type": "boolean", "description": None},
]
FAKE_CHUNKS = [
    {"source": "metrics.md", "title": "Revenue", "content": "Revenue = sum(price).", "score": 0.9},
    {"source": "metrics.md", "title": "AOV", "content": "AOV = revenue / orders.", "score": 0.5},
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_server(max_rows=200, runner=None, embedder=None):
    """Real MCP server wired to fake adapters: tests the protocol layer, not the database."""
    catalog = FakeCatalog(
        [TableInfo(**t) for t in FAKE_TABLES], [ColumnInfo(**c) for c in FAKE_COLUMNS]
    )
    warehouse = WarehouseService(
        catalog, runner or FakeQueryRunner(), max_rows=max_rows, timeout_ms=1000
    )
    store = FakeKnowledgeStore([DocChunk(**c) for c in FAKE_CHUNKS])
    knowledge = KnowledgeService(store, embedder or FakeEmbedder())
    return create_server(warehouse, knowledge)


@pytest.mark.anyio
async def test_list_tables_is_registered():
    async with Client(make_server()) as client:
        tools = await client.list_tools()
    assert "list_tables" in [t.name for t in tools.tools]


@pytest.mark.anyio
async def test_list_tables_returns_tables():
    async with Client(make_server()) as client:
        result = await client.call_tool("list_tables", {})
    assert not result.is_error
    assert result.structured_content == {"result": FAKE_TABLES}


@pytest.mark.anyio
async def test_describe_table_returns_columns():
    async with Client(make_server()) as client:
        result = await client.call_tool("describe_table", {"table_name": "fct_orders"})
    assert not result.is_error
    assert result.structured_content == {
        "table_name": "fct_orders",
        "description": None,
        "columns": FAKE_COLUMNS,
    }


@pytest.mark.anyio
async def test_describe_table_unknown_table_is_error():
    async with Client(make_server()) as client:
        result = await client.call_tool("describe_table", {"table_name": "orders"})
    assert result.is_error
    assert "dim_customers, fct_orders" in result.content[0].text


@pytest.mark.anyio
async def test_run_readonly_sql_truncates_rows():
    async with Client(make_server(max_rows=3)) as client:
        result = await client.call_tool(
            "run_readonly_sql", {"sql": "select 1 as n from fct_orders"}
        )
    assert not result.is_error
    assert result.structured_content == {
        "columns": ["n"],
        "rows": [[0], [1], [2]],
        "row_count": 3,
        "truncated": True,
    }


@pytest.mark.anyio
async def test_run_readonly_sql_rejects_writes():
    async with Client(make_server()) as client:
        result = await client.call_tool("run_readonly_sql", {"sql": "delete from fct_orders"})
    assert result.is_error
    assert "Query rejected" in result.content[0].text


@pytest.mark.anyio
async def test_search_docs_returns_chunks():
    async with Client(make_server()) as client:
        result = await client.call_tool("search_docs", {"query": "what is revenue", "top_k": 1})
    assert not result.is_error
    assert result.structured_content == {"result": FAKE_CHUNKS[:1]}


@pytest.mark.anyio
async def test_search_docs_rejects_too_large_top_k():
    async with Client(make_server()) as client:
        result = await client.call_tool("search_docs", {"query": "revenue", "top_k": 50})
    assert result.is_error


@pytest.mark.anyio
async def test_run_readonly_sql_returns_database_errors_to_the_llm():
    runner = FakeQueryRunner(error='column "nope" does not exist')
    async with Client(make_server(runner=runner)) as client:
        result = await client.call_tool("run_readonly_sql", {"sql": "select nope from fct_orders"})
    assert result.is_error
    assert 'Database error: column "nope" does not exist' in result.content[0].text


@pytest.mark.anyio
async def test_search_docs_reports_embedding_errors():
    async with Client(make_server(embedder=FakeEmbedder(error="quota exceeded"))) as client:
        result = await client.call_tool("search_docs", {"query": "revenue"})
    assert result.is_error
    assert "Embedding provider error: quota exceeded" in result.content[0].text
