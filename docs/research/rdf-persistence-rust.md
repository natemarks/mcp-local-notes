# Research: Standards-first RDF persistence and tooling in Rust

**Date:** 2026-10-24
**Issue:** [#66 Standards-first RDF persistence and tooling in Rust](https://github.com/natemarks/mcp-local-notes/issues/66)
(child of map [#48](https://github.com/natemarks/mcp-local-notes/issues/48), "Local file ontology CLI + Neovim finder: v1 spec")

**Constraints from #48:** Rust is expected. The project is standards-first (RDF,
RDFS, OWL 2, SKOS, SPARQL 1.1, SHACL), and learning ontologies outranks raw
performance. Ubuntu 26.04 only. Fewer than 10k Resources (about 100k triples).
No daemon. nvim and AI agents call the CLI as **short-lived processes** and
may overlap. A git-friendly Turtle/TriG export is required.

**This builds on, and does not repeat:**
[`ontology-storage.md`](https://github.com/natemarks/mcp-local-notes/blob/research/ontology-storage/docs/research/ontology-storage.md)
(#50: Oxigraph overview, the single-RW-opener and read-only-UB caveats, and that
dumps are unsorted) and
[`go-vs-rust-cli.md`](https://github.com/natemarks/mcp-local-notes/blob/research/go-vs-rust-cli/docs/research/go-vs-rust-cli.md)
(#49: the toolchain, the RocksDB C++ build cost, MSRV 1.87, and Rust RDF library
maturity). Its prefix and ConceptScheme conventions come from
[`skos-owl-personal-kb-conventions.md`](./skos-owl-personal-kb-conventions.md).

**Measurement note.** No Rust toolchain is installed here, and none was
installed. The latency figures in section 1 are a **proxy measurement**. They
come from the `pyoxigraph` 0.5.13 wheel, which wraps the same Rust `oxigraph`
crate, run in a throwaway venv in `/tmp` on an i7-11800H with ext4 on NVMe. Each
timed operation is a single Python-to-Rust call, so interpreter overhead is
small but not zero. The "parse only" row is inflated because it builds a Python
object for every triple. Treat all of them as **estimates for a native Rust
CLI**, not as measurements of one.

---

## TL;DR / Recommendation

**Choose (b): Turtle files are canonical, and each invocation loads them into an
in-memory Oxigraph `Store`. Split the files the way (c) does, but keep them all
as files:**

- `ontology.ttl` is hand-authored: OWL/RDFS classes and properties, plus SHACL
  shapes (or a separate `shapes.ttl`). The CLI only reads it.
- `concepts.ttl` is tool-managed: the SKOS ConceptScheme. It changes only
  through explicit vocabulary commands.
- `resources.ttl` is tool-managed: the ABox, one block per Resource.

Each file is loaded into its own named graph, so a SPARQL query can see where a
fact came from, and `dump_graph_to_writer` can write each file back
independently. Writes are serialised with an advisory `flock` and published by
write-temp-then-`rename`. Readers take a shared lock. Serialisation sorts its
output, contains no blank nodes and uses a fixed prefix table, so git diffs show
one block per change.

Why (b) wins here:

1. **It is the most standards-first option.** The canonical artefact is W3C
   Turtle, which you can read, diff, hand-edit and open in Protégé or any other
   RDF tool. That serves the "learning ontologies" goal better than a RocksDB
   directory whose readable form is a derived export.
2. **No RocksDB.** `oxigraph = { default-features = false }` is pure Rust. That
   removes the C++20 RocksDB build that #49 flagged, removes the
   "read-only while another process writes is UB" hazard, and removes the
   on-disk format migrations (one happened at 0.5).
3. **Storage is the export.** The map's open item "Export format & round-trip"
   disappears, because no separate export or import path can drift from the
   store.
4. **The cost is acceptable.** Loading about 100k triples into an in-memory
   store is an estimated **140-160 ms** per invocation at the top of the scale
   (section 1), and roughly proportionally less at the "low thousands"
   Resources the map expects. A Telescope picker calls the CLI once per open,
   not per keystroke.

**When to switch to (a)** (an Oxigraph RocksDB store as canonical, with a sorted
export): when p95 read latency matters more than about 200 ms, for example a
live-query picker that re-runs the CLI on every keystroke, or when the corpus
grows well past 100k triples. Both options use the same `oxigraph::Store` API,
so keep the open/load step behind a single `storage` seam and the switch stays
local.

**Do not choose (c)** as specified, with the ABox in RocksDB. It pays every
cost of (a) (RocksDB, locking, a separate export for git) for the bulk of the
data, and it adds a second persistence mechanism. Its good idea, separating the
hand-authored TBox from the machine-managed ABox, is kept in (b) as separate
files.

**Validation and inference:**

- SHACL: use rudof's `shacl` crate (0.3.35) in Native (in-memory) mode, run on
  every mutating command and in `validate`.
- Oxigraph does **no inference**. Answer the inferences this project needs at
  query time with SPARQL 1.1 property paths
  (`rdf:type/rdfs:subClassOf*`, `skos:broader*`).
- Optionally add an `infer` command that uses `reasonable` (OWL 2 RL, which
  takes `oxrdf::Triple` directly) to materialise into a separate, never-exported
  `inferred` named graph. That is a learning feature, not a dependency of
  `find`.

**Pin exact versions** for all of these crates. All are 0.x, and rudof shipped
four releases in two days in October 2026.

---

## 1. Load/startup latency for (b), and open latency for (a)

Synthetic corpus: 500 SKOS concepts (random `skos:broader` tree) plus 10,000
Resources with 10 triples each (type, title, path, sha256, format, 3 subjects,
created, relatedTo). That gives **101,938 triples, 3.4 MB of Turtle**. Medians
of 15 runs, proxy-measured via pyoxigraph 0.5.13 (see the note above):

| Operation | Median | Notes |
|---|---|---|
| Parse Turtle only (iterate triples) | ~73 ms | inflated by Python object creation per triple |
| `Store::new()` + `load_from_reader` (Turtle) | ~137 ms | atomic load into the in-memory store |
| `Store::new()` + `load_from_reader` (N-Triples) | ~137-140 ms | the same, so indexing dominates, not parsing |
| `Store::new()` + `bulk_loader` | ~156 ms | no gain in memory at this size |
| SPARQL `?c skos:broader* ex:c3 . ?r dct:subject ?c` (22k rows) | ~11 ms | on an already-loaded store |
| (a) `Store::open` (RocksDB) + the same query | ~56-59 ms | so open costs about 45 ms |
| (a) `Store::open_read_only` + the same query | ~50 ms | |

Estimated per-invocation wall time for a native Rust CLI at about 100k triples:

- **(b)**: about 1 ms process spawn, plus about 140 ms load, plus query time,
  giving roughly **150-170 ms**.
- **(a)**: roughly **50-60 ms**.

At 2-3k Resources (about 25k triples), (b) should be around 40 ms, extrapolated
linearly from the load figures. The Oxigraph README warns that it "is in heavy
development and SPARQL query evaluation has not been optimized yet"
([README](https://github.com/oxigraph/oxigraph/blob/main/README.md)). The
property-path query above was not a bottleneck at this scale.

The load cost could be halved later without changing the format. Use
`Store::new()` without the transactional `load_from_reader`, or parse files in
parallel with `parallel_load_from_slice`, added in 0.5.0-beta.5
([CHANGELOG](https://github.com/oxigraph/oxigraph/blob/main/CHANGELOG.md)).
This is not needed for v1.

## 2. Oxigraph: single read-write opener, multi-process behaviour, locking

**What the API promises** (docs.rs, `Store` 0.5.13,
[link](https://docs.rs/oxigraph/0.5.13/oxigraph/store/struct.Store.html)):

- `Store::open`: "Only one read-write Store can exist at the same time."
- `Store::open_read_only`: "Opening as read-only while having an other process
  writing the database is undefined behavior."
- Isolation is "repeatable read". `start_transaction` keeps "the complete set of
  changes into memory".
- The "secondary" mode, which let a process follow a live primary, **was
  removed** in 0.4.0-alpha.8 because "it was quite buggy, especially with
  RocksDB 9"
  ([CHANGELOG](https://github.com/oxigraph/oxigraph/blob/main/CHANGELOG.md)).
  No supported way remains to read safely while another process writes.
- `Store::snapshot`, a lock-free pinned read view, was merged to `main` on
  2026-09-22 ([PR #1957](https://github.com/oxigraph/oxigraph/pull/1957)). It
  is **not in 0.5.13**, which is released from the `0.5` branch, and it is
  intra-process only, so it does not help across CLI processes.

**What actually happens on a second open.** RocksDB takes the `LOCK` file with
a non-blocking `fcntl(F_SETLK)`
([`env/fs_posix.cc`](https://github.com/facebook/rocksdb/blob/main/env/fs_posix.cc),
`LockOrUnlock`). The second opener **fails immediately and does not wait**.
Proxy-observed: a second process got `IO error: While lock file: …/LOCK:
Resource temporarily unavailable` after 1.4 ms. A second open in the same
process gets `lock hold by current process`. For (a), every overlapping
nvim-plus-agent invocation would therefore error out unless the CLI adds its
own waiting lock.

**Locking protocol for short-lived CLI processes.** The same protocol works for
(a) and (b).

Use a lock file `~/.local/share/<app>/lock` (the XDG data dir from #52) with
`std::fs::File::lock` / `lock_shared` / `try_lock`. These are in std and stable
since **Rust 1.89**
([docs](https://doc.rust-lang.org/std/fs/struct.File.html#method.lock)), so
`fs2`/`fs4`/`fd-lock` are not needed. They block, or with `try_*` they return
`WouldBlock`. The lock is "released when this file … is closed", so a crashed
process never leaves a stale lock, unlike a PID file.

- **Readers** (`find`, `describe`, `show`, and the nvim picker): take
  `lock_shared`. In (a), then call `Store::open_read_only`. In (b), load the
  files.
- **Writers** (`add`, `tag`, `relink`, `concept add`, …): take the exclusive
  `lock`.
  - (a): call `Store::open`, apply the change, `flush()`, write the export,
    then drop the store.
  - (b): load the files, apply the change, and run SHACL validation. For each
    changed file: write `<file>.tmp` in the same directory, `fsync` it,
    `rename(2)` it over the target (atomic,
    [man7](https://man7.org/linux/man-pages/man2/rename.2.html)), then `fsync`
    the directory.
- **Waiting**: loop on `try_lock`/`try_lock_shared` with backoff up to a
  deadline (about 5 s, configurable). std has no timed lock. On timeout, return
  the #48 structured error, for example rule `store-busy` with the suggested
  fix "retry; another <app> process is writing".
- **`--dry-run`**: takes only the shared lock and never writes.
- Readers need the shared lock in (b) too. Each `rename` is atomic for one
  file, but a write that touches `concepts.ttl` and `resources.ttl` is not
  atomic across both. The shared lock gives readers a consistent cross-file
  view. Writers hold it for milliseconds, so contention is negligible.

## 3. SPARQL 1.1 Query/Update support

Oxigraph implements "SPARQL Query, SPARQL Update, and SPARQL Federated Query".
It also has the XML/JSON/CSV/TSV results formats, and "most implementations are
nearly fully conformant with the latest recommendations (1.1 for RDF, SPARQL and
JSON-LD)". SPARQL 1.2 and RDF 1.2 are behind the `rdf-12` feature
([README](https://github.com/oxigraph/oxigraph/blob/main/README.md),
[lib README](https://github.com/oxigraph/oxigraph/blob/main/lib/oxigraph/README.md)).

The in-memory `Store::new()` supports the same Query/Update API as the RocksDB
store ([Store docs](https://docs.rs/oxigraph/0.5.13/oxigraph/store/struct.Store.html)),
so (b) loses no SPARQL capability. Since 0.5 the entry point is
`SparqlEvaluator` (`Store::query`/`update` are deprecated), and it supports
pre-bound variables (`substitute_variable`), which is the safe way to inject CLI
arguments into queries.

SPARQL correctness is still being fixed at a steady rate. 0.5.12 and 0.5.13
(Oct 2026) fixed `OPTIONAL` filter scope, implicit aggregation on empty input,
and Update delete-before-insert ordering
([releases](https://github.com/oxigraph/oxigraph/releases)). Pin the version,
and test the queries the CLI ships with golden tests.

An implementation consequence: the CLI's built-in commands (`find --tag`,
`--type`, `--related`) can be fixed SPARQL templates with bound variables. A
raw `query <sparql>` passthrough is cheap to add if "Query expressiveness" (a
map open item) wants it.

## 4. SHACL validation in Rust

**rudof** ([rudof-project/rudof](https://github.com/rudof-project/rudof),
Apache-2.0/MIT) is the WESO group's ShEx/SHACL/DCTAP toolkit, led by Jose Labra
with several regular contributors.

- The SHACL validator is the **`shacl`** crate, 0.3.35, released 2026-10-23.
  It replaces the older `shacl_validation` (0.2.12, last released April 2026)
  and `shacl_ast` crates, and `srdf` became `rudof_rdf`. These renames are
  churn to plan for. (crates.io API, 2026-10-24.)
- It has two engines. **Native** is "designed for in-memory graphs … the
  recommended mode whenever the data already lives in the process". **Sparql**
  targets remote endpoints. The default `sparql` feature also routes inline
  `sh:sparql` (SHACL-SPARQL) constraints in Native mode
  ([shacl README](https://github.com/rudof-project/rudof/blob/master/shacl/README.md)).
- It is tested against the W3C data-shapes test suite. The `core` harness wires
  108 Core cases (node, property, path, targets, misc, complex) with no
  `#[ignore]`, plus `sparql` and `shacl12` suites
  ([tests](https://github.com/rudof-project/rudof/tree/master/shacl/tests)). I
  did not verify pass status myself.
- It builds on Oxigraph's crates: `oxigraph = "0.5.9"` with
  `default-features = false` and the `rdf-12` feature, plus `oxrdf` 0.3 and
  `oxttl` 0.2
  ([workspace Cargo.toml](https://github.com/rudof-project/rudof/blob/master/Cargo.toml)).
  This matches the recommended stack. Cargo feature unification will turn on
  `rdf-12` in your `oxigraph` too, which is harmless but changes serialisation
  of RDF 1.2 terms.
- Dependency weight: the default `sparql` feature of `rudof_rdf` pulls
  `reqwest` + `tokio` (for remote endpoints). With `default-features = false`
  on `shacl` you keep SHACL Core and drop SHACL-SPARQL. Check the actual
  `cargo tree` in the stack ticket.
- Integration cost: rudof validates its own in-memory graph, so validation is a
  second load of the data (estimated tens of ms at 100k triples, comparable to
  section 1). Do it only on mutating commands and `validate`, never on `find`.

**Alternatives:**

- **Oxigraph itself has no SHACL.**
  [PR #1692](https://github.com/oxigraph/oxigraph/pull/1692) ("oxreason: OWL 2 RL
  forward chainer + SHACL Core scaffold") was closed unmerged in 2026-07, with
  only `sh:minCount` implemented.
- **No other maintained pure-Rust SHACL validator** turned up. pySHACL is
  Python, which is out, and TopBraid SHACL is JVM, which is too slow to start
  for a CLI.

**Verdict:** rudof `shacl`, pinned exactly, in Native mode.

## 5. OWL 2 RL / RDFS inference in Rust

**Oxigraph does no inference.** It has no RDFS or OWL entailment regime.
Issue [#130 "Support OWL 2 RL reasoning?"](https://github.com/oxigraph/oxigraph/issues/130)
is still open; the maintainer would like "some kind of 'datalog-like'
declarative language" but is not doing it himself. A `Store::reason`
integration was proposed (PR #1679 and #1692, both closed unmerged).
[#1681](https://github.com/oxigraph/oxigraph/issues/1681) describes a design
that is not in any release: the 0.5.13 `Store` method list has no `reason`.

**`reasonable`** ([gtfierro/reasonable](https://github.com/gtfierro/reasonable),
BSD-3-Clause):

- Latest stable 0.4.4 (2026-05-28), with a 0.5.0-a1 pre-release on 2026-09-17.
  Mostly a single maintainer (Gabe Fierro, about 512 of about 530 commits).
- It is "an OWL 2 RL reasoner" using the W3C OWL 2 RL/RDF rule tables. The
  README marks **42 rules done and 17 not done**. Missing rules include the
  `eq-diff*`, `prp-key`, `prp-npa*` and `cls-maxc*`/`maxqc*` cardinality rules,
  and `eq-ref`. Some of the missing rules only "throw exception"
  (inconsistency checks), and violations that are detected are reported as
  diagnostics (`cax-dw`, `prp-pdw`, …).
- RDFS coverage is partial: `rdfs11` and `rdfs12` plus datatype diagnostics;
  `rdfs:subClassOf`/`subPropertyOf`/domain/range come from the OWL RL
  `cax-sco`/`prp-spo1`/`prp-dom`/`prp-rng` rules
  ([README](https://github.com/gtfierro/reasonable/blob/master/README.md)).
- Rust API: `Reasoner::new()`, `load_triples(Vec<oxrdf::Triple>)`, `reason()`,
  `get_triples()`, `diagnostics()`
  ([docs.rs 0.4.4](https://docs.rs/reasonable/0.4.4/reasonable/reasoner/struct.Reasoner.html)).
  It depends on `oxrdf ^0.3.3`, so triples move from an Oxigraph store without
  conversion. It still depends on the archived `rio_turtle` for its own file
  loading, which you don't need.

**Other options:**

- `horned-owl` 4.0.0 (2026-09) is an OWL 2 *ontology library*
  (parse/manipulate/serialise), not a reasoner.
- `whelk-rs` (INCATools) is an OWL EL reasoner; its last push was 2026-06.
- Nemo (knowsys) is a Datalog engine that can import RDF, but it is not on
  crates.io.

**What this project needs.** The inferences in scope are:

- a Resource matches a supertype, via `rdfs:subClassOf`;
- a Resource tagged with a narrower concept matches its broader concept.

Both are **query-time SPARQL property paths**:
`?r rdf:type/rdfs:subClassOf* ex:Document` and
`?r dct:subject/skos:broader* ex:topic`. SKOS itself says `skos:broader` is
*not* transitive and provides `skos:broaderTransitive` for that, so a property
path matches SKOS semantics without materialising anything.

**Recommendation:** no reasoner in the read path. If you want to learn OWL RL,
add an optional `infer` command that runs `reasonable` over the loaded graphs
and stores the result in a separate `urn:<app>:graph:inferred` named graph. That
graph is cache-only, rebuildable, never exported and never canonical. Report its
diagnostics (for example disjoint-class violations) through `validate`.

## 6. Deterministic, diff-friendly serialisation for git

What Oxigraph gives you:

- `dump_to_writer` / `dump_graph_to_writer` emit quads in **store index
  order**. On RocksDB the keys are SipHash-128 `StrHash` term encodings
  ([`numeric_encoder.rs`](https://github.com/oxigraph/oxigraph/blob/v0.5.13/lib/oxigraph/src/storage/numeric_encoder.rs)),
  so the order is stable for a given content but not lexical. The in-memory
  store order differs again. Neither is documented as stable across versions.
- `oxttl::TurtleSerializer` (0.2.5) supports `with_prefix` and `with_base_iri`.
  It writes triples in the order you give them, grouping consecutive triples
  that share a subject with `;` and those that share a subject and predicate
  with `,` (see the test in
  [`turtle.rs`](https://github.com/oxigraph/oxigraph/blob/v0.5.13/lib/oxttl/src/turtle.rs)).
  Since 0.5.0-beta.3 it uses "the longest possible prefix".
  ([docs.rs](https://docs.rs/oxttl/0.2.5/oxttl/turtle/struct.TurtleSerializer.html))
- `oxrdf` `Graph`/`Dataset::canonicalize` supports **RDFC-1.0** (W3C RDF
  Dataset Canonicalization) behind the `rdfc-10` feature, added in 0.5.4. The
  default `Unstable` algorithm "might change between versions".
  ([`dataset.rs`](https://github.com/oxigraph/oxigraph/blob/v0.5.13/lib/oxrdf/src/dataset.rs))

**Recipe for tool-managed files:**

1. **No blank nodes in tool-managed files.** Mint IRIs for every Resource,
   concept and relation instance (prior research's `ex:`-style IRIs). Blank node
   labels are the main source of nondeterminism. If one ever appears, convert it
   to an IRI on write, or fall back to RDFC-1.0 for that graph.
2. Collect each named graph's triples and **sort** them by (subject, predicate,
   object), comparing each term's N-Triples form. Optionally put `rdf:type`
   first within a subject. Feed the sorted triples to `TurtleSerializer`, which
   then emits one subject block per Resource.
3. Use a **fixed, ordered prefix table** (rdf, rdfs, owl, xsd, skos, dct, sh,
   and the app namespace), whether or not each prefix is used.
4. Write a newline after every block, use LF line endings, and always end with
   a trailing newline.
5. A golden test asserts that load followed by serialise is byte-identical for
   a fixture (round-trip idempotence).

The hand-authored `ontology.ttl` is **never rewritten** by the tool. It may
contain comments, blank-node SHACL property shapes and RDF lists (`sh:in`), all
of which a re-serialise would lose or relabel. oxttl does not preserve
comments, so tool-managed files should begin with a fixed
"generated by <app>; edit with the CLI" banner.

## 7. Crate maturity and maintenance (crates.io and GitHub, checked 2026-10-24)

| Crate | Latest | Released | Signals |
|---|---|---|---|
| `oxigraph` | 0.5.13 | 2026-10-22 | ~2.0k stars; Tpt is the main author (~2.2k of the commits); releases every 1-2 months; MSRV 1.87; 0.6 in development on `main` |
| `oxttl` / `oxrdf` / `oxrdfio` / `spargebra` | 0.2.5 / 0.3.5 / 0.2.7 / 0.4.8 | 2026-10-18 | same repo; 1-1.8M downloads each |
| `shacl` (rudof) | 0.3.35 | 2026-10-23 | WESO group, several active contributors; rapid releases; crates renamed in 2026 |
| `reasonable` | 0.4.4 (0.5.0-a1 pre) | 2026-05-28 / 2026-09-17 | single maintainer; ~137 stars; README marks 42 of 59 listed rules done |
| `horned-owl` | 4.0.0 | 2026-09-17 | OWL library, not a reasoner; MSRV 1.88 |
| `sophia` | 0.10.0 | 2026-05-19 | alternative RDF toolkit; SPARQL "currently partial" (#49) |
| std `File::lock` | Rust 1.89 | stable | replaces `fs2` (last release 2018) / `fs4` / `fd-lock` |

Risks:

- **Oxigraph is pre-1.0 and mostly one maintainer.** 0.5 broke the 0.4 Rust
  API: `SparqlEvaluator`, and `bulk_loader` now needs `commit`. 0.5 also
  migrated the RocksDB format on first open and changed N-Triples/Turtle
  serialisation when RDF-star was replaced by RDF 1.2
  ([CHANGELOG](https://github.com/oxigraph/oxigraph/blob/main/CHANGELOG.md)).
  Option (b) is exposed only to the API and serialisation changes. Option (a)
  is also exposed to on-disk format changes.
- **rudof is fast-moving.** Pin it exactly, and expect renames.
- **`reasonable` has a bus factor of 1.** That is why it is kept optional and
  out of the read path.
- No Rust toolchain is installed on this machine (#49). Ubuntu 26.04's packaged
  rustc 1.93.1 (per #49) meets every MSRV above.

## 8. Option comparison

| Concern | (a) Oxigraph RocksDB canonical + export | (b) Turtle canonical, in-memory store per run | (c) TBox Turtle + ABox RocksDB |
|---|---|---|---|
| Read latency at 100k triples | ~50-60 ms (est.) | ~150-170 ms (est.) | ~55-65 ms (est.) |
| Build | RocksDB C++20 via `oxrocksdb-sys` | pure Rust | RocksDB |
| Concurrency | app flock is mandatory: 2nd RW open fails fast; RO during write is UB | app flock + atomic rename | as (a) for the ABox |
| Git history | separate sorted export after every write; `import` must stay lossless | the files *are* the history | TBox native; ABox needs an export |
| Hand-editable | export only, and edits must be re-imported | yes (TBox freely; managed files via CLI, though hand edits are read) | TBox only |
| Format/upgrade risk | API + on-disk format + serialisation | API + serialisation | all three |
| Standards-first / learning value | good (SPARQL), but the artefact is opaque | **best**: Turtle is the source of truth | mixed |
| Moving parts | store + exporter + importer + lock | files + serialiser + lock | files + store + exporter + lock |

## Open items for downstream tickets

- **Stack ticket:** confirm the crate set (`oxigraph` with
  `default-features = false`, `oxttl`, `oxrdf` with `rdfc-10`, `shacl` with
  features chosen by `cargo tree`, optional `reasonable`), all pinned exactly.
  Confirm Rust ≥ 1.89 for `File::lock`.
- **Export format & round-trip** (map item): mostly answered by (b). What
  remains is the exact file split, the prefix table, the sort order and the
  golden round-trip test.
- **Query expressiveness** (map item): property paths make transitive narrower
  matching free. Decide whether to expose raw `query <sparql>`.
- **Testing strategy:** golden serialisation tests; a concurrency test that
  spawns overlapping reader and writer processes to check the flock protocol.
- **Re-measure natively** once a Rust toolchain exists. If (b) exceeds about
  200 ms p95 on the real corpus, revisit (a) behind the `storage` seam.
