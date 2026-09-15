"""Unit tests for core.notes: new_note, update_note, sync_note, rebuild_abox."""

from datetime import date
from pathlib import Path

import pytest
from rdflib import Literal
from rdflib.namespace import DCTERMS

from conftest import (
    build_seeded_corpus,
    mint_intro_to_sparql,
    mint_sparql_basics,
)
from mcp_local_notes.core import notes, vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.core.models import dump_markdown, load_markdown
from mcp_local_notes.ontology import abox
from mcp_local_notes.ontology.tbox import NS


@pytest.fixture(name="corpus")
def _corpus(tmp_path: Path) -> Corpus:
    """An isolated, pre-seeded corpus."""
    return build_seeded_corpus(tmp_path)


@pytest.mark.unit
def test_note_path_is_notes_dir_slash_id_dot_md(corpus: Corpus) -> None:
    """note_path is the one place the <id>.md filename convention lives,
    so adapters can report a note's absolute path without reinventing it
    or re-resolving it themselves."""
    assert (
        notes.note_path("sparql-basics", corpus.notes_dir)
        == (corpus.notes_dir / "sparql-basics.md").resolve()
    )


@pytest.mark.unit
def test_new_note_creates_file_and_abox_entry(corpus: Corpus) -> None:
    """A valid new_note writes the note file and its ABox entry atomically."""
    note = mint_sparql_basics(corpus)

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
    mint_sparql_basics(corpus)
    abox_before = corpus.abox_path.read_text()

    with pytest.raises(NotesError) as exc_info:
        mint_sparql_basics(corpus)
    assert exc_info.value.rule == Rule.DUPLICATE_TITLE
    assert not (corpus.notes_dir / "sparql-basics-2.md").exists()
    assert corpus.abox_path.read_text() == abox_before


@pytest.mark.unit
def test_new_note_rejects_case_punctuation_variant_as_duplicate(
    corpus: Corpus,
) -> None:
    """A differently-cased/punctuated title colliding on slug is a duplicate."""
    mint_sparql_basics(corpus)
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
    mint_intro_to_sparql(corpus)
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


# --- update_note -------------------------------------------------------


@pytest.mark.unit
def test_update_note_adding_a_tag_regenerates_abox_with_one_entry(
    corpus: Corpus,
) -> None:
    """Adding a tag regenerates the ABox entry -- exactly one per note id."""
    vocabulary.add_topic("semantic-web", corpus.tbox_path)
    mint_sparql_basics(corpus)

    updated = notes.update_note(
        "sparql-basics", corpus, add_tags=["semantic-web"]
    )

    assert updated.modified == date.today().isoformat()
    graph = abox.load(corpus.abox_path)
    tag_triples = list(
        graph.triples((NS["sparql-basics"], DCTERMS.subject, None))
    )
    assert {str(o) for _, _, o in tag_triples} == {
        str(NS["knowledge-graphs"]),
        str(NS["semantic-web"]),
    }


@pytest.mark.unit
def test_update_note_renaming_preserves_old_title_as_alias(
    corpus: Corpus,
) -> None:
    """Renaming keeps the id/filename and preserves the old title as an alias."""
    mint_sparql_basics(corpus)

    updated = notes.update_note(
        "sparql-basics", corpus, title="Intro to SPARQL basics"
    )

    assert updated.title == "Intro to SPARQL basics"
    assert "SPARQL basics" in updated.aliases
    assert updated.id == "sparql-basics"
    assert (corpus.notes_dir / "sparql-basics.md").exists()

    graph = abox.load(corpus.abox_path)
    assert (
        NS["sparql-basics"],
        DCTERMS.title,
        Literal("Intro to SPARQL basics"),
    ) in graph


