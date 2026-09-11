# Research: SKOS/OWL conventions for a personal-KB ontology

Issue: [#4 Research SKOS/OWL conventions for a personal-KB ontology](https://github.com/natemarks/mcp-local-notes/issues/4)
(child of map issue [#1](https://github.com/natemarks/mcp-local-notes/issues/1))

Scope, per the issue and `features/vocabulary_governance.feature`: conventions for a
single, small, hand/tool-maintained Turtle file (`tbox.ttl`) — not a triple-store —
that declares (a) a flat controlled tag vocabulary as a `skos:ConceptScheme`, and
(b) a small fixed set of note types (`Note`, `Person`, `Project`, `Meeting`,
`Reference`, `Concept`) as an OWL class hierarchy via `rdfs:subClassOf`.

## 1. Namespace / prefix conventions

- **Hash URIs for small, self-contained vocabularies.** The W3C TAG note *Cool URIs
  for the Semantic Web* recommends hash URIs over slash (303) URIs precisely for
  this case: "Hash URIs should be preferred for rather small and stable sets of
  resources that evolve together... The ideal case are RDF Schema vocabularies and
  OWL ontologies, where the terms are often used together, and the number of terms
  is unlikely to grow out of control." A hash namespace also lets the whole
  vocabulary be fetched/edited as one document with no server-side content
  negotiation — matching "single hand-maintained Turtle file, not a triple-store."
  ([w3.org/TR/cooluris, §4.4](https://www.w3.org/TR/cooluris/))
  → Recommendation: mint a stable base like `http://example.org/local-notes#` (or
  any namespace you actually control/won't need to change) and use it as the
  **default/empty prefix** `:` for all local terms (`:Note`, `:Person`,
  `:topics`, `:semantic-web`, ...).
- **Empty prefix (`:`) is standard Turtle.** The Turtle spec's own examples
  demonstrate binding the empty prefix to a local namespace: `@prefix : <http://another.example/> .`
  then using `:subject5 :predicate5 :object5 .` This is exactly the pattern the
  repo's own feature files already assume (`":topics"`, `":Note"` in
  `features/vocabulary_governance.feature`). ([w3.org/TR/turtle, §2.4/Example 9](https://www.w3.org/TR/turtle/))
- **Reuse standard prefixes for borrowed vocabulary, don't reinvent them.**
  Declare the well-known prefixes at the top of `tbox.ttl` exactly as their
  owning specs do:
  - `rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>`
  - `rdfs: <http://www.w3.org/2000/01/rdf-schema#>`
  - `owl: <http://www.w3.org/2002/07/owl#>`
  - `skos: <http://www.w3.org/2004/02/skos/core#>`
  - `dct: <http://purl.org/dc/terms/>` (used by the SKOS Primer itself for
    scheme metadata like `dct:title`, `dct:creator`)
  ([w3.org/TR/skos-primer §1.1](https://www.w3.org/TR/skos-primer/),
  [w3.org/TR/turtle Examples 1/10/11/14/19](https://www.w3.org/TR/turtle/))
- **TBox/ABox split is a standard description-logic convention**, not something
  invented for this repo — the terminological box (class/vocabulary axioms) vs.
  assertional box (individual facts) split maps directly onto this project's
  `tbox.ttl` (schema: concept scheme + class hierarchy) vs. `abox.ttl` (per-note
  instance data) design.

## 2. SKOS pattern for a flat, non-hierarchical tag vocabulary

Only four constructs are needed — `skos:ConceptScheme`, `skos:Concept`,
`skos:inScheme`, and `skos:prefLabel` (optionally `skos:altLabel`) — and
**`skos:broader`/`skos:narrower` should be omitted entirely**, since this
vocabulary only ever adds flat topics.

- Declare one scheme, and make every topic a `skos:Concept` linked to it with
  `skos:inScheme` — no hierarchy required:
  ```turtle
  :topics a skos:ConceptScheme ;
      dct:title "Local notes topic vocabulary" .

  :knowledge-graphs a skos:Concept ;
      skos:prefLabel "knowledge-graphs"@en ;
      skos:inScheme :topics .

  :semantic-web a skos:Concept ;
      skos:prefLabel "semantic-web"@en ;
      skos:inScheme :topics .
  ```
  This mirrors the SKOS Primer's own worked example (`ex:animalThesaurus a
  skos:ConceptScheme`; `ex:fish a skos:Concept ; skos:inScheme
  ex:animalThesaurus`). ([w3.org/TR/skos-primer §2.5](https://www.w3.org/TR/skos-primer/))
- Normatively, `skos:inScheme`'s only constraint is that its range is
  `skos:ConceptScheme` — there is no requirement to also use
  `skos:hasTopConcept`/`skos:topConceptOf` or any broader/narrower structure.
  Concepts can be "stand-alone entities" simply asserted into a scheme.
  ([w3.org/TR/skos-reference §4.3, §8.1](https://www.w3.org/TR/skos-reference/))
- `skos:broader`/`skos:narrower` (inverses of each other, §8.3 of the SKOS
  Reference) exist specifically to encode hierarchical/thesaurus relationships.
  Since US-4.1–4.3 only ever *add* new flat topics and never describe
  sub-topic relationships, these properties should not appear in `tbox.ttl` at
  all — adding them later, if ever needed, is a non-breaking additive change.
- Use `skos:prefLabel` as the canonical display form (max one per language tag —
  SKOS integrity condition S14) and `skos:altLabel` only if you need to record
  synonyms/aliases for a topic; both are plain-literal-valued annotation
  properties, so they carry no OWL semantics that would complicate a
  hand-maintained file. ([w3.org/TR/skos-reference §5.3–§5.4](https://www.w3.org/TR/skos-reference/))
- **Keep concept identity and class identity separate.** `skos:Concept` is
  itself declared as an `owl:Class`, and each topic (e.g. `:semantic-web`) is an
  *instance* of that class — it is emphatically not itself an OWL class. This
  matters for this repo because `tbox.ttl` also declares real OWL classes for
  note types (§3 below): topics are SKOS individuals, note types are OWL
  classes — don't conflate the two vocabularies or declare a topic as both a
  class and an instance elsewhere in the file. Mixing them carelessly is a
  well-known way small SKOS+OWL files drift from OWL 2 DL into OWL Full
  ("punning" issues), which the paper *SKOS with OWL: Don't be Full-ish!*
  discusses as the standard pitfall to avoid when SKOS and OWL share one file.
  ([w3.org/TR/skos-reference §3.3](https://www.w3.org/TR/skos-reference/);
  [Alistair Miles & Sean Bechhofer, "SKOS with OWL: Don't be Full-ish!", CEUR-WS Vol-432](https://ceur-ws.org/Vol-432/owled2008eu_submission_22.pdf))

## 3. OWL class-hierarchy pattern for note types

For the fixed set `Note, Person, Project, Meeting, Reference, Concept`, only
`owl:Class` declarations plus `rdfs:subClassOf` triples are needed — no
`owl:Restriction`, cardinality, or disjointness axioms:

```turtle
:Note a owl:Class .

:Person     a owl:Class ; rdfs:subClassOf :Note .
:Project    a owl:Class ; rdfs:subClassOf :Note .
:Meeting    a owl:Class ; rdfs:subClassOf :Note .
:Reference  a owl:Class ; rdfs:subClassOf :Note .
:Concept    a owl:Class ; rdfs:subClassOf :Note .
```

- This is exactly the OWL 2 Primer's minimal subclass pattern (its own worked
  example is `:Woman rdfs:subClassOf :Person .`), applied one level deep for
  each note type against a single root `:Note` class. The primer's guiding
  heuristic for when a subclass edge is warranted — "a subclass relationship
  between two classes A and B can be specified if the phrase 'every A is a B'
  makes sense" — cleanly justifies "every Meeting is a Note", "every Project is
  a Note", etc. ([w3.org/TR/owl2-primer §4.2](https://www.w3.org/TR/owl2-primer/))
  Adding a new type later (e.g. the `Recipe` example in
  `vocabulary_governance.feature`) is just one more `owl:Class` +
  `rdfs:subClassOf` pair — no other file edits required, which is what keeps
  this tractable as a hand-maintained/tool-appended file.
- Deliberately **avoid** heavier OWL constructs for this use case:
  - No `owl:disjointWith` between sibling types (Person/Project/Meeting/etc.) —
    disjointness axioms require a reasoner to enforce and add O(n²) boilerplate
    triples for a 6-class hierarchy with no runtime benefit here, since
    validation (per `validate_consistency.feature`) is done by application code
    checking the frontmatter `type` against the declared classes, not by an OWL
    reasoner running consistency checks.
  - No `owl:Restriction`/property cardinality — those exist to constrain
    instance data via reasoning, which is out of scope for a file whose job is
    simply "declare which type names exist and their supertype."
  - A single root class (`:Note`) rather than multiple unrelated top-level
    classes keeps `?type rdfs:subClassOf* :Note` a valid, simple query pattern
    for "is this a valid note type," which is the only thing this hierarchy
    needs to answer.

## Sources consulted (primary)

- W3C, *SKOS Simple Knowledge Organization System Primer* — https://www.w3.org/TR/skos-primer/
- W3C, *SKOS Simple Knowledge Organization System Reference* — https://www.w3.org/TR/skos-reference/
- W3C, *OWL 2 Web Ontology Language Primer (Second Edition)* — https://www.w3.org/TR/owl2-primer/
- W3C, *Turtle — Terse RDF Triple Language* — https://www.w3.org/TR/turtle/
- W3C TAG, *Cool URIs for the Semantic Web* — https://www.w3.org/TR/cooluris/
- Alistair Miles & Sean Bechhofer, *SKOS with OWL: Don't be Full-ish!*, OWLED 2008 — https://ceur-ws.org/Vol-432/owled2008eu_submission_22.pdf
- This repo's `features/vocabulary_governance.feature` (existing project conventions: `tbox.ttl`/`abox.ttl` split, `:topics` scheme, six fixed note types)
