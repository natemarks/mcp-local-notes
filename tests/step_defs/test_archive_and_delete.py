"""Step definitions for features/archive_and_delete.feature.

Calls core.notes functions (and core.validate for the post-delete
verification scenario) directly, per the ticket's own acceptance
criterion -- no CLI or MCP transport involved.
"""

import shutil
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from conftest import (
    mint_note_with_id,
    mint_sparql_basics,
    seed_tbox_with_defaults,
)
from mcp_local_notes.core import notes, validate
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError
from mcp_local_notes.ontology import abox
from mcp_local_notes.ontology.tbox import NS

BOOTSTRAP_TBOX = Path(__file__).parent.parent.parent / "notes" / "tbox.ttl"

pytestmark = pytest.mark.unit

scenarios("archive_and_delete.feature")


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """Pre-seed the standard vocabulary this feature file's Background note
    needs, since vocabulary governance isn't what's under test."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    seed_tbox_with_defaults(path)
    return path


# --- Given -------------------------------------------------------------


@given(parsers.parse('a note "{note_id}" exists'))
def given_note_exists(note_id: str, corpus: Corpus) -> None:
    """note_id is already a normalized slug, so using it as the title mints
    exactly that id."""
    if note_id == "sparql-basics":
        mint_sparql_basics(corpus)
    else:
        mint_note_with_id(note_id, corpus)


@given(parsers.parse('no other note references "{note_id}"'))
def given_no_other_note_references(
    note_id: str,  # pylint: disable=unused-argument
) -> None:
    """Already true by construction -- the Background note has no related
    references and no other note has been created yet."""


@given(
    parsers.parse(
        'a note "{referencing_id}" has "related" referencing "{note_id}"'
    )
)
def given_note_has_related_reference(
    referencing_id: str, note_id: str, corpus: Corpus
) -> None:
    """Pre-seed a second note whose related field points at note_id."""
    mint_note_with_id(referencing_id, corpus)
    notes.update_note(referencing_id, corpus, add_related=[note_id])


# --- When ------------------------------------------------------------------


@when(parsers.parse('I archive note "{note_id}"'))
def when_archive_note(
    note_id: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Archive the named note."""
    outcome["note"] = notes.archive_note(note_id, corpus)


@when(parsers.parse('I request to delete "{note_id}"'))
@when(parsers.parse('I request to delete "{note_id}" without confirmation'))
def when_request_delete(
    note_id: str, corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """Attempt an unconfirmed delete, recording any NotesError raised."""
    try:
        notes.delete_note(note_id, corpus)
    except NotesError as error:
        outcome["error"] = error


@when(parsers.parse('I confirm deletion of "{note_id}" despite the warning'))
def when_confirm_deletion(note_id: str, corpus: Corpus) -> None:
    """Delete the named note with confirmation."""
    notes.delete_note(note_id, corpus, confirm=True)


# --- Then --------------------------------------------------------------


@then(parsers.parse('its "{field}" should be "{value}"'))
def then_field_is(field: str, value: str, outcome: dict[str, Any]) -> None:
    """The recorded note's field equals the expected value."""
    assert getattr(outcome["note"], field) == value


@then(parsers.parse('the note file "{filename}" should still exist'))
def then_note_file_still_exists(filename: str, corpus: Corpus) -> None:
    """The note file still exists in the notes directory."""
    assert (corpus.notes_dir / filename).exists()


@then(parsers.parse('the ABox block for "{note_id}" should still exist'))
def then_abox_block_still_exists(note_id: str, corpus: Corpus) -> None:
    """The ABox still has at least one triple for the note's subject."""
    graph = abox.load(corpus.abox_path)
    assert list(graph.triples((NS[note_id], None, None)))


@then("the note file should be removed")
def then_note_file_removed(corpus: Corpus) -> None:
    """No note files remain in the notes directory."""
    assert not list(corpus.notes_dir.glob("*.md"))


@then(parsers.parse('the note file "{filename}" should be removed'))
def then_named_note_file_removed(filename: str, corpus: Corpus) -> None:
    """The named note file no longer exists."""
    assert not (corpus.notes_dir / filename).exists()


@then("its ABox block should be removed from abox.ttl")
def then_abox_block_removed(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """No triples remain for sparql-basics, and the delete succeeded."""
    graph = abox.load(corpus.abox_path)
    assert not list(graph.triples((NS["sparql-basics"], None, None)))
    assert "error" not in outcome


@then("the request should be rejected")
def then_request_rejected(outcome: dict[str, Any]) -> None:
    """A NotesError was recorded."""
    assert "error" in outcome, "expected a NotesError to have been raised"


@then(
    parsers.parse(
        'I should be told that "{referencing_id}" references "{note_id}"'
    )
)
def then_told_of_reference(
    referencing_id: str, note_id: str, outcome: dict[str, Any]
) -> None:
    """The recorded error names the referencing note and the target note."""
    error = outcome["error"]
    assert error.details["note_id"] == note_id
    assert referencing_id in error.details["referencing_note_ids"]


@then(
    parsers.parse(
        'a subsequent validation run should report a "dangling reference" '
        'issue for "{note_id}"'
    )
)
def then_subsequent_validation_reports_dangling(
    note_id: str, corpus: Corpus
) -> None:
    """A subsequent validate() run flags the now-dangling reference."""
    issues = validate.validate(corpus)
    assert any(
        issue.type.value
        in ("RELATED_NOTE_NOT_FOUND", "PART_OF_NOTE_NOT_FOUND")
        and issue.note_id == note_id
        for issue in issues
    )
