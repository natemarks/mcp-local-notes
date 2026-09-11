"""CliRunner smoke tests: new-note works end-to-end via the CLI."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_local_notes.cli.main import app
from mcp_local_notes.core import vocabulary

BOOTSTRAP = Path(__file__).parent.parent / "notes" / "tbox.ttl"

runner = CliRunner()


@pytest.fixture(name="_notes_dir")
def _notes_dir_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """An isolated NOTES_DIR, pre-seeded with a valid tag and type."""
    tbox_path = tmp_path / "tbox.ttl"
    shutil.copy(BOOTSTRAP, tbox_path)
    (tmp_path / "abox.ttl").write_text(
        "@prefix : <https://notes.natenite.net/ontology#> .\n"
    )
    vocabulary.add_topic("knowledge-graphs", tbox_path)
    vocabulary.add_class("Concept", tbox_path)
    monkeypatch.setenv("NOTES_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.unit
def test_new_note_creates_a_file(_notes_dir: Path) -> None:
    """new-note creates the note file with the expected slug filename."""
    result = runner.invoke(
        app,
        [
            "new-note",
            "SPARQL basics",
            "--tag",
            "knowledge-graphs",
            "--type",
            "Concept",
        ],
    )
    assert result.exit_code == 0
    assert (_notes_dir / "sparql-basics.md").exists()


@pytest.mark.unit
def test_new_note_duplicate_fails_with_message_and_exit_1(
    _notes_dir: Path,
) -> None:
    """A duplicate new-note prints the error message and exits 1."""
    args = [
        "new-note",
        "SPARQL basics",
        "--tag",
        "knowledge-graphs",
        "--type",
        "Concept",
    ]
    runner.invoke(app, args)
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "duplicate title" in result.output
