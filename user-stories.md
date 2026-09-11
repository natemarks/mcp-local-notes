# User Stories: Local Notes Ontology Tooling

Scope: a standalone tool (library + CLI + optional MCP server) that manages
markdown notes with frontmatter and a synchronized Turtle (TBox/ABox)
ontology, replacing ad hoc hand-authored Turtle edits.

Roles referenced below:
- **Nate** — the notes author/maintainer, and the person any tool ultimately serves.
- **Assistant** — any AI agent (Claude or otherwise) invoking the tool on Nate's behalf.
- **CI** — an automated pipeline (e.g. pre-commit hook, GitHub Action) invoking validation.

---

## Epic 1 — Creating notes

**US-1.1** As Nate, I want to create a new note by providing a title, one or
more tags, and a type, so that a consistent, uniquely-identified note and its
ontology entry are created together in a single step.

**US-1.2** As Nate, I want the tool to reject a title or alias that collides
with any existing note's title or alias, so that every note stays uniquely
addressable.

**US-1.3** As Nate, I want the tool to reject tags that aren't already in the
controlled topic vocabulary unless I explicitly approve adding them, so the
vocabulary doesn't fragment into near-duplicate tags (`ml` vs `machine-learning`).

**US-1.4** As Nate, I want the tool to auto-generate a stable, immutable
id/slug for each note, so links and ontology references never break when I
later rename it.

**US-1.5** As an Assistant, I want the note-creation operation to fail loudly
and atomically on any validation error, so I never leave a half-written note
file or a partially-updated ontology behind.

## Epic 2 — Editing notes & keeping the ontology synced

**US-2.1** As Nate, I want editing a note's frontmatter to automatically
regenerate its ABox entry, so the ontology never drifts from what the note
actually says.

**US-2.2** As Nate, I want renaming a note's title to automatically preserve
the old title as an alias, so existing references and search terms keep
working.

**US-2.3** As Nate, I want to re-sync a single note, or rebuild the entire
ABox from every note's current frontmatter, on demand, so I can recover from
edits made outside the tool (e.g. by hand, or by another program).

**US-2.4** As Nate, I want archiving a note (setting status rather than
deleting it) to be the default way to retire it, so inbound links from other
notes aren't silently broken.

## Epic 3 — Validation

**US-3.1** As Nate, I want one validation command that reports missing
required fields, duplicate ids/titles/aliases, unknown tags, dangling
`related`/`part_of` references, and stale ABox entries, so I can trust the
corpus is internally consistent.

**US-3.2** As Nate, I want validation to only report problems, never silently
fix them, so I stay in control of every change.

**US-3.3** As CI, I want validation results available as a non-zero exit
code and/or machine-readable (JSON) output, so I can gate commits or runs on
a clean notes corpus.

## Epic 4 — Vocabulary governance

**US-4.1** As Nate, I want to add a new topic or note type as its own
explicit action, so growing the vocabulary is always a visible, deliberate
decision rather than an implicit side effect of writing a note.

**US-4.2** As Nate, I want to list the current topics and types before
creating a note, so I reuse existing vocabulary instead of creating
near-duplicates.

**US-4.3** As Nate, I want an attempt to add a topic or type that already
exists to be rejected as a duplicate, so the vocabulary stays clean.

## Epic 5 — Archiving & deletion

**US-5.1** As Nate, I want a hard delete of a note that has inbound
references from other notes to warn me and require explicit confirmation,
so I don't unknowingly break links.

**US-5.2** As Nate, I want a confirmed hard delete to also remove the note's
ABox block, so the ontology doesn't retain a ghost entry.

## Epic 6 — Tool exposure & packaging

**US-6.1** As Nate, I want these operations exposed as callable tools (not
prose instructions an assistant has to reconstruct each time), so any
assistant or script can invoke them the same way, every time.

**US-6.2** As Nate, I want the tools grouped under a clearly named category
(e.g. "local ontology tools"), so their purpose is obvious when I or an
assistant is browsing available tools.

**US-6.3** As Nate, I want the underlying operations available both as a
CLI (for scripting/CI) and as MCP tools (for assistant use), sharing one
implementation, so I'm not locked into a single interface and behavior can't
diverge between them.

**US-6.4** As Nate, I want every operation to run entirely against local
files with no network calls, so my personal notes never leave my device.

**US-6.5** As an Assistant, I want tool errors returned as structured,
specific failures (e.g. "duplicate title: X already used by note Y"), not
raw exceptions or generic failures, so I can explain the problem to Nate
without guessing.

---

## Recommendation: how to expose these operations

**Yes — package them as a local MCP server, in a clearly named category,
backed by a plain library.**

Concretely:

1. **Core logic as a transport-agnostic library.** Implement `new_note`,
   `update_note`, `add_topic`, `add_class`, `sync_note`, `rebuild_abox`,
   `validate`, `list_topics`, `list_types` (and later, `archive_note` /
   `delete_note`) as plain functions operating on the local filesystem, with
   no dependency on CLI or MCP framing. This is what US-6.3 and US-6.1 above
   are really asking for, and it's what makes the Gherkin scenarios in this
   project testable without spinning up a server.

2. **A thin CLI adapter** over that library, useful standalone for
   scripting, cron jobs, and CI validation gates — no assistant required.

3. **A thin local MCP server adapter** over the same library, run as a
   stdio process the user's desktop app launches, registered once. This
   environment already has first-class support for exactly this pattern —
   a user-configured local MCP server whose tools get proxied into any
   session as `mcp__<server>__<tool>` — so this isn't a new mechanism to
   invent, just a server to write against a client that already exists.

4. **Group the tools under one category name**, e.g. `local-ontology`
   (surfacing as `mcp__local-ontology__new_note`, `mcp__local-ontology__validate`,
   etc.), so an assistant browsing tools sees them as one obviously-related
   family rather than loose, unrelated functions.

Why MCP over "just shell out to the CLI from a skill": a typed tool
definition (explicit parameters, explicit return schema, explicit error
shape) is far more reliable for an assistant to call correctly than
constructing a shell command and parsing free-text stdout — exactly the
failure mode the original notes-ontology-manager *skill* has today (Claude
hand-composing Turtle text and eyeballing the syntax). The CLI stays valuable
in parallel for anything that isn't assistant-driven.
