"""Vocabulary governance: add_topic, add_class, list_topics, list_types.

Growing the controlled vocabulary is always an explicit, auditable action
(US-4.1) -- these are the only operations that ever write to tbox.ttl.
"""

from pathlib import Path

from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.ontology import tbox


def add_topic(name: str, tbox_path: Path) -> None:
    """Declare a new topic, or reject one that already exists."""
    graph = tbox.load(tbox_path)
    if tbox.topic_exists(graph, name):
        raise NotesError(
            Rule.TOPIC_ALREADY_EXISTS,
            f"topic already exists: {name!r}",
            {"topic": name},
        )
    tbox.add_topic_triples(graph, name)
    tbox.save(graph, tbox_path)


def add_class(
    name: str, tbox_path: Path, subclass_of: str = tbox.ROOT_TYPE
) -> None:
    """Declare a new note type, or reject one that already exists."""
    graph = tbox.load(tbox_path)
    if tbox.type_exists(graph, name):
        raise NotesError(
            Rule.TYPE_ALREADY_EXISTS,
            f"type already exists: {name!r}",
            {"type": name},
        )
    tbox.add_class_triples(graph, name, subclass_of)
    tbox.save(graph, tbox_path)


def list_topics(tbox_path: Path) -> list[str]:
    """Every topic currently in the controlled vocabulary."""
    return tbox.list_topic_names(tbox.load(tbox_path))


def list_types(tbox_path: Path) -> list[str]:
    """Every note type currently declared."""
    return tbox.list_type_names(tbox.load(tbox_path))
