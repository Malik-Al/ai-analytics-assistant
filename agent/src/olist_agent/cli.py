"""Command line entrypoint: olist-agent "question"."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from olist_agent.config import Settings, get_settings
from olist_agent.graph import build_graph
from olist_agent.mcp_tools import open_mcp_tools

PREVIEW_CHARS = 200


async def ask(graph: CompiledStateGraph, question: str, *, max_steps: int) -> str:
    """Run the graph, print every tool call and result, return the final answer."""
    # one step = one node run; an LLM call + its tools run = 2 steps
    config = {"recursion_limit": 2 * max_steps + 1}
    answer = ""
    # stream_mode="updates" yields {node_name: what_the_node_returned} after each node
    async for chunk in graph.astream(
        {"messages": [HumanMessage(question)]}, config, stream_mode="updates"
    ):
        for update in chunk.values():
            for message in update["messages"]:
                if isinstance(message, AIMessage):
                    for call in message.tool_calls:
                        args = json.dumps(call["args"], ensure_ascii=False)
                        print(f"-> {call['name']}({args})")
                    if not message.tool_calls:
                        answer = message.text
                elif isinstance(message, ToolMessage):
                    preview = message.text.replace("\n", " ")[:PREVIEW_CHARS]
                    print(f"<- {message.name} [{message.status}]: {preview}")
    return answer


async def run(question: str, settings: Settings) -> str:
    """Composition root: settings -> LLM + MCP tools -> graph -> answer."""
    model = ChatOpenAI(model=settings.agent_model, temperature=0)
    async with open_mcp_tools(settings) as tools:
        graph = build_graph(model, tools)
        return await ask(graph, question, max_steps=settings.agent_max_steps)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="olist-agent", description="Ask a question about the Olist data warehouse."
    )
    parser.add_argument("question")
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        answer = asyncio.run(run(args.question, settings))
    except* GraphRecursionError:
        # except* also matches the error wrapped in an ExceptionGroup by the MCP client;
        # sys.exit(text) prints the text to stderr and exits with code 1
        sys.exit(
            f"Agent stopped: no answer after {settings.agent_max_steps} steps. "
            "Rephrase the question or raise AGENT_MAX_STEPS."
        )
    print(f"\n{answer}")
