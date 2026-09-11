"""Note lifecycle operations: new_note (this ticket), plus update_note,
sync_note, archive_note, delete_note (later tickets).
"""

from datetime import date
from pathlib import Path

from mcp_local_notes.core import vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.core.models import Note, dump_markdown, load_markdown
from mcp_local_notes.ontology import abox, tbox
from mcp_local_notes.ontology.slug import normalize


def _scan_existing_notes(notes_dir: Path) -> list[Note]:
    """Every note currently on disk, parsed from its frontmatter."""
    if not notes_dir.exists():
        return []
    return [
        load_markdown(path.read_text())
        for path in sorted(notes_dir.glob("*.md"))
    ]


def _check_for_duplicates(
    title: str, aliases: list[str], existing: list[Note]
) -> None:
    """Reject a title/alias that normalizes to an existing note's title/alias.

    Which field of the NEW note caused the collision (title vs. alias)
    decides which Rule is raised -- not which field of the existing note
    was hit.
    """
    index: dict[str, str] = {}
    for other in existing:
        index.setdefault(normalize(other.title), other.id)
        for alias in other.aliases:
            index.setdefault(normalize(alias), other.id)

    title_norm = normalize(title)
    if title_norm in index:
        conflicting_id = index[title_norm]
        raise NotesError(
            Rule.DUPLICATE_TITLE,
            f"duplicate title: {title!r} already used by note {conflicting_id}",
            {"conflicting_note_id": conflicting_id},
        )

    for alias in aliases:
        alias_norm = normalize(alias)
        if alias_norm in index:
            conflicting_id = index[alias_norm]
            raise NotesError(
                Rule.DUPLICATE_ALIAS,
                f"duplicate alias: {alias!r} already used by note {conflicting_id}",
                {"conflicting_note_id": conflicting_id, "alias": alias},
            )


def _check_tags(
    tags: list[str], approve_topics: list[str], tbox_path: Path
) -> None:
    """Reject an unknown tag, unless approved in the same request."""
    graph = tbox.load(tbox_path)
    for tag in tags:
        if tbox.topic_exists(graph, tag):
            continue
        if tag in approve_topics:
            vocabulary.add_topic(tag, tbox_path)
            graph = tbox.load(tbox_path)
            continue
        raise NotesError(
            Rule.UNKNOWN_TOPIC,
            f"unknown topic: {tag!r} is not present in the topic vocabulary",
            {"topic": tag},
        )


def _check_type(note_type: str, tbox_path: Path) -> None:
    """Reject a type that isn't declared as a class in the TBox."""
    graph = tbox.load(tbox_path)
    if not tbox.type_exists(graph, note_type):
        raise NotesError(
            Rule.UNKNOWN_TYPE,
            f"unknown type: {note_type!r} is not declared in the ontology",
            {"type": note_type},
        )


def new_note(  # pylint: disable=too-many-arguments
    title: str,
    tags: list[str],
    note_type: str,
    corpus: Corpus,
    *,
    aliases: list[str] | None = None,
    approve_topics: list[str] | None = None,
) -> Note:
    """Create a new note and its ABox entry, atomically.

    Every validation step runs before any file is written, so a rejection
    never leaves a partial note file or ABox change behind (US-1.5).
    """
    aliases = aliases or []
    approve_topics = approve_topics or []

    if not tags:
        raise NotesError(
            Rule.MISSING_REQUIRED_FIELD,
            "missing required field: tags",
            {"field": "tags"},
        )

    _check_tags(tags, approve_topics, corpus.tbox_path)
    _check_type(note_type, corpus.tbox_path)

    existing = _scan_existing_notes(corpus.notes_dir)
    _check_for_duplicates(title, aliases, existing)

    note_id = normalize(title)
    today = date.today().isoformat()
    note = Note(
        id=note_id,
        title=title,
        tags=tags,
        type=note_type,
        aliases=aliases,
        created=today,
        modified=today,
    )

    corpus.notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = corpus.notes_dir / f"{note_id}.md"
    note_path.write_text(dump_markdown(note))

    try:
        graph = abox.load(corpus.abox_path)
        abox.replace_note(graph, note_id, note.to_frontmatter())
        abox.save(graph, corpus.abox_path)
    except Exception:
        note_path.unlink(missing_ok=True)
        raise

    return note
