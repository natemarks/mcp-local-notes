"""Environment-driven configuration shared by the CLI and MCP adapters."""

import os
from pathlib import Path

DEFAULT_NOTES_DIR = "./notes"


def get_notes_dir() -> Path:
    """The notes directory: NOTES_DIR if set, else ./notes."""
    return Path(os.environ.get("NOTES_DIR", DEFAULT_NOTES_DIR))