@pytest.mark.unit
def test_update_note_rename_to_duplicate_title_is_rejected(
    corpus: Corpus,
) -> None:
    """A rename that collides with another note's title is rejected."""
    mint_sparql_basics(corpus)
    notes.new_note(
        title="RDF vs. property graphs",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )

    with pytest.raises(NotesError) as exc_info:
        notes.update_note(
            "sparql-basics", corpus, title="RDF vs. property graphs"
        )
    assert exc_info.value.rule == Rule.DUPLICATE_TITLE

    reloaded = notes.get_note("sparql-basics", corpus.notes_dir)
    assert reloaded.title == "SPARQL basics"


@pytest.mark.unit
def test_update_note_rejects_nonexistent_related_note(corpus: Corpus) -> None:
    """Adding a related reference to a nonexistent note is rejected."""
    mint_sparql_basics(corpus)

    with pytest.raises(NotesError) as exc_info:
        notes.update_note(
            "sparql-basics", corpus, add_related=["does-not-exist"]
        )
    assert exc_info.value.rule == Rule.RELATED_NOTE_NOT_FOUND


@pytest.mark.unit
def test_update_note_adds_valid_related_note_to_abox(corpus: Corpus) -> None:
    """A valid related reference produces a :relatesTo triple."""
    mint_sparql_basics(corpus)
    mint_intro_to_sparql(corpus)

    notes.update_note("sparql-basics", corpus, add_related=["intro-to-sparql"])

    graph = abox.load(corpus.abox_path)
    assert (
        NS["sparql-basics"],
        NS.relatesTo,
        NS["intro-to-sparql"],
    ) in graph


# --- sync_note -----------------------------------------------------------


@pytest.mark.unit
def test_sync_note_regenerates_abox_from_hand_edited_frontmatter(
    corpus: Corpus,
) -> None:
    """sync_note regenerates the ABox entry from the note's on-disk state."""
    mint_sparql_basics(corpus)

    # Simulate a hand edit outside any tool session: add a tag directly to
    # the file, without going through update_note (so the ABox is now stale).
    note_path = corpus.notes_dir / "sparql-basics.md"
    hand_edited = load_markdown(note_path.read_text())
    hand_edited.tags.append("rdf")
    note_path.write_text(dump_markdown(hand_edited))

    notes.sync_note("sparql-basics", corpus)

    graph = abox.load(corpus.abox_path)
    assert (NS["sparql-basics"], DCTERMS.subject, NS["rdf"]) in graph


# --- rebuild_abox ----------------------------------------------------------


@pytest.mark.unit
def test_rebuild_abox_regenerates_from_current_frontmatter(
    corpus: Corpus,
) -> None:
    """rebuild_abox regenerates every note's entry from current frontmatter."""
    mint_sparql_basics(corpus)
    mint_intro_to_sparql(corpus)

    note_path = corpus.notes_dir / "sparql-basics.md"
    hand_edited = load_markdown(note_path.read_text())
    hand_edited.tags.append("rdf")
    note_path.write_text(dump_markdown(hand_edited))

    notes.rebuild_abox(corpus)

    graph = abox.load(corpus.abox_path)
    assert (NS["sparql-basics"], DCTERMS.subject, NS["rdf"]) in graph
    assert (NS["intro-to-sparql"], DCTERMS.title, None) in graph


@pytest.mark.unit
def test_rebuild_abox_drops_entries_for_deleted_notes(corpus: Corpus) -> None:
    """rebuild_abox drops ABox entries for note ids with no corresponding file."""
    mint_sparql_basics(corpus)
    mint_intro_to_sparql(corpus)

    (corpus.notes_dir / "intro-to-sparql.md").unlink()

    notes.rebuild_abox(corpus)

    graph = abox.load(corpus.abox_path)
    assert (NS["sparql-basics"], DCTERMS.title, None) in graph
    assert not list(graph.triples((NS["intro-to-sparql"], None, None)))


# --- archive_note --------------------------------------------------------


