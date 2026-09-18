# mcp-local-notes

Manages a corpus of markdown notes whose metadata (id, title, tags, type,
relationships to other notes) is kept in sync with a Turtle/RDF ontology
(a TBox of controlled vocabulary and an ABox of per-note facts), instead
of hand-editing both and letting them drift. The same operations --
create a note, edit one, grow the vocabulary, validate the whole corpus,
archive/delete a note -- are available two ways from one shared
implementation: a Typer CLI for scripting/CI, and a local MCP server so
an AI assistant can call them as typed tools instead of guessing at file
edits. Every operation runs entirely against local files, with no
network calls beyond the MCP server itself listening on localhost.

## Deploy (Docker, no local Python required)

```sh
git clone https://github.com/natemarks/mcp-local-notes.git
cd mcp-local-notes
make build && make start
```

This builds the image and runs the server as a background container,
bind-mounting `./notes` (which ships with a bootstrap `tbox.ttl`/`abox.ttl`)
into the container and publishing the MCP endpoint at
`http://127.0.0.1:8000/mcp`.

Other targets:

```sh
make logs   # follow the running container's logs
make stop   # stop and remove the container
```

Configuration (env vars, all optional):

| Variable | Default | Meaning |
|---|---|---|
| `NOTES_DIR` | `./notes` | Host directory bind-mounted into the container as the notes corpus |
| `MCP_PORT` | `8000` | Host-side port the server is published on |
| `MCP_BIND_HOST` | `127.0.0.1` | Host-side address the port is published on -- loopback-only by default, so a fresh `make start` never exposes your notes to your local network. Set to `0.0.0.0` only if you deliberately want LAN access (e.g. from another of your own devices). |

### Persisting config across runs (.env.json)

Instead of exporting these every time, copy the committed example and
edit it:

```sh
cp .env.example.json .env.json
```

