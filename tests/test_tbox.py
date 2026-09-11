"""Unit tests for ontology.tbox's low-level TBox read/write helpers."""

from pathlib import Path

import pytest
from rdflib import Graph

from mcp_local_notes.ontology import tbox

BOOTSTRAP = Path(__file__).parent.parent / "notes" / "tbox.ttl"


def _bootstrap_graph() -> Graph:
    return tbox.load(BOOTSTRAP)


@pytest.mark.unit
def test_topic_exists_false_for_unknown_topic() -> None:
    """An undeclared topic reports as not existing."""
    graph = _bootstrap_graph()
    assert tbox.topic_exists(graph, "knowledge-graphs") is False


@pytest.mark.unit
def test_add_topic_triples_then_exists() -> None:
    """A topic just added reports as existing."""
    graph = _bootstrap_graph()
    tbox.add_topic_triples(graph, "knowledge-graphs")
    assert tbox.topic_exists(graph, "knowledge-graphs") is True


@pytest.mark.unit
def test_type_exists_true_for_note_root() -> None:
    """The bootstrap :Note root class reports as existing."""
    graph = _bootstrap_graph()
    assert tbox.type_exists(graph, "Note") is True


@pytest.mark.unit
def test_add_class_triples_then_exists() -> None:
    """A type just added reports as existing."""
    graph = _bootstrap_graph()
    tbox.add_class_triples(graph, "Recipe")
    assert tbox.type_exists(graph, "Recipe") is True


@pytest.mark.unit
def test_list_topic_names_sorted() -> None:
    """Topic names come back sorted, regardless of insertion order."""
    graph = _bootstrap_graph()
    tbox.add_topic_triples(graph, "semantic-web")
    tbox.add_topic_triples(graph, "knowledge-graphs")
    assert tbox.list_topic_names(graph) == ["knowledge-graphs", "semantic-web"]


@pytest.mark.unit
def test_list_type_names_includes_note_root() -> None:
    """list_type_names includes the :Note root, not just added subclasses."""
    graph = _bootstrap_graph()
    assert tbox.list_type_names(graph) == ["Note"]


@pytest.mark.unit
def test_save_then_load_round_trips(tmp_path: Path) -> None:
    """A graph saved to disk and reloaded still has what was added."""
    graph = _bootstrap_graph()
    tbox.add_topic_triples(graph, "knowledge-graphs")
    path = tmp_path / "tbox.ttl"
    tbox.save(graph, path)
    reloaded = tbox.load(path)
    assert tbox.topic_exists(reloaded, "knowledge-graphs") is True
