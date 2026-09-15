"""The local MCP server: one thin tool per core operation, served over
Streamable HTTP under the "local-ontology" name so a client that
registers it that way sees every tool as mcp__local-ontology__<tool>.

No tool re-implements a rule -- every tool just calls straight into the
matching core.* function and renders whatever it returns or raises.
"""

import functools
from typing import Any, Callable, TypeVar

import uvicorn
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

from mcp_local_notes.core import notes
from mcp_local_notes.core import validate as core_validate
from mcp_local_notes.core import vocabulary
from mcp_local_notes.core.config import (
    describe_env_source,
    get_corpus,
    get_mcp_host,
    get_mcp_port,
    get_notes_dir,
    get_tbox_path,
    load_env_file,
)
from mcp_local_notes.core.errors import NotesError
from mcp_local_notes.core.models import Note
from mcp_local_notes.ontology.tbox import ROOT_TYPE

mcp = MCPServer("local-ontology")

# uvicorn's own default (timeout_graceful_shutdown=None) waits indefinitely
# for every open connection to close on SIGINT/SIGTERM -- a real MCP client
# (Claude Desktop/Code) keeps its Streamable HTTP connection open for the
# whole session, so a bare Ctrl+C would hang forever waiting for a client
# that has no reason to disconnect. Bounding it lets the server (and the
# Makefile's own SIGINT trap, which only runs once this process exits)
# actually shut down promptly.
GRACEFUL_SHUTDOWN_SECONDS = 3

F = TypeVar("F", bound=Callable[..., Any])


def handle_notes_errors(func: F) -> F:
    """Render any NotesError identically across every MCP tool: a structured
    {rule, message, details} error result. The one place this rendering
    lives for the MCP adapter (the CLI adapter has its own, in cli/main.py,
    since stderr+exit-code and a structured CallToolResult are different
    enough renderings that a shared helper wouldn't simplify either)."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except NotesError as error:
            return CallToolResult(
                content=[TextContent(type="text", text=error.message)],
                structured_content={
                    "rule": error.rule.value,
                    "message": error.message,
                    "details": error.details,
                },
                is_error=True,
            )

    return wrapper  # type: ignore[return-value]


def _note_response(note: Note) -> dict:
    """A note's frontmatter plus its absolute file path -- every tool that
    creates or edits a note reports this, so a caller (or the user) can
    find the file directly rather than needing to know NOTES_DIR."""
    result = note.to_frontmatter()
    result["path"] = str(notes.note_path(note.id, get_notes_dir()))
    return result


@mcp.tool()
@handle_notes_errors
def new_note(
    title: str,
    tags: list[str],
    note_type: str,
    aliases: list[str] | None = None,
    approve_topics: list[str] | None = None,
) -> dict:
    """Create a new note."""
    # Identical to cli.main's new_note_command body: the spec requires
    # cli/ and mcp_server/ to be peer adapters over the same core/ with
    # zero divergent business logic, so this passthrough has nothing to
    # extract into a shared helper without adding an abstraction neither
    # adapter otherwise needs.
    # pylint: disable=duplicate-code
    note = notes.new_note(
        title=title,
        tags=tags,
        note_type=note_type,
        corpus=get_corpus(),
        aliases=aliases or [],
        approve_topics=approve_topics or [],
    )
    # pylint: enable=duplicate-code
    return _note_response(note)


@mcp.tool()
@handle_notes_errors
def update_note(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    note_id: str,
    title: str | None = None,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    add_related: list[str] | None = None,
    remove_related: list[str] | None = None,
    approve_topics: list[str] | None = None,
) -> dict:
    """Edit an existing note's frontmatter and regenerate its ABox entry."""
    note = notes.update_note(
        note_id,
        get_corpus(),
        title=title,
        add_tags=add_tags,
        remove_tags=remove_tags,
        add_related=add_related,
        remove_related=remove_related,
        approve_topics=approve_topics,
    )
    return _note_response(note)


@mcp.tool()
@handle_notes_errors
def add_topic(name: str) -> dict:
    """Add a new topic to the controlled vocabulary."""
    vocabulary.add_topic(name, get_tbox_path())
    return {"added_topic": name}


