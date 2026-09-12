"""Unit tests for core.config's NOTES_DIR resolution."""

from pathlib import Path

import pytest

from mcp_local_notes.core.config import (
    get_abox_path,
    get_mcp_host,
    get_mcp_port,
    get_notes_dir,
    get_tbox_path,
)


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


@pytest.mark.unit
def test_tbox_and_abox_paths_live_under_notes_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tbox.ttl/abox.ttl travel with the notes directory, not the repo root."""
    monkeypatch.setenv("NOTES_DIR", "/tmp/my-notes")
    assert get_tbox_path() == Path("/tmp/my-notes/tbox.ttl")
    assert get_abox_path() == Path("/tmp/my-notes/abox.ttl")


@pytest.mark.unit
def test_mcp_port_defaults_to_8000(monkeypatch: pytest.MonkeyPatch) -> None:
    """With MCP_PORT unset, the default is 8000, matching the SDK's own."""
    monkeypatch.delenv("MCP_PORT", raising=False)
    assert get_mcp_port() == 8000


@pytest.mark.unit
def test_mcp_port_respects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP_PORT, when set, overrides the default."""
    monkeypatch.setenv("MCP_PORT", "9000")
    assert get_mcp_port() == 9000


@pytest.mark.unit
def test_mcp_host_defaults_to_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With MCP_HOST unset, the server binds loopback-only -- the safe
    default for a bare (non-Dockerized) run."""
    monkeypatch.delenv("MCP_HOST", raising=False)
    assert get_mcp_host() == "127.0.0.1"


@pytest.mark.unit
def test_mcp_host_respects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP_HOST, when set, overrides the default -- the Docker image sets
    this to 0.0.0.0 so the container's own port-forwarding can reach it."""
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    assert get_mcp_host() == "0.0.0.0"
