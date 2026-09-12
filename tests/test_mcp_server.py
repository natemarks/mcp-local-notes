"""Unit tests for mcp_server.server: tool registration and error surfacing.

Uses the MCP SDK's in-process list_tools/call_tool -- no real HTTP socket.
"""

import asyncio
import json
from pathlib import Path

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
}


def _call(name: str, arguments: dict) -> CallToolResult:
    result = asyncio.run(mcp.call_tool(name, arguments))
    assert isinstance(result, CallToolResult)
    return result


def _success_payload(result: CallToolResult) -> object:
    """A successful call's return value, JSON-decoded from its text content
    (the SDK only populates structured_content when an output schema is
    declared, which these tools deliberately don't need)."""
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
    """The new_note tool creates the note file, same as the CLI command."""
    result = _call(
        "new_note",
        {
            "title": "SPARQL basics",
            "tags": ["knowledge-graphs"],
            "note_type": "Concept",
        },
    )
    assert result.is_error is False
    assert (_notes_dir / "sparql-basics.md").exists()


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
def test_main_runs_streamable_http_with_configured_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() wires the server to Streamable HTTP at the configured port,
    the one place transport/port selection actually happens."""
    monkeypatch.setenv("MCP_PORT", "9123")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    calls = {}

    def _fake_run(**kwargs: object) -> None:
        calls.update(kwargs)

    monkeypatch.setattr(mcp, "run", _fake_run)
    main()
    assert calls == {
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 9123,
    }
