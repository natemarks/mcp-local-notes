# Research: conventions for agent-friendly CLIs and agent docs

**Date:** 2026-10-24
**Issue:** [#63 Conventions for agent-friendly CLIs and agent docs](https://github.com/natemarks/mcp-local-notes/issues/63)
(child of map issue [#48](https://github.com/natemarks/mcp-local-notes/issues/48),
"Local file ontology CLI + Neovim finder: v1 spec")
**Scope:** Primary-source research only. No code was changed. `<app>` is a
placeholder for the new tool's name. The map's standing decisions are taken as
given: agents use the CLI through their shell tool, there is no MCP server, the
CLI and docs are agent-agnostic, and a Claude skill ships with the tool.

## TL;DR

- **The CLI is the primary agent interface and the primary doc.** Anthropic's
  own guidance is that CLI tools are "the most context-efficient way" for Claude
  Code to reach a service, and that Claude learns unfamiliar CLIs from
  `--help`. So `--help` (examples first), `<app> describe --json` and
  `<app> schema` carry most of the weight. Docs files back them up.
- **Developer docs: `AGENTS.md` is the shared file, and `CLAUDE.md` is a one-line
  `@AGENTS.md` import.** Codex, opencode, Cursor, Aider (via config), Gemini CLI
  (via config) and others read `AGENTS.md`. Claude Code reads it natively only
  when there is no `CLAUDE.md` (v2.1.277+). The import is the documented way to
  serve both, and it is safer than a symlink.
- **Skills are now a cross-agent format.** The [Agent Skills](https://agentskills.io)
  standard (`SKILL.md` + YAML frontmatter) is used by Claude Code, Codex and
  opencode. They differ only in *where* they look: Claude Code uses
  `~/.claude/skills/`, Codex uses `~/.agents/skills/`, and opencode reads both.
  One portable `SKILL.md`, installed by the binary into both directories, covers
  all three.
- **`llms.txt` is for websites, not local CLIs.** Skip it unless a docs site is
  published. The CLI's equivalent is `describe` plus `<app> help agents`.
- **Claude Code's Bash tool sets hard numbers the CLI should design for.** About
  30,000 chars of successful output come back inline. Past that, Claude gets a
  file path and a 2,000-char preview. A non-zero exit is treated as a failure
  and only about 10,000 chars come back. So: default result limits, a `total`
  and `truncated` in every list envelope, and **exit 0 for "no matches"**.
  Don't copy `rg`/`grep`'s exit 1 for that case.

## 1. Agent instruction files: AGENTS.md vs CLAUDE.md

### AGENTS.md (the cross-agent convention)

Source: [agents.md](https://agents.md/).

- "Think of AGENTS.md as a README for agents". It holds build steps, tests and
  conventions that would clutter a human README. It is "just standard Markdown"
  with no required fields. It is now stewarded by the Agentic AI Foundation
  under the Linux Foundation.
- It goes at the repo root. Nested files are allowed, and "The closest AGENTS.md
  to the edited file wins". Explicit chat prompts override it.
- Suggested sections: project overview, build and test commands, code style,
  testing instructions, security considerations. "If you list test commands,
  the agent will attempt to run them and fix failures."
- Listed supporters include Codex, Jules, Factory, Aider, goose, opencode, Zed,
  Warp, VS Code, Devin, Junie, Amp, Cursor, RooCode, Gemini CLI, Kilo Code,
  GitHub Copilot coding agent, Windsurf and Augment Code. Some need
  configuration: Aider uses `read: AGENTS.md` in `.aider.conf.yml`, and Gemini
  CLI uses `"context": {"fileName": [...]}`.

### How each agent actually loads it

| Agent | Project file(s) | User-wide file | Notes | Source |
|---|---|---|---|---|
| **Claude Code** | `CLAUDE.md` / `.claude/CLAUDE.md`. Reads `AGENTS.md` **only if** no `CLAUDE.md`/`CLAUDE.local.md` exists in cwd or above (default `claude-md-or-agents-md`). | `~/.claude/CLAUDE.md` | Native `AGENTS.md` reading needs v2.1.277+. Some sessions can't use it, and for those the docs say to "import it from a `CLAUDE.md`". Ignores `AGENTS.override.md`, `AGENTS.local.md` and `.agents/`. | [memory docs](https://code.claude.com/docs/en/memory#agents-md) |
| **Codex** | Walks from the git root down to cwd. Each dir: `AGENTS.override.md`, then `AGENTS.md`, then `project_doc_fallback_filenames`. At most one file per dir. | `~/.codex/AGENTS.override.md` or `AGENTS.md` | Concatenated root to leaf. Stops at `project_doc_max_bytes`, **default 32 KiB**. | [Codex AGENTS.md docs](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| **opencode** | `AGENTS.md`, else `CLAUDE.md` (walks up from cwd) | `~/.config/opencode/AGENTS.md`, else `~/.claude/CLAUDE.md` | "The first matching file wins in each category." | [opencode rules](https://opencode.ai/docs/rules/) |
| **Gemini CLI** | `GEMINI.md` by default | `~/.gemini/GEMINI.md` | Set `context.fileName` to include `AGENTS.md`. | [gemini-md.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md) |
| **Aider** | Nothing automatic | n/a | `aider --read CONVENTIONS.md` or `read:` in `.aider.conf.yml`. | [aider conventions](https://aider.chat/docs/usage/conventions.html) |

### Sharing one file between Claude Code and the rest

Claude Code's docs ([Share one file with other coding tools](https://code.claude.com/docs/en/memory#share-one-file-with-other-coding-tools))
document two options:

```markdown
@AGENTS.md

## Claude Code
<Claude-only additions here>
```

or `ln -s AGENTS.md CLAUDE.md`. The symlink has two drawbacks. Claude's
"Edit and Write tools refuse to write through a symlink". And Windows clones
check it out as a one-line text file. A `CLAUDE.md` that holds `@AGENTS.md` is
"never" read twice under any setting. **Use the import.** It also covers Claude
sessions that can't read `AGENTS.md` natively.

### What goes in it, and how big

- Claude Code: "target under 200 lines per CLAUDE.md file. Longer files consume
  more context and reduce adherence". Imports "don't reduce its context cost".
  Include "Bash commands Claude can't guess", style rules that differ from the
  defaults, test runners, repo etiquette, architectural decisions and gotchas.
  Exclude anything derivable from the code, detailed API docs ("link to docs
  instead") and file-by-file tours. Multi-step procedures belong in a skill.
  ([best practices](https://code.claude.com/docs/en/best-practices#write-an-effective-claude-md),
  [memory](https://code.claude.com/docs/en/memory))
- Codex truncates the combined chain at 32 KiB by default.
- So the developer `AGENTS.md` should *point to* `GLOSSARY.md`, `docs/adr/` and
  the spec by path, not `@`-import them. Agents read them on demand.

## 2. llms.txt

Source: [llmstxt.org](https://llmstxt.org/).

- "We propose adding a `/llms.txt` markdown file to websites to provide
  LLM-friendly content." It sits at the site root or a subpath. It has an H1
  (the only required section), a blockquote summary, and H2 lists of
  `[name](url): notes` links. An `## Optional` section marks skippable links.
- It targets **websites** used at inference time. It says nothing about CLIs.
  The docs sites researched here do serve one (code.claude.com, agentskills.io).
  A local agent driving a shell gets nothing from a file at a URL it has no
  reason to fetch.
- **Verdict:** not part of v1. If the project later publishes a docs site,
  add an `llms.txt` there that links the agent usage guide and the JSON schemas.
  The in-binary equivalents are `<app> describe` (the "what exists" summary) and
  `<app> help agents` (the usage guide).

## 3. Skill packaging and distribution

### The format is a cross-agent standard

- [Agent Skills spec](https://agentskills.io/specification): a skill is a directory
  `skill-name/SKILL.md`, with optional `scripts/`, `references/` and `assets/`.
  The frontmatter needs `name` (≤64 chars, `[a-z0-9-]`, must match the directory
  name) and `description` (≤1024 chars, saying what it does *and when to use
  it*). Optional fields are `license`, `compatibility`, `metadata` and
  `allowed-tools` (experimental). Progressive disclosure works in stages:
  metadata (~100 tokens) is loaded at startup, the body (<5000 tokens, "under
  500 lines") loads on activation, and references load as needed. Keep
  references "one level deep". The format was "originally developed by
  Anthropic, released as an open standard".
- Claude Code: "Claude Code skills follow the Agent Skills open standard". It
  adds extensions such as `disable-model-invocation`, `context: fork`, `paths`
  and `` !`cmd` `` context injection. Outside Claude Code (claude.ai, the API),
  non-spec fields are "a hard error". ([skills docs](https://code.claude.com/docs/en/skills))
- Codex: "Skills build on the open agent skills standard". Codex-specific
  metadata goes in a sidecar `agents/openai.yaml`, not in the frontmatter.
  ([Codex skills](https://learn.chatgpt.com/docs/build-skills))
- opencode: requires `name`/`description` as in the spec. "Unknown frontmatter
  fields are ignored." ([opencode skills](https://opencode.ai/docs/skills/))

### Where each agent looks

| Agent | User-wide | Project | Packaged distribution |
|---|---|---|---|
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/` | Plugin `skills/` dir, shipped through a marketplace (`.claude-plugin/marketplace.json`). `claude plugin marketplace add owner/repo`, then `claude plugin install <plugin>@<marketplace>`. Plugin skills are namespaced `/plugin:skill`. |
| Codex | `$HOME/.agents/skills/` (also `/etc/codex/skills` for admin) | `.agents/skills/`, scanned from cwd up to the repo root | Plugins ("some plugins contain only skills") and `$skill-installer` for curated skills |
| opencode | `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` | none needed |

Claude Code's docs don't mention `.agents/skills`, so it shouldn't be assumed to
read that path. Precedence in Claude Code is enterprise > personal > project.
Codex does "not merge" same-named skills. The opencode docs don't say what happens
when the same name appears in two of its directories. Installing into both
`~/.claude/skills` and `~/.agents/skills` should be checked against opencode
before it's relied on.

### Description budget

- Claude Code truncates each `description` + `when_to_use` at 1,536 chars. The
  whole listing gets about 1% of the context window, and the least-used skills
  lose their descriptions first.
- Codex caps the initial listing at 2% of context, or 8,000 chars.
- So the description should be short and lead with trigger words ("find, tag,
  catalog local files, ontology, concepts...").
- Anthropic's [skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
  add: write it in the third person, assume "Claude is already very smart",
  avoid time-sensitive text, and build evaluations before writing extensive docs.

### Prior art in this repo

`.claude/skills/local-notes/SKILL.md` and `.claude-plugin/{plugin,marketplace}.json`
already follow the Claude Code layout. The workflow pattern carries over well:
look up the vocabulary first, ask one field at a time, read structured
rejections back as questions, and report the absolute path. Two parts are
MCP-specific and must change for the new tool:

- the `allowed-tools: mcp__…` frontmatter (becomes `Bash(<app> *)`, or is
  dropped for portability)
- the `mcpServers` block in `plugin.json` (removed. The plugin becomes
  skills-only)

`docs/research/skill-and-mcp-server-integration.md` explains the
permission-prompt behaviour that `allowed-tools` changes.

## 4. CLI design for agents

### Vendor guidance

- **Claude Code** ([best practices, "Use CLI tools"](https://code.claude.com/docs/en/best-practices#use-cli-tools)):
  "CLI tools are the most context-efficient way to interact with external
  services." "Claude is also effective at learning CLI tools it doesn't already
  know. Try prompts like `Use 'foo-cli-tool --help' to learn about foo tool`".
  The help text is the first-contact doc.
- **Anthropic, [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)**
  (written for MCP tools, but the advice is about tool design in general):
  - consolidate tools that agents would chain into one call
  - "return only high signal information" and resolve opaque IDs to meaningful
    names
  - offer a concise/detailed `response_format`
  - use "pagination, range selection, filtering, and/or truncation" with
    sensible defaults (Claude Code caps tool responses at 25,000 tokens)
  - make errors "clearly communicate specific and actionable improvements,
    rather than opaque error codes or tracebacks"
  - use unambiguous parameter names
- **Claude Code Bash tool limits** ([tools reference, Output limits](https://code.claude.com/docs/en/tools-reference)):
  - A valid result comes back inline up to about 30,000 chars. Past that,
    Claude gets "the path of a file saved to the session directory … plus a
    preview of up to the first 2,000 characters".
  - A failure comes back inline up to about 10,000 chars. Past that, it gets a
    head-and-tail excerpt "with no file path".
  - Exit 1 counts as benign only for `grep`, `rg`, `find`, `diff`, `test`,
    `git diff`/`git grep`. "Every other command that exits 1 counts as a
    failure."
  - The default timeout is 2 minutes.
- **Claude Code env** ([env vars](https://code.claude.com/docs/en/env-vars)):
  `CLAUDECODE=1` is set in Bash-tool subprocesses. The CLI should *not* change
  its behaviour on this variable. Use the TTY check, which works for every
  agent.

### General CLI guidelines ([clig.dev](https://clig.dev/))

- "Display help when passed `-h` or `--help` flags." Lead with examples: "show
  them first in the help page".
- Primary output to stdout. "Log messages, errors, and so on should all be sent
  to `stderr`."
- "Display output as formatted JSON if `--json` is passed."
- "Only use prompts or interactive elements if `stdin` is an interactive
  terminal (a TTY)". "If `--no-input` is passed, don't prompt."
- "Catch errors and rewrite them for humans". "If the user did something wrong
  and you can guess what they meant, suggest it". "Suggest commands the user
  should run."
- Dry run: "describe the changes that would occur". "Confirm before doing
  anything dangerous."
- No pager unless stdin/stdout is a TTY. Disable color when not a TTY or when
  `NO_COLOR` is set.

### How established agent-friendly CLIs do it

- **`gh`** ([formatting](https://cli.github.com/manual/gh_help_formatting),
  [environment](https://cli.github.com/manual/gh_help_environment), `gh help exit-codes`):
  - `--json <fields>`. Running `--json` with no fields lists the available
    fields, which makes the schema discoverable from the CLI itself.
  - `--jq` and `--template` for in-tool filtering.
  - `GH_PROMPT_DISABLED`, `NO_COLOR` and `GH_PAGER` env controls.
  - Documented exit codes: 0 ok, 1 failure, 2 cancelled, 4 auth.
- **`rg`** (`rg --help`, `man rg`): `--json` emits JSON Lines with typed
  messages (`begin`, `match`, `end`, `context`, `summary`). Exit status is 0 for
  a match, 1 for no match, 2 for an error. Claude Code special-cases that exit 1.
  A new tool won't be on that list, so it shouldn't copy the convention.
- **`jq`**: the agent's default post-processor. The tool's JSON should be flat
  and stable enough that `jq -r '.results[].path'` just works.

## 5. Recommendation: the doc and discovery package for `<app>`

### A. The CLI surface (agent-agnostic, version-locked to the binary)

These refine the map's existing "agent-facing CLI requirements":

1. **`--help` on every command, examples first.** Each subcommand's help starts
   with 2-4 real invocations, including a `--json` and a `--dry-run` one.
   Generate the man page from the same source (`clap_mangen` / cobra `doc`), so
   help and man can't drift apart.
2. **`<app> describe [--json] [--brief]`** is the one "orient yourself" call. It
   returns:
   - the schema version
   - the store path
   - concepts with their broader/narrower links
   - Resource types and relation kinds
   - counts
   - the list of commands, each with a one-line summary and a mutating flag

   `--brief` drops the concept tree for large vocabularies. Target well under
   30k chars at the v1 scale.
3. **`<app> schema [<command>]`** prints the JSON Schema of each command's
   `--json` output and of the error envelope. It is the CLI-side version of
   `gh --json` field listing. Nvim uses it too.
4. **`<app> help agents`** prints the agent usage guide, embedded in the binary.
   It works for any agent, including Aider via `aider --read <(app help agents)`
   or a redirect to a file.
5. **Output envelope.** Results are always `{"schema_version": N, ...}`. List
   commands include `results`, `total`, `truncated`, `next_offset`, and use a
   default `--limit` (e.g. 50) with `--offset`. `--fields` narrows each record.
   Records carry absolute `path`, `media_type` and `editable`. `find` returns
   metadata, never file content.
6. **Exit codes, documented in `--help` and the guide:**
   - **0** = success, *including empty results*
   - **1** = rule/domain error (a structured error was emitted)
   - **2** = usage error (bad flags or arguments)
   - **3** = store or environment problem (missing store, lock held)

   Never use 1 for "no matches": Claude Code would truncate the output to the
   10k failure window.
7. **Structured errors.** Under `--json` the error goes to stderr as
   `{"schema_version", "error": {"rule", "message", "details",
   "suggested_fix", "suggested_command"}}`. In text mode it's one `error:` line
   plus a `hint:` line naming the next command, e.g.
   `hint: <app> concept add ml --dry-run`. Keep errors short, well under 10k
   chars.
8. **Non-interactive by default without a TTY.** No prompts, pager, color or
   spinners when stdin/stdout isn't a TTY or `NO_COLOR` is set. Destructive
   commands without a TTY fail with a rule error suggesting `--yes`, and never
   block on input. `--dry-run` on every mutating command prints the planned
   change in the same envelope.

### B. Docs for agents *using* the tool

| Artifact | Where | Notes |
|---|---|---|
| Agent usage guide | `docs/agent-usage.md` (single source), embedded in the binary and printed by `<app> help agents` | Read-only workflow first (`describe` → `find` → open the path). Then mutations, always `--dry-run` first. Vocabulary grows only by explicit command. Exit codes, the error envelope, pagination. |
| Skill | `skills/<app>/SKILL.md` (+ `references/usage.md` = the guide) | **Portable frontmatter only**: `name`, `description`, optionally `compatibility` and `allowed-tools: Bash(<app> *)`. No Claude-only fields and no `` !`cmd` `` injection, which other agents would show as literal text. The body tells the agent to run `<app> describe --json` first, and reuses the `local-notes` skill pattern (look up first, one field at a time, errors become questions, report the absolute path). Under 200 lines. |
| Skill installer | `<app> skill install [--claude] [--agents] [--print]` | Writes the embedded skill to `~/.claude/skills/<app>/` (Claude Code, opencode) and `~/.agents/skills/<app>/` (Codex, opencode), so the skill version always matches the binary. `--print` writes it to stdout for other agents. Verify opencode's duplicate-name behaviour before installing to both by default. |
| Claude plugin (optional) | `.claude-plugin/marketplace.json` + `plugin.json` at the repo root, **skills only, no `mcpServers`** | `claude plugin marketplace add natemarks/<app>` gives automatic updates for Claude users. A thin layer on the same `skills/` dir. |
| `llms.txt` | not in v1 | Only if a docs website appears. |

### C. Docs for agents *developing* the tool

| Artifact | Notes |
|---|---|
| `AGENTS.md` (canonical, <200 lines, well under 32 KiB) | Overview, build/test/lint commands (agents run them), layout, the "core + thin adapters" rule, testing strategy, and *pointers* to the docs below. |
| `CLAUDE.md` | Exactly `@AGENTS.md`, plus Claude-only notes if any. Not a symlink. |
| `GLOSSARY.md` | Domain terms (Resource, Concept, ...), referenced from `AGENTS.md`, not imported. |
| `docs/adr/NNNN-*.md` | One per decision closed on the map. |
| `docs/spec.md` | The v1 spec, written for an agent reader. |
| `.agents/skills/` or `.claude/skills/` project skills | Only for repo-specific workflows (e.g. release). Optional. |

### Open points for the spec

- Exact exit-code numbering beyond 0/1/2 (`gh` uses 4 for auth, which has no
  analogue here).
- Whether `find` should also offer `--jsonl` streaming (`rg`-style) for scripts.
  The default should stay a single bounded JSON document.
- opencode's behaviour when the same skill name exists in both
  `~/.claude/skills` and `~/.agents/skills`.
