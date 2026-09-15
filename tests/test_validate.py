"""Unit tests for core.validate."""

from pathlib import Path

import pytest

from conftest import (
    REMOVE_FIELD,
    build_seeded_corpus,
    mint_note_then_retitle,
    mint_sparql_basics,
    rewrite_frontmatter,
)
from mcp_local_notes.core import validate, vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import Rule


@pytest.fixture(name="corpus")
def _corpus(tmp_path: Path) -> Corpus:
    """An isolated, pre-seeded corpus."""
    return build_seeded_corpus(tmp_path)


@pytest.mark.unit
def test_clean_corpus_has_zero_issues(corpus: Corpus) -> None:
    """A corpus with no problems reports zero issues."""
    mint_sparql_basics(corpus)
    assert not validate.validate(corpus)


@pytest.mark.unit
def test_detects_missing_required_field(corpus: Corpus) -> None:
    """A note missing its tags field is flagged with MISSING_REQUIRED_FIELD."""
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(corpus.notes_dir / f"{note.id}.md", tags=REMOVE_FIELD)

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.MISSING_REQUIRED_FIELD
        and issue.details.get("field") == "tags"
        and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_detects_duplicate_title(corpus: Corpus) -> None:
    """Two notes sharing a title are flagged with DUPLICATE_TITLE, both named."""
    note_a = mint_sparql_basics(corpus)
    note_b = mint_note_then_retitle(corpus, "Something else", "SPARQL basics")

    issues = validate.validate(corpus)
    duplicates = [i for i in issues if i.type == Rule.DUPLICATE_TITLE]
    assert len(duplicates) == 1
    assert set(duplicates[0].details["note_ids"]) == {note_a.id, note_b.id}


@pytest.mark.unit
def test_detects_unknown_topic(corpus: Corpus) -> None:
    """A tag not in the controlled vocabulary is flagged with UNKNOWN_TOPIC."""
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(
        corpus.notes_dir / f"{note.id}.md",
        tags=["knowledge-graphs", "quantum-computing"],
    )

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.UNKNOWN_TOPIC
        and issue.details.get("topic") == "quantum-computing"
        and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_detects_unknown_type(corpus: Corpus) -> None:
    """An undeclared type is flagged with UNKNOWN_TYPE."""
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(corpus.notes_dir / f"{note.id}.md", type="Widget")

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.UNKNOWN_TYPE
        and issue.details.get("type") == "Widget"
        and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_detects_dangling_related_reference(corpus: Corpus) -> None:
    """A related id with no corresponding note is flagged with
    RELATED_NOTE_NOT_FOUND."""
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(
        corpus.notes_dir / f"{note.id}.md", related=["does-not-exist"]
    )

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.RELATED_NOTE_NOT_FOUND
        and issue.details.get("missing_id") == "does-not-exist"
        and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_detects_dangling_part_of_reference(corpus: Corpus) -> None:
    """A part_of id with no corresponding note is flagged with
    PART_OF_NOTE_NOT_FOUND."""
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(
        corpus.notes_dir / f"{note.id}.md", part_of="does-not-exist"
    )

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.PART_OF_NOTE_NOT_FOUND
        and issue.details.get("missing_id") == "does-not-exist"
        and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_detects_stale_abox_entry(corpus: Corpus) -> None:
    """Frontmatter that no longer matches abox.ttl is flagged STALE_ABOX_ENTRY."""
    vocabulary.add_topic("semantic-web", corpus.tbox_path)
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(
        corpus.notes_dir / f"{note.id}.md",
        tags=["knowledge-graphs", "semantic-web"],
    )

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.STALE_ABOX_ENTRY and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_detects_filename_id_mismatch(corpus: Corpus) -> None:
    """A note file whose name doesn't match its id is flagged
    FILENAME_ID_MISMATCH."""
    note = mint_sparql_basics(corpus)
    old_path = corpus.notes_dir / f"{note.id}.md"
    old_path.rename(corpus.notes_dir / "renamed.md")

    issues = validate.validate(corpus)
    assert any(
        issue.type == Rule.FILENAME_ID_MISMATCH and issue.note_id == note.id
        for issue in issues
    )


@pytest.mark.unit
def test_validation_never_modifies_any_file(corpus: Corpus) -> None:
    """Running validate leaves every file byte-for-byte unchanged."""
    note = mint_sparql_basics(corpus)
    rewrite_frontmatter(corpus.notes_dir / f"{note.id}.md", tags=REMOVE_FIELD)

    note_before = (corpus.notes_dir / f"{note.id}.md").read_text()
    tbox_before = corpus.tbox_path.read_text()
    abox_before = corpus.abox_path.read_text()

    validate.validate(corpus)

    assert (corpus.notes_dir / f"{note.id}.md").read_text() == note_before
    assert corpus.tbox_path.read_text() == tbox_before
    assert corpus.abox_path.read_text() == abox_before


@pytest.mark.unit
def test_build_report_shape(corpus: Corpus) -> None:
    """build_report produces the documented {ok, issues} JSON-ready shape."""
    mint_sparql_basics(corpus)
    report = validate.build_report(validate.validate(corpus))
    assert report == {"ok": True, "issues": []}
