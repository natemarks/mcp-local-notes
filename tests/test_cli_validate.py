"""CliRunner smoke tests: validate works end-to-end via the CLI."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import NEW_SPARQL_BASICS_CLI_ARGS
from mcp_local_notes.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_validate_clean_corpus_exits_zero(_notes_dir: Path) -> None:
    """validate on a clean corpus exits 0 with no issues printed."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    assert "no issues found" in result.output


@pytest.mark.unit
def test_validate_json_mode_reports_issues(_notes_dir: Path) -> None:
    """validate --json exits 1 and emits a structured report on a bad corpus."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)
    # Introduce a duplicate title by hand-editing a second note.
    runner.invoke(
        app,
        [
            "new-note",
            "Something else",
            "--tag",
            "knowledge-graphs",
            "--type",
            "Concept",
        ],
    )
    note_path = _notes_dir / "something-else.md"
    note_path.write_text(
        note_path.read_text().replace("Something else", "SPARQL basics")
    )

    result = runner.invoke(app, ["validate", "--json"])
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["ok"] is False
    assert any(
        issue["type"] == "DUPLICATE_TITLE" for issue in report["issues"]
    )
