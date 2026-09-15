"""Step definitions for features/vocabulary_governance.feature.

Calls core.vocabulary directly, per the ticket's own acceptance criterion --
no CLI or MCP transport involved.
"""

import re
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib.namespace import RDFS, SKOS

from conftest import MINIMAL_TBOX
from mcp_local_notes.core import vocabulary
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.ontology import tbox

pytestmark = pytest.mark.unit

scenarios("vocabulary_governance.feature")


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """A minimal tbox with just the :Note root -- deliberately not a copy
    of the shipped bootstrap, so this feature's exact-count assertions
    (e.g. "all six declared types") stay correct regardless of whatever
    types the product's bootstrap happens to pre-seed."""
    path = tmp_path / "tbox.ttl"
    path.write_text(MINIMAL_TBOX)
    return path


_PHRASE_TO_RULE = {
    "topic already exists": Rule.TOPIC_ALREADY_EXISTS,
    "type already exists": Rule.TYPE_ALREADY_EXISTS,
}


def _quoted(text: str) -> list[str]:
    return re.findall(r'"([^"]+)"', text)


# --- Given -------------------------------------------------------------


@given(parsers.parse('the topic "{name}" already exists'))
def given_topic_exists(name: str, tbox_path: Path) -> None:
    """Pre-seed the TBox with an existing topic."""
    vocabulary.add_topic(name, tbox_path)


@given(parsers.parse('the type "{name}" already exists'))
def given_type_exists(name: str, tbox_path: Path) -> None:
    """Pre-seed the TBox with an existing type."""
    vocabulary.add_class(name, tbox_path)


@given(parsers.re(r"the topic vocabulary contains (?P<items>.+)"))
def given_topic_vocabulary_contains(items: str, tbox_path: Path) -> None:
    """Pre-seed the TBox with each quoted topic name."""
    for name in _quoted(items):
        try:
            vocabulary.add_topic(name, tbox_path)
        except NotesError:
            pass


@given(parsers.re(r"the type vocabulary contains (?P<items>.+)"))
def given_type_vocabulary_contains(items: str, tbox_path: Path) -> None:
    """Pre-seed the TBox with each quoted type name."""
    for name in _quoted(items):
        try:
            vocabulary.add_class(name, tbox_path)
        except NotesError:
            pass


# --- When ----------------------------------------------------------------


@when(parsers.parse('I add the topic "{name}"'))
@when(parsers.parse('I try to add the topic "{name}" again'))
def when_add_topic(
    name: str, tbox_path: Path, outcome: dict[str, Any]
) -> None:
    """Attempt add_topic, recording any NotesError raised."""
    try:
        vocabulary.add_topic(name, tbox_path)
    except NotesError as error:
        outcome["error"] = error


@when(parsers.parse('I add the type "{name}" as a subclass of "{parent}"'))
def when_add_type_with_parent(
    name: str, parent: str, tbox_path: Path, outcome: dict[str, Any]
) -> None:
    """Attempt add_class with an explicit parent, recording any error."""
    try:
        vocabulary.add_class(name, tbox_path, subclass_of=parent)
    except NotesError as error:
        outcome["error"] = error


@when(parsers.parse('I try to add the type "{name}" again'))
def when_add_type_again(
    name: str, tbox_path: Path, outcome: dict[str, Any]
) -> None:
    """Attempt add_class with the default parent, recording any error."""
    try:
        vocabulary.add_class(name, tbox_path)
    except NotesError as error:
        outcome["error"] = error


@when("I request the list of topics", target_fixture="result")
def when_list_topics(tbox_path: Path) -> list[str]:
    """Fetch the current topic vocabulary."""
    return vocabulary.list_topics(tbox_path)


@when("I request the list of types", target_fixture="result")
def when_list_types(tbox_path: Path) -> list[str]:
    """Fetch the current type vocabulary."""
    return vocabulary.list_types(tbox_path)


# --- Then ------------------------------------------------------------------


@then(
    parsers.parse(
        'tbox.ttl should contain a new skos:Concept "{name}" in the "{scheme}" scheme'
    )
)
def then_new_concept_in_scheme(
    name: str, scheme: str, tbox_path: Path
) -> None:
    """The topic is a skos:Concept declared in the given scheme."""
    graph = tbox.load(tbox_path)
    assert tbox.topic_exists(graph, name)
    assert (tbox.NS[name], SKOS.inScheme, tbox.NS[scheme.lstrip(":")]) in graph


@then(parsers.parse('"{name}" should now be usable as a tag on notes'))
def then_usable_as_tag(name: str, tbox_path: Path) -> None:
    """The topic shows up in the current topic vocabulary."""
    assert name in vocabulary.list_topics(tbox_path)


@then(
    parsers.parse(
        'tbox.ttl should contain a new owl:Class "{name}" with rdfs:subClassOf "{parent}"'
    )
)
def then_new_class_with_parent(
    name: str, parent: str, tbox_path: Path
) -> None:
    """The type is an owl:Class declared as a subclass of the given parent."""
    graph = tbox.load(tbox_path)
    assert tbox.type_exists(graph, name)
    assert (
        tbox.NS[name],
        RDFS.subClassOf,
        tbox.NS[parent.lstrip(":")],
    ) in graph


@then(parsers.parse('"{name}" should now be usable as a note\'s "type"'))
def then_usable_as_type(name: str, tbox_path: Path) -> None:
    """The type shows up in the current type vocabulary."""
    assert name in vocabulary.list_types(tbox_path)


@then(parsers.parse('the request should be rejected with a "{phrase}" error'))
def then_rejected_with(phrase: str, outcome: dict[str, Any]) -> None:
    """The recorded error's rule matches the expected phrase."""
    assert "error" in outcome, "expected a NotesError to have been raised"
    assert outcome["error"].rule == _PHRASE_TO_RULE[phrase]


@then(parsers.parse('I should receive exactly "{first}" and "{second}"'))
def then_receive_exactly(first: str, second: str, result: list[str]) -> None:
    """The result is exactly the two named items, in either order."""
    assert sorted(result) == sorted([first, second])


@then("I should receive all six declared types")
def then_receive_all_six_types(result: list[str]) -> None:
    """The result is exactly the six declared note types."""
    assert set(result) == {
        "Note",
        "Person",
        "Project",
        "Meeting",
        "Reference",
        "Concept",
    }
    assert len(result) == 6
