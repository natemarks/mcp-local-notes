"""The note frontmatter data model (see the frontmatter-schema decision).

Every field is always present in the YAML frontmatter, even when empty --
tooling should never have to treat "missing key" and "empty list" as the
same thing.
"""

from dataclasses import dataclass, field

import yaml

STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"


@dataclass
class Note:  # pylint: disable=too-many-instance-attributes
    """One note's frontmatter. Exactly the ten fields the schema decides;
    not reducible without dropping a documented field."""

    id: str
    title: str
    tags: list[str]
    type: str
    aliases: list[str] = field(default_factory=list)
    status: str = STATUS_ACTIVE
    created: str = ""
    modified: str = ""
    related: list[str] = field(default_factory=list)
    part_of: str | None = None

    def to_frontmatter(self) -> dict:
        """The frontmatter as an ordered dict, ready for YAML dumping."""
        return {
            "id": self.id,
            "title": self.title,
            "aliases": self.aliases,
            "tags": self.tags,
            "type": self.type,
            "status": self.status,
            "created": self.created,
            "modified": self.modified,
            "related": self.related,
            "part_of": self.part_of,
        }

    @classmethod
    def from_frontmatter(cls, data: dict) -> "Note":
        """Build a Note from a parsed frontmatter dict."""
        return cls(
            id=data["id"],
            title=data["title"],
            tags=list(data.get("tags", [])),
            type=data["type"],
            aliases=list(data.get("aliases", [])),
            status=data.get("status", STATUS_ACTIVE),
            created=data.get("created", ""),
            modified=data.get("modified", ""),
            related=list(data.get("related", [])),
            part_of=data.get("part_of"),
        )


def dump_markdown(note: Note, body: str = "") -> str:
    """Serialize a Note (plus optional body prose) to a markdown file's text."""
    frontmatter_yaml = yaml.safe_dump(note.to_frontmatter(), sort_keys=False)
    return f"---\n{frontmatter_yaml}---\n{body}"


def load_markdown(text: str) -> Note:
    """Parse a note markdown file's text back into a Note."""
    _, frontmatter_text, _ = text.split("---\n", 2)
    data = yaml.safe_load(frontmatter_text)
    return Note.from_frontmatter(data)
