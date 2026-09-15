"""Typer CLI: thin command wiring over core.*, sharing all business logic.

No command re-implements a rule -- every command just calls straight into
the matching core.* function and renders whatever it returns or raises.
"""

import json
from functools import wraps
from typing import Any, Callable, TypeVar

import typer

from mcp_local_notes.core import notes, validate, vocabulary
from mcp_local_notes.core.config import (
    get_corpus,
    get_tbox_path,
    load_env_file,
)
from mcp_local_notes.core.errors import NotesError
from mcp_local_notes.core.models import Note
from mcp_local_notes.ontology.tbox import ROOT_TYPE

app = typer.Typer(
    help="local-ontology: manage markdown notes and their Turtle ontology."
)


@app.callback()
def _load_config() -> None:
    """Load .env.json (if present) before any command runs, filling in
    only vars not already set in the environment.

    Renders a malformed file the same way handle_notes_errors renders a
    NotesError (message to stderr, exit 1) -- this isn't a NotesError
    itself (it's a config-file problem, not a notes/vocabulary rule),
    but every command depends on this callback running first, so it
    needs the same non-traceback rendering the rest of the CLI has."""
    try:
        load_env_file()
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


F = TypeVar("F", bound=Callable[..., Any])


def handle_notes_errors(func: F) -> F:
    """Render any NotesError identically across every CLI command:
    message to stderr, exit code 1. The one place this logic lives."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except NotesError as error:
            typer.echo(error.message, err=True)
            raise typer.Exit(code=1) from error

    return wrapper  # type: ignore[return-value]


def _echo_note(action: str, note: Note) -> None:
    """Print "<action> note: <id> (<absolute path>)" -- every command
    that creates or edits a note shares this, so the user can find the
    file directly rather than needing to know NOTES_DIR."""
    path = notes.note_path(note.id, get_corpus().notes_dir).resolve()
    typer.echo(f"{action} note: {note.id} ({path})")


@app.command("add-topic")
@handle_notes_errors
def add_topic_command(name: str) -> None:
    """Add a new topic to the controlled vocabulary."""
    vocabulary.add_topic(name, get_tbox_path())
    typer.echo(f"added topic: {name}")


@app.command("add-class")
@handle_notes_errors
def add_class_command(
    name: str,
    subclass_of: str = typer.Option(ROOT_TYPE, "--subclass-of"),
) -> None:
    """Add a new note type to the ontology."""
    vocabulary.add_class(name, get_tbox_path(), subclass_of=subclass_of)
    typer.echo(f"added type: {name}")


@app.command("new-note")
@handle_notes_errors
def new_note_command(
    title: str,
    tags: list[str] = typer.Option([], "--tag"),
    note_type: str = typer.Option(..., "--type"),
    alias: list[str] = typer.Option([], "--alias"),
    approve_topic: list[str] = typer.Option([], "--approve-topic"),
) -> None:
    """Create a new note."""
    note = notes.new_note(
        title=title,
        tags=tags,
        note_type=note_type,
        corpus=get_corpus(),
        aliases=alias,
        approve_topics=approve_topic,
    )
    _echo_note("created", note)


@app.command("update-note")
@handle_notes_errors
def update_note_command(  # pylint: disable=too-many-arguments
    note_id: str,
    *,
    title: str = typer.Option(None, "--title"),
    add_tag: list[str] = typer.Option([], "--add-tag"),
    remove_tag: list[str] = typer.Option([], "--remove-tag"),
    add_related: list[str] = typer.Option([], "--add-related"),
    remove_related: list[str] = typer.Option([], "--remove-related"),
    approve_topic: list[str] = typer.Option([], "--approve-topic"),
) -> None:
    """Edit an existing note's frontmatter and regenerate its ABox entry."""
    note = notes.update_note(
        note_id,
        get_corpus(),
        title=title,
        add_tags=add_tag,
        remove_tags=remove_tag,
        add_related=add_related,
        remove_related=remove_related,
        approve_topics=approve_topic,
    )
    _echo_note("updated", note)


@app.command("sync-note")
@handle_notes_errors
def sync_note_command(note_id: str) -> None:
    """Regenerate a single note's ABox entry from its current frontmatter."""
    note = notes.sync_note(note_id, get_corpus())
    _echo_note("synced", note)


@app.command("rebuild-abox")
@handle_notes_errors
def rebuild_abox_command() -> None:
    """Rebuild the entire ABox from every note's current frontmatter."""
    notes.rebuild_abox(get_corpus())
    typer.echo("rebuilt abox.ttl")


@app.command("archive-note")
@handle_notes_errors
def archive_note_command(note_id: str) -> None:
    """Archive a note: sets status, keeps the file and ABox entry."""
    note = notes.archive_note(note_id, get_corpus())
    _echo_note("archived", note)


@app.command("delete-note")
@handle_notes_errors
def delete_note_command(
    note_id: str,
    confirm: bool = typer.Option(False, "--confirm"),
) -> None:
    """Hard delete a note and its ABox entry."""
    notes.delete_note(note_id, get_corpus(), confirm=confirm)
    typer.echo(f"deleted note: {note_id}")


@app.command("validate")
def validate_command(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Report every consistency problem in the corpus. Never modifies a file."""
    issues = validate.validate(get_corpus())
    report = validate.build_report(issues)

    if json_output:
        typer.echo(json.dumps(report))
    elif not issues:
        typer.echo("no issues found")
    else:
        for issue in issues:
            typer.echo(
                f"[{issue.type.value}] {issue.note_id}: {issue.message}"
            )

    raise typer.Exit(code=0 if report["ok"] else 1)


@app.command("find-notes-by-topic")
@handle_notes_errors
def find_notes_by_topic_command(
    topic: str,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List every note currently tagged with the given topic."""
    matches = notes.find_notes_by_topic(topic, get_corpus())

    if json_output:
        typer.echo(json.dumps([note.to_frontmatter() for note in matches]))
    elif not matches:
        typer.echo("no notes found")
    else:
        for note in matches:
            typer.echo(f"{note.id}: {note.title}")


@app.command("list-topics")
def list_topics_command() -> None:
    """List the current controlled topic vocabulary."""
    for name in vocabulary.list_topics(get_tbox_path()):
        typer.echo(name)


@app.command("list-types")
def list_types_command() -> None:
    """List the current declared note types."""
    for name in vocabulary.list_types(get_tbox_path()):
        typer.echo(name)


if __name__ == "__main__":
    app()
