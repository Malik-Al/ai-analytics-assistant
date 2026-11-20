import pytest
from mcp.client import Client

import db
import server

FAKE_TABLES = [
    {"table_name": "dim_customers", "description": "One row per real customer."},
    {"table_name": "fct_orders", "description": None},
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


FAKE_COLUMNS = [
    {"column_name": "order_id", "data_type": "text", "description": "Order key."},
    {"column_name": "is_late", "data_type": "boolean", "description": None},
]


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    monkeypatch.setattr(db, "fetch_tables", lambda schema=db.SCHEMA: FAKE_TABLES)
    monkeypatch.setattr(db, "fetch_columns", lambda table_name, schema=db.SCHEMA: FAKE_COLUMNS)
    monkeypatch.setattr(
        db,
        "run_query",
        lambda sql, max_rows, timeout_ms: (["n"], [(i,) for i in range(max_rows + 1)]),
    )


@pytest.mark.anyio
async def test_list_tables_is_registered():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
    assert "list_tables" in [t.name for t in tools.tools]


@pytest.mark.anyio
async def test_list_tables_returns_tables():
    async with Client(server.mcp) as client:
        result = await client.call_tool("list_tables", {})
    assert not result.is_error
    assert result.structured_content == {"result": FAKE_TABLES}


@pytest.mark.anyio
async def test_describe_table_returns_columns():
    async with Client(server.mcp) as client:
        result = await client.call_tool("describe_table", {"table_name": "fct_orders"})
    assert not result.is_error
    assert result.structured_content == {
        "table_name": "fct_orders",
        "description": None,
        "columns": FAKE_COLUMNS,
    }


@pytest.mark.anyio
async def test_describe_table_unknown_table_is_error():
    async with Client(server.mcp) as client:
        result = await client.call_tool("describe_table", {"table_name": "orders"})
    assert result.is_error
    assert "dim_customers, fct_orders" in result.content[0].text


@pytest.mark.anyio
async def test_run_readonly_sql_truncates_rows(monkeypatch):
    monkeypatch.setattr(server, "MAX_ROWS", 3)
    async with Client(server.mcp) as client:
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
    async with Client(server.mcp) as client:
        result = await client.call_tool("run_readonly_sql", {"sql": "delete from fct_orders"})
    assert result.is_error
    assert "Query rejected" in result.content[0].text
