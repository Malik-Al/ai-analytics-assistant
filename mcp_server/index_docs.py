"""Embed docs/knowledge/*.md into knowledge.chunks (pgvector) for search_docs.

Incremental: only new or changed chunks are sent to the embedding API.
Run from mcp_server/:  uv run --env-file ../.env python index_docs.py [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import psycopg

from embeddings import get_embedder

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs" / "knowledge"
PRICE_PER_1M_TOKENS = 0.02  # text-embedding-3-small, USD


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


def connect_owner() -> psycopg.Connection:
    # the indexer writes, so it uses the owner role, not mcp_reader
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5433"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def ensure_table(conn: psycopg.Connection, dimensions: int) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS knowledge")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS knowledge.chunks (
            source          text        NOT NULL,
            chunk_index     int         NOT NULL,
            title           text        NOT NULL,
            content         text        NOT NULL,
            content_hash    text        NOT NULL,
            embedding_model text        NOT NULL,
            embedding       vector({int(dimensions)}) NOT NULL,
            indexed_at      timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (source, chunk_index)
        )
        """
    )
    # HNSW: approximate nearest-neighbour index for cosine distance (<=>)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS chunks_embedding_idx "
        "ON knowledge.chunks USING hnsw (embedding vector_cosine_ops)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="show the plan, call no API")
    args = parser.parse_args()

    chunks = [
        chunk
        for path in sorted(DOCS_DIR.glob("*.md"))
        for chunk in split_markdown(path.name, path.read_text(encoding="utf-8"))
    ]
    embedder = get_embedder()

    with connect_owner() as conn:
        ensure_table(conn, embedder.dimensions)
        rows = conn.execute(
            "SELECT source, chunk_index, content_hash, embedding_model FROM knowledge.chunks"
        ).fetchall()
        existing = {(r[0], r[1]): (r[2], r[3]) for r in rows}

        to_embed, to_delete = plan_changes(chunks, existing, embedder.model)
        tokens = sum(len(c.content) for c in to_embed) // 4  # rough: ~4 chars per token
        print(f"{len(chunks)} chunks in docs, {len(to_embed)} to embed, {len(to_delete)} to delete")
        print(f"~{tokens} tokens, ~${tokens / 1_000_000 * PRICE_PER_1M_TOKENS:.6f}")
        if args.dry_run:
            conn.rollback()
            return

        vectors = embedder.embed([c.content for c in to_embed]) if to_embed else []
        for chunk, vector in zip(to_embed, vectors, strict=True):
            conn.execute(
                """
                INSERT INTO knowledge.chunks
                    (source, chunk_index, title, content, content_hash, embedding_model, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (source, chunk_index) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding = EXCLUDED.embedding,
                    indexed_at = now()
                """,
                (
                    chunk.source,
                    chunk.chunk_index,
                    chunk.title,
                    chunk.content,
                    chunk.content_hash,
                    embedder.model,
                    str(vector),  # pgvector text format: [0.1, 0.2, ...]
                ),
            )
        for source, chunk_index in to_delete:
            conn.execute(
                "DELETE FROM knowledge.chunks WHERE source = %s AND chunk_index = %s",
                (source, chunk_index),
            )
    print("done")


if __name__ == "__main__":
    main()
