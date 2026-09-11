"""Unit tests for core.config's NOTES_DIR resolution."""

from pathlib import Path

import pytest

from mcp_local_notes.core.config import get_notes_dir


@pytest.mark.unit
def test_defaults_to_notes_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """With NOTES_DIR unset, the default is ./notes."""
    monkeypatch.delenv("NOTES_DIR", raising=False)
    assert get_notes_dir() == Path("./notes")


@pytest.mark.unit
def test_respects_notes_dir_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """NOTES_DIR, when set, overrides the default."""
    monkeypatch.setenv("NOTES_DIR", "/tmp/my-notes")
    assert get_notes_dir() == Path("/tmp/my-notes")
