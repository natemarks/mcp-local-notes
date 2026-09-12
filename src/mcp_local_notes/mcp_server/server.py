"""The local MCP server: one thin tool per core operation, served over
Streamable HTTP under the "local-ontology" name so a client that
registers it that way sees every tool as mcp__local-ontology__<tool>.

No tool re-implements a rule -- every tool just calls straight into the
matching core.* function and renders whatever it returns or raises.
"""

import functools
from typing import Any, Callable, TypeVar

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

from mcp_local_notes.core import notes
from mcp_local_notes.core import validate as core_validate
from mcp_local_notes.core import vocabulary
from mcp_local_notes.core.config import get_corpus, get_mcp_port, get_tbox_path
from mcp_local_notes.core.errors import NotesError
from mcp_local_notes.ontology.tbox import ROOT_TYPE

mcp = MCPServer("local-ontology")

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
    note = notes.new_note(
        title=title,
        tags=tags,
        note_type=note_type,
        corpus=get_corpus(),
        aliases=aliases or [],
        approve_topics=approve_topics or [],
    )
    return note.to_frontmatter()


@mcp.tool()
@handle_notes_errors
def update_note(  # pylint: disable=too-many-arguments
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
    return note.to_frontmatter()


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
    return note.to_frontmatter()


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
    return note.to_frontmatter()


@mcp.tool()
@handle_notes_errors
def delete_note(note_id: str, confirm: bool = False) -> dict:
    """Hard delete a note and its ABox entry."""
    notes.delete_note(note_id, get_corpus(), confirm=confirm)
    return {"deleted": note_id}


def main() -> None:
    """Run the server over Streamable HTTP at the SDK's own defaults
    (127.0.0.1:8000/mcp), port overridable via MCP_PORT."""
    mcp.run(transport="streamable-http", port=get_mcp_port())


if __name__ == "__main__":
    main()