@pytest.mark.unit
def test_archive_note_sets_status_keeps_file_and_abox(corpus: Corpus) -> None:
    """archive_note flips status; the file and ABox entry remain."""
    mint_sparql_basics(corpus)

    archived = notes.archive_note("sparql-basics", corpus)

    assert archived.status == "archived"
    note_path = corpus.notes_dir / "sparql-basics.md"
    assert note_path.exists()
    reloaded = load_markdown(note_path.read_text())
    assert reloaded.status == "archived"

    graph = abox.load(corpus.abox_path)
    assert (NS["sparql-basics"], DCTERMS.title, None) in graph


# --- delete_note ---------------------------------------------------------


@pytest.mark.unit
def test_delete_note_with_no_inbound_references(corpus: Corpus) -> None:
    """delete_note removes the file and ABox entry when nothing references it."""
    mint_sparql_basics(corpus)

    notes.delete_note("sparql-basics", corpus)

    assert not (corpus.notes_dir / "sparql-basics.md").exists()
    graph = abox.load(corpus.abox_path)
    assert not list(graph.triples((NS["sparql-basics"], None, None)))


@pytest.mark.unit
def test_delete_note_blocked_by_inbound_references(corpus: Corpus) -> None:
    """delete_note is rejected, naming the referencing note, unless confirmed."""
    mint_sparql_basics(corpus)
    mint_intro_to_sparql(corpus)
    notes.update_note("intro-to-sparql", corpus, add_related=["sparql-basics"])

    with pytest.raises(NotesError) as exc_info:
        notes.delete_note("sparql-basics", corpus)
    assert exc_info.value.rule == Rule.DELETE_BLOCKED_BY_REFERENCES
    assert "intro-to-sparql" in exc_info.value.details["referencing_note_ids"]
    assert (corpus.notes_dir / "sparql-basics.md").exists()


@pytest.mark.unit
def test_delete_note_confirmed_despite_inbound_references(
    corpus: Corpus,
) -> None:
    """A confirmed delete removes the note even with inbound references."""
    mint_sparql_basics(corpus)
    mint_intro_to_sparql(corpus)
    notes.update_note("intro-to-sparql", corpus, add_related=["sparql-basics"])

    notes.delete_note("sparql-basics", corpus, confirm=True)

    assert not (corpus.notes_dir / "sparql-basics.md").exists()
    graph = abox.load(corpus.abox_path)
    assert not list(graph.triples((NS["sparql-basics"], None, None)))


# --- find_notes_by_topic --------------------------------------------------


@pytest.mark.unit
def test_find_notes_by_topic_returns_matching_notes(corpus: Corpus) -> None:
    """Only notes tagged with the given topic are returned."""
    mint_sparql_basics(corpus)
    vocabulary.add_topic("other-topic", corpus.tbox_path)
    notes.new_note(
        title="Unrelated note",
        tags=["other-topic"],
        note_type="Concept",
        corpus=corpus,
    )

    matches = notes.find_notes_by_topic("knowledge-graphs", corpus)

    assert [note.id for note in matches] == ["sparql-basics"]


@pytest.mark.unit
def test_find_notes_by_topic_returns_empty_list_when_unused(
    corpus: Corpus,
) -> None:
    """A known topic with no matching notes returns an empty list, not an
    error -- distinct from an unknown topic, which is rejected."""
    vocabulary.add_topic("unused-topic", corpus.tbox_path)

    assert notes.find_notes_by_topic("unused-topic", corpus) == []


@pytest.mark.unit
def test_find_notes_by_topic_rejects_unknown_topic(corpus: Corpus) -> None:
    """A topic not in the vocabulary is rejected, not silently empty --
    the caller likely mistyped it."""
    with pytest.raises(NotesError) as exc_info:
        notes.find_notes_by_topic("no-such-topic", corpus)
    assert exc_info.value.rule == Rule.UNKNOWN_TOPIC
    assert exc_info.value.details["topic"] == "no-such-topic"
