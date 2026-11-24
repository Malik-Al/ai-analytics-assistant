"""Embedding providers behind one small interface, selected by settings."""

from __future__ import annotations

from typing import Protocol

from olist_mcp.config import get_settings


class Embedder(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, model: str = "text-embedding-3-small", dimensions: int = 1536) -> None:
        from openai import OpenAI  # imported lazily: tests never need the SDK client

        self.model = model
        self.dimensions = dimensions
        self._client = OpenAI()  # reads OPENAI_API_KEY from env

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimensions
        )
        return [item.embedding for item in response.data]


def get_embedder() -> Embedder:
    settings = get_settings()
    provider = settings.embedding_provider
    if provider == "openai":
        return OpenAIEmbedder(model=settings.embedding_model)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")
