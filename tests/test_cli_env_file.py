"""CliRunner tests: the CLI loads .env.json (if present) before any
command runs, filling in only vars not already set in the environment.
"""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_local_notes.cli.main import app

BOOTSTRAP_TBOX = Path(__file__).parent.parent / "notes" / "tbox.ttl"
EMPTY_ABOX = "@prefix : <https://notes.natenite.net/ontology#> .\n"

runner = CliRunner()


@pytest.mark.unit
def test_cli_picks_up_notes_dir_from_env_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With NOTES_DIR unset, a .env.json in the working directory supplies
    it, and the CLI genuinely reads/writes that directory."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NOTES_DIR", raising=False)

    real_notes_dir = tmp_path / "actual-notes"
    real_notes_dir.mkdir()
    shutil.copy(BOOTSTRAP_TBOX, real_notes_dir / "tbox.ttl")
    (real_notes_dir / "abox.ttl").write_text(EMPTY_ABOX)
    (tmp_path / ".env.json").write_text(
        f'{{"NOTES_DIR": "{real_notes_dir}"}}'
    )

    result = runner.invoke(app, ["add-topic", "knowledge-graphs"])

    assert result.exit_code == 0
    assert "knowledge-graphs" in (real_notes_dir / "tbox.ttl").read_text()


@pytest.mark.unit
def test_cli_already_set_notes_dir_wins_over_env_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An already-exported NOTES_DIR is not overridden by .env.json."""
    monkeypatch.chdir(tmp_path)

    real_notes_dir = tmp_path / "real"
    real_notes_dir.mkdir()
    shutil.copy(BOOTSTRAP_TBOX, real_notes_dir / "tbox.ttl")
    (real_notes_dir / "abox.ttl").write_text(EMPTY_ABOX)
    monkeypatch.setenv("NOTES_DIR", str(real_notes_dir))

    decoy_notes_dir = tmp_path / "decoy"
    decoy_notes_dir.mkdir()
    (tmp_path / ".env.json").write_text(
        f'{{"NOTES_DIR": "{decoy_notes_dir}"}}'
    )

    result = runner.invoke(app, ["add-topic", "knowledge-graphs"])

    assert result.exit_code == 0
    assert "knowledge-graphs" in (real_notes_dir / "tbox.ttl").read_text()
    assert not (decoy_notes_dir / "tbox.ttl").exists()


@pytest.mark.unit
def test_cli_malformed_env_json_fails_with_message_and_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed .env.json is rejected consistently -- message to
    stderr, exit 1 -- instead of an uncaught traceback on every command."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.json").write_text("{not valid json")

    result = runner.invoke(app, ["list-topics"])

    assert result.exit_code == 1
    assert "invalid JSON in" in result.output
