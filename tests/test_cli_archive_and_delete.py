"""CliRunner smoke tests: archive-note/delete-note via the CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import NEW_SPARQL_BASICS_CLI_ARGS
from mcp_local_notes.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_archive_note_via_cli(_notes_dir: Path) -> None:
    """archive-note sets status via the CLI, keeping the file in place."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(app, ["archive-note", "sparql-basics"])
    assert result.exit_code == 0
    assert "archived note: sparql-basics" in result.output
    assert (_notes_dir / "sparql-basics.md").exists()


@pytest.mark.unit
def test_delete_note_via_cli(_notes_dir: Path) -> None:
    """delete-note removes the file via the CLI when nothing references it."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(app, ["delete-note", "sparql-basics"])
    assert result.exit_code == 0
    assert not (_notes_dir / "sparql-basics.md").exists()


@pytest.mark.unit
def test_delete_note_blocked_without_confirm_via_cli(_notes_dir: Path) -> None:
    """delete-note without --confirm fails with exit 1 when referenced."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    runner.invoke(
        app,
        [
            "new-note",
            "Intro to SPARQL",
            "--tag",
            "knowledge-graphs",
            "--type",
            "Concept",
        ],
    )
    runner.invoke(
        app,
        ["update-note", "intro-to-sparql", "--add-related", "sparql-basics"],
    )

    result = runner.invoke(app, ["delete-note", "sparql-basics"])
    assert result.exit_code == 1
    assert "intro-to-sparql" in result.output

    result = runner.invoke(app, ["delete-note", "sparql-basics", "--confirm"])
    assert result.exit_code == 0
    assert not (_notes_dir / "sparql-basics.md").exists()