`.env.json` is gitignored (your own machine's settings, not shared),
while `.env.example.json` stays committed with the defaults above. It's
read by:

- `make build`/`make start` -- supplies `NOTES_DIR`/`MCP_PORT`/`MCP_BIND_HOST`
  defaults for the Makefile itself.
- The CLI and the bare `mcp-local-notes-server` -- read it directly for
  `NOTES_DIR`/`MCP_PORT`/`MCP_HOST`.

An already-exported shell env var always wins over `.env.json` (it only
fills in what isn't already set), and a `make start NOTES_DIR=...`
command-line argument wins over both. `.env.json` is never read inside
the Docker container itself (it isn't shipped in the image) -- the MCP
server logs which file it used and the resolved values at startup:

```
loaded config from .env.json
NOTES_DIR=./notes MCP_PORT=8000 MCP_HOST=127.0.0.1
```

or, with no file present:

```
no .env.json found; using the process environment and defaults
NOTES_DIR=./notes MCP_PORT=8000 MCP_HOST=127.0.0.1
```

## Use it from Claude Desktop

Claude Code connects to a local, unencrypted `http://` MCP server
directly, with the simple URL-based config shown below in "Use it
from Claude Code" -- Claude Desktop does not. Desktop needs a stdio
bridge in front of it instead, via the
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) package.

Once the server is running (`make start`), edit
`claude_desktop_config.json` directly (macOS: `~/Library/Application
Support/Claude/claude_desktop_config.json`; Windows:
`%APPDATA%\Claude\claude_desktop_config.json`) to add:

```json
{
  "mcpServers": {
    "local-notes": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "http://localhost:8000/mcp",
        "--allow-http",
        "--transport",
        "http-first"
      ]
    }
  }
}
```

then restart Claude Desktop. Its tools then appear grouped under
`local-notes`, e.g. `mcp__local-notes__new_note` -- same as Claude
Code.

## Use it from Claude Code

With the server running on localhost (`make start`, or a bare
`mcp-local-notes-server`), register it once from this repo's directory:

```sh
claude mcp add --transport http local-notes http://127.0.0.1:8000/mcp
```

This uses the default `local` scope -- private to you, specific to this
project directory. Use `--scope project` instead if you want the
registration checked into a shared `.mcp.json` for teammates, or
`--scope user` to make it available from every project on this machine.
Verify with `claude mcp list`; tools then appear the same way, as
`mcp__local-notes__<tool>`.

The name `local-notes` is just this repo's suggested registration
alias -- it's the client-side label you choose with `claude mcp add`
(or the "Name" field in Claude Desktop), not something the server
itself enforces, so registering it under a different name works too;
the tool prefix simply follows whatever alias you pick.

If your `MCP_BIND_HOST`/`MCP_PORT` differ from the defaults, use the
matching host/port in the URL above in either client.

## Claude skill

This repo ships a Claude Code skill at `.claude/skills/local-notes/`
that teaches an assistant the workflow for each tool below: which
fields are required vs. optional, and -- critically -- to check
`list_topics`/`list_types` (or a note's current frontmatter) *before*
asking the user what to use, rather than guessing or asking blind.
It's available automatically to any Claude Code session run from this
repo. To make it available from every project on your machine instead:

```sh
make deploy-skill
```

This copies `.claude/skills/local-notes/SKILL.md` into
`~/.claude/skills/local-notes/SKILL.md`, overwriting only that one
file -- nothing else under `~/.claude/skills` is touched.

## Registered tools

`new_note`, `update_note`, `add_topic`, `add_class`, `sync_note`,
`rebuild_abox`, `validate`, `list_topics`, `list_types`, `archive_note`,
`delete_note`, `find_notes_by_topic`.

## Example prompts

Want to try these against a disposable corpus instead of your real
notes? See [DEMO.md](DEMO.md) -- `make demo` spins up a throwaway
notes directory and walks through a larger version of these same
prompts end to end.

### Creating documents with the Divio documentation types

The [Divio documentation system](https://docs.divio.com/documentation-system/introduction/)
identifies four document purposes -- tutorial, how-to, reference,
explanation -- that should stay distinct rather than blended together.
They map directly onto this project's single-valued `type` field, and
the bootstrap `tbox.ttl` ships with all four already declared
(`Tutorial`, `How-to`, `Reference`, `Explanation`) -- no `add_class`
step needed, just classify every new note as exactly one of them.
Examples in the domain of beginner lacrosse coaching:

**Tutorial** (learning-oriented, hand-holds a first-time coach)
> "Create a note titled 'Running Your First Beginner Practice', type
> `Tutorial`, tagged `lacrosse-coaching` (approve the topic), covering the
> practice in order: cradling warm-up, wall ball pairs, then a ground-ball
> scramble."

**How-to** (goal-oriented, solves one specific problem)
> "Create a note titled 'How to Run a Ground Ball Drill', type `How-to`,
> tagged `lacrosse-coaching`, with the steps for a two-line
> grounder-and-scoop drill and a common coaching cue for body position."

**Reference** (dry, lookup-only)
> "Create a note titled 'Youth Lacrosse Positions and Field Terminology',
> type `Reference`, tagged `lacrosse-coaching`, listing attack/midfield/
> defense/goalie roles and basic field zones."

**Explanation** (understanding-oriented, the "why" behind a choice)
> "Create a note titled 'Why Wall Ball Is the Foundation of Stick Skills',
> type `Explanation`, tagged `lacrosse-coaching`, discussing why
> repetition against a wall builds the muscle memory later drills depend
> on."

### Searching for notes by topic

First list what topics exist, then search within one:

> "What topics are in my local-notes vocabulary?"

This calls `list_topics`, returning every topic currently declared in
`tbox.ttl` (e.g. `lacrosse-coaching`, from the notes created above).

> "Show me every note tagged `lacrosse-coaching`."

This calls `find_notes_by_topic`, returning the four notes created above
(one per Divio type). An unknown topic name is rejected with a structured
`UNKNOWN_TOPIC` error rather than silently returning nothing, since that
usually means a typo -- run the `list_topics` prompt above first if
you're not sure of the exact name.

## Local development (no Docker)

```sh
make .venv        # create a virtualenv and install dependencies + the package
make static       # black, mypy, pylint, unit tests -- everything CI runs
make unit         # just the unit/pytest-bdd tests
```

The CLI (`mcp-local-notes`) and the bare MCP server
(`mcp-local-notes-server`, binding to `127.0.0.1:8000/mcp` by default) both
work without Docker once the virtualenv is set up; see `make help` for
every available target.
