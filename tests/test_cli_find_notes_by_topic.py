"""CliRunner smoke tests: find-notes-by-topic works end-to-end via the CLI."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import NEW_SPARQL_BASICS_CLI_ARGS
from mcp_local_notes.cli.main import app

runner = CliRunner()


@pytest.mark.unit
def test_find_notes_by_topic_lists_matching_notes(_notes_dir: Path) -> None:
    """A note tagged with the topic is listed by id and title."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)

    result = runner.invoke(app, ["find-notes-by-topic", "knowledge-graphs"])

    assert result.exit_code == 0
    assert "sparql-basics: SPARQL basics" in result.stdout


@pytest.mark.unit
def test_find_notes_by_topic_json_mode(_notes_dir: Path) -> None:
    """--json returns the full frontmatter for every matching note."""
    runner.invoke(app, NEW_SPARQL_BASICS_CLI_ARGS)

    result = runner.invoke(
        app, ["find-notes-by-topic", "knowledge-graphs", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [note["id"] for note in payload] == ["sparql-basics"]


@pytest.mark.unit
def test_find_notes_by_topic_unknown_topic_fails_with_message_and_exit_1(
    _notes_dir: Path,
) -> None:
    """An unknown topic prints the error message and exits 1."""
    result = runner.invoke(app, ["find-notes-by-topic", "no-such-topic"])

    assert result.exit_code == 1
    assert "unknown topic" in result.output
