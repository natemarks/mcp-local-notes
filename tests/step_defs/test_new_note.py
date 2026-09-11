"""Step definitions for features/new_note.feature.

Calls core.notes.new_note directly, per the ticket's own acceptance
criterion -- no CLI or MCP transport involved.
"""

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from conftest import mint_note_with_id, seed_tbox_with_defaults
from mcp_local_notes.core import notes, vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.ontology import abox, tbox

BOOTSTRAP_TBOX = Path(__file__).parent.parent.parent / "notes" / "tbox.ttl"

pytestmark = pytest.mark.unit

scenarios("new_note.feature")

_PHRASE_TO_RULE = {
    "duplicate title": Rule.DUPLICATE_TITLE,
    "duplicate alias": Rule.DUPLICATE_ALIAS,
    "unknown topic": Rule.UNKNOWN_TOPIC,
    "unknown type": Rule.UNKNOWN_TYPE,
    "missing required field: tags": Rule.MISSING_REQUIRED_FIELD,
}

_TITLE_RE = re.compile(r'title "([^"]+)"')
_TAGS_RE = re.compile(r'tags? "([^"]+)"')
_TYPE_RE = re.compile(r'type "([^"]+)"')
_ALIAS_RE = re.compile(r'alias "([^"]+)"')
_APPROVE_RE = re.compile(r'approve adding topic "([^"]+)"')


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """Every scenario's Background assumes knowledge-graphs/Concept already
    exist, so seed them here rather than relying on Background step order
    (the Background creates a note BEFORE its own vocabulary-setup steps)."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    seed_tbox_with_defaults(path)
    return path


def _parse_request(text: str) -> dict[str, Any]:
    """Extract title/tags/type/alias/approve_topics from free-form step text."""
    title_match = _TITLE_RE.search(text)
    assert title_match is not None, f"no title found in: {text!r}"
    request: dict[str, Any] = {
        "title": title_match.group(1),
        "tags": ["knowledge-graphs"],
        "note_type": "Concept",
        "aliases": [],
        "approve_topics": [],
    }
    if "no tags" in text:
        request["tags"] = []
    else:
        tags_match = _TAGS_RE.search(text)
        if tags_match:
            request["tags"] = [tags_match.group(1)]
    type_match = _TYPE_RE.search(text)
    if type_match:
        request["note_type"] = type_match.group(1)
    alias_match = _ALIAS_RE.search(text)
    if alias_match:
        request["aliases"] = [alias_match.group(1)]
    approve_match = _APPROVE_RE.search(text)
    if approve_match:
        request["approve_topics"] = [approve_match.group(1)]
    return request


# --- Given -------------------------------------------------------------


@given(
    parsers.re(
        r'the notes directory contains a note titled "(?P<title>[^"]+)"'
    )
)
@given(parsers.parse('a note titled "{title}" exists'))
def given_note_titled(title: str, corpus: Corpus) -> None:
    """Pre-seed the corpus with an existing note titled `title`."""
    notes.new_note(
        title=title,
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )


@given(parsers.parse('a note with id "{note_id}" already exists'))
def given_note_with_id(note_id: str, corpus: Corpus) -> None:
    """Pre-seed the corpus with a note whose id is exactly note_id."""
    mint_note_with_id(note_id, corpus)


@given(parsers.parse('the topic vocabulary contains "{name}"'))
def given_topic_vocabulary_has(name: str, tbox_path: Path) -> None:
    """Pre-seed the TBox with an existing topic, idempotently."""
    try:
        vocabulary.add_topic(name, tbox_path)
    except NotesError:
        pass


@given(parsers.parse('the type vocabulary contains "{name}"'))
def given_type_vocabulary_has(name: str, tbox_path: Path) -> None:
    """Pre-seed the TBox with an existing type, idempotently."""
    try:
        vocabulary.add_class(name, tbox_path)
    except NotesError:
        pass


# --- When ------------------------------------------------------------------


@when(parsers.re(r"I request a new note with (?P<rest>.+)"))
def when_request_new_note(
    rest: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Attempt new_note with the parsed request, recording the outcome."""
    request = _parse_request(rest)
    outcome["notes_before"] = sorted(
        p.name for p in corpus.notes_dir.glob("*.md")
    )
    outcome["abox_before"] = corpus.abox_path.read_text()
    try:
        outcome["note"] = notes.new_note(
            title=request["title"],
            tags=request["tags"],
            note_type=request["note_type"],
            corpus=corpus,
            aliases=request["aliases"],
            approve_topics=request["approve_topics"],
        )
    except NotesError as error:
        outcome["error"] = error


