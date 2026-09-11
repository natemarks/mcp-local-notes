"""Step definitions for features/edit_note_and_sync.feature.

Calls core.notes functions directly, per the ticket's own acceptance
criterion -- no CLI or MCP transport involved.
"""

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import Literal
from rdflib.namespace import DCTERMS

from conftest import (
    mint_intro_to_sparql,
    mint_note_with_id,
    seed_tbox_with_defaults,
)
from mcp_local_notes.core import notes, vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.core.models import dump_markdown, load_markdown
from mcp_local_notes.ontology import abox
from mcp_local_notes.ontology.tbox import NS

BOOTSTRAP_TBOX = Path(__file__).parent.parent.parent / "notes" / "tbox.ttl"

pytestmark = pytest.mark.unit

scenarios("edit_note_and_sync.feature")

_PHRASE_TO_RULE = {
    "duplicate title": Rule.DUPLICATE_TITLE,
    "related note not found": Rule.RELATED_NOTE_NOT_FOUND,
}

_RELATED_RE = re.compile(r"related:\s*([^\"]+)")

_NO_STALE_BLOCK_STEP = (
    "abox.ttl should contain no block for a note id "
    "that no longer has a corresponding file"
)


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """Pre-seed every topic/type this feature file's scenarios assume
    already exists, since vocabulary governance isn't what's under test."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    seed_tbox_with_defaults(path)
    for topic in ("semantic-web", "rdf"):
        vocabulary.add_topic(topic, path)
    return path


def _hand_edit_add_tag(note_id: str, tag: str, notes_dir: Path) -> None:
    """Simulate an edit made outside any tool session: mutate the note
    file directly, without touching the ABox."""
    note_path = notes_dir / f"{note_id}.md"
    note = load_markdown(note_path.read_text())
    note.tags.append(tag)
    note_path.write_text(dump_markdown(note))


# --- Given -------------------------------------------------------------


@given(
    parsers.parse(
        'a note "{note_id}" exists with title "{title}" and tags "{tag}"'
    )
)
def given_note_with_title_and_tag(
    note_id: str, title: str, tag: str, corpus: Corpus
) -> None:
    """Pre-seed the corpus with a note of the given title and single tag."""
    note = notes.new_note(
        title=title, tags=[tag], note_type="Concept", corpus=corpus
    )
    assert note.id == note_id


@given(parsers.parse('a note "{note_id}" exists with title "{title}"'))
def given_note_with_title(note_id: str, title: str, corpus: Corpus) -> None:
    """Pre-seed the corpus with a note of the given title."""
    note = notes.new_note(
        title=title,
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )
    assert note.id == note_id


@given(parsers.parse('a note "{note_id}" exists'))
def given_note_exists(note_id: str, corpus: Corpus) -> None:
    """Pre-seed the corpus with a note whose id is exactly note_id."""
    mint_note_with_id(note_id, corpus)


@given("its ABox block in abox.ttl matches its current frontmatter")
def given_abox_matches_frontmatter() -> None:
    """Already guaranteed by new_note's atomic write -- nothing to do."""


@given(
    parsers.parse(
        'note "{note_id}" was hand-edited outside any tool session to add tag "{tag}"'
    )
)
def given_note_hand_edited_to_add_tag(
    note_id: str, tag: str, corpus: Corpus
) -> None:
    """Mutate the note file directly, bypassing update_note entirely."""
    _hand_edit_add_tag(note_id, tag, corpus.notes_dir)


@given('its ABox block still only lists "knowledge-graphs"')
def given_abox_still_stale() -> None:
    """Already true by construction of the hand-edit step -- nothing to do."""


@given("multiple notes have been hand-edited outside any tool session")
def given_multiple_notes_hand_edited(corpus: Corpus) -> None:
    """Create a second and third note, hand-edit one, delete the other."""
    mint_intro_to_sparql(corpus)
    notes.new_note(
        title="Stale note",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )
    _hand_edit_add_tag("sparql-basics", "rdf", corpus.notes_dir)
    (corpus.notes_dir / "stale-note.md").unlink()


@given("abox.ttl no longer matches some of their frontmatter")
def given_abox_no_longer_matches() -> None:
    """Already true by construction of the previous step -- nothing to do."""


# --- When ------------------------------------------------------------------


