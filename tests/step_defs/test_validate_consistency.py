"""Step definitions for features/validate_consistency.feature.

Calls core.validate.validate directly, per the ticket's own acceptance
criterion -- no CLI or MCP transport involved.
"""

import shutil
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from conftest import (
    REMOVE_FIELD,
    mint_note_then_retitle,
    mint_sparql_basics,
    rewrite_frontmatter,
    seed_tbox_with_defaults,
)
from mcp_local_notes.core import validate, vocabulary
from mcp_local_notes.core.config import Corpus

BOOTSTRAP_TBOX = Path(__file__).parent.parent.parent / "notes" / "tbox.ttl"

pytestmark = pytest.mark.unit

scenarios("validate_consistency.feature")

_PHRASE_TO_TYPE = {
    "missing required field: tags": "MISSING_REQUIRED_FIELD",
    "duplicate title": "DUPLICATE_TITLE",
    "unknown topic": "UNKNOWN_TOPIC",
    "unknown type": "UNKNOWN_TYPE",
    "dangling reference": {"RELATED_NOTE_NOT_FOUND", "PART_OF_NOTE_NOT_FOUND"},
    "stale ABox entry": "STALE_ABOX_ENTRY",
    "filename/id mismatch": "FILENAME_ID_MISMATCH",
}


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """Pre-seed every topic/type this feature file's scenarios assume
    already exists, since vocabulary governance isn't what's under test."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    seed_tbox_with_defaults(path)
    return path


def _one_note(corpus: Corpus, **overrides: object) -> str:
    """Create a single valid note, returning its id."""
    note = mint_sparql_basics(corpus)
    if overrides:
        rewrite_frontmatter(corpus.notes_dir / f"{note.id}.md", **overrides)
    return note.id


# --- Given -------------------------------------------------------------


@given(
    "all notes have required fields, unique ids/titles/aliases, valid tags "
    "and types, valid references, and up-to-date ABox blocks"
)
def given_clean_corpus(corpus: Corpus) -> None:
    """A single, entirely valid note -- new_note guarantees consistency."""
    _one_note(corpus)


@given(parsers.parse('a note is missing its "{field}" field'))
def given_note_missing_field(field: str, corpus: Corpus) -> None:
    """Pre-seed a note whose raw frontmatter is missing the named field."""
    _one_note(corpus, **{field: REMOVE_FIELD})


@given("two notes share the same title")
def given_two_notes_share_a_title(corpus: Corpus) -> None:
    """Pre-seed two notes with the same title (hand-edited, since new_note
    itself would reject this)."""
    _one_note(corpus)
    mint_note_then_retitle(corpus, "Something else", "SPARQL basics")


@given("a note uses a tag that is not declared in tbox.ttl")
def given_note_with_unknown_tag(corpus: Corpus) -> None:
    """Pre-seed a note with an unapproved, undeclared tag."""
    _one_note(corpus, tags=["knowledge-graphs", "quantum-computing"])


@given(
    parsers.parse('a note\'s "type" is not declared as a class in tbox.ttl')
)
def given_note_with_unknown_type(corpus: Corpus) -> None:
    """Pre-seed a note with an undeclared type."""
    _one_note(corpus, type="Widget")


@given(
    parsers.parse(
        'a note\'s "related" field references an id that does not exist'
    )
)
def given_note_with_dangling_related(corpus: Corpus) -> None:
    """Pre-seed a note whose related field points at a nonexistent note."""
    _one_note(corpus, related=["does-not-exist"])


@given("a note's frontmatter differs from its current ABox block in abox.ttl")
def given_note_frontmatter_differs_from_abox(corpus: Corpus) -> None:
    """Pre-seed a note hand-edited after creation, leaving abox.ttl stale."""
    vocabulary.add_topic("semantic-web", corpus.tbox_path)
    _one_note(corpus, tags=["knowledge-graphs", "semantic-web"])


@given(
    parsers.parse('a note file is named differently from its frontmatter "id"')
)
def given_note_filename_mismatch(corpus: Corpus) -> None:
    """Pre-seed a note, then rename its file without updating its id."""
    note_id = _one_note(corpus)
    (corpus.notes_dir / f"{note_id}.md").rename(
        corpus.notes_dir / "renamed.md"
    )


@given("the corpus has one or more issues")
def given_corpus_has_issues(corpus: Corpus) -> None:
    """Pre-seed a note with a missing required field, as one example issue."""
    _one_note(corpus, tags=REMOVE_FIELD)


# --- When ------------------------------------------------------------------


@when("I run validation", target_fixture="result")
@when(
    "I run validation with structured output requested",
    target_fixture="result",
)
def when_run_validation(
    corpus: Corpus, outcome: dict[str, Any]
) -> dict[str, Any]:
    """Run validate, snapshotting every file first to prove none change."""
    outcome["notes_before"] = {
        p.name: p.read_text() for p in corpus.notes_dir.glob("*.md")
    }
    outcome["tbox_before"] = corpus.tbox_path.read_text()
    outcome["abox_before"] = corpus.abox_path.read_text()
    return validate.build_report(validate.validate(corpus))


# --- Then --------------------------------------------------------------


@then("the report should show zero issues")
def then_zero_issues(result: dict[str, Any]) -> None:
    """The report's issues list is empty."""
    assert result["issues"] == []


