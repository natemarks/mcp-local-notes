"""Environment-driven configuration shared by the CLI and MCP adapters."""

import os
from pathlib import Path

DEFAULT_NOTES_DIR = "./notes"


def get_notes_dir() -> Path:
    """The notes directory: NOTES_DIR if set, else ./notes."""
    return Path(os.environ.get("NOTES_DIR", DEFAULT_NOTES_DIR))


def get_tbox_path() -> Path:
    """tbox.ttl lives inside the notes directory, alongside the notes."""
    return get_notes_dir() / "tbox.ttl"


def get_abox_path() -> Path:
    """abox.ttl lives inside the notes directory, alongside the notes."""
    return get_notes_dir() / "abox.ttl"
