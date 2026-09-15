"""validate: report every consistency problem in the corpus, without ever
modifying a file (US-3.2). The report schema (issue type/note_id/message/
details, overall {ok, issues} shape) is a decision recorded on the
project's wayfinder map (see "Decide the validation report JSON schema").
"""

from dataclasses import dataclass, field
from pathlib import Path

from mcp_local_notes.core.config import Corpus
from mcp_local_notes.core.errors import Rule
from mcp_local_notes.core.models import Note, parse_frontmatter
from mcp_local_notes.ontology import abox, tbox
from mcp_local_notes.ontology.slug import normalize
from mcp_local_notes.ontology.tbox import NS

_REQUIRED_FIELDS = ("id", "title", "tags", "type")
_FIELDS_TO_CONSTRUCT_NOTE = ("id", "title", "type")


@dataclass
class Issue:
    """One consistency problem, per the documented report schema."""

    type: Rule  # pylint: disable=redefined-builtin
    note_id: str
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """The JSON-ready shape: {type, note_id, message, details}."""
        return {
            "type": self.type.value,
            "note_id": self.note_id,
            "message": self.message,
            "details": self.details,
        }


def build_report(issues: list[Issue]) -> dict:
    """The overall {ok, issues} report, ok iff there are no issues."""
    return {"ok": not issues, "issues": [issue.to_dict() for issue in issues]}


def _check_required_fields(raw: dict, fallback_id: str) -> list[Issue]:
    note_id = raw.get("id") or fallback_id
    return [
        Issue(
            Rule.MISSING_REQUIRED_FIELD,
            note_id,
            f"missing required field: {field_name}",
            {"field": field_name},
        )
        for field_name in _REQUIRED_FIELDS
        if field_name not in raw
    ]


def _check_filename_matches_id(path: Path, note: Note) -> list[Issue]:
    if path.stem == note.id:
        return []
    return [
        Issue(
            Rule.FILENAME_ID_MISMATCH,
            note.id,
            f"filename/id mismatch: file {path.name!r} does not match id {note.id!r}",
            {"filename": path.name},
        )
    ]


def _check_tags_known(note: Note, tbox_graph) -> list[Issue]:
    return [
        Issue(
            Rule.UNKNOWN_TOPIC,
            note.id,
            f"unknown topic: {tag!r} is not present in the topic vocabulary",
            {"topic": tag},
        )
        for tag in note.tags
        if not tbox.topic_exists(tbox_graph, tag)
    ]


def _check_type_known(note: Note, tbox_graph) -> list[Issue]:
    if tbox.type_exists(tbox_graph, note.type):
        return []
    return [
        Issue(
            Rule.UNKNOWN_TYPE,
            note.id,
            f"unknown type: {note.type!r} is not declared in the ontology",
            {"type": note.type},
        )
    ]


def _check_references(note: Note, known_ids: set[str]) -> list[Issue]:
    issues = [
        Issue(
            Rule.RELATED_NOTE_NOT_FOUND,
            note.id,
            f'dangling reference: "related" points to {related_id!r}, '
            "which does not exist",
            {"missing_id": related_id, "field": "related"},
        )
        for related_id in note.related
        if related_id not in known_ids
    ]
    if note.part_of and note.part_of not in known_ids:
        issues.append(
            Issue(
                Rule.PART_OF_NOTE_NOT_FOUND,
                note.id,
                f'dangling reference: "part_of" points to {note.part_of!r}, '
                "which does not exist",
                {"missing_id": note.part_of, "field": "part_of"},
            )
        )
    return issues


def _check_stale_abox(note: Note, abox_graph) -> list[Issue]:
    expected_graph = abox.new_graph()
    abox.replace_note(expected_graph, note.id, note.to_frontmatter())
    expected = set(expected_graph.triples((NS[note.id], None, None)))
    actual = set(abox_graph.triples((NS[note.id], None, None)))
    if expected == actual:
        return []
    return [
        Issue(
            Rule.STALE_ABOX_ENTRY,
            note.id,
            f"stale ABox entry: abox.ttl no longer matches {note.id}'s "
            "current frontmatter",
        )
    ]


def _check_duplicates(all_notes: list[Note]) -> list[Issue]:
    index: dict[str, list[tuple[str, str]]] = {}
    for note in all_notes:
        index.setdefault(normalize(note.title), []).append((note.id, "title"))
        for alias in note.aliases:
            index.setdefault(normalize(alias), []).append((note.id, "alias"))

    issues = []
    for entries in index.values():
        distinct_ids = sorted({note_id for note_id, _ in entries})
        if len(distinct_ids) < 2:
            continue
        fields = {field_name for _, field_name in entries}
        if fields == {"title"}:
            rule, label = Rule.DUPLICATE_TITLE, "duplicate title"
        else:
            rule, label = Rule.DUPLICATE_ALIAS, "duplicate alias"
        issues.append(
            Issue(
                rule,
                distinct_ids[0],
                f"{label}: shared by notes {', '.join(distinct_ids)}",
                {"note_ids": distinct_ids},
            )
        )
    return issues


def validate(corpus: Corpus) -> list[Issue]:
    """Every consistency problem currently in the corpus. Read-only."""
    issues: list[Issue] = []
    parsed: list[tuple[Path, Note]] = []

    if corpus.notes_dir.exists():
        for path in sorted(corpus.notes_dir.glob("*.md")):
            raw = parse_frontmatter(path.read_text())
            issues.extend(_check_required_fields(raw, path.stem))
            if any(f not in raw for f in _FIELDS_TO_CONSTRUCT_NOTE):
                continue
            note = Note.from_frontmatter(raw)
            issues.extend(_check_filename_matches_id(path, note))
            parsed.append((path, note))

    known_ids = {note.id for _, note in parsed}
    tbox_graph = tbox.load(corpus.tbox_path)
    abox_graph = abox.load(corpus.abox_path)

    for _, note in parsed:
        issues.extend(_check_tags_known(note, tbox_graph))
        issues.extend(_check_type_known(note, tbox_graph))
        issues.extend(_check_references(note, known_ids))
        issues.extend(_check_stale_abox(note, abox_graph))

    issues.extend(_check_duplicates([note for _, note in parsed]))

    return issues
