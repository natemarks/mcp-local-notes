"""Fixtures shared across pytest-bdd step-definition modules."""

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from mcp_local_notes.core import notes, vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.models import Note, parse_frontmatter

BOOTSTRAP_TBOX = Path(__file__).parent.parent / "notes" / "tbox.ttl"
EMPTY_ABOX = "@prefix : <https://notes.natenite.net/ontology#> .\n"
MINIMAL_TBOX = """\
@prefix : <https://notes.natenite.net/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

:Note a owl:Class .
:topics a skos:ConceptScheme .
"""


def seed_tbox_with_defaults(path: Path) -> None:
    """Pre-seed the standard "knowledge-graphs"/"Concept" vocabulary most
    feature files' scenarios assume already exists."""
    vocabulary.add_topic("knowledge-graphs", path)
    vocabulary.add_class("Concept", path)


def build_seeded_corpus(tmp_path: Path) -> Corpus:
    """A corpus with a fresh bootstrap tbox.ttl (knowledge-graphs/Concept
    pre-seeded) and an empty abox.ttl -- the standard starting corpus for
    unit tests that aren't specifically testing vocabulary governance."""
    tbox_path = tmp_path / "tbox.ttl"
    abox_path = tmp_path / "abox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, tbox_path)
    abox_path.write_text(EMPTY_ABOX)
    seed_tbox_with_defaults(tbox_path)
    return Corpus(notes_dir=tmp_path, tbox_path=tbox_path, abox_path=abox_path)


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """An isolated, per-scenario copy of the bootstrap tbox.ttl."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    return path


@pytest.fixture(name="notes_dir")
def _notes_dir(tmp_path: Path) -> Path:
    """The notes directory for a scenario -- same dir as tbox.ttl/abox.ttl."""
    return tmp_path


@pytest.fixture(name="abox_path")
def _abox_path(tmp_path: Path) -> Path:
    """An isolated, empty abox.ttl for a scenario."""
    path = tmp_path / "abox.ttl"
    path.write_text(EMPTY_ABOX)
    return path


@pytest.fixture(name="corpus")
def _corpus(notes_dir: Path, tbox_path: Path, abox_path: Path) -> Corpus:
    """The three paths a scenario's notes.* calls need, bundled together."""
    return Corpus(
        notes_dir=notes_dir, tbox_path=tbox_path, abox_path=abox_path
    )


@pytest.fixture(name="outcome")
def _outcome() -> dict[str, Any]:
    """A scratch dict a scenario's steps use to pass state to each other."""
    return {}


@pytest.fixture(name="_notes_dir")
def _cli_notes_dir(corpus: Corpus, monkeypatch: pytest.MonkeyPatch) -> Path:
    """NOTES_DIR pointed at an isolated corpus pre-seeded with a valid tag
    and type, for CliRunner-based smoke tests."""
    seed_tbox_with_defaults(corpus.tbox_path)
    monkeypatch.setenv("NOTES_DIR", str(corpus.notes_dir))
    return corpus.notes_dir


def mint_note_with_id(note_id: str, corpus: Corpus) -> None:
    """Shared Given-step helper: note_id is already a normalized slug, so
    using it as the title mints exactly that id."""
    notes.new_note(
        title=note_id,
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )


def mint_sparql_basics(corpus: Corpus) -> Note:
    """Shared test helper: create the standard "SPARQL basics" note used
    as the default single valid note across many test suites."""
    return notes.new_note(
        title="SPARQL basics",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )


def mint_intro_to_sparql(corpus: Corpus) -> None:
    """Shared test helper: create the "Intro to SPARQL" note used across
    several update_note/sync/rebuild tests."""
    notes.new_note(
        title="Intro to SPARQL",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )


def mint_note_then_retitle(
    corpus: Corpus, original_title: str, new_title: str
) -> Note:
    """Create a note, then hand-edit its title without renaming its id/file
    -- simulates a hand-introduced duplicate title for validate() tests."""
    note = notes.new_note(
        title=original_title,
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )
    rewrite_frontmatter(corpus.notes_dir / f"{note.id}.md", title=new_title)
    return note


NEW_SPARQL_BASICS_CLI_ARGS = [
    "new-note",
    "SPARQL basics",
    "--tag",
    "knowledge-graphs",
    "--type",
    "Concept",
]

REMOVE_FIELD = object()


def rewrite_frontmatter(path: Path, **overrides: object) -> None:
    """Test-only helper: directly rewrite a note's raw frontmatter dict,
    bypassing Note's required-field construction so an invalid/incomplete
    state can be represented on disk (e.g. a genuinely missing field,
    an unknown tag, a dangling reference) without going through the
    validated new_note/update_note operations."""
    text = path.read_text()
    _, _, body = text.split("---\n", 2)
    raw = parse_frontmatter(text)
    for key, value in overrides.items():
        if value is REMOVE_FIELD:
            raw.pop(key, None)
        else:
            raw[key] = value
    path.write_text(f"---\n{yaml.safe_dump(raw, sort_keys=False)}---\n{body}")
