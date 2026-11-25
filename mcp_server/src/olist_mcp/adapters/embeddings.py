"""Embedding providers behind one small interface, selected by settings."""

from __future__ import annotations

import openai

from olist_mcp.config import Settings, get_settings
from olist_mcp.domain.errors import EmbeddingError
from olist_mcp.ports import Embedder


class OpenAIEmbedder:
    """Embedder port on the OpenAI API. Reads OPENAI_API_KEY from env."""

    def __init__(self, model: str = "text-embedding-3-small", dimensions: int = 1536) -> None:
        self.model = model
        self.dimensions = dimensions
        self._client = openai.OpenAI()  # raises right away if OPENAI_API_KEY is missing

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._client.embeddings.create(
                model=self.model, input=texts, dimensions=self.dimensions
            )
        except openai.OpenAIError as e:
            raise EmbeddingError(str(e)) from e
        return [item.embedding for item in response.data]


def build_embedder(settings: Settings) -> Embedder:
    """Factory: pick the provider from settings. Bedrock will be added here at the AWS stage."""
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder(model=settings.embedding_model)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}")


def get_embedder() -> Embedder:
    # TODO(MR B): removed once entrypoints build the embedder in the composition root
    return build_embedder(get_settings())
