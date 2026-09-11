"""The structured error model shared by the CLI and MCP adapters."""

from enum import Enum
from typing import Any


class Rule(str, Enum):
    """Every rule violation a core operation can reject a request for,
    plus the validate-only findings that never arise as a rejection."""

    DUPLICATE_TITLE = "DUPLICATE_TITLE"
    DUPLICATE_ALIAS = "DUPLICATE_ALIAS"
    UNKNOWN_TOPIC = "UNKNOWN_TOPIC"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    RELATED_NOTE_NOT_FOUND = "RELATED_NOTE_NOT_FOUND"
    PART_OF_NOTE_NOT_FOUND = "PART_OF_NOTE_NOT_FOUND"
    TOPIC_ALREADY_EXISTS = "TOPIC_ALREADY_EXISTS"
    TYPE_ALREADY_EXISTS = "TYPE_ALREADY_EXISTS"
    DELETE_BLOCKED_BY_REFERENCES = "DELETE_BLOCKED_BY_REFERENCES"
    STALE_ABOX_ENTRY = "STALE_ABOX_ENTRY"
    FILENAME_ID_MISMATCH = "FILENAME_ID_MISMATCH"


class NotesError(Exception):
    """A single parameterized error type raised by every core operation.

    Both the CLI and MCP adapters render this identically: rule is the
    machine-checkable discriminator, message is human-readable, details
    is a plain rule-specific dict of secondary context.
    """

    def __init__(
        self, rule: Rule, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message
        self.details = details or {}
