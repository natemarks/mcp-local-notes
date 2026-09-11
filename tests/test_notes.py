"""Unit tests for core.notes.new_note."""

import shutil
from pathlib import Path

import pytest
from rdflib.namespace import DCTERMS

from mcp_local_notes.core import notes, vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.core.models import load_markdown
from mcp_local_notes.ontology import abox
from mcp_local_notes.ontology.tbox import NS

BOOTSTRAP_TBOX = Path(__file__).parent.parent / "notes" / "tbox.ttl"


@pytest.fixture(name="corpus")
def _corpus(tmp_path: Path) -> Corpus:
    """An isolated corpus with a bootstrap tbox.ttl and empty abox.ttl."""
    tbox_path = tmp_path / "tbox.ttl"
    abox_path = tmp_path / "abox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, tbox_path)
    abox_path.write_text(
        "@prefix : <https://notes.natenite.net/ontology#> .\n"
    )
    vocabulary.add_topic("knowledge-graphs", tbox_path)
    vocabulary.add_class("Concept", tbox_path)
    return Corpus(notes_dir=tmp_path, tbox_path=tbox_path, abox_path=abox_path)


@pytest.mark.unit
def test_new_note_creates_file_and_abox_entry(corpus: Corpus) -> None:
    """A valid new_note writes the note file and its ABox entry atomically."""
    note = notes.new_note(
        title="SPARQL basics",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )

    assert note.id == "sparql-basics"
    note_file = corpus.notes_dir / "sparql-basics.md"
    assert note_file.exists()
    reloaded = load_markdown(note_file.read_text())
    assert reloaded.title == "SPARQL basics"
    assert reloaded.created != ""

    graph = abox.load(corpus.abox_path)
    assert (NS["sparql-basics"], DCTERMS.title, None) in graph


@pytest.mark.unit
def test_new_note_rejects_duplicate_title(corpus: Corpus) -> None:
    """A second note with the same title is rejected, no file/ABox change."""
    notes.new_note(
        title="SPARQL basics",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )
    abox_before = corpus.abox_path.read_text()

    with pytest.raises(NotesError) as exc_info:
        notes.new_note(
            title="SPARQL basics",
            tags=["knowledge-graphs"],
            note_type="Concept",
            corpus=corpus,
        )
    assert exc_info.value.rule == Rule.DUPLICATE_TITLE
    assert not (corpus.notes_dir / "sparql-basics-2.md").exists()
    assert corpus.abox_path.read_text() == abox_before


@pytest.mark.unit
def test_new_note_rejects_case_punctuation_variant_as_duplicate(
    corpus: Corpus,
) -> None:
    """A differently-cased/punctuated title colliding on slug is a duplicate."""
    notes.new_note(
        title="SPARQL basics",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )
    with pytest.raises(NotesError) as exc_info:
        notes.new_note(
            title="Sparql Basics",
            tags=["knowledge-graphs"],
            note_type="Concept",
            corpus=corpus,
        )
    assert exc_info.value.rule == Rule.DUPLICATE_TITLE


@pytest.mark.unit
def test_new_note_rejects_alias_colliding_with_existing_title(
    corpus: Corpus,
) -> None:
    """A new note's alias colliding with an existing title is a duplicate alias."""
    notes.new_note(
        title="Intro to SPARQL",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )
    with pytest.raises(NotesError) as exc_info:
        notes.new_note(
            title="SPARQL Intro",
            tags=["knowledge-graphs"],
            note_type="Concept",
            aliases=["Intro to SPARQL"],
            corpus=corpus,
        )
    assert exc_info.value.rule == Rule.DUPLICATE_ALIAS


@pytest.mark.unit
def test_new_note_rejects_unknown_tag_without_approval(corpus: Corpus) -> None:
    """An unapproved unknown tag is rejected with UNKNOWN_TOPIC."""
    with pytest.raises(NotesError) as exc_info:
        notes.new_note(
            title="Quantum SPARQL",
            tags=["quantum-computing"],
            note_type="Concept",
            corpus=corpus,
        )
    assert exc_info.value.rule == Rule.UNKNOWN_TOPIC
    assert exc_info.value.details["topic"] == "quantum-computing"


@pytest.mark.unit
def test_new_note_approves_topic_in_same_request(corpus: Corpus) -> None:
    """An approved unknown tag is added to the vocabulary and the note is created."""
    note = notes.new_note(
        title="Quantum SPARQL",
        tags=["quantum-computing"],
        note_type="Concept",
        approve_topics=["quantum-computing"],
        corpus=corpus,
    )
    assert "quantum-computing" in note.tags
    assert "quantum-computing" in vocabulary.list_topics(corpus.tbox_path)


@pytest.mark.unit
def test_new_note_rejects_no_tags(corpus: Corpus) -> None:
    """A note with no tags is rejected with MISSING_REQUIRED_FIELD."""
    with pytest.raises(NotesError) as exc_info:
        notes.new_note(
            title="Untagged note",
            tags=[],
            note_type="Concept",
            corpus=corpus,
        )
    assert exc_info.value.rule == Rule.MISSING_REQUIRED_FIELD


@pytest.mark.unit
def test_new_note_rejects_unknown_type(corpus: Corpus) -> None:
    """An undeclared type is rejected with UNKNOWN_TYPE."""
    with pytest.raises(NotesError) as exc_info:
        notes.new_note(
            title="Mystery Note",
            tags=["knowledge-graphs"],
            note_type="Widget",
            corpus=corpus,
        )
    assert exc_info.value.rule == Rule.UNKNOWN_TYPE
    assert exc_info.value.details["type"] == "Widget"