# --- Then --------------------------------------------------------------


@then(parsers.parse('a new note file "{filename}" should exist'))
def then_note_file_exists(filename: str, corpus: Corpus) -> None:
    """The note file exists in the notes directory."""
    assert (corpus.notes_dir / filename).exists()


@then(parsers.parse('the note "{filename}" should be created successfully'))
def then_note_created_successfully(
    filename: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """No error was recorded, and the note file exists."""
    assert "error" not in outcome
    assert (corpus.notes_dir / filename).exists()


@then(parsers.parse('its frontmatter "{field}" should be "{value}"'))
def then_frontmatter_field_is(
    field: str, value: str, outcome: dict[str, Any]
) -> None:
    """The created note's field equals the expected value."""
    assert getattr(outcome["note"], field) == value


@then(parsers.parse('its frontmatter "{field}" date should be set to today'))
def then_frontmatter_date_is_today(
    field: str, outcome: dict[str, Any]
) -> None:
    """The created note's date field is today's date."""
    assert getattr(outcome["note"], field) == date.today().isoformat()


@then(parsers.parse('its frontmatter "{field}" should include "{value}"'))
def then_frontmatter_field_includes(
    field: str, value: str, outcome: dict[str, Any]
) -> None:
    """The created note's list field includes the expected value."""
    assert value in getattr(outcome["note"], field)


@then(
    parsers.parse(
        'an ABox block for "{note_id}" should be appended to abox.ttl'
    )
)
def then_abox_block_appended(note_id: str, corpus: Corpus) -> None:
    """The ABox has at least one triple for the note's subject."""
    graph = abox.load(corpus.abox_path)
    assert list(graph.triples((tbox.NS[note_id], None, None)))


@then("no new note file should be created")
def then_no_new_note_file(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """The notes directory's file listing is unchanged since the request."""
    notes_after = sorted(p.name for p in corpus.notes_dir.glob("*.md"))
    assert notes_after == outcome["notes_before"]


@then("abox.ttl should be unchanged")
def then_abox_unchanged(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """abox.ttl's content is unchanged since the request."""
    assert corpus.abox_path.read_text() == outcome["abox_before"]


@then(parsers.parse('a new skos:Concept "{name}" should be added to tbox.ttl'))
def then_new_concept_added(name: str, tbox_path: Path) -> None:
    """The named topic is now declared in the TBox."""
    graph = tbox.load(tbox_path)
    assert tbox.topic_exists(graph, name)


@then(parsers.parse('the request should be rejected with a "{phrase}" error'))
@then(parsers.parse('the request should be rejected with an "{phrase}" error'))
def then_rejected_with(phrase: str, outcome: dict[str, Any]) -> None:
    """The recorded error's rule matches the expected phrase."""
    assert "error" in outcome, "expected a NotesError to have been raised"
    assert outcome["error"].rule == _PHRASE_TO_RULE[phrase]


@then(
    parsers.parse(
        'the error should name "{name}" as not present in the topic vocabulary'
    )
)
def then_error_names_topic(name: str, outcome: dict[str, Any]) -> None:
    """The recorded error's details name the offending topic."""
    assert outcome["error"].details.get("topic") == name


@then(
    parsers.parse(
        'the error should name "{name}" as not declared in the ontology'
    )
)
def then_error_names_type(name: str, outcome: dict[str, Any]) -> None:
    """The recorded error's details name the offending type."""
    assert outcome["error"].details.get("type") == name
