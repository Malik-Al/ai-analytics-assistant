"""Markdown chunking for the knowledge-base indexer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    source: str  # file name, e.g. metrics.md
    chunk_index: int
    title: str
    content: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


def split_markdown(source: str, text: str) -> list[Chunk]:
    """One chunk per `## section`, prefixed with the document title for context."""
    doc_title = ""
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("# "):
            doc_title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)

    chunks = []
    for i, (section, body) in enumerate(sections):
        title = f"{doc_title} / {section}" if doc_title else section
        content = f"{title}\n\n" + "\n".join(body).strip()
        chunks.append(Chunk(source=source, chunk_index=i, title=title, content=content))
    return chunks


def plan_changes(
    chunks: list[Chunk], existing: dict[tuple[str, int], tuple[str, str]], model: str
) -> tuple[list[Chunk], list[tuple[str, int]]]:
    """Return (chunks to embed, keys to delete). existing: key -> (content_hash, model)."""
    to_embed = [
        c for c in chunks if existing.get((c.source, c.chunk_index)) != (c.content_hash, model)
    ]
    current = {(c.source, c.chunk_index) for c in chunks}
    to_delete = [key for key in existing if key not in current]
    return to_embed, to_delete
