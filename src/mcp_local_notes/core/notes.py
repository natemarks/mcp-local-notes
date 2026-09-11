"""Note lifecycle operations: new_note, update_note, sync_note,
rebuild_abox, archive_note, delete_note.
"""

from datetime import date
from pathlib import Path

from mcp_local_notes.core import vocabulary
from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import NotesError, Rule
from mcp_local_notes.core.models import (
    STATUS_ARCHIVED,
    Note,
    dump_markdown,
    load_markdown,
)
from mcp_local_notes.ontology import abox, tbox
from mcp_local_notes.ontology.slug import normalize


def _note_path(note_id: str, notes_dir: Path) -> Path:
    return notes_dir / f"{note_id}.md"


def get_note(note_id: str, notes_dir: Path) -> Note:
    """Load a single note's current on-disk frontmatter."""
    return load_markdown(_note_path(note_id, notes_dir).read_text())


def _write_note(note: Note, notes_dir: Path) -> None:
    _note_path(note.id, notes_dir).write_text(dump_markdown(note))


def _scan_existing_notes(notes_dir: Path) -> list[Note]:
    """Every note currently on disk, parsed from its frontmatter."""
    if not notes_dir.exists():
        return []
    return [
        load_markdown(path.read_text())
        for path in sorted(notes_dir.glob("*.md"))
    ]


def _check_for_duplicates(
    title: str,
    aliases: list[str],
    existing: list[Note],
    exclude_id: str | None = None,
) -> None:
    """Reject a title/alias that normalizes to an existing note's title/alias.

    Which field of the NEW note caused the collision (title vs. alias)
    decides which Rule is raised -- not which field of the existing note
    was hit. exclude_id skips a note being renamed comparing against itself.
    """
    index: dict[str, str] = {}
    for other in existing:
        if other.id == exclude_id:
            continue
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
    _write_note(note, corpus.notes_dir)

    try:
        graph = abox.load(corpus.abox_path)
        abox.replace_note(graph, note_id, note.to_frontmatter())
        abox.save(graph, corpus.abox_path)
    except Exception:
        _note_path(note_id, corpus.notes_dir).unlink(missing_ok=True)
        raise

    return note


def _check_related_exists(note_id: str, notes_dir: Path) -> None:
    """Reject a related/part_of reference to a note id that doesn't exist."""
    if not _note_path(note_id, notes_dir).exists():
        raise NotesError(
            Rule.RELATED_NOTE_NOT_FOUND,
            f"related note not found: {note_id!r} does not exist",
            {"related_id": note_id},
        )


def _apply_tag_edits(
    note: Note,
    add_tags: list[str] | None,
    remove_tags: list[str] | None,
    approve_topics: list[str] | None,
    tbox_path: Path,
) -> list[str]:
    """The note's new tag list, validated against the vocabulary."""
    new_tags = list(note.tags)
    for tag in add_tags or []:
        if tag not in new_tags:
            new_tags.append(tag)
    for tag in remove_tags or []:
        if tag in new_tags:
            new_tags.remove(tag)
    _check_tags(new_tags, approve_topics or [], tbox_path)
    return new_tags


def _apply_related_edits(
    note: Note,
    add_related: list[str] | None,
    remove_related: list[str] | None,
    notes_dir: Path,
) -> list[str]:
    """The note's new related-id list, validated against existing notes."""
    new_related = list(note.related)
    for related_id in add_related or []:
        _check_related_exists(related_id, notes_dir)
        if related_id not in new_related:
            new_related.append(related_id)
    for related_id in remove_related or []:
        if related_id in new_related:
            new_related.remove(related_id)
    return new_related


def _apply_rename(
    note: Note, new_title: str | None, notes_dir: Path
) -> tuple[str, list[str]]:
    """The note's new (title, aliases), preserving the old title as an
    alias on a genuine rename (US-2.2); rejects a colliding new title."""
    if new_title is None or new_title == note.title:
        return note.title, list(note.aliases)

    existing = _scan_existing_notes(notes_dir)
    _check_for_duplicates(
        new_title, note.aliases, existing, exclude_id=note.id
    )
    aliases = [note.title] + [
        alias for alias in note.aliases if alias != note.title
    ]
    return new_title, aliases


