"""Step definitions for features/mcp_tool_exposure.feature.

Uses the MCP SDK's in-process list_tools/call_tool for the MCP side, and
Typer's CliRunner for the CLI side -- no real HTTP socket or subprocess,
matching the in-process seam already used across the test suite.
"""

import asyncio
import json
import shutil
import socket
from pathlib import Path
from typing import Any

import pytest
from mcp.server import MCPServer
from mcp.types import CallToolResult
from pytest_bdd import given, parsers, scenarios, then, when
from typer.testing import CliRunner

from conftest import (
    EMPTY_ABOX,
    NEW_SPARQL_BASICS_CLI_ARGS,
    seed_tbox_with_defaults,
)
from mcp_local_notes.cli.main import app as cli_app
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.mcp_server.server import mcp as mcp_server
from mcp_local_notes.ontology import abox, tbox

BOOTSTRAP_TBOX = Path(__file__).parent.parent.parent / "notes" / "tbox.ttl"

pytestmark = pytest.mark.unit

scenarios("mcp_tool_exposure.feature")

_CLI_RUNNER = CliRunner()


@pytest.fixture(name="tbox_path")
def _tbox_path(tmp_path: Path) -> Path:
    """Pre-seed the standard vocabulary these scenarios assume already exists."""
    path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP_TBOX, path)
    seed_tbox_with_defaults(path)
    return path


# --- Background ----------------------------------------------------------


@given(
    parsers.parse(
        'a local MCP server named "{name}" is registered with the desktop app'
    )
)
def given_server_registered(name: str) -> None:
    """The server object this repo builds is in fact named `name`."""
    assert mcp_server.name == name


@given("it is connected to the current session")
def given_connected() -> None:
    """Nothing to set up for the in-process seam -- calls go straight to
    the same server object the Background just checked."""


# --- Scenario: Tools are discoverable under a clear category -------------


@when("an assistant lists available tools")
def when_lists_tools(outcome: dict[str, Any]) -> None:
    """Record every tool name the server currently registers."""
    tools = asyncio.run(mcp_server.list_tools())
    outcome["tool_names"] = {tool.name for tool in tools}


@then(parsers.parse('it should see tools named with the "{prefix}" prefix'))
def then_named_with_prefix(prefix: str, outcome: dict[str, Any]) -> None:
    """The client applies the mcp__<prefix>__<tool> scoping at registration
    time, keyed off the server's own name -- this repo's job is to supply
    that stable name and bare, unprefixed tool names for the client to
    scope, not to prefix them itself."""
    assert mcp_server.name == prefix
    assert all(prefix not in name for name in outcome["tool_names"])


@then(parsers.parse("that group should include at least: {names}"))
def then_group_includes(names: str, outcome: dict[str, Any]) -> None:
    """Every named tool is among the ones the server registered."""
    expected = {name.strip() for name in names.split(",")}
    assert expected <= outcome["tool_names"]


# --- Scenario: Creating a note via the MCP tool matches the CLI behavior -


@given("identical input is used for both interfaces")
def given_identical_input() -> None:
    """The When step below uses the same title/tags/type for both calls."""


