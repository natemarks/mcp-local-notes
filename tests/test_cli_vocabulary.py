"""CliRunner smoke tests: the vocabulary commands work end-to-end via the CLI.

Verifies the CLI is a genuinely thin adapter -- same behavior, same errors,
same rendering rule (message to stderr, exit 1) -- over core.vocabulary.
"""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_local_notes.cli.main import app

BOOTSTRAP = Path(__file__).parent.parent / "notes" / "tbox.ttl"

runner = CliRunner()


@pytest.fixture(name="_notes_dir")
def _notes_dir_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """An isolated NOTES_DIR, pre-seeded with the bootstrap tbox.ttl."""
    shutil.copy(BOOTSTRAP, tmp_path / "tbox.ttl")
    monkeypatch.setenv("NOTES_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.unit
def test_add_topic_then_list_topics(_notes_dir: Path) -> None:
    """add-topic followed by list-topics shows the new topic."""
    result = runner.invoke(app, ["add-topic", "knowledge-graphs"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["list-topics"])
    assert result.exit_code == 0
    assert "knowledge-graphs" in result.stdout


@pytest.mark.unit
def test_add_topic_twice_fails_with_message_and_exit_1(
    _notes_dir: Path,
) -> None:
    """A duplicate add-topic prints the error message and exits 1."""
    runner.invoke(app, ["add-topic", "knowledge-graphs"])
    result = runner.invoke(app, ["add-topic", "knowledge-graphs"])
    assert result.exit_code == 1
    assert "topic already exists" in result.output


@pytest.mark.unit
def test_add_class_then_list_types(_notes_dir: Path) -> None:
    """add-class followed by list-types shows the new type."""
    result = runner.invoke(app, ["add-class", "Recipe"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["list-types"])
    assert result.exit_code == 0
    assert "Recipe" in result.stdout
    assert "Note" in result.stdout


@pytest.mark.unit
def test_add_class_twice_fails_with_message_and_exit_1(
    _notes_dir: Path,
) -> None:
    """A duplicate add-class prints the error message and exits 1."""
    runner.invoke(app, ["add-class", "Recipe"])
    result = runner.invoke(app, ["add-class", "Recipe"])
    assert result.exit_code == 1
    assert "type already exists" in result.output
