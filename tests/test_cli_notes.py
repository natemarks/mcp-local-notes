"""CliRunner smoke tests: new-note works end-to-end via the CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import NEW_SPARQL_BASICS_CLI_ARGS
from mcp_local_notes.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_new_note_creates_a_file(_notes_dir: Path) -> None:
    """new-note creates the note file with the expected slug filename."""
    result = runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    assert result.exit_code == 0
    assert (_notes_dir / "sparql-basics.md").exists()


@pytest.mark.unit
def test_new_note_duplicate_fails_with_message_and_exit_1(
    _notes_dir: Path,
) -> None:
    """A duplicate new-note prints the error message and exits 1."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    assert result.exit_code == 1
    assert "duplicate title" in result.output
