# Research: Go vs Rust for a user-wide ontology CLI

Issue: [#49 Go vs Rust for a user-wide ontology CLI](https://github.com/natemarks/mcp-local-notes/issues/49)
(child of map issue [#48](https://github.com/natemarks/mcp-local-notes/issues/48)).
Companion ticket: [#50 Ontology storage technologies](https://github.com/natemarks/mcp-local-notes/issues/50).

**Context from the map.** One machine (Ubuntu 26.04), fewer than 10k Resources, a
single-binary CLI that a Neovim/Telescope picker shells out to on every open,
explicit `add` plus optional `scan` with media-type detection, a central store
(possibly a DB) with a git-friendly export, and SKOS/Turtle export as nice-to-haves.
Python is out.

**This machine** (checked 2026-10-24): Go 1.26.8 installed; no Rust toolchain
(`apt-cache policy` offers `rustc`/`cargo` 1.93.1 and `rustup` 1.27.1);
`file`/`libmagic1t64` 5.46 installed, `libmagic-dev` **not** installed; `gcc` 15.2
installed; Neovim 0.12.6.

Library facts below come from each project's own repo, README, or docs (fetched
2026-10-24). Star counts and release dates are from the GitHub API on the same day.

## TL;DR

**Pick Go**, with `modernc.org/sqlite` (pure Go, no cgo) as the store driver and
`file --mime-type` (or the pure-Go `gabriel-vasile/mimetype`) for detection. Go
is already installed, `CGO_ENABLED=0` gives one static binary that
`go install ...@latest` drops into `~/.local/bin` (via `GOBIN`), and it
starts in under a millisecond. Every piece of the likely stack (SQLite, JSON,
CLI, golden tests) is mature in Go.

**Rust wins if** storage research picks an **embedded RDF/SPARQL store**
(Oxigraph). Go has nothing equivalent. Rust also wins if you want libmagic
linked in-process with safe, typed bindings, or if you value Rust's type system
enough to pay for the toolchain. Startup latency and binary size do not
separate the two at this scale.

## 1. Startup latency and binary size

Measured on this machine with throwaway probes (`/tmp`, not committed). Each
was run 100 times after 5 warm-ups; figures are wall-clock medians, process
spawn included.

| Probe | Size (stripped, `-trimpath -ldflags="-s -w"`) | Linkage | Median | p95 |
|---|---|---|---|---|
| `/bin/true` (floor) | n/a | n/a | 0.31 ms | 0.64 ms |
| Go: encode a 1-element JSON array | 1.86 MB | static | 0.75 ms | 0.82 ms |
| Go + `modernc.org/sqlite` v1.61.0: `SELECT` 10k rows, emit JSON | 6.80 MB | static (`CGO_ENABLED=0`) | 12.85 ms | 13.50 ms |
| Go + `mattn/go-sqlite3` v1.14.52 (cgo): same query | 3.98 MB | dynamic (libc) | 12.29 ms | 14.04 ms |
| `file --mime-type -b` on one file | n/a | n/a | 0.92 ms | 1.02 ms |

Findings:

- Go's runtime start costs about 0.4 ms above `/bin/true`. That is nothing next to a
  Telescope picker opening.
- At 10k rows the pure-Go and cgo SQLite drivers run within about 0.5 ms of each other. The
  time goes to row scanning and `map`-based JSON encoding, not to SQLite. So the
  "transpiled SQLite is 1.3x-2x slower" caveat in the modernc docs
  ([pkg.go.dev/modernc.org/sqlite](https://pkg.go.dev/modernc.org/sqlite))
  doesn't matter for this workload. That holds as long as queries use indexes, which the
  same docs advise checking with `EXPLAIN QUERY PLAN`.
- Rust was **not measured**: no toolchain is installed, and installing one would have
  expanded the scope. A Rust binary has no GC runtime to start. Expect a
  hello-world in the same sub-millisecond band and a `rusqlite`+`bundled` binary
  of a few MB. In the picker path the difference from Go would be well under a
  millisecond, so it shouldn't decide anything.
- Binary size: about 7 MB (Go, pure SQLite) against "a few MB" (Rust) is irrelevant for a
  binary in `~/.local/bin`.

**Verdict: tie.** Both are fast enough to run on every picker open.

## 2. Install story and toolchain cost

**Go.**
- `go install <module>/cmd/<name>@latest` builds in module-aware mode and installs into
  `GOBIN`, which defaults to `$GOPATH/bin` or `$HOME/go/bin`
  ([go.dev/ref/mod#go-install](https://go.dev/ref/mod#go-install)). Running
  `GOBIN=~/.local/bin go install ...` gives the XDG-friendly location directly.
- With no cgo, the binary is static. A GitHub-release tarball of one file is then
  trivial, and so is cross-compiling (`GOOS`/`GOARCH`) if macOS ever returns.
- cgo is "enabled by default for native builds" but "disabled ... when
  cross-compiling" and when no C compiler is on `PATH`
  ([pkg.go.dev/cmd/cgo](https://pkg.go.dev/cmd/cgo)). Any cgo dependency (libmagic,
  `mattn/go-sqlite3`) brings back a C toolchain and dev headers on every
  build machine. That is the main reason to stay cgo-free.
- Toolchain cost: zero, since Go 1.26.8 is already here.

**Rust.**
- `cargo install` builds from source and installs into `<root>/bin`. The root
  resolves from `--root`, then `CARGO_INSTALL_ROOT`, then `install.root` config,
  then `CARGO_HOME`, then `$HOME/.cargo`. So `cargo install --root ~/.local` lands in
  `~/.local/bin`. `--locked` is needed for reproducible installs. Without it Cargo
  "will recompute which versions of dependencies to use"
  ([doc.rust-lang.org/cargo/commands/cargo-install](https://doc.rust-lang.org/cargo/commands/cargo-install.html)).
- Toolchain: install either rustup (its official installer, which puts `rustc`/`cargo`/`rustup` in
  `$HOME/.cargo/bin`, per
  [rustup installation](https://rust-lang.github.io/rustup/installation/index.html))
  or Ubuntu's `rustc`/`cargo` 1.93.1 packages. Either is a one-off cost for this
  single-machine user.
- Native build deps: `rusqlite`'s `bundled` feature compiles SQLite from source
  via the `cc` crate ([docs.rs/crate/rusqlite](https://docs.rs/crate/rusqlite/latest)),
  so it needs a C compiler (`gcc` is present). Oxigraph's default `rocksdb`
  feature builds RocksDB, a large C++ library, from a git submodule
  ([oxrocksdb-sys README](https://github.com/oxigraph/oxigraph/blob/main/oxrocksdb-sys/README.md)),
  with `bindgen` and `cc` among workspace dependencies
  ([Cargo.toml](https://github.com/oxigraph/oxigraph/blob/main/Cargo.toml)).
  That makes the first build slow and needs a C++ toolchain.
- Oxigraph's MSRV is Rust 1.87 (`rust-version` in the workspace `Cargo.toml`).
  Ubuntu's packaged 1.93.1 meets it.

**Verdict: Go is clearly cheaper**: no new toolchain, and no C toolchain if you stay
cgo-free. Rust's cost is real but one-off, so it is not disqualifying.

## 3. libmagic access

Ubuntu ships `libmagic1t64` 5.46 (installed). Linking against it needs
`libmagic-dev` (not installed).

| Option | Language | How | Notes |
|---|---|---|---|
| `rakyll/magicmime` | Go | cgo binding | Needs `apt-get install libmagic-dev` or "compilation will be terminated by an error saying `magic.h` cannot be found" ([README](https://github.com/rakyll/magicmime)). Last push 2024-03. Forces cgo, so the static-binary story is lost. |
| `vimeo/go-magic` | Go | cgo binding | Last push 2019-11, so treat it as unmaintained. |
| `gabriel-vasile/mimetype` v1.4.16 (2026-10-17) | Go | pure Go, magic numbers | "no external dependencies", "no C bindings", detects text vs binary, and is compared against libmagic on "around 50 000 sample files". It reads only the header by default (`SetLimit` adjusts that). Its README admits magic-number detection is "slow, inaccurate, and non-standard" ([README](https://github.com/gabriel-vasile/mimetype)). |
| `h2non/filetype` | Go | pure Go | Last release v1.1.1 (2021). Binary formats only. |
| `magic` crate (robo9k/rust-magic) v0.16.7 | Rust | FFI via `magic-sys` | Needs "sudo apt-get install libmagic1 libmagic-dev", has feature flags per libmagic version (e.g. `libmagic+v5-45`), MSRV 1.64 ([README-crate](https://github.com/robo9k/rust-magic/blob/main/README-crate.md)). Actively maintained. |
| `infer` v0.22.0, `tree_magic_mini` | Rust | pure Rust | Magic-number signatures and a freedesktop-style type tree respectively. |
| Shell out to `file --mime-type -b` | either | subprocess | Measured at 0.92 ms per file here. It uses the system magic database, so results match what `xdg-open`/`file` users see. No build deps. |

Detection matters only for `add`/`scan`, never in the picker path. At under 10k
files, a subprocess per file costs about 10 s for a full scan (one `file` call can also
take many paths at once). So **shelling out to `file` is a legitimate seam in
either language**, and it removes libmagic from the language decision. If
in-process detection is wanted, Rust's `magic` crate is the better-maintained
binding. In Go, the in-process choice is `mimetype` (pure, good coverage, not
libmagic-identical), because cgo would cost the static binary.

**Verdict: neutral if you shell out (recommended). Rust leads slightly for linked libmagic.**

## 4. Embedded SQLite

**Go.**
- `modernc.org/sqlite` v1.61.0 is a "CGo-free port of the C SQLite3 library", a
  `database/sql` driver supporting linux/amd64 among many others. Docs warn that
  two goroutines on one connection "can corrupt memory", that `database/sql` opens
  unlimited connections by default (set `SetMaxOpenConns`), and that it is
  1.3x-2x slower than native C on CPU-heavy queries
  ([pkg.go.dev](https://pkg.go.dev/modernc.org/sqlite)). Measured above: no visible
  penalty at 10k rows.
- `ncruces/go-sqlite3` v0.35.6 is a "cgo-free SQLite wrapper" that wraps a Wasm build of
  SQLite translated to Go with wasm2go. It includes JSON, math, and Unicode extensions
  and online backup. Memory use is higher than the alternatives because "each
  connection runs in a Wasm sandbox"
  ([repo](https://github.com/ncruces/go-sqlite3)). It is pre-1.0.
- `mattn/go-sqlite3` v1.14.52 is the long-standing cgo driver (9.2k stars). It bundles the
  amalgamation but requires cgo. It is no faster here (see section 1).

**Rust.**
- `rusqlite` v0.41.0 (2026-10-24, 4.4k stars), with `bundled`: "use the cc crate
  to compile SQLite ... from source and link against that". It bundles SQLite 3.54.0
  ([docs.rs](https://docs.rs/crate/rusqlite/latest)). This is the most direct
  path: native-speed SQLite, statically linked, with an ergonomic typed API.
- `tursodatabase/turso` v0.8.3 is a SQLite-compatible database rewritten in Rust.
  It is interesting, but pre-1.0, and a rewrite is not SQLite.

Both languages get WAL-mode SQLite. That covers the "CLI writes while the picker
reads" concurrency case the same way in either, because it is a property of the
SQLite file format, not the binding ([sqlite.org/wal.html](https://www.sqlite.org/wal.html)).

**Verdict: tie on capability.** Rust's `rusqlite`+`bundled` is native C with no
caveats. Go's `modernc` is pure Go with a static binary and no C toolchain.
For this workload neither has a practical edge.

## 5. RDF / Turtle / SKOS library maturity

This is the one dimension where the gap is large.

**Rust.**
- **Oxigraph** v0.5.13 (2026-10-22, 2.0k stars, very active) is "a graph database
  library implementing the SPARQL standard". It has SPARQL 1.1 Query/Update/Federated;
  Turtle, TriG, N-Triples, N-Quads, and RDF/XML I/O; and RDF 1.2 behind a feature flag. Its
  backend is RocksDB on disk, or an in-memory `Store::new()` with
  `default-features = false`
  ([lib README](https://github.com/oxigraph/oxigraph/blob/main/lib/oxigraph/README.md)).
  Caveats from its own docs: "in heavy development and SPARQL query evaluation
  has not been optimized yet"; isolation is "repeatable read"; "Only one
  read-write Store can exist at the same time"; and "Opening as read-only while
  having an other process writing the database is undefined behavior"
  ([Store docs](https://docs.rs/oxigraph/latest/oxigraph/store/struct.Store.html)).
  That last point matters directly here. Nvim and an `add` can each run a CLI
  process at the same moment, so an Oxigraph-on-disk design needs a lock file, a
  single-writer protocol, or a load-from-export-into-memory approach.
- Oxigraph's parser crates (`oxttl`, `oxrdfio`) replaced **Rio**, which is now
  archived ([oxigraph/rio](https://github.com/oxigraph/rio)).
- **Sophia** (332 stars, active) provides a generic RDF 1.2 API (`sophia_api`), Turtle-family
  parsers and serializers, JSON-LD 1.1 behind a feature, in-memory graphs, and a
  "currently partial" SPARQL implementation
  ([repo](https://github.com/pchampin/sophia_rs)). It is a toolkit, not a
  persistent store.

**Go.**
- `knakk/rdf` (76 stars, no tagged releases) handles "parsing and serialization of RDF
  data", with Turtle, N-Triples, N-Quads, and RDF/XML source files. It has no store or SPARQL
  ([repo](https://github.com/knakk/rdf)).
- `deiu/rdf2go` (81 stars, no releases) parses and serializes Turtle and JSON-LD,
  with in-memory triple matching and a deterministic Turtle serializer. It has no SPARQL
  ([repo](https://github.com/deiu/rdf2go)).
- `cayleygraph/cayley` (15k stars) is a graph DB whose last release was v0.7.7 in
  **2019**. Treat it as dormant.
- **There is no maintained, embeddable Go SPARQL store comparable to Oxigraph.**

What this means here: the map already says the internal store "need not be a triple
store" and that Turtle *export* is a nice-to-have. Writing SKOS Turtle from your own
schema is a small templating job in either language, since you control the
vocabulary and the escaping rules for IRIs and literals are short. Only
*parsing arbitrary Turtle* (re-import, or Turtle-as-canonical) needs a real
library. There, Go's options work but are low-activity, while Rust's
(`oxttl`, Sophia) are first-rate.

**Verdict: Rust wins decisively *if* RDF is load-bearing. Go is adequate if RDF is export-only.**

## 6. CLI and JSON ergonomics

- **Go.** `spf13/cobra` v1.10.2 (44.7k stars) is the de facto subcommand framework.
  The stdlib `flag` package is enough for a small surface. `encoding/json` with
  struct tags is in the stdlib, and Go 1.26 cut baseline cgo call overhead by about 30% (irrelevant
  if cgo-free) ([go.dev/doc/go1.26](https://go.dev/doc/go1.26)). JSON
  contracts are easy, but `omitempty`/nil-slice-vs-`[]` quirks need tests to pin
  the wire shape for the Lua side.
- **Rust.** `clap` v4.6.7 (16.8k stars) with derive gives typed subcommands, help,
  and shell completions from structs. `serde`/`serde_json` give the strongest typed
  JSON contract available, with enums for Resource kinds and `#[serde(rename_all)]`
  and similar attributes. Exhaustive `match` on result and error enums suits a stable
  JSON contract.

**Verdict: slight edge to Rust on contract rigor. Go is faster to write and plenty good.**

## 7. Testing

- **Go.** `go test` is built in. `rogpeppe/go-internal`'s **testscript** (v1.15.0) is the
  standard way to write CLI golden tests as `.txtar` scripts that run the real
  binary against fixture trees. It is the same harness the Go toolchain uses for its own
  `cmd/go` tests. Go 1.26 adds `T.ArtifactDir` for keeping test outputs
  ([go1.26 notes](https://go.dev/doc/go1.26)).
- **Rust.** `cargo test` is built in. `insta` v1.49.0 provides snapshot testing
  (good for JSON output), and `assert_cmd` provides process-level CLI assertions.
- Neovim plugin tests (plenary/busted) are language-independent: they exercise the
  JSON contract.

**Verdict: tie.** Both have first-class golden and snapshot CLI testing.

## 8. Scorecard

| Dimension | Go | Rust | Edge |
|---|---|---|---|
| Startup / size | sub-ms start, about 7 MB static | sub-ms (expected), a few MB | tie |
| Install / toolchain | installed; static `go install` | new toolchain; C/C++ for bundled deps | **Go** |
| libmagic | shell out or pure-Go `mimetype`; cgo bindings weak | maintained `magic` FFI crate | slight Rust (neutral if shelling out) |
| Embedded SQLite | pure-Go `modernc`, no penalty at this scale | `rusqlite` bundled, native | tie |
| RDF / SPARQL | parse/serialize only, low activity, no store | Oxigraph, Sophia, oxttl | **Rust** (decisive if RDF is core) |
| CLI / JSON | cobra + stdlib json | clap derive + serde | slight Rust |
| Testing | testscript | insta + assert_cmd | tie |

## 9. Which language each storage option favours

These are the options surveyed in [#50](https://github.com/natemarks/mcp-local-notes/issues/50):

1. **SQLite with a relational schema, plus Turtle/JSON export: Go (mild).** Both
   languages are equally capable. Go wins on zero toolchain cost and a
   cgo-free static binary. Transitive narrower-concept matching is a recursive
   CTE in SQL, so no RDF library is needed. Turtle export is templated, and JSON is stdlib.
2. **Embedded RDF store (Oxigraph) with SPARQL: Rust (strong).** Oxigraph is a
   Rust library with no Go equivalent. Choosing it means choosing Rust. Note
   its single-writer and read-only-while-writing UB caveats for the CLI-plus-nvim
   concurrency case, and its heavy RocksDB build.
3. **Plain text (Turtle, TOML or YAML) as canonical plus a cache index: depends on the
   format.**
   - **Turtle canonical: Rust**, because round-tripping hand-editable Turtle
     reliably needs a solid parser (`oxttl`/Sophia), and Go's are thin.
   - **TOML/YAML/JSON canonical with a SQLite cache: Go (mild).** Go has mature
     TOML and YAML libraries and the stdlib JSON, and the cache is option 1's SQLite. Rust is
     equally good here (`serde` + `toml`), so the toolchain cost decides it.

## Recommendation

**Go**, assuming #50 lands on SQLite (or text-plus-SQLite-cache) with Turtle as
export only. That assumption fits the map's standing decisions: the store need not be
a triple store, and SKOS/Turtle are nice-to-haves. Use a cgo-free build with
`modernc.org/sqlite`, `file --mime-type` behind a detection seam (or pure-Go
`mimetype` as the in-process option), cobra or stdlib `flag`, stdlib JSON, and testscript
golden tests.

**Choose Rust instead if any of these hold:**
- #50 chooses Oxigraph or SPARQL as the store, or Turtle as the canonical
  hand-edited format that must round-trip.
- Query expressiveness (a "Not yet specified" item on the map) grows to SPARQL.
- You want libmagic linked in-process rather than shelling out to `file`.
- You value compile-time exhaustiveness for the JSON contract and errors more than
  you mind installing a Rust toolchain and paying slower first builds.
