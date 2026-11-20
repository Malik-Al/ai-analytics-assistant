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