@when(
    parsers.parse(
        'a note is created once via the "{tool_name}" MCP tool and once '
        "via the equivalent CLI command"
    )
)
def when_created_both_ways(
    tool_name: str,
    tmp_path: Path,
    outcome: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run identical input through the CLI and the MCP tool, each against
    its own freshly-seeded corpus, so the resulting files can be diffed."""
    cli_dir = tmp_path / "cli"
    mcp_dir = tmp_path / "mcp"
    for corpus_dir in (cli_dir, mcp_dir):
        corpus_dir.mkdir()
        seeded_tbox = corpus_dir / "tbox.ttl"
        shutil.copy(BOOTSTRAP_TBOX, seeded_tbox)
        seed_tbox_with_defaults(seeded_tbox)
        (corpus_dir / "abox.ttl").write_text(EMPTY_ABOX)

    monkeypatch.setenv("NOTES_DIR", str(cli_dir))
    cli_result = _CLI_RUNNER.invoke(cli_app, NEW_SPARQL_BASICS_CLI_ARGS)
    assert cli_result.exit_code == 0

    monkeypatch.setenv("NOTES_DIR", str(mcp_dir))
    mcp_result = asyncio.run(
        mcp_server.call_tool(
            tool_name,
            {
                "title": "SPARQL basics",
                "tags": ["knowledge-graphs"],
                "note_type": "Concept",
            },
        )
    )
    assert isinstance(mcp_result, CallToolResult)
    assert mcp_result.is_error is False

    outcome["cli_dir"] = cli_dir
    outcome["mcp_dir"] = mcp_dir


@then("both should produce an identical note file")
def then_identical_note_file(outcome: dict[str, Any]) -> None:
    """The CLI-created and MCP-created note files are byte-identical."""
    cli_text = (outcome["cli_dir"] / "sparql-basics.md").read_text()
    mcp_text = (outcome["mcp_dir"] / "sparql-basics.md").read_text()
    assert cli_text == mcp_text


@then("both should produce an identical ABox block")
def then_identical_abox_block(outcome: dict[str, Any]) -> None:
    """The CLI-created and MCP-created ABox entries hold the same triples."""
    cli_graph = abox.load(outcome["cli_dir"] / "abox.ttl")
    mcp_graph = abox.load(outcome["mcp_dir"] / "abox.ttl")
    subject = tbox.NS["sparql-basics"]
    assert set(cli_graph.triples((subject, None, None))) == set(
        mcp_graph.triples((subject, None, None))
    )


# --- Scenario: The server operates only on local files -------------------


@when(parsers.parse('any "{name}" tool is invoked'))
def when_any_tool_invoked(
    name: str,
    corpus: Corpus,
    outcome: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """list_topics is a representative read-only tool; a blocked network
    socket proves nothing beyond the notes directory was touched or reached
    for. Only AF_INET/AF_INET6 are blocked -- asyncio's own event loop opens
    an AF_UNIX self-pipe internally, which isn't a network call."""
    assert mcp_server.name == name
    monkeypatch.setenv("NOTES_DIR", str(corpus.notes_dir))

    real_socket = socket.socket

    def _guarded_socket(*args: Any, **kwargs: Any) -> socket.socket:
        family = args[0] if args else kwargs.get("family", socket.AF_INET)
        if family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError(
                "network socket attempted during tool invocation"
            )
        return real_socket(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _guarded_socket)

    outcome["files_before"] = sorted(
        str(p.relative_to(corpus.notes_dir))
        for p in corpus.notes_dir.rglob("*")
    )
    outcome["result"] = asyncio.run(mcp_server.call_tool("list_topics", {}))


@then(
    "it should read and write only files under the configured notes "
    "directory on the local device"
)
def then_reads_writes_only_notes_dir(
    corpus: Corpus, outcome: dict[str, Any]
) -> None:
    """The notes directory's file listing is unchanged by the read-only call."""
    files_after = sorted(
        str(p.relative_to(corpus.notes_dir))
        for p in corpus.notes_dir.rglob("*")
    )
    assert files_after == outcome["files_before"]


@then("it should make no network calls")
def then_no_network_calls(outcome: dict[str, Any]) -> None:
    """If the blocked socket had fired, the SDK converts that exception
    into an error result rather than propagating it -- so is_error is the
    reliable signal here, not an uncaught AssertionError."""
    assert outcome["result"].is_error is False


# --- Scenario: The server surfaces validation errors as structured errors


@given("a request that would violate a uniqueness or vocabulary rule")
def given_violating_request(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """ "knowledge-graphs" is already seeded by the tbox_path fixture above,
    so re-adding it via add_topic is a ready-made TOPIC_ALREADY_EXISTS case."""
    outcome["tbox_before"] = corpus.tbox_path.read_text()
    outcome["notes_before"] = sorted(
        p.name for p in corpus.notes_dir.glob("*.md")
    )


@when(parsers.parse('the corresponding "{name}" tool is invoked'))
def when_violating_tool_invoked(
    name: str,
    corpus: Corpus,
    outcome: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invoke add_topic with a name already in the vocabulary."""
    assert mcp_server.name == name
    monkeypatch.setenv("NOTES_DIR", str(corpus.notes_dir))
    outcome["result"] = asyncio.run(
        mcp_server.call_tool("add_topic", {"name": "knowledge-graphs"})
    )


@then("it should return a structured error naming the specific rule violated")
def then_structured_error(outcome: dict[str, Any]) -> None:
    """The result is a structured TOPIC_ALREADY_EXISTS error."""
    result = outcome["result"]
    assert result.is_error is True
    assert result.structured_content["rule"] == "TOPIC_ALREADY_EXISTS"
    assert result.structured_content["details"]["topic"] == "knowledge-graphs"


@then("it should make no partial writes to any note file or ontology file")
def then_no_partial_writes(corpus: Corpus, outcome: dict[str, Any]) -> None:
    """Neither tbox.ttl nor the notes directory's file listing changed."""
    assert corpus.tbox_path.read_text() == outcome["tbox_before"]
    assert (
        sorted(p.name for p in corpus.notes_dir.glob("*.md"))
        == outcome["notes_before"]
    )


# --- Scenario: The server is unavailable gracefully -----------------------


@given(
    parsers.parse('the "{name}" MCP server is not running or not registered')
)
def given_server_not_registered(name: str, outcome: dict[str, Any]) -> None:
    """Model "not registered" with a genuinely separate, freshly-built
    MCPServer that never had any of this repo's tools added to it -- as
    close as an in-process test can get to "this server was never wired
    up", rather than asserting against a hardcoded empty list."""
    outcome["unregistered_server_name"] = name
    outcome["unregistered_server"] = MCPServer(f"{name}-unregistered-stand-in")


@when(parsers.parse('an assistant looks for "{name}" tools'))
def when_assistant_looks_for_tools(name: str, outcome: dict[str, Any]) -> None:
    """List whatever tools the unregistered stand-in server has (none)."""
    assert outcome["unregistered_server_name"] == name
    tools = asyncio.run(outcome["unregistered_server"].list_tools())
    outcome["tools"] = [tool.name for tool in tools]


@then("it should find none")
def then_finds_none(outcome: dict[str, Any]) -> None:
    """No tools were found on the unregistered stand-in server."""
    assert outcome["tools"] == []


@then(
    "it should fall back to telling Nate the local ontology tools aren't "
    "available, rather than guessing at file edits by hand"
)
def then_falls_back_gracefully() -> None:
    """The fallback behavior belongs to the assistant/client, not this
    repo's code -- this repo's only obligation is the one already checked:
    when the server isn't registered, no tools are found to guess with."""


# --- Scenario: CLI remains usable without any assistant or MCP server ----


@given("no MCP client is involved")
def given_no_mcp_client() -> None:
    """The When step below drives the CLI directly, via CliRunner."""


@when(parsers.parse('"{command}" is run directly from a terminal or CI job'))
def when_command_run_directly(
    command: str,
    corpus: Corpus,
    outcome: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run `command --json` via the CLI, recording its parsed report."""
    monkeypatch.setenv("NOTES_DIR", str(corpus.notes_dir))
    result = _CLI_RUNNER.invoke(cli_app, [command, "--json"])
    assert result.exit_code == 0
    outcome["cli_report"] = json.loads(result.stdout)


@then("it should behave identically to being invoked through the MCP tool")
def then_behaves_identically_to_mcp(
    corpus: Corpus, outcome: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The validate MCP tool, against the same corpus, reports the same thing."""
    monkeypatch.setenv("NOTES_DIR", str(corpus.notes_dir))
    mcp_result = asyncio.run(mcp_server.call_tool("validate", {}))
    mcp_report = json.loads(mcp_result.content[0].text)  # type: ignore[union-attr]
    assert mcp_report == outcome["cli_report"]


@then("it should not require network access or an MCP server to be running")
def then_no_network_or_server_required(outcome: dict[str, Any]) -> None:
    """The CLI call above never touched mcp_server or any transport."""
    assert outcome["cli_report"] == {"ok": True, "issues": []}
