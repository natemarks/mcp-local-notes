"""Fixtures shared across pytest-bdd step-definition modules."""

import shutil
from pathlib import Path
from typing import Any

import pytest

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
