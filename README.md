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

## Use it from Claude Desktop

Once the server is running (`make start`), add it as a custom connector:

1. Settings → Connectors → Add custom connector
2. Name: `local-ontology`
3. URL: `http://127.0.0.1:8000/mcp`

Older Desktop versions that read `claude_desktop_config.json` directly
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`;
Windows: `%APPDATA%\Claude\claude_desktop_config.json`) can instead add:

```json
{
  "mcpServers": {
    "local-ontology": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

then restart Claude Desktop. Either way, its tools appear grouped under
`local-ontology`, e.g. `mcp__local-ontology__new_note`.

## Use it from Claude Code

```sh
claude mcp add --transport http local-ontology http://127.0.0.1:8000/mcp
```

Add `--scope project` to scope the registration to this repo instead of
your user config. Verify with `claude mcp list`; tools then appear the
same way, as `mcp__local-ontology__<tool>`.

If your `MCP_BIND_HOST`/`MCP_PORT` differ from the defaults, use the
matching host/port in the URL above in either client.

## Registered tools

`new_note`, `update_note`, `add_topic`, `add_class`, `sync_note`,
`rebuild_abox`, `validate`, `list_topics`, `list_types`, `archive_note`,
`delete_note`.

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
