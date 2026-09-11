"""Environment-driven configuration shared by the CLI and MCP adapters."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_NOTES_DIR = "./notes"


@dataclass
class Corpus:
    """The three paths every note operation touches, bundled together."""

    notes_dir: Path
    tbox_path: Path
    abox_path: Path


def get_notes_dir() -> Path:
    """The notes directory: NOTES_DIR if set, else ./notes."""
    return Path(os.environ.get("NOTES_DIR", DEFAULT_NOTES_DIR))


def get_tbox_path() -> Path:
    """tbox.ttl lives inside the notes directory, alongside the notes."""
    return get_notes_dir() / "tbox.ttl"


def get_abox_path() -> Path:
    """abox.ttl lives inside the notes directory, alongside the notes."""
    return get_notes_dir() / "abox.ttl"


def get_corpus() -> Corpus:
    """The current NOTES_DIR bundled with its tbox.ttl/abox.ttl paths."""
    return Corpus(
        notes_dir=get_notes_dir(),
        tbox_path=get_tbox_path(),
        abox_path=get_abox_path(),
    )
