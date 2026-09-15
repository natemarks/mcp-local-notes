"""Unit tests for mcp_server.server: tool registration and error surfacing.

Uses the MCP SDK's in-process list_tools/call_tool -- no real HTTP socket.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult

from mcp_local_notes.mcp_server.server import main, mcp

EXPECTED_TOOLS = {
    "new_note",
    "update_note",
    "add_topic",
    "add_class",
    "sync_note",
    "rebuild_abox",
    "validate",
    "list_topics",
    "list_types",
    "archive_note",
    "delete_note",
    "find_notes_by_topic",
}


def _call(name: str, arguments: dict) -> CallToolResult:
    result = asyncio.run(mcp.call_tool(name, arguments))
    assert isinstance(result, CallToolResult)
    return result


def _success_payload(result: CallToolResult) -> dict[str, Any]:
    """A successful call's return value, JSON-decoded from its text content
    (the SDK only populates structured_content when an output schema is
    declared, which these tools deliberately don't need). Every tool this
    helper is used for returns a dict (a note's frontmatter+path, or the
    validate report), never a bare list/scalar."""
    return json.loads(result.content[0].text)  # type: ignore[union-attr]


@pytest.mark.unit
def test_server_is_named_local_ontology() -> None:
    """The server's own name is "local-ontology", driving the client-side
    mcp__local-ontology__<tool> prefix."""
    assert mcp.name == "local-ontology"


@pytest.mark.unit
def test_registers_every_core_operation() -> None:
    """Every core operation from the acceptance criteria is a registered tool."""
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert EXPECTED_TOOLS <= names


@pytest.mark.unit
def test_new_note_tool_creates_a_file(_notes_dir: Path) -> None:
    """The new_note tool creates the note file, same as the CLI command,
    and reports its absolute path so a caller can find it without
    knowing NOTES_DIR."""
    result = _call(
        "new_note",
        {
            "title": "SPARQL basics",
            "tags": ["knowledge-graphs"],
            "note_type": "Concept",
        },
    )
    assert result.is_error is False
    note_file = _notes_dir / "sparql-basics.md"
    assert note_file.exists()
    payload = _success_payload(result)
    assert payload["path"] == str(note_file.resolve())


@pytest.mark.unit
def test_update_note_tool_reports_absolute_path(_notes_dir: Path) -> None:
    """update_note also reports the note's absolute path, since editing
    is the other half of "creating or editing a note" the path is for."""
    _call(
        "new_note",
        {
            "title": "SPARQL basics",
            "tags": ["knowledge-graphs"],
            "note_type": "Concept",
        },
    )

    result = _call("update_note", {"note_id": "sparql-basics", "add_tags": []})

    assert result.is_error is False
    payload = _success_payload(result)
    assert payload["path"] == str((_notes_dir / "sparql-basics.md").resolve())


@pytest.mark.unit
def test_sync_note_tool_reports_absolute_path(_notes_dir: Path) -> None:
    """sync_note (recovery after a hand-edit) also reports the path."""
    _call(
        "new_note",
        {
            "title": "SPARQL basics",
            "tags": ["knowledge-graphs"],
            "note_type": "Concept",
        },
    )

    result = _call("sync_note", {"note_id": "sparql-basics"})

    assert result.is_error is False
    payload = _success_payload(result)
    assert payload["path"] == str((_notes_dir / "sparql-basics.md").resolve())


@pytest.mark.unit
def test_archive_note_tool_reports_absolute_path(_notes_dir: Path) -> None:
    """archive_note (setting status) also reports the path."""
    _call(
        "new_note",
        {
            "title": "SPARQL basics",
            "tags": ["knowledge-graphs"],
            "note_type": "Concept",
        },
    )

    result = _call("archive_note", {"note_id": "sparql-basics"})

    assert result.is_error is False
    payload = _success_payload(result)
    assert payload["path"] == str((_notes_dir / "sparql-basics.md").resolve())


@pytest.mark.unit
def test_add_topic_duplicate_returns_structured_error(
    _notes_dir: Path,
) -> None:
    """A NotesError surfaces as a structured {rule, message, details} result."""
    # _notes_dir already pre-seeds "knowledge-graphs" (see conftest._cli_notes_dir).
    result = _call("add_topic", {"name": "knowledge-graphs"})

    assert result.is_error is True
    assert result.structured_content["rule"] == "TOPIC_ALREADY_EXISTS"
    assert result.structured_content["details"]["topic"] == "knowledge-graphs"


@pytest.mark.unit
def test_validate_tool_matches_core_validate_shape(_notes_dir: Path) -> None:
    """The validate tool returns the same {ok, issues} shape as the CLI."""
    result = _call("validate", {})
    assert result.is_error is False
    assert _success_payload(result) == {"ok": True, "issues": []}


@pytest.mark.unit
def test_find_notes_by_topic_tool_returns_matching_notes(
    _notes_dir: Path,
) -> None:
    """The tool returns every note currently tagged with the topic."""
    _call(
        "new_note",
        {
            "title": "SPARQL basics",
            "tags": ["knowledge-graphs"],
            "note_type": "Concept",
        },
    )

    result = _call("find_notes_by_topic", {"topic": "knowledge-graphs"})

    assert result.is_error is False
    # A list-returning tool's structured_content wraps the list under
    # "result" (unlike a dict-returning tool's, which mirrors it 1:1) --
    # see _success_payload's docstring for the dict-shaped equivalent.
    payload = result.structured_content["result"]
    assert [note["id"] for note in payload] == ["sparql-basics"]


@pytest.mark.unit
def test_find_notes_by_topic_tool_rejects_unknown_topic(
    _notes_dir: Path,
) -> None:
    """An unknown topic surfaces as a structured UNKNOWN_TOPIC error."""
    result = _call("find_notes_by_topic", {"topic": "no-such-topic"})

    assert result.is_error is True
    assert result.structured_content["rule"] == "UNKNOWN_TOPIC"


@pytest.fixture(name="fake_uvicorn_server")
def _fake_uvicorn_server(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Replaces uvicorn.Server so main() never actually binds a socket or
    blocks waiting for connections -- captures the Config it was built
    with instead."""
    captured: dict[str, Any] = {}

    class _FakeServer:  # pylint: disable=too-few-public-methods
        """Stands in for uvicorn.Server's (config) -> .run() shape."""

        def __init__(self, config: Any) -> None:
            captured["config"] = config

        def run(self) -> None:
            """Record that main() actually called .run()."""
            captured["ran"] = True

    monkeypatch.setattr("uvicorn.Server", _FakeServer)
    return captured


@pytest.mark.unit
def test_main_runs_streamable_http_with_configured_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_uvicorn_server: dict[str, Any],
) -> None:
    """main() wires the server to Streamable HTTP at the configured
    host/port, the one place transport/host/port selection happens."""
    monkeypatch.chdir(tmp_path)  # no .env.json here
    monkeypatch.setenv("MCP_PORT", "9123")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")

    main()

    config = fake_uvicorn_server["config"]
    assert config.host == "0.0.0.0"
    assert config.port == 9123
    assert config.log_level == "info"
    assert fake_uvicorn_server["ran"] is True


