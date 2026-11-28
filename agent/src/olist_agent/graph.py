"""ReAct agent as a LangGraph StateGraph: the LLM node and the tools node call each other."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from olist_agent.prompts import SYSTEM_PROMPT


class AgentState(TypedDict):
    # add_messages is a reducer: messages returned by a node are appended, not overwritten
    messages: Annotated[list[AnyMessage], add_messages]


def route_after_agent(state: AgentState) -> Literal["tools", "__end__"]:
    """Go to the tools node if the LLM asked for tools, otherwise finish."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def build_graph(
    model: BaseChatModel, tools: list[BaseTool], *, system_prompt: str = SYSTEM_PROMPT
) -> CompiledStateGraph:
    """Wire the graph: START -> agent -> (tools -> agent)* -> END."""
    # bind_tools sends the tool schemas to the LLM with every request
    model_with_tools = model.bind_tools(tools)
    system = SystemMessage(system_prompt)

    async def call_model(state: AgentState) -> dict:
        # the system prompt goes first on every LLM call but is not stored in the state
        response = await model_with_tools.ainvoke([system, *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    # ToolNode runs every tool call from the last AIMessage and returns ToolMessages
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent)
    graph.add_edge("tools", "agent")
    return graph.compile()
