"""ABox read/write: per-note facts regenerated from frontmatter.

Predicate mapping and the graph-based regeneration mechanism (remove all
triples for the subject, add the fresh ones, reserialize the whole graph)
are decisions recorded on the project's wayfinder map (see "Decide the
TBox structure").
"""

from pathlib import Path
from typing import Any

from rdflib import RDF, Graph, Literal
from rdflib.namespace import DCTERMS, SKOS

from mcp_local_notes.ontology.tbox import NS


def load(path: Path) -> Graph:
    """Parse an ABox Turtle file into a graph."""
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def save(graph: Graph, path: Path) -> None:
    """Serialize an ABox graph back to a Turtle file."""
    graph.bind("", NS, override=True)
    graph.bind("dcterms", DCTERMS)
    graph.bind("skos", SKOS)
    graph.serialize(destination=path, format="turtle")


def replace_note(graph: Graph, note_id: str, frontmatter: dict[str, Any]) -> None:
    """Remove all existing triples for note_id, add the ones the given
    frontmatter dict implies (see Note.to_frontmatter for its shape)."""
    remove_note(graph, note_id)
    subject = NS[note_id]
    graph.add((subject, RDF.type, NS[frontmatter["type"]]))
    graph.add((subject, DCTERMS.title, Literal(frontmatter["title"])))
    graph.add((subject, NS.status, Literal(frontmatter["status"])))
    graph.add((subject, DCTERMS.created, Literal(frontmatter["created"])))
    graph.add((subject, DCTERMS.modified, Literal(frontmatter["modified"])))
    for alias in frontmatter["aliases"]:
        graph.add((subject, SKOS.altLabel, Literal(alias)))
    for tag in frontmatter["tags"]:
        graph.add((subject, DCTERMS.subject, NS[tag]))
    for related_id in frontmatter["related"]:
        graph.add((subject, NS.relatesTo, NS[related_id]))
    if frontmatter["part_of"]:
        graph.add((subject, NS.partOf, NS[frontmatter["part_of"]]))


def remove_note(graph: Graph, note_id: str) -> None:
    """Remove every triple with note_id's subject, if any exist."""
    subject = NS[note_id]
    for triple in list(graph.triples((subject, None, None))):
        graph.remove(triple)