@pytest.mark.unit
def test_main_bounds_graceful_shutdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_uvicorn_server: dict[str, Any],
) -> None:
    """main() sets a bounded timeout_graceful_shutdown -- without it,
    uvicorn waits indefinitely for any still-open client connection
    (the normal case for a real MCP client) before Ctrl+C can complete,
    which also means the Makefile's own SIGINT trap never gets to run."""
    monkeypatch.chdir(tmp_path)

    main()

    timeout = fake_uvicorn_server["config"].timeout_graceful_shutdown
    assert timeout is not None
    assert 0 < timeout <= 10


@pytest.mark.unit
def test_main_suppresses_uvicorns_reraised_sigint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """uvicorn.Server.serve()'s capture_signals() deliberately re-raises
    the SIGINT it caught (via signal.raise_signal) after its own graceful
    shutdown already completed -- inside our asyncio_run() call, the
    now-restored default handler turns that into a KeyboardInterrupt
    propagating out of Server.run(). By that point uvicorn has already
    logged "Application shutdown complete", so main() should swallow it
    rather than let a KeyboardInterrupt traceback print on every Ctrl+C."""
    monkeypatch.chdir(tmp_path)

    class _FakeServer:  # pylint: disable=too-few-public-methods
        def __init__(self, config: Any) -> None:
            del config

        def run(self) -> None:
            """Simulate uvicorn's own post-shutdown signal re-raise."""
            raise KeyboardInterrupt

    monkeypatch.setattr("uvicorn.Server", _FakeServer)

    main()  # must not raise


@pytest.mark.unit
def test_main_logs_no_env_file_when_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    fake_uvicorn_server: dict[str, Any],
) -> None:
    """With no .env.json in the working directory, main() says so, and
    still reports the resolved config values."""
    monkeypatch.chdir(tmp_path)

    main()

    out = capsys.readouterr().out
    assert "no .env.json found" in out
    assert "NOTES_DIR=" in out
    assert "MCP_PORT=" in out
    assert "MCP_HOST=" in out
    assert fake_uvicorn_server["ran"] is True


@pytest.mark.unit
def test_main_logs_env_file_and_picks_up_its_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    fake_uvicorn_server: dict[str, Any],
) -> None:
    """A present .env.json is named in the log, and its values (when not
    already set in the environment) actually drive the server config."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NOTES_DIR", raising=False)
    monkeypatch.delenv("MCP_PORT", raising=False)
    (tmp_path / ".env.json").write_text(
        '{"NOTES_DIR": "/from/env/json", "MCP_PORT": 9321}'
    )

    main()

    out = capsys.readouterr().out
    assert "loaded config from .env.json" in out
    assert "NOTES_DIR=/from/env/json" in out
    assert fake_uvicorn_server["config"].port == 9321


@pytest.mark.unit
def test_main_exits_cleanly_on_malformed_env_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed .env.json fails loudly with a clear message (via
    SystemExit's string form, which the interpreter prints to stderr
    and turns into exit code 1) rather than an uncaught traceback."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.json").write_text("{not valid json")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert "invalid JSON in" in str(exc_info.value.code)
