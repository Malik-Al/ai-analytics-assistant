"""Fake LLM for graph tests: replays scripted AIMessages instead of calling OpenAI."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.tools import BaseTool


class FakeToolModel(GenericFakeChatModel):
    """Returns the next scripted message on each call and records what it was given."""

    bound_tools: list[str] = []
    seen_messages: list[list[Any]] = []

    def bind_tools(self, tools: Sequence[BaseTool], **kwargs: Any) -> FakeToolModel:
        self.bound_tools = [t.name for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
