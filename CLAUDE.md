# CLAUDE.md

Guidance for Claude Code (or any AI assistant) working in this repository.

## Repository Overview

`mcp-local-notes` manages a corpus of markdown notes whose metadata (id,
title, tags, type, relationships) is kept in sync with a Turtle/RDF
ontology (a TBox of controlled vocabulary, an ABox of per-note facts).
The same operations are exposed two ways from one shared implementation:
a Typer CLI and a local MCP server, so an AI assistant can call them as
typed tools instead of hand-editing files or guessing at Turtle syntax.

See `README.md` for the user-facing quickstart, deployment, and example
prompts. See `user-stories.md` and `features/*.feature` for the original
requirements this project was built from.

## Technology Stack

- **Language**: Python 3.13.7 (declared floor: `>=3.12` in `pyproject.toml`)
- **Package management**: plain `pip` + `requirements.txt` -- no `uv`/`poetry`
- **CLI**: Typer
- **MCP server**: the official `mcp` SDK (`MCPServer`, not the third-party
  `fastmcp` package), served over Streamable HTTP
- **Ontology**: `rdflib` over Turtle files (`tbox.ttl`/`abox.ttl`)
- **Testing**: `pytest` + `pytest-bdd` (Gherkin `.feature` files under
  `features/`, step definitions under `tests/step_defs/`)
- **Packaging**: single-stage Docker image (`python:3.13-slim`), plus a
  Makefile with `build`/`start`/`stop`/`logs` targets

## Code Standards

- **Package layout** (`src/mcp_local_notes/`): `core/` (transport-agnostic
  business logic), `ontology/` (all `rdflib`/Turtle handling), `cli/` (the
  Typer app), `mcp_server/` (the MCP tool registration). `cli/` and
  `mcp_server/` are peer adapters over the same `core/`, with zero
  divergent business logic between them -- every tool/command is a thin
  wrapper that calls straight into a `core.*` function.
- **Shared error model**: `core/errors.py`'s `NotesError(rule, message,
  details)` -- one class, no per-rule subclasses -- rendered identically
  by each adapter's own `handle_notes_errors` wrapper (CLI: message to
  stderr + exit 1; MCP: a structured `{rule, message, details}`
  `CallToolResult`).
- **Config**: `core/config.py` centralizes every environment-driven
  setting (`NOTES_DIR`, `MCP_PORT`, `MCP_HOST`) and the `.env.json`
  loader. Never read `os.environ` directly outside this module.
- Don't add abstractions, error handling, or validation beyond what's
  actually needed -- this codebase favors small, direct functions over
  premature generalization.

## Static Analysis & Testing Standards

This project follows opinionated standards enforced by the
`scaffold-project` skill:

1. **Pinned dependencies**: every version in `requirements.txt` is exact
   (`==`), no ranges.
2. **Static analysis**: run `make static` before committing.
3. **Pre-commit hooks**: configured with gitleaks (secret scanning) and
   `make static`.
4. **Dependabot**: configured for weekly `pip` and `github-actions`
   updates.
5. **CI/CD**: `.github/workflows/static-check.yml` runs `make static-check`
   on every PR and on pushes to `main`.

### Available Make targets

Run `make help` to see all available targets. Key ones:

| Target | Purpose |
|---|---|
| `make static` | Run all static checks with auto-format (black, mypy, shellcheck, pylint, unit tests) |
| `make static-check` | Same, but check-only (no auto-format) -- what CI runs |
| `make unit` | Run unit/pytest-bdd tests only |
| `make unit-update-golden` | Update golden files (this project doesn't currently use golden-file testing, but the target exists for consistency) |
| `make integration` | Run integration tests (none exist yet; the marker is reserved) |
| `make build` / `make start` / `make stop` / `make logs` | Docker packaging -- build the image, run/stop the server as a background container, follow its logs |
| `make demo` | Run a throwaway notes corpus (`mktemp -d`) in the foreground, for trying prompts without touching real notes -- see `DEMO.md` |
| `make .venv` | Create the virtualenv and install dependencies + the package |

## Testing Strategy

- **Unit tests** (`@pytest.mark.unit`): no external dependencies, no
  credentials, no network. This includes the pytest-bdd scenarios (they
  run against the MCP SDK's in-process `list_tools`/`call_tool`, never a
  real HTTP socket) and CLI smoke tests (via Typer's `CliRunner`).
- **Integration tests** (`@pytest.mark.integration`): reserved for tests
  that need real credentials or external fixtures. None exist yet.
- Shared fixtures/helpers live in `tests/conftest.py` (e.g.
  `seed_tbox_with_defaults`, `build_seeded_corpus`, `mint_sparql_basics`).
  Prefer reusing these over duplicating setup logic across test files.
- Every registered operation (CLI command + MCP tool) should have at
  least: a `core.*` unit test, a CLI smoke test, and an MCP-tool test
  (see `tests/test_notes.py`, `tests/test_cli_*.py`,
  `tests/test_mcp_server.py` for the pattern to follow).

## Workflows

- **Git**: feature branches off `main`, PRs reviewed before merge. No
  direct force-pushes to `main`.
- **CI/CD**: GitHub Actions runs `make static-check` on every pull
  request and on every push to `main` -- exactly once per event.
- **Docker**: `make build && make start` gives a fresh clone a working
  MCP server with no local Python install. See `README.md` for
  `MCP_BIND_HOST`/`MCP_PORT`/`NOTES_DIR` configuration and the
  `.env.json` persistence mechanism.

## Guidelines for Claude Code

- Use TDD at the `core.*` seam: write the failing test first, confirm
  red, implement, confirm green, then wire the same behavior into the
  CLI and MCP adapters as thin passthroughs.
- Run `make static` before considering any change complete.
- When adding a new operation, register it in all three places it needs
  to exist: `core/`, `cli/main.py`, `mcp_server/server.py` -- and update
  `README.md`'s "Registered tools" list.
- Don't duplicate business logic between the CLI and MCP adapters; if
  you find yourself doing that, the logic belongs in `core/` instead.
