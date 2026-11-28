import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import ToolException, tool

from olist_agent.graph import build_graph
from tests.fakes import FakeToolModel

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@tool
def list_tables() -> str:
    """List warehouse tables."""
    return "fct_orders, dim_customers"


@tool
def describe_table(table_name: str) -> str:
    """Describe one table."""
    if table_name != "fct_orders":
        raise ToolException(f"Unknown table '{table_name}'")
    return "fct_orders: order_id, items_amount"


# like the MCP adapter: a server ToolError comes back to the LLM as text, not as a crash
describe_table.handle_tool_error = True


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


async def test_answers_without_tools():
    model = FakeToolModel(messages=iter([AIMessage(content="Hello!")]))
    graph = build_graph(model, [list_tables])

    result = await graph.ainvoke({"messages": [HumanMessage("hi")]})

    assert [type(m) for m in result["messages"]] == [HumanMessage, AIMessage]
    assert result["messages"][-1].content == "Hello!"
    assert model.bound_tools == ["list_tables"]


async def test_calls_tool_then_answers():
    model = FakeToolModel(
        messages=iter(
            [
                tool_call("list_tables", {}, "call_1"),
                AIMessage(content="There are 2 tables."),
            ]
        )
    )
    graph = build_graph(model, [list_tables])

    result = await graph.ainvoke({"messages": [HumanMessage("which tables?")]})

    human, ai_call, tool_result, answer = result["messages"]
    assert isinstance(tool_result, ToolMessage)
    assert tool_result.tool_call_id == "call_1"
    assert tool_result.content == "fct_orders, dim_customers"
    assert answer.content == "There are 2 tables."
    # the 2nd LLM call saw the system prompt and the whole history:
    # question, its own tool call and the result
    assert len(model.seen_messages[1]) == 4


async def test_tool_error_goes_back_to_llm():
    model = FakeToolModel(
        messages=iter(
            [
                tool_call("describe_table", {"table_name": "orders"}, "call_1"),
                tool_call("describe_table", {"table_name": "fct_orders"}, "call_2"),
                AIMessage(content="fct_orders has items_amount."),
            ]
        )
    )
    graph = build_graph(model, [describe_table])

    result = await graph.ainvoke({"messages": [HumanMessage("describe orders")]})

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_messages[0].status == "error"
    assert "Unknown table 'orders'" in tool_messages[0].content
    assert tool_messages[1].status == "success"
    assert result["messages"][-1].content == "fct_orders has items_amount."


async def test_system_prompt_is_sent_first_but_not_stored():
    model = FakeToolModel(messages=iter([AIMessage(content="Hello!")]))
    graph = build_graph(model, [list_tables], system_prompt="You are a test analyst.")

    result = await graph.ainvoke({"messages": [HumanMessage("hi")]})

    first_call = model.seen_messages[0]
    assert isinstance(first_call[0], SystemMessage)
    assert first_call[0].content == "You are a test analyst."
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])
