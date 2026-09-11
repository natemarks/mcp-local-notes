"""Typer CLI: thin command wiring over core.*, sharing all business logic.

No command re-implements a rule -- every command just calls straight into
the matching core.* function and renders whatever it returns or raises.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

import typer

from mcp_local_notes.core import notes, vocabulary
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
