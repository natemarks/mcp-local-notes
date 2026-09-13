"""Unit tests for core.config's NOTES_DIR resolution."""

from pathlib import Path

import pytest

from mcp_local_notes.core.config import (
    describe_env_source,
    get_abox_path,
    get_mcp_host,
    get_mcp_port,
    get_notes_dir,
    get_tbox_path,
    load_env_file,
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


@pytest.mark.unit
def test_load_env_file_fills_in_unset_vars(tmp_path: Path) -> None:
    """Every key in the JSON file is set, into the given environ mapping,
    when not already present there."""
    env_file = tmp_path / ".env.json"
    env_file.write_text('{"NOTES_DIR": "/from/file", "MCP_PORT": 9000}')
    environ: dict[str, str] = {}

    load_env_file(env_file, environ)

    assert environ == {"NOTES_DIR": "/from/file", "MCP_PORT": "9000"}


@pytest.mark.unit
def test_load_env_file_does_not_override_already_set_vars(
    tmp_path: Path,
) -> None:
    """An already-present key in the environ mapping is left untouched --
    an explicit shell export always wins over the persisted file."""
    env_file = tmp_path / ".env.json"
    env_file.write_text('{"NOTES_DIR": "/from/file"}')
    environ = {"NOTES_DIR": "/already/set"}

    load_env_file(env_file, environ)

    assert environ == {"NOTES_DIR": "/already/set"}


@pytest.mark.unit
def test_load_env_file_missing_file_is_a_noop(tmp_path: Path) -> None:
    """No .env.json (e.g. inside Docker, where none is shipped) is not an
    error -- the environ mapping is simply left as-is."""
    environ: dict[str, str] = {}

    load_env_file(tmp_path / "does-not-exist.json", environ)

    assert not environ


@pytest.mark.unit
def test_load_env_file_raises_clear_error_on_malformed_json(
    tmp_path: Path,
) -> None:
    """Malformed JSON is rejected with a message naming the file -- not a
    raw json.JSONDecodeError with no file context, since this runs before
    every CLI command and every MCP server startup."""
    env_file = tmp_path / ".env.json"
    env_file.write_text("{not valid json")

    with pytest.raises(ValueError) as exc_info:
        load_env_file(env_file, {})
    assert str(env_file) in str(exc_info.value)


@pytest.mark.unit
def test_describe_env_source_reports_the_file_when_present(
    tmp_path: Path,
) -> None:
    """The message names the file that was actually loaded."""
    env_file = tmp_path / ".env.json"
    env_file.write_text("{}")

    assert str(env_file) in describe_env_source(env_file)


@pytest.mark.unit
def test_describe_env_source_reports_no_file_when_absent(
    tmp_path: Path,
) -> None:
    """The message says no file was found, distinctly from the found case."""
    missing = tmp_path / "does-not-exist.json"

    message = describe_env_source(missing)

    assert str(missing) in message
    assert "no" in message.lower()
