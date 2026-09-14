---
name: local-notes
description: Create, edit, and organize notes in this project's Turtle/RDF-backed notes corpus through its MCP tools. Use when the user wants to create a note, edit or retag an existing note, add a topic or note type, list the vocabulary, search notes by topic, recover the ontology after hand-edited notes, validate the corpus, or archive/delete a note.
---

# Local Notes

Every note is tagged from a controlled topic vocabulary and classified under a declared note type -- both grow only by explicit `add_topic`/`add_class` calls, never implicitly. That means every workflow below starts from the same question: does what the user wants already exist in the vocabulary, or does it need to be added first? Answer that by looking, not by asking.

## The pattern every workflow follows

1. **Look up the decision context before asking anything.** Call whatever read-only tool tells you what already exists: `list_topics` and `list_types` before creating or retagging a note, `find_notes_by_topic` before pointing a `related` field at another note. There is no `get_note` tool -- to see a note's current frontmatter before editing it, read `<NOTES_DIR>/<id>.md` directly, or use `find_notes_by_topic` if you already know one of its tags. Done when you can name, for every field you're about to ask about, what already exists to choose from.
2. **Ask for each required field one at a time**, stating the existing options and your recommendation alongside the question. Reusing an existing topic or type is the default recommendation; propose creating a new one only when nothing existing fits. Done when every required field has an explicit answer.
3. **Ask for each optional field the same way**, skipping only a field the user's own request already answered. Done when every optional field has been asked about or explicitly skipped.
4. **Call the tool.** A rejection carries a specific rule and details (`UNKNOWN_TOPIC`, `DELETE_BLOCKED_BY_REFERENCES`, etc.) -- read it, turn it back into a question per steps 2-3, rather than retrying blind or dropping information the user already gave you.

## Worked example: creating a note

User: "Create a note about SPARQL basics."

1. Call `list_topics` and `list_types` first -- say they return `["knowledge-graphs"]` and `["Concept"]`.
2. Ask: "What topic should this be tagged with? You already have `knowledge-graphs` -- reuse that, or add a new one?" -- one field, not "give me title/tags/type/aliases."
3. Ask: "What type should this be? You already have `Concept` -- reuse that, or add a new one?"
4. Ask about `aliases` only if the user hasn't already ruled it out; skip `approve_topics` entirely unless step 2 picked a new topic.
5. Call `new_note` with the answers.

## Workflows

| Workflow | Tool(s) | Required | Optional | Check first |
|---|---|---|---|---|
| Create a note | `new_note` | title, tags, note_type | aliases, approve_topics | `list_topics`, `list_types` |
| Edit a note | `update_note` | note_id | title, add_tags, remove_tags, add_related, remove_related, approve_topics | the note's current frontmatter (see above); `list_topics`/`list_types` for any new tag or type; `find_notes_by_topic` for related-note ids |
| Add a topic | `add_topic` | name | -- | `list_topics`, to catch a near-duplicate before it's created (`ml` vs `machine-learning`) |
| Add a note type | `add_class` | name | subclass_of (defaults to `Note`) | `list_types` |
| List the vocabulary | `list_topics`, `list_types` | -- | -- | -- |
| Search notes by topic | `find_notes_by_topic` | topic | -- | `list_topics` -- an unknown topic is rejected outright, so check first if the name's origin is uncertain |
| Recover after hand-edits | `sync_note` (one note), `rebuild_abox` (whole corpus) | note_id (sync_note only) | -- | -- |
| Validate the corpus | `validate` | -- | -- | -- |
| Archive a note | `archive_note` | note_id | -- | -- |
| Delete a note | `delete_note` | note_id | confirm | attempt without `confirm` first -- a `DELETE_BLOCKED_BY_REFERENCES` error names every referencing note; show those to the user before asking whether to force it |
