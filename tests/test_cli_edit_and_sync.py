"""CliRunner smoke tests: update-note/sync-note/rebuild-abox via the CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import NEW_SPARQL_BASICS_CLI_ARGS
from mcp_local_notes.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_update_note_renames_via_cli(_notes_dir: Path) -> None:
    """update-note --title renames the note via the CLI."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(
        app, ["update-note", "sparql-basics", "--title", "Intro to SPARQL"]
    )
    assert result.exit_code == 0
    assert "updated note: sparql-basics" in result.output


@pytest.mark.unit
def test_sync_note_via_cli(_notes_dir: Path) -> None:
    """sync-note regenerates the ABox entry via the CLI."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(app, ["sync-note", "sparql-basics"])
    assert result.exit_code == 0
    assert "synced note: sparql-basics" in result.output


@pytest.mark.unit
def test_rebuild_abox_via_cli(_notes_dir: Path) -> None:
    """rebuild-abox regenerates the whole ABox via the CLI."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(app, ["rebuild-abox"])
    assert result.exit_code == 0
    assert "rebuilt abox.ttl" in result.output