@then("validation should exit with a zero (success) status")
def then_exit_zero(result: dict[str, Any]) -> None:
    """The report is ok."""
    assert result["ok"] is True


@then("validation should exit with a non-zero status")
def then_exit_nonzero(result: dict[str, Any]) -> None:
    """The report is not ok."""
    assert result["ok"] is False


@then(
    parsers.parse('the report should list a "{phrase}" issue naming that note')
)
@then(
    parsers.parse(
        'the report should list an "{phrase}" issue naming that note'
    )
)
@then(
    parsers.parse(
        'the report should list an "{phrase}" issue naming that note and tag'
    )
)
@then(
    parsers.parse(
        'the report should list an "{phrase}" issue naming that note and type'
    )
)
def then_lists_issue(phrase: str, result: dict[str, Any]) -> None:
    """An issue of the type the phrase maps to is present in the report."""
    expected_types = _PHRASE_TO_TYPE[phrase]
    if isinstance(expected_types, str):
        expected_types = {expected_types}
    assert any(issue["type"] in expected_types for issue in result["issues"])


@then(
    parsers.parse(
        'the report should list a "{phrase}" issue naming both notes'
    )
)
def then_lists_issue_naming_both(phrase: str, result: dict[str, Any]) -> None:
    """Exactly one issue of the expected type names both conflicting notes."""
    expected_type = _PHRASE_TO_TYPE[phrase]
    matching = [i for i in result["issues"] if i["type"] == expected_type]
    assert len(matching) == 1
    assert len(matching[0]["details"]["note_ids"]) == 2


@then(
    'the report should list a "dangling reference" issue naming the note '
    "and the missing id"
)
def then_lists_dangling_reference(result: dict[str, Any]) -> None:
    """Exactly one dangling-reference issue names the missing id."""
    expected_types = _PHRASE_TO_TYPE["dangling reference"]
    matches = [i for i in result["issues"] if i["type"] in expected_types]
    assert len(matches) == 1
    assert matches[0]["details"]["missing_id"] == "does-not-exist"


@then("no note file should be changed")
def then_no_note_file_changed(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """Every note file's content is identical to before validate() ran."""
    notes_after = {
        p.name: p.read_text() for p in corpus.notes_dir.glob("*.md")
    }
    assert notes_after == outcome["notes_before"]


@then("tbox.ttl and abox.ttl should be unchanged")
def then_tbox_abox_unchanged(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """tbox.ttl and abox.ttl are identical to before validate() ran."""
    assert corpus.tbox_path.read_text() == outcome["tbox_before"]
    assert corpus.abox_path.read_text() == outcome["abox_before"]


@then("I should receive a machine-readable (e.g. JSON) list of issues")
def then_receive_json_list(result: dict[str, Any]) -> None:
    """The report's issues field is a list."""
    assert isinstance(result["issues"], list)


@then(
    "each issue should include a type, an affected note id, and a "
    "human-readable message"
)
def then_each_issue_has_fields(result: dict[str, Any]) -> None:
    """Every issue dict carries type, note_id, and message keys."""
    for issue in result["issues"]:
        assert {"type", "note_id", "message"} <= issue.keys()