def update_note(  # pylint: disable=too-many-arguments
    note_id: str,
    corpus: Corpus,
    *,
    title: str | None = None,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    add_related: list[str] | None = None,
    remove_related: list[str] | None = None,
    approve_topics: list[str] | None = None,
) -> Note:
    """Edit an existing note's frontmatter and regenerate its ABox entry.

    Renaming (a changed title) preserves the old title as an alias; the
    id and filename never change (US-2.2). Every validation step runs
    before the note file is rewritten, so a rejection leaves the note
    untouched.
    """
    note = get_note(note_id, corpus.notes_dir)

    note.tags = _apply_tag_edits(
        note, add_tags, remove_tags, approve_topics, corpus.tbox_path
    )
    note.related = _apply_related_edits(
        note, add_related, remove_related, corpus.notes_dir
    )
    note.title, note.aliases = _apply_rename(note, title, corpus.notes_dir)
    note.modified = date.today().isoformat()

    _write_note(note, corpus.notes_dir)

    graph = abox.load(corpus.abox_path)
    abox.replace_note(graph, note.id, note.to_frontmatter())
    abox.save(graph, corpus.abox_path)

    return note


def sync_note(note_id: str, corpus: Corpus) -> Note:
    """Regenerate a single note's ABox entry from its current on-disk
    frontmatter, recovering from edits made outside any tool session."""
    note = get_note(note_id, corpus.notes_dir)
    graph = abox.load(corpus.abox_path)
    abox.replace_note(graph, note.id, note.to_frontmatter())
    abox.save(graph, corpus.abox_path)
    return note


def rebuild_abox(corpus: Corpus) -> None:
    """Regenerate the entire ABox from every note's current frontmatter.

    Built from a fresh graph rather than the old one, so a note id with
    no corresponding file is simply never re-added -- no separate
    "prune stale entries" pass is needed.
    """
    graph = abox.new_graph()
    for note in _scan_existing_notes(corpus.notes_dir):
        abox.replace_note(graph, note.id, note.to_frontmatter())
    abox.save(graph, corpus.abox_path)


def archive_note(note_id: str, corpus: Corpus) -> Note:
    """Retire a note by setting its status, the safe default (US-2.4).
    The note file and its ABox entry are left in place."""
    note = get_note(note_id, corpus.notes_dir)
    note.status = STATUS_ARCHIVED
    note.modified = date.today().isoformat()
    _write_note(note, corpus.notes_dir)

    graph = abox.load(corpus.abox_path)
    abox.replace_note(graph, note.id, note.to_frontmatter())
    abox.save(graph, corpus.abox_path)

    return note


def _find_referencing_notes(note_id: str, notes_dir: Path) -> list[str]:
    """Every note id whose related or part_of field points at note_id."""
    return [
        other.id
        for other in _scan_existing_notes(notes_dir)
        if note_id in other.related or other.part_of == note_id
    ]


def delete_note(note_id: str, corpus: Corpus, confirm: bool = False) -> None:
    """Hard delete a note and its ABox entry.

    Rejected with the referencing notes named if any other note points
    at it, unless explicitly confirmed (US-5.1).
    """
    referencing = _find_referencing_notes(note_id, corpus.notes_dir)
    if referencing and not confirm:
        names = ", ".join(referencing)
        raise NotesError(
            Rule.DELETE_BLOCKED_BY_REFERENCES,
            f"delete blocked: {names} references {note_id!r}",
            {"note_id": note_id, "referencing_note_ids": referencing},
        )

    _note_path(note_id, corpus.notes_dir).unlink(missing_ok=True)

    graph = abox.load(corpus.abox_path)
    abox.remove_note(graph, note_id)
    abox.save(graph, corpus.abox_path)
