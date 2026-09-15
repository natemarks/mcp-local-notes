"""Unit tests for core.vocabulary: add_topic, add_class, list_topics, list_types."""

import shutil
from pathlib import Path

import pytest

from mcp_local_notes.core import vocabulary
from mcp_local_notes.core.errors import NotesError, Rule

BOOTSTRAP = Path(__file__).parent.parent / "notes" / "tbox.ttl"


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """An isolated, per-test copy of the bootstrap tbox.ttl."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP, path)
    return path


@pytest.mark.unit
def test_add_topic_adds_a_new_concept(tbox_path: Path) -> None:
    """add_topic makes the topic show up in list_topics."""
    vocabulary.add_topic("semantic-web", tbox_path)
    assert "semantic-web" in vocabulary.list_topics(tbox_path)


@pytest.mark.unit
def test_add_topic_rejects_an_existing_topic(tbox_path: Path) -> None:
    """A duplicate add_topic raises TOPIC_ALREADY_EXISTS."""
    vocabulary.add_topic("knowledge-graphs", tbox_path)
    with pytest.raises(NotesError) as exc_info:
        vocabulary.add_topic("knowledge-graphs", tbox_path)
    assert exc_info.value.rule == Rule.TOPIC_ALREADY_EXISTS


@pytest.mark.unit
def test_add_class_adds_a_new_type(tbox_path: Path) -> None:
    """add_class makes the type show up in list_types."""
    vocabulary.add_class("Recipe", tbox_path)
    assert "Recipe" in vocabulary.list_types(tbox_path)


@pytest.mark.unit
def test_add_class_rejects_an_existing_type(tbox_path: Path) -> None:
    """A duplicate add_class raises TYPE_ALREADY_EXISTS."""
    vocabulary.add_class("Concept", tbox_path)
    with pytest.raises(NotesError) as exc_info:
        vocabulary.add_class("Concept", tbox_path)
    assert exc_info.value.rule == Rule.TYPE_ALREADY_EXISTS


@pytest.mark.unit
def test_list_topics_returns_current_vocabulary(tbox_path: Path) -> None:
    """list_topics returns every declared topic, sorted."""
    vocabulary.add_topic("knowledge-graphs", tbox_path)
    vocabulary.add_topic("semantic-web", tbox_path)
    assert vocabulary.list_topics(tbox_path) == [
        "knowledge-graphs",
        "semantic-web",
    ]


@pytest.mark.unit
def test_list_types_returns_current_vocabulary(tbox_path: Path) -> None:
    """list_types returns every declared type, including the :Note root and
    the bootstrap's pre-seeded Divio documentation types."""
    for name in ("Person", "Project", "Meeting", "Article", "Concept"):
        vocabulary.add_class(name, tbox_path)
    assert vocabulary.list_types(tbox_path) == [
        "Article",
        "Concept",
        "Explanation",
        "How-to",
        "Meeting",
        "Note",
        "Person",
        "Project",
        "Reference",
        "Tutorial",
    ]
