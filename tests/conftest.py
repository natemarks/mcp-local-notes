"""Fixtures shared across pytest-bdd step-definition modules."""

import shutil
from pathlib import Path
from typing import Any

import pytest

BOOTSTRAP_TBOX = Path(__file__).parent.parent / "notes" / "tbox.ttl"


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """An isolated, per-scenario copy of the bootstrap tbox.ttl."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    return path


@pytest.fixture(name="outcome")
def _outcome() -> dict[str, Any]:
    """A scratch dict a scenario's steps use to pass state to each other."""
    return {}
