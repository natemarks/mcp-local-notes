"""Environment-driven configuration shared by the CLI and MCP adapters."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import MutableMapping

DEFAULT_NOTES_DIR = "./notes"
DEFAULT_MCP_PORT = 8000
DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_ENV_FILE = Path(".env.json")


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


def get_mcp_port() -> int:
    """The MCP server's listen port: MCP_PORT if set, else 8000 (this
    project's own default, chosen to match the mcp SDK's current default)."""
    return int(os.environ.get("MCP_PORT", DEFAULT_MCP_PORT))


def get_mcp_host() -> str:
    """The MCP server's bind address: MCP_HOST if set, else loopback-only
    (safe for a bare local run; see mcp_server.server.main for why a
    containerized run needs a different value)."""
    return os.environ.get("MCP_HOST", DEFAULT_MCP_HOST)


def load_env_file(
    path: Path = DEFAULT_ENV_FILE,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Fill in any var from a JSON env file that isn't already set --
    an explicit shell export always wins over a persisted default.
    No-ops if the file doesn't exist (e.g. inside Docker, where none is
    shipped: the container gets its config from real env vars only)."""
    if environ is None:
        environ = os.environ
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error
    for key, value in data.items():
        environ.setdefault(key, str(value))


def describe_env_source(path: Path = DEFAULT_ENV_FILE) -> str:
    """One line describing where startup config came from, for the MCP
    server to log at boot."""
    if path.exists():
        return f"loaded config from {path}"
    return f"no {path} found; using the process environment and defaults"


def get_corpus() -> Corpus:
    """The current NOTES_DIR bundled with its tbox.ttl/abox.ttl paths."""
    return Corpus(
        notes_dir=get_notes_dir(),
        tbox_path=get_tbox_path(),
        abox_path=get_abox_path(),
    )
