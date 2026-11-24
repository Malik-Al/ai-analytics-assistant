"""Embed docs/knowledge/*.md into knowledge.chunks (pgvector) for search_docs.

Incremental: only new or changed chunks are sent to the embedding API.
Run as: uv run --env-file ../.env olist-index-docs [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

import psycopg

from olist_mcp.adapters.embeddings import get_embedder
from olist_mcp.config import get_settings
from olist_mcp.domain.chunking import plan_changes, split_markdown

PRICE_PER_1M_TOKENS = 0.02  # text-embedding-3-small, USD


def connect_owner() -> psycopg.Connection:
    # the indexer writes, so it uses the owner role, not mcp_reader
    settings = get_settings()
    if settings.postgres_user is None or settings.postgres_password is None:
        sys.exit("POSTGRES_USER and POSTGRES_PASSWORD are required for the indexer")
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
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

    docs_dir = get_settings().knowledge_docs_dir
    chunks = [
        chunk
        for path in sorted(docs_dir.glob("*.md"))
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
