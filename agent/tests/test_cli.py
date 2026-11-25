import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from olist_agent.cli import ask
from olist_agent.graph import build_graph
from tests.fakes import FakeToolModel

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@tool
def run_readonly_sql(sql: str) -> str:
    """Run one SELECT."""
    return '{"rows": [[5960000.0]]}'


async def test_ask_prints_tool_calls_and_returns_answer(capsys):
    model = FakeToolModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "run_readonly_sql", "args": {"sql": "select 1"}, "id": "c1"}
                    ],
                ),
                AIMessage(content="Revenue is R$5.96M."),
            ]
        )
    )
    graph = build_graph(model, [run_readonly_sql])

    answer = await ask(graph, "revenue 2017?", max_steps=5)

    assert answer == "Revenue is R$5.96M."
    out = capsys.readouterr().out
    assert '-> run_readonly_sql({"sql": "select 1"})' in out
    assert '<- run_readonly_sql [success]: {"rows": [[5960000.0]]}' in out


async def test_ask_stops_after_max_steps():
    # the fake LLM asks for a tool forever; the graph must stop instead of looping
    endless = (
        AIMessage(
            content="",
            tool_calls=[{"name": "run_readonly_sql", "args": {"sql": "x"}, "id": f"c{i}"}],
        )
        for i in range(100)
    )
    graph = build_graph(FakeToolModel(messages=endless), [run_readonly_sql])

    with pytest.raises(GraphRecursionError):
        await ask(graph, "loop", max_steps=2)
