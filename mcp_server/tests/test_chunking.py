from olist_mcp.domain.chunking import Chunk, plan_changes, split_markdown

DOC = """# Business metrics

Intro text that belongs to no section.

## Revenue

Revenue is sum(price).

## Late delivery

Late when delivered after the estimate.
"""


def test_split_markdown_one_chunk_per_section():
    chunks = split_markdown("metrics.md", DOC)
    assert [c.title for c in chunks] == [
        "Business metrics / Revenue",
        "Business metrics / Late delivery",
    ]
    assert chunks[0].content == "Business metrics / Revenue\n\nRevenue is sum(price)."
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_plan_changes_embeds_only_new_or_changed():
    a, b = split_markdown("metrics.md", DOC)
    existing = {
        ("metrics.md", 0): (a.content_hash, "m1"),  # unchanged
        ("metrics.md", 1): ("old-hash", "m1"),  # changed text
        ("old.md", 0): ("x", "m1"),  # file removed
    }
    to_embed, to_delete = plan_changes([a, b], existing, model="m1")
    assert to_embed == [b]
    assert to_delete == [("old.md", 0)]


def test_plan_changes_reembeds_everything_on_model_change():
    chunks = split_markdown("metrics.md", DOC)
    existing = {(c.source, c.chunk_index): (c.content_hash, "m1") for c in chunks}
    to_embed, _ = plan_changes(chunks, existing, model="m2")
    assert to_embed == chunks


def test_chunk_hash_depends_on_content():
    assert Chunk("a.md", 0, "t", "x").content_hash != Chunk("a.md", 0, "t", "y").content_hash