@when(parsers.parse('I update note "{note_id}" to add the tag "{tag}"'))
def when_update_note_add_tag(
    note_id: str, tag: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Attempt update_note adding one tag, recording the outcome."""
    try:
        outcome["note"] = notes.update_note(note_id, corpus, add_tags=[tag])
    except NotesError as error:
        outcome["error"] = error


@when(parsers.parse('I rename note "{note_id}" to "{new_title}"'))
def when_rename_note(
    note_id: str, new_title: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Attempt update_note with a new title, recording the outcome."""
    try:
        outcome["note"] = notes.update_note(note_id, corpus, title=new_title)
    except NotesError as error:
        outcome["error"] = error


@when(parsers.parse('I update note "{note_id}" to add "{spec}"'))
def when_update_note_add_related(
    note_id: str, spec: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Attempt update_note adding one related id, recording the outcome."""
    match = _RELATED_RE.search(spec)
    assert match is not None, f"expected 'related: <id>' in {spec!r}"
    related_id = match.group(1).strip()
    try:
        outcome["note"] = notes.update_note(
            note_id, corpus, add_related=[related_id]
        )
    except NotesError as error:
        outcome["error"] = error


@when(parsers.parse('I sync note "{note_id}"'))
def when_sync_note(
    note_id: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Sync the named note from its current on-disk frontmatter."""
    outcome["note"] = notes.sync_note(note_id, corpus)


@when("I run a full rebuild")
def when_run_full_rebuild(corpus: Corpus) -> None:
    """Rebuild the entire ABox from every note's current frontmatter."""
    notes.rebuild_abox(corpus)


# --- Then --------------------------------------------------------------


@then(parsers.parse('the note\'s "{field}" date should be updated to today'))
def then_note_field_is_today(field: str, outcome: dict[str, Any]) -> None:
    """The recorded note's date field is today's date."""
    assert getattr(outcome["note"], field) == date.today().isoformat()


@then(
    parsers.parse(
        'the ABox block for "{note_id}" should list both "{tag_a}" and "{tag_b}"'
    )
)
def then_abox_lists_both_tags(
    note_id: str, tag_a: str, tag_b: str, corpus: Corpus
) -> None:
    """The ABox has exactly these two tag triples for the note."""
    graph = abox.load(corpus.abox_path)
    triples = list(graph.triples((NS[note_id], DCTERMS.subject, None)))
    tagged = {str(obj) for _, _, obj in triples}
    assert tagged == {str(NS[tag_a]), str(NS[tag_b])}


@then(parsers.parse('there should be exactly one ABox block for "{note_id}"'))
def then_exactly_one_abox_block(note_id: str, corpus: Corpus) -> None:
    """The ABox has exactly one dcterms:title triple for the note."""
    graph = abox.load(corpus.abox_path)
    title_triples = list(graph.triples((NS[note_id], DCTERMS.title, None)))
    assert len(title_triples) == 1


@then(parsers.parse('the note\'s "{field}" should be "{value}"'))
def then_note_field_is(
    field: str, value: str, outcome: dict[str, Any]
) -> None:
    """The recorded note's field equals the expected value."""
    assert getattr(outcome["note"], field) == value


@then(parsers.parse('the note\'s "{field}" should include "{value}"'))
def then_note_field_includes(
    field: str, value: str, outcome: dict[str, Any]
) -> None:
    """The recorded note's list field includes the expected value."""
    assert value in getattr(outcome["note"], field)


@then(parsers.parse('the note\'s "{field}" should remain "{value}"'))
def then_note_field_remains(
    field: str, value: str, outcome: dict[str, Any]
) -> None:
    """The recorded note's field is unchanged, equal to the expected value."""
    assert getattr(outcome["note"], field) == value


@then(parsers.parse('the note\'s filename should remain "{filename}"'))
def then_note_filename_remains(filename: str, corpus: Corpus) -> None:
    """The note file still exists at its original filename."""
    assert (corpus.notes_dir / filename).exists()


@then(
    parsers.parse(
        'the ABox block\'s dcterms:title for "{note_id}" should be "{title}"'
    )
)
def then_abox_title_is(note_id: str, title: str, corpus: Corpus) -> None:
    """The ABox's dcterms:title triple for the note matches the given title."""
    graph = abox.load(corpus.abox_path)
    assert (NS[note_id], DCTERMS.title, Literal(title)) in graph


@then(parsers.parse('the request should be rejected with a "{phrase}" error'))
def then_rejected_with(phrase: str, outcome: dict[str, Any]) -> None:
    """The recorded error's rule matches the expected phrase."""
    assert "error" in outcome, "expected a NotesError to have been raised"
    assert outcome["error"].rule == _PHRASE_TO_RULE[phrase]


@then(parsers.parse('note "{note_id}" should keep its original title'))
def then_note_keeps_original_title(note_id: str, corpus: Corpus) -> None:
    """The note's on-disk title is unchanged after a rejected rename."""
    reloaded = notes.get_note(note_id, corpus.notes_dir)
    assert reloaded.title == "SPARQL basics"


@then(
    parsers.parse(
        'the ABox block for "{note_id}" should include ":relatesTo :{related_id}"'
    )
)
def then_abox_includes_relates_to(
    note_id: str, related_id: str, corpus: Corpus
) -> None:
    """The ABox has a :relatesTo triple linking the note to related_id."""
    graph = abox.load(corpus.abox_path)
    assert (NS[note_id], NS.relatesTo, NS[related_id]) in graph


@then(
    parsers.parse(
        'the ABox block for "{note_id}" should be regenerated to include "{tag}"'
    )
)
def then_abox_regenerated_to_include_tag(
    tag: str, note_id: str, corpus: Corpus
) -> None:
    """The ABox reflects the note's current (hand-edited) tag set."""
    graph = abox.load(corpus.abox_path)
    assert (NS[note_id], DCTERMS.subject, NS[tag]) in graph


@then(
    "every note's ABox block should be regenerated from its current frontmatter"
)
def then_every_abox_block_regenerated(corpus: Corpus) -> None:
    """Every currently-existing note's ABox title matches its on-disk title."""
    graph = abox.load(corpus.abox_path)
    for note_path in corpus.notes_dir.glob("*.md"):
        note = load_markdown(note_path.read_text())
        assert (NS[note.id], DCTERMS.title, Literal(note.title)) in graph


@then(_NO_STALE_BLOCK_STEP)
def then_no_block_for_deleted_note(corpus: Corpus) -> None:
    """No triples remain for the note id whose file was deleted."""
    graph = abox.load(corpus.abox_path)
    assert not list(graph.triples((NS["stale-note"], None, None)))
