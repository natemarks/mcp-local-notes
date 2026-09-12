# mcp-local-notes

Local markdown notes with a synchronized Turtle (TBox/ABox) ontology,
exposed as a CLI and a local MCP server. Every operation runs entirely
against local files, with no network calls beyond the MCP server itself
listening on localhost.

## Quickstart (Docker, no local Python required)

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

## Registering with an MCP client

Register the server under the `local-ontology` key so its tools appear as
`mcp__local-ontology__<tool>` (e.g. `mcp__local-ontology__new_note`). For a
client that takes a Streamable HTTP URL directly:

```json
{
  "mcpServers": {
    "local-ontology": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

If your `MCP_BIND_HOST`/`MCP_PORT` differ from the defaults, use the
matching host/port in the URL above.

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
