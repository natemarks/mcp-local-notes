"""Unit tests for core.models: the Note frontmatter schema and markdown I/O."""

import pytest

from mcp_local_notes.core.models import (
    Note,
    dump_markdown,
    load_markdown,
    parse_frontmatter,
)


@pytest.mark.unit
def test_note_defaults() -> None:
    """A minimally-constructed Note has the documented defaults."""
    note = Note(
        id="sparql-basics",
        title="SPARQL basics",
        tags=["knowledge-graphs"],
        type="Concept",
    )
    assert not note.aliases
    assert note.status == "active"
    assert not note.related
    assert note.part_of is None


@pytest.mark.unit
def test_dump_then_load_round_trips() -> None:
    """A Note serialized to markdown and reloaded is identical."""
    note = Note(
        id="sparql-basics",
        title="SPARQL basics",
        tags=["knowledge-graphs"],
        type="Concept",
        aliases=["Intro to SPARQL"],
        created="2026-09-11",
        modified="2026-09-11",
        related=["intro-to-sparql"],
        part_of="knowledge-graphs-project",
    )
    text = dump_markdown(note)
    reloaded = load_markdown(text)
    assert reloaded == note


@pytest.mark.unit
def test_dump_markdown_always_includes_empty_fields() -> None:
    """Empty list/None fields are still present in the frontmatter, not omitted."""
    note = Note(id="x", title="X", tags=["knowledge-graphs"], type="Concept")
    text = dump_markdown(note)
    assert "aliases: []" in text
    assert "related: []" in text
    assert "part_of: null" in text


@pytest.mark.unit
def test_parse_frontmatter_returns_raw_dict_without_defaulting() -> None:
    """parse_frontmatter exposes exactly what's on disk, no defaulting --
    so validation can tell "key absent" apart from "key present empty"."""
    text = "---\nid: x\ntitle: X\ntype: Concept\n---\n"
    raw = parse_frontmatter(text)
    assert "tags" not in raw
    assert raw["id"] == "x"
