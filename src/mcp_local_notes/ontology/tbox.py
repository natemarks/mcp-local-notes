"""TBox read/write: the controlled topic vocabulary and note-type hierarchy.

Namespace, SKOS/OWL shape, and predicate choices are decisions recorded on
the project's wayfinder map (see the "Decide the TBox structure" ticket).
"""

from pathlib import Path

from rdflib import RDF, RDFS, Graph, Literal, Namespace
from rdflib.namespace import OWL, SKOS

NS = Namespace("https://notes.natenite.net/ontology#")
TOPICS_SCHEME = NS.topics
ROOT_TYPE = "Note"


def load(path: Path) -> Graph:
    """Parse a TBox Turtle file into a graph."""
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def save(graph: Graph, path: Path) -> None:
    """Serialize a TBox graph back to a Turtle file."""
    graph.bind("", NS, override=True)
    graph.bind("skos", SKOS)
    graph.bind("owl", OWL)
    graph.serialize(destination=path, format="turtle")


def topic_exists(graph: Graph, name: str) -> bool:
    """Whether a skos:Concept with this local name is already declared."""
    return (NS[name], RDF.type, SKOS.Concept) in graph


def type_exists(graph: Graph, name: str) -> bool:
    """Whether an owl:Class with this local name is already declared."""
    return (NS[name], RDF.type, OWL.Class) in graph


def add_topic_triples(graph: Graph, name: str) -> None:
    """Declare a new flat skos:Concept in the :topics scheme."""
    subject = NS[name]
    graph.add((subject, RDF.type, SKOS.Concept))
    graph.add((subject, SKOS.prefLabel, Literal(name, lang="en")))
    graph.add((subject, SKOS.inScheme, TOPICS_SCHEME))


def add_class_triples(
    graph: Graph, name: str, subclass_of: str = ROOT_TYPE
) -> None:
    """Declare a new owl:Class as a subclass of an existing note type."""
    subject = NS[name]
    graph.add((subject, RDF.type, OWL.Class))
    graph.add((subject, RDFS.subClassOf, NS[subclass_of]))


def list_topic_names(graph: Graph) -> list[str]:
    """Every declared topic's local name, sorted."""
    return sorted(
        str(subject).rsplit("#", maxsplit=1)[-1]
        for subject in graph.subjects(RDF.type, SKOS.Concept)
    )


def list_type_names(graph: Graph) -> list[str]:
    """Every declared note type's local name (including the :Note root), sorted."""
    return sorted(
        str(subject).rsplit("#", maxsplit=1)[-1]
        for subject in graph.subjects(RDF.type, OWL.Class)
    )
