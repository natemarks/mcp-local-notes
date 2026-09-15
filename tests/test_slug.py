"""Unit tests for ontology.slug.normalize (see the id/slug decision)."""

import pytest

from mcp_local_notes.ontology.slug import normalize


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,expected",
    [
        ("SPARQL basics", "sparql-basics"),
        ("Sparql Basics", "sparql-basics"),
        ("RDF vs. property graphs", "rdf-vs-property-graphs"),
        ("café", "cafe"),
        ("  leading and trailing  ", "leading-and-trailing"),
        ("multiple---hyphens", "multiple-hyphens"),
    ],
)
def test_normalize(text: str, expected: str) -> None:
    """normalize() lowercases, transliterates, hyphenates, and trims."""
    assert normalize(text) == expected
