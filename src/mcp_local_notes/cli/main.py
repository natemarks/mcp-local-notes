"""Typer CLI: thin command wiring over core.*, sharing all business logic.

No command re-implements a rule -- every command just calls straight into
the matching core.* function and renders whatever it returns or raises.
"""

import json
from functools import wraps
from typing import Any, Callable, TypeVar

import typer

from mcp_local_notes.core import notes, validate, vocabulary
from mcp_local_notes.core.config import get_corpus, get_tbox_path
from mcp_local_notes.core.errors import NotesError
from mcp_local_notes.ontology.tbox import ROOT_TYPE

app = typer.Typer(
    help="local-ontology: manage markdown notes and their Turtle ontology."
)

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
    typer.echo(f"created note: {note.id}")


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
    typer.echo(f"updated note: {note.id}")


@app.command("sync-note")
@handle_notes_errors
def sync_note_command(note_id: str) -> None:
    """Regenerate a single note's ABox entry from its current frontmatter."""
    note = notes.sync_note(note_id, get_corpus())
    typer.echo(f"synced note: {note.id}")


@app.command("rebuild-abox")
@handle_notes_errors
def rebuild_abox_command() -> None:
    """Rebuild the entire ABox from every note's current frontmatter."""
    notes.rebuild_abox(get_corpus())
    typer.echo("rebuilt abox.ttl")


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
