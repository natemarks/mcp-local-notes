# Research: Ontology storage technologies for <10k Resources

**Date:** 2026-10-24
**Issue:** [#50 Ontology storage technologies for <10k Resources](https://github.com/natemarks/mcp-local-notes/issues/50)
(child of map [#48](https://github.com/natemarks/mcp-local-notes/issues/48), "Local file ontology CLI + Neovim finder: v1 spec")

**Standing constraints from #48:** one machine (Ubuntu 26.04); fewer than 10k
Resources; a DB is allowed as the canonical store if it has a git-friendly
export; SKOS concepts and Turtle export are nice-to-haves, and the internal
store does not have to be a triple store; Go or Rust (Python is out); Neovim
is read-only and reads the CLI's JSON output, so **the CLI is the only
process that opens the store**; no daemon.

Prior art reused: [`skos-owl-personal-kb-conventions.md`](./skos-owl-personal-kb-conventions.md)
(prefix and ConceptScheme conventions for a Turtle export).

---

## TL;DR / Recommendation

**Use SQLite with a small relational schema as the canonical store, in WAL
mode, and generate a deterministic, sorted text export (Turtle, plus
optionally JSON Lines) that you commit to git. Make `import` of that export
rebuild the DB.** Model SKOS broader/narrower as an edge table and expand
"tag including narrower concepts" with a `WITH RECURSIVE` CTE.

This works equally well in Go and Rust. Go has the edge if you want a
cgo-free static binary (`modernc.org/sqlite`). Rust's `rusqlite` with the
`bundled` feature is also self-contained.

When each alternative wins:

- **Embedded RDF store (Oxigraph)** wins only if SPARQL itself becomes a
  user-facing feature (arbitrary graph queries, round-tripping third-party
  RDF), and only in **Rust**, because Oxigraph has no Go binding. You pay
  for it with a single-writer RocksDB directory that is undefined behaviour
  to read while another process writes, a binary directory that is not
  git-friendly (you still need an export), and an upstream that calls
  itself "in heavy development".
- **Plain text canonical + cache index** wins if hand-editing the metadata
  in `$EDITOR` and reviewing changes as git diffs matter more than
  transactional integrity. At <10k Resources it is cheap to rebuild an
  index on every run. But you then need a cache (in practice SQLite again),
  so you carry two representations and a staleness check. TOML/YAML suits
  either language. Turtle as the canonical format favours **Rust** (`oxttl`)
  over Go, whose Turtle libraries are small single-maintainer projects.

---

## Query patterns a picker needs

The Telescope picker needs these filters, combined with AND:

1. **Tag, including narrower concepts:** Resources tagged C or any concept
   transitively narrower than C.
2. **Type:** Resources of type T (optionally including subtypes).
3. **Relation:** Resources related to R by predicate P, in either direction.
4. **Title:** substring or fuzzy match. Telescope does the fuzzy match
   client-side, so the store only has to emit `id, title, path, type, tags`
   as JSON.

SKOS semantics for (1): `skos:broader` is **not** transitive. Transitive
inference comes from its super-property `skos:broaderTransitive`, which is
an `owl:TransitiveProperty`. SKOS allows cycles: there is "no condition
requiring that `skos:broaderTransitive` be irreflexive". Integrity condition
S27 makes `skos:related` disjoint with `skos:broaderTransitive`.
([SKOS Reference §8, S22/S24/S27, §8.6.6, §8.6.8](https://www.w3.org/TR/skos-reference/))
So every option has to compute the closure itself and must not loop on
cycles. `validate` should report cycles as warnings, since SKOS itself does
not forbid them.

---

## Option A: SQLite with a relational schema (+ Turtle/JSON export)

Sketch schema: `concept(id, pref_label, scheme)`, `concept_broader(child,
parent)`, `rtype(id, label, parent)`, `resource(id, path, sha256, title,
media_type, rtype)`, `resource_tag(resource, concept)`,
`predicate(id, label, inverse)`, `relation(subject, predicate, object)`.

**Queries.** Recursive CTEs exist for exactly this case: "Recursive common
table expressions provide the ability to do hierarchical or recursive
queries of trees and graphs". The docs' org-chart example (`WITH RECURSIVE
works_for_alice(n) AS (VALUES('Alice') UNION SELECT name FROM org,
works_for_alice WHERE org.boss=works_for_alice.n)`) maps one-to-one onto
"concept C and everything narrower". Use `UNION`, not `UNION ALL`: "UNION is
used instead of UNION ALL to prevent the recursion from entering an infinite
loop if the graph contains cycles." ([sqlite.org/lang_with.html](https://www.sqlite.org/lang_with.html))
Type, relation and title filters are plain joins and `LIKE`. FTS5, if full
text over titles is ever needed, is "an SQLite virtual table module that
provides full-text search" and is enabled by default in the amalgamation
build. ([sqlite.org/fts5.html](https://www.sqlite.org/fts5.html))

**Integrity / validation.** You get real constraints: `PRIMARY KEY`,
`UNIQUE(path)`, `NOT NULL`, `CHECK`, and foreign keys from tags/relations to
concepts/resources. One catch: "Foreign key constraints are disabled by
default ... so must be enabled separately for each database connection"
with `PRAGMA foreign_keys = ON`.
([sqlite.org/foreignkeys.html](https://www.sqlite.org/foreignkeys.html))
The CLI must set this on every open. Cycle detection and missing-file or
hash checks stay in application code (`validate`).

**Concurrency (CLI + nvim reading at once).** In WAL mode "readers do not
block writers and a writer does not block readers", with "only one writer
at a time". WAL mode persists once set. "All processes using a database
must be on the same host ... WAL does not work over a network filesystem",
which is fine for a single-machine tool.
([sqlite.org/wal.html](https://www.sqlite.org/wal.html)) Concurrent writers
(two `add`s at once) are serialised by setting a busy timeout, which "sleeps
... until at least 'ms' milliseconds" before returning `SQLITE_BUSY`.
([sqlite.org/c3ref/busy_timeout.html](https://www.sqlite.org/c3ref/busy_timeout.html))
This is the strongest concurrency story of the three options.

**Export / rebuild.** The DB file is binary and should not be committed.
`sqlite3 db .dump` turns "the entire contents of a database into a single
UTF-8 text file" that can be "converted back into a database by piping it
back into sqlite3". ([sqlite.org/cli.html §9](https://www.sqlite.org/cli.html))
`.dump` is a usable fallback backup, but its diffs are noisy (INSERT order,
schema DDL). For history, use an app-level export instead: a sorted Turtle
file (using the prefix conventions in the prior research) and/or JSON Lines,
one Resource per line sorted by id, so a git diff shows one line per
change. Write an `import` that rebuilds the DB from it, which makes the
export the round-trip format.

**Go.** `modernc.org/sqlite` is "a CGo-free port of the C SQLite3 library"
(v1.61.0, SQLite 3.54.1, linux/amd64 and arm64 among the supported
platforms). ([pkg.go.dev/modernc.org/sqlite](https://pkg.go.dev/modernc.org/sqlite))
`mattn/go-sqlite3` (cgo, v1.14.52, Sep 2026) and `ncruces/go-sqlite3`
(Wasm-based, cgo-free, v0.35.6, Sep 2026) are alternatives (GitHub releases).
For the Turtle export, either hand-write a small serializer for a fixed
shape, or use [`knakk/rdf`](https://github.com/knakk/rdf) (Turtle/N-Triples
files; commits as recent as Sep 2026) or [`deiu/rdf2go`](https://github.com/deiu/rdf2go).
Both are small single-maintainer projects.

**Rust.** `rusqlite` ("an ergonomic wrapper for using SQLite from Rust",
v0.41.0) ([docs.rs/rusqlite](https://docs.rs/rusqlite/latest/rusqlite/)).
Its `bundled` feature "uses a bundled version of SQLite", currently 3.54.0,
so no system libsqlite is needed. ([github.com/rusqlite/rusqlite](https://github.com/rusqlite/rusqlite))
For the Turtle export, `oxttl` (v0.2.5) provides a Turtle parser and a
`TurtleSerializer`. ([docs.rs/oxttl](https://docs.rs/oxttl/latest/oxttl/))

**Language lean:** neutral. Go is slightly easier for a cgo-free static
binary. Rust has the better RDF library for the export.

---

## Option B: Embedded RDF store (Oxigraph) with SPARQL

**What it is.** "Oxigraph is both a graph database and a RDF and SPARQL
toolkit". The on-disk store is "based on the RocksDB key-value store". It
implements SPARQL 1.1 Query/Update/Federated Query (nearly fully
conformant). It reads and writes Turtle, TriG, N-Triples, N-Quads, RDF/XML
and JSON-LD. The project also states that it "is in heavy development and
SPARQL query evaluation has not been optimized yet". Bindings exist for
Rust, Python and JS/Wasm, and there is a CLI/server. **There is no Go
binding.** ([github.com/oxigraph/oxigraph](https://github.com/oxigraph/oxigraph))
The latest release is v0.5.13 (2026-10-22).

**Queries.** This is the most natural fit for (1)-(3). SPARQL property
paths define `elt*` as "zero or more matches" and `elt+` as "one or more",
for example `?x rdf:type/rdfs:subClassOf* ?type`.
([SPARQL 1.1 §9 Property Paths](https://www.w3.org/TR/sparql11-query/#propertypaths))
So "tag C or narrower" is `?r :tag/skos:broader* :C`, with cycles handled
by path semantics. Title search uses `FILTER(CONTAINS(...))` or `REGEX`.
There is no FTS.

**Integrity / validation.** A triple store is schema-less. It will accept a
tag that is not a `skos:Concept`, or a Resource with two titles.
Validation has to be SPARQL `ASK` queries in `validate`, or SHACL/ShEx via
[`rudof`](https://github.com/rudof-project/rudof), a Rust library and CLI
with `shacl-validate`/`shex-validate`. This is more work than SQL
constraints for the same guarantees.

**Concurrency.** `Store::open(path)` is read-write, and "only one
read-write store can exist at a time". `open_read_only` exists, but opening
read-only "while another process writes to the database is undefined
behavior". Transactions are repeatable-read but hold all changes in memory.
([docs.rs Store, v0.5.13](https://docs.rs/oxigraph/latest/oxigraph/store/struct.Store.html))
Because nvim goes through the CLI, any two overlapping CLI invocations
(nvim picker query + a terminal `add`) contend for the RocksDB lock. The
second one fails or must retry. This is weaker than SQLite WAL and would
push toward a long-lived server process, which #48 rules out.

**Export / rebuild.** This is where Oxigraph is strongest. Its native
format is RDF: `dump_to_writer` writes the whole store in any supported
format, and `load_from_reader`/`bulk_loader` rebuild it.
(Store docs, as above.) The RocksDB directory itself is not git-friendly,
so you still commit an export. Default dumps are not guaranteed sorted, so
for stable diffs you would sort N-Triples or canonicalise yourself.

**Go.** No viable equivalent. There is no Oxigraph binding. Cayley's last
release is v0.7.7 (2019-10-15), and its query languages are Gizmo, GraphQL
and MQL, not SPARQL. ([github.com/cayleygraph/cayley](https://github.com/cayleygraph/cayley))
From Go you would shell out to the `oxigraph` CLI/server, which reintroduces
a second process.

**Rust.** First-class: the `oxigraph` crate, plus `oxttl`/`oxrdf`, plus
`rudof` for SHACL.

**Language lean:** strongly Rust.

---

## Option C: Plain text files canonical, with a cache index

Canonical data lives in text, for example a `vocab.ttl` or `vocab.toml`
(concepts, broader, types, predicates) plus a `resources.toml`/`.jsonl` or
one file per Resource under `$XDG_DATA_HOME/<tool>/`. A derived index (in
practice SQLite under `$XDG_CACHE_HOME`) is rebuilt when file mtimes or
hashes change.

**Queries.** At <10k Resources you could skip the index and load everything
into memory on each CLI invocation (parse, build maps, walk broader edges
with a visited set). That is simple, and probably fast enough to parse a
few MB of TOML/JSON per picker launch, but this is unmeasured and should be
prototyped. With a SQLite cache, queries are identical to Option A.

**Integrity / validation.** None at write time beyond what the CLI
enforces. Users (or git merges) can hand-edit files into invalid states, so
`validate` becomes essential rather than a nice-to-have, and every load has
to tolerate or reject bad input. If the files are Turtle, SHACL via `rudof`
(Rust) is an option.

**Concurrency.** Readers never block. Writers must do write-to-temp then
`rename(2)`, which atomically replaces the target, plus an advisory lock
file to serialise concurrent writers. The cache adds a staleness check on
every read. ([man7.org rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html))
The cache-invalidation logic is the main source of bugs in this design.

**Export / rebuild.** Best of the three: the canonical files are the git
history. If the tool always writes sorted output, diffs are minimal. The
index is disposable.

**Go.** TOML: [`BurntSushi/toml`](https://pkg.go.dev/github.com/BurntSushi/toml),
[`pelletier/go-toml/v2`](https://pkg.go.dev/github.com/pelletier/go-toml/v2).
JSON is in the stdlib. Turtle as canonical has only the small libraries
mentioned under Option A.

**Rust.** [`toml`](https://docs.rs/toml) + `serde`, `serde_json`. Turtle
via `oxttl`.

**Language lean:** neutral for TOML/JSON, Rust for Turtle-as-canonical.

---

## Comparison

| Concern | A: SQLite + export | B: Oxigraph | C: Text + cache |
|---|---|---|---|
| Tag incl. narrower | `WITH RECURSIVE` + `UNION` | `skos:broader*` path | in-memory walk or CTE on cache |
| Type / relation / title | joins, `LIKE`, FTS5 | SPARQL patterns, `FILTER` | same as A via cache |
| Integrity at write | PK/UNIQUE/FK/CHECK (FK pragma per connection) | none; SPARQL ASK or SHACL | none; `validate` only |
| CLI + nvim concurrency | WAL: concurrent readers + 1 writer, busy timeout | single RW opener; RO during write is UB | atomic rename + lock file; cache staleness |
| Git-friendly history | app-level sorted export (+ `.dump` fallback) | `dump_to_writer` (sort for stable diffs) | native |
| Rebuild from export | write `import` | `load_from_reader`/`bulk_loader` | index is disposable |
| Go | strong (`modernc.org/sqlite`, cgo-free) | none | strong (TOML/JSON) |
| Rust | strong (`rusqlite` bundled, `oxttl` export) | strong (native) | strong (`serde`, `oxttl`) |
| Moving parts | 1 store + 1 exporter | 1 store + exporter + validator | 2 representations + invalidation |

## Open items for downstream tickets

- Export format and round-trip (#48 "Not yet specified"): this research
  suggests a sorted Turtle export with an `import` that rebuilds, with JSON
  Lines as an optional second export. Whether `import` is lossless needs
  its own ticket.
- Whether the export is written automatically after every mutating command
  (keeps git in sync) or only by an explicit `export` (fewer writes).
- Measure parse and query latency on a synthetic 10k-Resource corpus before
  ruling Option C's no-index variant in or out (unmeasured here).