@mcp.tool()
@handle_notes_errors
def add_class(name: str, subclass_of: str = ROOT_TYPE) -> dict:
    """Add a new note type to the ontology."""
    vocabulary.add_class(name, get_tbox_path(), subclass_of=subclass_of)
    return {"added_type": name}


@mcp.tool()
@handle_notes_errors
def sync_note(note_id: str) -> dict:
    """Regenerate a single note's ABox entry from its current frontmatter."""
    note = notes.sync_note(note_id, get_corpus())
    return _note_response(note)


@mcp.tool()
@handle_notes_errors
def rebuild_abox() -> dict:
    """Rebuild the entire ABox from every note's current frontmatter."""
    notes.rebuild_abox(get_corpus())
    return {"status": "rebuilt"}


@mcp.tool()
@handle_notes_errors
def validate() -> dict:
    """Report every consistency problem in the corpus. Never modifies a file."""
    return core_validate.build_report(core_validate.validate(get_corpus()))


@mcp.tool()
@handle_notes_errors
def list_topics() -> list[str]:
    """List the current controlled topic vocabulary."""
    return vocabulary.list_topics(get_tbox_path())


@mcp.tool()
@handle_notes_errors
def list_types() -> list[str]:
    """List the current declared note types."""
    return vocabulary.list_types(get_tbox_path())


@mcp.tool()
@handle_notes_errors
def archive_note(note_id: str) -> dict:
    """Archive a note: sets status, keeps the file and ABox entry."""
    note = notes.archive_note(note_id, get_corpus())
    return _note_response(note)


@mcp.tool()
@handle_notes_errors
def delete_note(note_id: str, confirm: bool = False) -> dict:
    """Hard delete a note and its ABox entry."""
    notes.delete_note(note_id, get_corpus(), confirm=confirm)
    return {"deleted": note_id}


@mcp.tool()
@handle_notes_errors
def find_notes_by_topic(topic: str) -> list[dict]:
    """List every note currently tagged with the given topic."""
    matches = notes.find_notes_by_topic(topic, get_corpus())
    return [note.to_frontmatter() for note in matches]


def main() -> None:
    """Run the server over Streamable HTTP at the SDK's own defaults
    (127.0.0.1:8000/mcp), host/port overridable via MCP_HOST/MCP_PORT (the
    Docker image sets MCP_HOST=0.0.0.0; a bare local run keeps loopback).

    Loads .env.json first (if present -- never shipped inside the Docker
    image, so this is a no-op there) and logs where the startup config
    came from and what it resolved to, before binding anything.

    Both lines are explicitly flushed: stdout is fully block-buffered
    (not line-buffered) when it isn't a TTY -- as under `docker logs` --
    so an unflushed print() here could sit invisible in the buffer
    indefinitely instead of appearing at startup as intended.

    A malformed .env.json exits with a clear message rather than an
    uncaught traceback, before anything binds.

    Builds the uvicorn server directly (mcp.run()'s own convenience
    wrapper hardcodes host/port/log_level with no way to also set
    timeout_graceful_shutdown) so shutdown stays bounded -- see
    GRACEFUL_SHUTDOWN_SECONDS. This mirrors MCPServer.run_streamable_http_async
    closely enough (same host/port/log_level/app construction) that an
    SDK upgrade changing what it passes to uvicorn.Config should be
    reflected here too.

    uvicorn's own capture_signals() deliberately re-raises the SIGINT it
    caught, via signal.raise_signal(), once its graceful shutdown is
    already done -- a courtesy for callers that want standard signal
    semantics. We don't: the Makefile's own trap already handles the
    user-facing cleanup message, so that re-raised KeyboardInterrupt is
    swallowed here rather than printing a traceback on every Ctrl+C.
    """
    try:
        load_env_file()
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(describe_env_source(), flush=True)
    print(
        f"NOTES_DIR={get_notes_dir()} MCP_PORT={get_mcp_port()} "
        f"MCP_HOST={get_mcp_host()}",
        flush=True,
    )

    host = get_mcp_host()
    app = mcp.streamable_http_app(host=host)
    config = uvicorn.Config(
        app,
        host=host,
        port=get_mcp_port(),
        log_level=mcp.settings.log_level.lower(),
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
    )
    try:
        uvicorn.Server(config).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
