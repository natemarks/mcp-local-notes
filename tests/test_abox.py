"""Unit tests for ontology.abox's graph-based ABox regeneration.

Predicate mapping and the "remove all triples for the subject, add the
fresh ones, reserialize" mechanism are decisions recorded on the project's
wayfinder map (see the "Decide the TBox structure" ticket).
"""

from pathlib import Path

import pytest
from rdflib import RDF, Graph, Literal
from rdflib.namespace import DCTERMS, SKOS

from mcp_local_notes.core.models import Note
from mcp_local_notes.ontology import abox
from mcp_local_notes.ontology.tbox import NS


def _note(**overrides: object) -> Note:
    """A convenience Note builder for tests -- ontology.abox itself only
    ever sees the plain dict from .to_frontmatter(), never this type."""
    defaults: dict = {
        "id": "sparql-basics",
        "title": "SPARQL basics",
        "tags": ["knowledge-graphs"],
        "type": "Concept",
        "created": "2026-09-11",
        "modified": "2026-09-11",
    }
    defaults.update(overrides)
    return Note(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_replace_note_adds_the_documented_predicates() -> None:
    """Every frontmatter field maps to its documented ABox predicate."""
    graph = Graph()
    note = _note(
        aliases=["Intro to SPARQL"],
        related=["intro-to-sparql"],
        part_of="knowledge-graphs-project",
    )
    abox.replace_note(graph, note.id, note.to_frontmatter())

    subject = NS["sparql-basics"]
    assert (subject, RDF.type, NS["Concept"]) in graph
    assert (subject, DCTERMS.title, Literal("SPARQL basics")) in graph
    assert (subject, SKOS.altLabel, Literal("Intro to SPARQL")) in graph
    assert (subject, DCTERMS.subject, NS["knowledge-graphs"]) in graph
    assert (subject, NS.status, Literal("active")) in graph
    assert (subject, DCTERMS.created, Literal("2026-09-11")) in graph
    assert (subject, DCTERMS.modified, Literal("2026-09-11")) in graph
    assert (subject, NS.relatesTo, NS["intro-to-sparql"]) in graph
    assert (subject, NS.partOf, NS["knowledge-graphs-project"]) in graph


@pytest.mark.unit
def test_replace_note_omits_part_of_when_unset() -> None:
    """No :partOf triple exists when part_of is None."""
    graph = Graph()
    note = _note()
    abox.replace_note(graph, note.id, note.to_frontmatter())
    assert (NS["sparql-basics"], NS.partOf, None) not in graph


@pytest.mark.unit
def test_replace_note_replaces_rather_than_accumulates() -> None:
    """Re-running replace_note leaves exactly one entry for the subject."""
    graph = Graph()
    note = _note(tags=["knowledge-graphs"])
    abox.replace_note(graph, note.id, note.to_frontmatter())

    updated = _note(tags=["knowledge-graphs", "semantic-web"])
    abox.replace_note(graph, updated.id, updated.to_frontmatter())

    subject = NS["sparql-basics"]
    tag_triples = list(graph.triples((subject, DCTERMS.subject, None)))
    assert len(tag_triples) == 2


@pytest.mark.unit
def test_replace_note_does_not_disturb_other_notes() -> None:
    """Regenerating one note's entry leaves every other note's entry intact."""
    graph = Graph()
    abox.replace_note(graph, "sparql-basics", _note().to_frontmatter())
    abox.replace_note(
        graph,
        "intro-to-sparql",
        _note(id="intro-to-sparql", title="Intro to SPARQL").to_frontmatter(),
    )
    abox.replace_note(
        graph,
        "sparql-basics",
        _note(title="SPARQL basics (updated)").to_frontmatter(),
    )

    assert (
        NS["intro-to-sparql"],
        DCTERMS.title,
        Literal("Intro to SPARQL"),
    ) in graph
    assert (
        NS["sparql-basics"],
        DCTERMS.title,
        Literal("SPARQL basics (updated)"),
    ) in graph


@pytest.mark.unit
def test_remove_note_drops_every_triple_for_the_subject() -> None:
    """remove_note leaves no triples with that subject."""
    graph = Graph()
    abox.replace_note(graph, "sparql-basics", _note().to_frontmatter())
    abox.remove_note(graph, "sparql-basics")
    assert not list(graph.triples((NS["sparql-basics"], None, None)))


@pytest.mark.unit
def test_save_then_load_round_trips(tmp_path: Path) -> None:
    """A graph saved to disk and reloaded still has what was added."""
    graph = Graph()
    abox.replace_note(graph, "sparql-basics", _note().to_frontmatter())
    path = tmp_path / "abox.ttl"
    abox.save(graph, path)
    reloaded = abox.load(path)
    assert (
        NS["sparql-basics"],
        DCTERMS.title,
        Literal("SPARQL basics"),
    ) in reloaded
