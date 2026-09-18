# Research: tying the `local-notes` skill to the `local-notes` MCP server

**Date:** 2026-09-18
**Scope:** Primary-source research only. No code was changed as part of this
document. See the final section for concrete follow-up changes.

## Overview

**Purpose of this section.** The four questions below (and the "Current
state" section they build on) investigate whether/how this repo's
`local-notes` Skill and its `local-notes` MCP server can be tied together
more tightly. This Overview translates those findings into (A) a concrete
before/after of what a user actually experiences, and (B) the ordered list
of project changes that gets them there. It cites the sections below
rather than re-deriving them, plus one piece of new primary-source
verification (Claude Code's actual permission-prompt behavior) that the
original four questions did not check directly.

### A. The optimized prompt workflow

**Setup, today.** Two independent manual steps, in either order, with
nothing enforcing that both happen: (1) start the server -- `make build
&& make start` (Docker) or equivalent, since this is an HTTP-transport
server Claude Code never spawns itself (see "Current state" below:
`README.md:127`'s `claude mcp add --transport http local-notes
http://127.0.0.1:8000/mcp` only works once something is already listening
at that URL); (2) `claude mcp add --transport http local-notes
http://127.0.0.1:8000/mcp` to register the server, and separately `make
deploy-skill` to copy `SKILL.md` into
`~/.claude/skills/local-notes/SKILL.md` (`Makefile:106-109`). Forgetting
either step silently breaks the pairing -- the skill triggers with no
server to call, or the server is registered with no skill guiding how to
use it.

**Setup, optimized (target state, after Recommended next steps #3
below).** One command pair replaces both manual steps for a new machine:
`/plugin marketplace add natemarks/mcp-local-notes` followed by `/plugin
install mcp-local-notes` (Question 3) installs the skill and registers
the server declaration together. **This does not remove step (1).**
Verified directly against Claude Code's own docs
(https://code.claude.com/docs/en/mcp, the "Add a remote HTTP server" and
plugin "Automatic lifecycle" sections): Claude Code spawns a *stdio* MCP
server itself via `command`/`args`, but for an *http*-transport server it
only *connects* to a URL that must already be listening -- installing the
plugin never starts the process, because an http-type server declaration
has no `command` field for Claude Code to run. So even in the fully
optimized state, the user still runs `make start` (or however the server
is deployed) before the plugin's registration does anything useful; the
plugin collapses the *registration* + *skill-install* steps, not the
*"is the server actually running"* step. This is the same HTTP-transport
constraint the "Current state" section and Question 3's Recommendation
already flag -- worth restating here because it's the one piece of
friction no amount of Claude-Code-side tooling removes.

**First request, today and optimized (identical in both states).** The
user types a plain task-shaped request -- e.g. "Create a note about
beginner lacrosse practice" -- naming neither "local-notes," "MCP," nor
any tool name. Per Question 2, Claude Code matches this against every
installed skill's `description` alone and triggers `local-notes`
autonomously; nothing about the plugin/`allowed-tools` changes touches
this, because triggering was never the gap. Once triggered, the skill's
own documented workflow runs (`SKILL.md:10-25`): call
`list_topics`/`list_types` first, ask one required field at a time
stating existing options and a recommendation, then ask optional fields,
then call `new_note`.

**Where the two states genuinely differ: permission prompts.** Today,
with no `allowed-tools` line and no session-level allow rule, Manual
(`default`) mode "prompts for permission on first use of each tool"
(https://code.claude.com/docs/en/permission-modes) -- each *distinct*
tool name gets its own one-time prompt the first time it's called in the
session, so a full "create a note" run can surface separate prompts for
`list_topics`, `list_types`, and `new_note` (and `add_topic`/`add_class`
if new vocabulary gets approved along the way).

Adding `allowed-tools: mcp__local-notes__*` to `SKILL.md`'s frontmatter
(Question 1, Recommended next steps #1) does verifiably suppress prompts
-- but **only partially**, which is the gap this Overview was asked to
check directly rather than assume. Per Claude Code's own skills docs
(https://code.claude.com/docs/en/skills, "Pre-approve tools for a
skill"): "The `allowed-tools` field grants permission for the listed
tools during the turn that invokes the skill... The grant clears when you
send your next message." Because this skill's own documented workflow
explicitly asks required fields "one at a time" (`SKILL.md:13`,
`:22-24`) -- meaning the user answers across multiple separate
messages/turns -- only the read-only lookups made in the *first* turn
(`list_topics`, `list_types`) are covered by the grant. The mutating call
at the end (`new_note`, or `add_topic`/`add_class`) happens only after the
user has replied at least once more, by which point the grant has already
cleared, so it still surfaces its own first-use prompt. The docs state
the fix explicitly: "To pre-approve tools for the whole session rather
than a single turn, add allow rules to those permission settings
instead" -- i.e. a `permissions.allow: ["mcp__local-notes__*"]` entry (in
`.claude/settings.json`, not the skill's frontmatter) is what actually
removes prompts for the *entire* multi-turn "create a note" workflow, not
`allowed-tools` alone. `allowed-tools` is still worth adding -- it's real,
documented, removes the first-turn prompts, and is useful
self-documentation per Question 1 -- it just isn't the whole story the
original Question 1 finding's phrasing implied ("a first-time user isn't
prompted tool-by-tool through the five-tool 'create a note' workflow").
See the correction folded into part B below.

**Where friction still remains even at the target state:**

1. The server must already be running (above) -- a Docker/process
   step no client-side registration mechanism removes, because this
   server is HTTP-transport by design, not stdio.
2. The multi-turn permission-grant gap above: `allowed-tools` alone does
   not eliminate every prompt across the skill's own documented "ask one
   field at a time" workflow; a session/project-level `permissions.allow`
   rule is additionally needed for full coverage.
3. The tool-name-prefix migration cost already flagged in Question 3:
   installing the plugin changes the callable name to
   `mcp__plugin_mcp-local-notes_local-notes__<tool>`, which would
   silently break both the `allowed-tools: mcp__local-notes__*` glob and
   any pre-existing direct `claude mcp add local-notes ...` registration
   a user already had, unless that's reconciled first.

### B. What has to change in the project

This mostly sharpens, rather than replaces, the existing "Recommended
next steps" section below -- see that section for the full four-item list
and its ordering rationale. In order:

1. **`SKILL.md` frontmatter: add `allowed-tools: mcp__local-notes__*`**
   (Recommended next steps #1, Question 1) -- still worth doing exactly as
   recommended there. **Correction verified in part A above:** this only
   pre-approves tool calls made in the single turn that invokes the
   skill, not the skill's full multi-turn "ask one field at a time"
   workflow (https://code.claude.com/docs/en/skills). To close that gap,
   also consider a session/project-scoped allow rule -- e.g. a checked-in
   `.claude/settings.json` with `{"permissions": {"allow":
   ["mcp__local-notes__*"]}}` -- which the skills docs themselves point
   to as the mechanism for whole-session pre-approval. Treat this as a
   small fifth item alongside the original four, not a replacement for
   any of them.
2. **Cross-link `README.md`'s two sections** (Recommended next steps #2)
   -- unchanged.
3. **Ship `.claude-plugin/plugin.json` + `.claude-plugin/
   marketplace.json`** (Recommended next steps #3, Question 3) --
   unchanged, with the HTTP-transport caveat from part A restated
   explicitly in whatever docs accompany the plugin: installing it does
   not start the server, so the plugin's own install instructions should
   say "run `make start` first," rather than implying `/plugin install`
   is sufficient on its own.
4. **Optional `@mcp.prompt()`/`@mcp.resource()` layer** (Recommended next
   steps #4, Question 4) -- unchanged, lowest priority.

**Sources for this section** (in addition to those cited throughout the
rest of this document): Claude Code docs, Configure permissions
(MCP tool-naming/allow-rule scope, Manual-mode "first use of each tool"
behavior) -- https://code.claude.com/docs/en/permissions; Claude Code
docs, Permission modes (`default`/Manual mode table) --
https://code.claude.com/docs/en/permission-modes; Claude Code docs,
Skills, "Pre-approve tools for a skill" section (`allowed-tools`
turn-scoped grant, explicit pointer to session-level allow rules
instead) -- https://code.claude.com/docs/en/skills; Claude Code docs, MCP
reference, "Add a remote HTTP server" and plugin "Automatic lifecycle"
sections (HTTP/SSE servers are connected to, never spawned, by Claude
Code) -- https://code.claude.com/docs/en/mcp.

---

## Current state (ground truth, this repo)

- The MCP server is defined in `src/mcp_local_notes/mcp_server/server.py:31`
  as `mcp = MCPServer("local-ontology")`, but the *client-visible* tool
  prefix is not this internal name -- it's whatever alias the user picks at
  registration time. `README.md:127` has the user run
  `claude mcp add --transport http local-notes http://127.0.0.1:8000/mcp`,
  which is why this session's tools appear as `mcp__local-notes__new_note`,
  etc. (confirmed live in this session's own tool list). `README.md:137-141`
  already documents that the alias, not the server's internal name, drives
  the prefix.
- The skill lives at `.claude/skills/local-notes/SKILL.md:1-4` with
  frontmatter `name: local-notes` and a `description` that is entirely
  task-oriented ("Use when the user wants to create a note, edit or retag
  an existing note, ... search notes by topic, ..."). It never mentions
  "MCP", "local-notes" the server, or any `mcp__...` tool name.
- Installing the two pieces are two unrelated manual steps today:
  `claude mcp add ...` (`README.md:127`) and `make deploy-skill`
  (`Makefile:106-109`, a plain `mkdir -p` + `cp` of one file into
  `~/.claude/skills/local-notes/SKILL.md`). Nothing links them.
- This repo has no `.mcp.json` and no `.claude-plugin/` directory yet
  (checked directly -- neither exists).
- The pinned SDK is `mcp==2.2.0` (`requirements.txt`). Its
  `MCPServer` class (installed at
  `.venv/lib/python3.13/site-packages/mcp/server/mcpserver/server.py`)
  exposes `@mcp.tool()` (line 660), `@mcp.resource()` (line 779), and
  `@mcp.prompt()` (line 959) decorators. This server currently only uses
  `@mcp.tool()`.

---

## Question 1: Should the skill mention/reference the MCP server explicitly?

**Finding.** Anthropic's Claude Code skill documentation
(https://code.claude.com/docs/en/skills) ties autonomous invocation
entirely to the `description` field: "Claude uses this to decide when to
apply the skill," matched against the user's own words, not against any
MCP-specific vocabulary. The docs give no guidance about a skill's
`description` mentioning MCP tool names or a server alias, and explicitly
warn that the description's job is to state "the key use case first" in
user-facing terms.

There *is* a documented, primary-source mechanism for a skill to formally
pair itself with an MCP server's tools, but it lives in the frontmatter's
`allowed-tools` field, not `description`. Per
https://code.claude.com/docs/en/mcp (the "Plugin MCP tool names" /
permission-rules section) and corroborated by
https://code.claude.com/docs/en/skills (the `allowed-tools` section):

- Every MCP tool has a stable callable name of the form
  `mcp__<server-alias>__<tool-name>` (or, for a *plugin-bundled* server,
  `mcp__plugin_<plugin-name>_<server-name>__<tool-name>` -- a different
  prefix shape, which matters for Question 3 below).
- `allowed-tools` accepts glob patterns against that name, e.g.
  `mcp__local-notes__*` grants (pre-approves, for the invoking turn) every
  tool the `local-notes` server exposes, exactly the same syntax used for
  `Bash(...)` patterns.
- The same `mcp__<server>__<tool>` name is valid in general permission
  rules (`/docs/en/permissions`), a subagent's `tools` field, and hook
  matchers.

So: the *description* is deliberately server-agnostic (matches user
intent), while `allowed-tools` is the documented place a skill "owns" or
pairs with a specific MCP server's tools.

**Recommendation.** Keep `SKILL.md`'s `description` exactly as it is now
(task-oriented, no mention of "MCP" or "local-notes" the server) -- this
already matches Anthropic's own guidance and is the reason the skill can
trigger without the user knowing an MCP server is involved at all (see
Question 2). Separately, *add* an `allowed-tools: mcp__local-notes__*`
line to the frontmatter. This doesn't change triggering, but it does two
useful things primary sources confirm: (a) it pre-approves the specific
tool set this skill is documented to use, for the invoking turn, so a
first-time user isn't prompted tool-by-tool through the five-tool "create
a note" workflow; and (b) it's a machine-checkable statement, visible in
the file, of exactly which MCP server this skill is paired with -- useful
documentation even though Claude Code doesn't enforce it as a hard
dependency (there is a known SDK issue,
https://github.com/anthropics/claude-code/issues/37683, that
`allowed-tools` is not always enforced as a hard *restriction*; treat it
as a pre-approval/documentation mechanism, not a security boundary).

Caveat worth calling out in the change itself: `mcp__local-notes__*` only
matches if the user registers the server under the alias `local-notes`
(the README's suggested alias, but not enforced -- `README.md:137-141`).
A user who registers it under a different alias breaks this glob silently
(no error, the pre-approval just never matches). The `allowed-tools` line
should be commented to say so.

---

## Question 2: Does the user need to name both the skill and the MCP server, or can the description alone trigger it?

**Finding.** No naming of either is required, by design, and this is
exactly how the skill is already written. Per
https://code.claude.com/docs/en/skills, the `description` field alone
drives autonomous invocation: Claude loads all installed skills'
`name`/`description` pairs into the system prompt at startup and decides
which to invoke by matching the *task* the user describes against that
description -- there is no requirement, and no mechanism shown in the
docs, for the user's prompt to name the skill, name an MCP server, or use
any special syntax. The `README.md`'s own "Example prompts" section
already relies on this: "Create a note titled ... tagged
`lacrosse-coaching`..." (`README.md:189-192`) never says "local-notes" or
"skill."

The one thing that *would* break this is the `disable-model-invocation`
frontmatter flag (https://code.claude.com/docs/en/skills): setting it to
`true` removes the skill's description from the system prompt entirely
and requires the user to invoke it explicitly by name (`/local-notes`).
`SKILL.md` does not set this flag, which is correct for this skill --
"create a note about X" is exactly the kind of task Claude should be able
to route to the skill's workflow on its own, unlike the docs' own example
of a `deploy`-to-production skill that *should* require explicit
invocation.

**Recommendation.** No change needed here -- the skill is already written
to trigger purely from task-shaped language, which is the documented
best case. The only risk is *drift*: if `description` is ever edited to
add implementation detail ("uses the local-notes MCP server's `new_note`
tool..."), that would narrow the phrases that reliably match a user's
natural request without adding any triggering benefit, since triggering
is semantic-match-driven, not keyword/tool-name-driven per the docs
reviewed. Keep future edits to `description` scoped to *what a user might
ask for*, never to *which tool implements it*.

---

## Question 3: Can one registration step install both the MCP server and the skill?

**Finding.** Yes -- via the Claude Code **plugin** system, which is a
first-class, documented mechanism for exactly this, and it is the only
mechanism found that installs a Skill and an MCP server as one unit.

Primary source: https://code.claude.com/docs/en/plugins-reference. A
plugin is described by an optional `.claude-plugin/plugin.json` manifest.
The manifest's `skills` field points at a directory of `<name>/SKILL.md`
files (adds to the default `skills/` scan) and its `mcpServers` field
points at an `.mcp.json`-shaped file (or accepts the server config
inline) -- both fields "merge with other sources," and the docs give a
worked example (`deployment-tools`) whose manifest is literally:

```json
{
  "name": "deployment-tools",
  "skills": "./skills/",
  "mcpServers": "./.mcp.json"
}
```

`${CLAUDE_PLUGIN_ROOT}` is available inside the plugin's own
`.mcp.json`/manifest so a bundled server's `command`/`args` can reference
files relative to wherever the plugin gets installed, rather than a fixed
path.

Installing such a plugin is a *single* command from the user's
perspective once it's published: `/plugin marketplace add
natemarks/mcp-local-notes` (a GitHub repo, or a local path, containing a
`.claude-plugin/marketplace.json` catalog) followed by `/plugin install
mcp-local-notes`, or (for local development, no publishing required)
`claude --plugin-dir ./path/to/repo` to load it directly for testing. This
replaces today's two independent, easy-to-forget steps (`claude mcp add`
+ `make deploy-skill`) with one artifact a user points Claude Code at
once.

Compared to `.mcp.json` project-scope registration (`code.claude.com
/docs/en/mcp-quickstart`, "Edit .mcp.json directly" section): project
scope *does* auto-register the MCP server for every teammate who clones
the repo (Claude Code reads `.mcp.json` at session start and prompts for
one-time approval), but `.mcp.json` has no field for bundling a skill --
it is purely `{"mcpServers": {...}}`. It solves "don't make teammates
remember `claude mcp add`," but not "install the skill too." Only the
plugin manifest's `skills` field solves both together.

**Important side effect to flag**, confirmed from the same MCP-naming
section of `code.claude.com/docs/en/mcp`: a plugin-bundled MCP server's
tools are named `mcp__plugin_<plugin-name>_<server-name>__<tool-name>`,
*not* `mcp__<alias>__<tool-name>`. If this repo becomes a plugin named
e.g. `mcp-local-notes` bundling a server keyed `local-notes`, every tool
name changes shape to something like
`mcp__plugin_mcp-local-notes_local-notes__new_note`. That breaks:
(a) this repo's own README's documented tool-name examples
(`README.md:117-119, 135, 166-168`), (b) the `allowed-tools:
mcp__local-notes__*` glob recommended in Question 1, and (c) any user's
existing direct `claude mcp add local-notes ...` registration, which would
now coexist with a second, differently-prefixed registration if they also
installed the plugin. This is a real migration cost, not just a docs
update -- worth deciding deliberately rather than as a side effect of
"just bundle it."

**Recommendation.** Ship a plugin as an *additional*, not replacement,
installation path: add a `.claude-plugin/plugin.json` (with `skills:
"./.claude/skills/"` and `mcpServers` pointing at a new small
`.mcp.json`-shaped file whose `command`/`args` invoke the already-existing
`mcp-local-notes-server` entry point, using `${CLAUDE_PLUGIN_ROOT}` so it
works from any install location) plus a minimal
`.claude-plugin/marketplace.json` so `/plugin marketplace add
natemarks/mcp-local-notes && /plugin install mcp-local-notes` becomes the
one-step alternative to today's `claude mcp add` + `make deploy-skill`.
Keep the existing manual paths documented in the README as-is for anyone
who prefers a locally-run (non-Docker-hosted-by-Claude-Code) server, since
the plugin's `mcpServers` entry would need to itself run/launch the
server (likely via `mcp-local-notes-server` directly, sidestepping
Docker) -- reconcile that with the Docker-first deployment story before
shipping, rather than as an afterthought.

---

## Question 4: Can the MCP server itself serve the skill via the protocol (no `~/.claude/skills/` copy)?

**Finding.** Mechanically, the SDK supports it; behaviorally, it would not
substitute for a Skill, per the protocol's own stated design.

The pinned SDK, `mcp==2.2.0`, exposes both `@mcp.prompt()` and
`@mcp.resource()` (`.venv/lib/python3.13/site-packages/mcp/server/
mcpserver/server.py:779` and `:959`) which back the protocol's
`resources/list`/`resources/read` and `prompts/list`/`prompts/get`
methods. This server (`src/mcp_local_notes/mcp_server/server.py`) uses
neither today -- only `@mcp.tool()`. So it is entirely possible to add,
e.g., `@mcp.prompt()` registering the SKILL.md workflow text as a prompt
named `create-note` (or a `@mcp.resource("notes://workflow-guide")`
serving the raw workflow text), and any MCP client, including Claude Code,
would see it via `prompts/list`/`resources/list` with zero additional
`~/.claude/skills/` file management -- it travels with the server
connection itself.

However, the MCP specification is explicit that this is a *different*
invocation model than a Skill, not an equivalent one. From
https://modelcontextprotocol.io/specification/2025-06-18/server/prompts:
"Prompts are designed to be **user-controlled**, meaning they are exposed
from servers to clients with the intention of the user being able to
explicitly select them for use. Typically, prompts would be triggered
through user-initiated commands in the user interface... as slash
commands." Claude Code's own docs (`code.claude.com/docs/en
/mcp-quickstart`, "Next steps": "Run MCP prompts as commands from the `/`
menu") confirm this is how Claude Code actually surfaces them -- as
explicit, user-typed `/mcp__local-notes__<prompt-name>` slash commands,
not something Claude autonomously reaches for the way it does a Skill's
`description`-matched invocation (Question 2). MCP resources are likewise
surfaced for explicit `@`-mention reference (per the same doc's "Next
steps" list: "Reference MCP resources in prompts with @ mentions"), not
autonomously consulted.

That is the crux of the gap: `SKILL.md`'s entire value in this repo is
the *procedural* guidance -- "look up `list_topics`/`list_types` before
asking," "ask one field at a time," "read a `DELETE_BLOCKED_BY_REFERENCES`
error's details back as a question" -- being loaded and applied
*automatically* whenever the user says "create a note about X," with no
extra action from the user. An MCP prompt/resource serving that same text
would require the user to already know to type `/mcp__local-notes__...`
or `@local-notes:...` first, which defeats the "ask one field at a time,
starting from what already exists" workflow the skill exists to
automate. It moves the discovery burden back onto the user -- the exact
problem the skill was built to avoid.

**Recommendation.** Do not replace the Skill with an MCP prompt/resource.
It is a legitimate *complementary* addition, not a substitute:
`@mcp.resource("notes://schema")` exposing a live snapshot of
`list_topics()`/`list_types()` as a resource a user (or the model, once
already engaged) can `@`-mention is plausibly useful for manual,
exploratory sessions, and `@mcp.prompt()` versions of the worked examples
in `README.md`'s "Creating documents with the Divio documentation types"
section could give power users a fast, explicit shortcut. But keep
`SKILL.md` as the mechanism that makes "create a note about X" work
without the user knowing anything about MCP, prompts, or slash commands
at all -- that's the one invocation model the protocol itself says is not
what `prompts`/`resources` are for.

---

## Recommended next steps

Ordered by value-for-effort, most valuable/cheapest first:

1. **Add `allowed-tools: mcp__local-notes__*` to `SKILL.md`'s
   frontmatter**, with a one-line comment noting it only pre-approves
   correctly if the server is registered under the `local-notes` alias.
   Cheapest change here (one frontmatter line), directly documents the
   skill/server pairing the way Anthropic's own docs support doing it,
   and removes a real per-tool approval-prompt annoyance on first use.
   (Question 1.)

2. **Cross-link `README.md`'s "Use it from Claude Code" and "Claude
   skill" sections.** Today they're two unconnected headings
   (`README.md:121-145` and `146-163`). A single added sentence in each
   ("this pairs with the skill below" / "this skill is written for the
   `local-notes` MCP server above") costs nothing and fixes the
   documentation-level disconnect the task description opens with, even
   before any code/plugin change ships.

3. **Ship a `.claude-plugin/plugin.json` + `.claude-plugin/
   marketplace.json`** bundling the existing `.claude/skills/local-notes/`
   directory and a new `.mcp.json`-shaped `mcpServers` entry that launches
   `mcp-local-notes-server` via `${CLAUDE_PLUGIN_ROOT}`. This is the only
   mechanism found that gives a true single-command install
   (`/plugin marketplace add` + `/plugin install`) for both pieces
   together (Question 3). Do this only after deciding how it coexists
   with the Docker-first deployment story and after updating every
   `mcp__local-notes__<tool>` reference in `README.md` to note the
   different `mcp__plugin_mcp-local-notes_local-notes__<tool>` prefix a
   plugin install produces, since that's a breaking naming change for
   anyone following existing docs literally.

4. **Optionally add one or two `@mcp.prompt()`/`@mcp.resource()`
   registrations** to `src/mcp_local_notes/mcp_server/server.py` (e.g. a
   `notes://vocabulary` resource mirroring `list_topics`/`list_types`, or
   a prompt version of one Divio-type worked example) as a power-user
   convenience layered on top of, never instead of, the Skill (Question
   4). Lowest priority: it's additive polish, not something closing a gap
   the other three items don't already close.

## Sources

- This repo: `.claude/skills/local-notes/SKILL.md`,
  `src/mcp_local_notes/mcp_server/server.py`, `README.md`, `Makefile`,
  `requirements.txt` (`mcp==2.2.0`), and the installed SDK at
  `.venv/lib/python3.13/site-packages/mcp/server/mcpserver/server.py`
  (decorator docstrings for `tool`/`resource`/`prompt` at lines 660, 779,
  959).
- MCP specification, prompts: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
- Claude Code docs, Skills: https://code.claude.com/docs/en/skills
- Claude Code docs, MCP reference (tool-naming/permission-rules section):
  https://code.claude.com/docs/en/mcp
- Claude Code docs, MCP quickstart (`.mcp.json`, scopes, "Run MCP prompts
  as commands" / "Use MCP resources" pointers):
  https://code.claude.com/docs/en/mcp-quickstart
- Claude Code docs, Plugins reference (manifest schema, bundling
  `skills` + `mcpServers`): https://code.claude.com/docs/en/plugins-reference
- Claude Code plugin marketplace docs:
  https://code.claude.com/docs/en/plugin-marketplaces
- `allowed-tools` enforcement caveat:
  https://github.com/anthropics/claude-code/issues/37683
