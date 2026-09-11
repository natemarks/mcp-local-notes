"""Fixtures shared across pytest-bdd step-definition modules."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from mcp_local_notes.core import notes, vocabulary
from mcp_local_notes.core.config import Corpus

BOOTSTRAP_TBOX = Path(__file__).parent.parent / "notes" / "tbox.ttl"


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
    path.write_text("@prefix : <https://notes.natenite.net/ontology#> .\n")
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
    vocabulary.add_topic("knowledge-graphs", corpus.tbox_path)
    vocabulary.add_class("Concept", corpus.tbox_path)
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


def mint_intro_to_sparql(corpus: Corpus) -> None:
    """Shared test helper: create the "Intro to SPARQL" note used across
    several update_note/sync/rebuild tests."""
    notes.new_note(
        title="Intro to SPARQL",
        tags=["knowledge-graphs"],
        note_type="Concept",
        corpus=corpus,
    )


NEW_SPARQL_BASICS_CLI_ARGS = [
    "new-note",
    "SPARQL basics",
    "--tag",
    "knowledge-graphs",
    "--type",
    "Concept",
]
