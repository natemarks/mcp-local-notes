# Research: Standard vocabularies for describing local files

**Date:** 2026-10-24
**Issue:** [#65 Standard vocabularies for describing local files](https://github.com/natemarks/mcp-local-notes/issues/65)
(a research ticket on map issue [#48](https://github.com/natemarks/mcp-local-notes/issues/48), the
local-file ontology CLI v1 spec)
**Scope:** Primary sources only, plus empirical checks on this Ubuntu 26.04.1 machine. Nothing was
changed outside this document. Builds on
[`skos-owl-personal-kb-conventions.md`](skos-owl-personal-kb-conventions.md), which covers hash-namespace
TBox conventions, flat SKOS schemes and `rdfs:subClassOf` type hierarchies. That material is not
repeated here.

**Constraints from the map:** standards first (RDF, RDFS, OWL 2, SKOS, SPARQL 1.1, SHACL), reuse
existing vocabularies where they fit, and learning value outranks performance. A **Resource** is a
file catalogued in place. Its identity is path plus content hash, `relink` re-finds a moved file by
hash, metadata lives only in the central store, and agents add Resources through the CLI.

## TL;DR (recommendation for v1)

| Concern | Use | Why |
|---|---|---|
| The file itself | an app class `:Resource rdfs:subClassOf dcat:Distribution, prov:Entity` | DCAT 3 is a current W3C Recommendation (2024) and already has the file-level properties |
| Location | `dcat:downloadURL <file:///abs/path>` (one per Resource) | Range `rdfs:Resource`, so the value is a real IRI. RFC 8089 file URI, UTF-8 percent-encoded |
| Media type | `dcat:mediaType <http://www.iana.org/assignments/media-types/…>`; fall back to `dcterms:format` for non-IANA types | That is the rule DCAT itself states |
| Size | `dcat:byteSize "n"^^xsd:nonNegativeInteger` | DCAT |
| Content hash | `spdx:checksum [ spdx:algorithm spdx:checksumAlgorithm_sha256 ; spdx:checksumValue "…"^^xsd:hexBinary ]` | DCAT 3 adopted the SPDX 2.x checksum terms for exactly this |
| Title, dates, generic relations | Dublin Core Terms (`dcterms:title`, `dcterms:modified`, `dcterms:references`, `dcterms:isPartOf`, `dcterms:source`, `dcterms:relation` …) | DCMI Recommendation, used throughout DCAT and SKOS |
| App-specific relation kinds | `owl:ObjectProperty` declared `rdfs:subPropertyOf` a DCTerms or PROV property | Generic queries still work, and subproperties are a good way to learn RDFS |
| Tags / topics | SKOS concepts (`skos:broader` for hierarchy) linked by `dcterms:subject` | W3C Recommendation, and the existing prior art |
| Who or what added it | a `dcat:CatalogRecord` (`foaf:primaryTopic`, `dcterms:issued`) with `prov:wasAttributedTo` a `prov:Person` or `prov:SoftwareAgent` | DCAT says this is what the record is for, and points to PROV-O for the agent |
| Resource IRI | opaque, minted once: `urn:uuid:<UUIDv7>` | Path, inode and hash all change. "Cool URIs don't change" |
| NIE/NFO (Tracker) | **don't** depend on it. Borrow its ideas, optionally align with it in a separate file | Two diverging copies, neither a W3C standard, and the copy Ubuntu ships uses a GNOME-API namespace with non-OWL `nrl:` annotations |
| schema.org | **don't** use as the core. Optionally align with it | Actively maintained, but loosely typed (`rangeIncludes`, `sha256`/`contentSize` as Text) and aimed at web markup |
| Constraints | SHACL shapes (one location, one media type, one checksum) | RDFS and OWL are open-world and will not reject a Resource with no path |

A complete example graph (one PDF, one markdown note), validated with rdflib and pySHACL, is in
[section 9](#9-example-graph-one-pdf-and-one-markdown-file).

---

## 1. Vocabulary survey: status and maintenance

| Vocabulary | Namespace | Status (primary source) | Maintenance |
|---|---|---|---|
| **DCAT 3** | `http://www.w3.org/ns/dcat#` | W3C Recommendation, 22 Aug 2024. "Supersedes DCAT 2" but does not make it obsolete ([TR/vocab-dcat-3](https://www.w3.org/TR/vocab-dcat-3/)) | Active (W3C DXWG). 2024 additions include `spdx:checksum` (issue #1287) |
| **DCMI Metadata Terms** | `http://purl.org/dc/terms/` | DCMI Recommendation, issued 2020-01-20 ([dcmi-terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)) | Stable. DCMI Usage Board |
| **SKOS** | `http://www.w3.org/2004/02/skos/core#` | W3C Recommendation, 18 Aug 2009 ([TR/skos-reference](https://www.w3.org/TR/skos-reference/)) | Stable and finished |
| **PROV-O** | `http://www.w3.org/ns/prov#` | W3C Recommendation, 30 Apr 2013 ([TR/prov-o](https://www.w3.org/TR/prov-o/)) | Stable and finished |
| **SPDX 2.3 RDF terms** (only the checksum terms) | `http://spdx.org/rdf/terms#` | SPDX 2.3, version IRI `http://spdx.org/rdf/terms/2.3` ([spdx.org/rdf/terms](https://spdx.org/rdf/terms/)) | SPDX 3.x has since moved to a different model and namespace. DCAT 3 links to the 2.x terms, and this namespace still resolves |
| **schema.org** | `https://schema.org/` | Community vocabulary. V30.1, 2026-09-16 ([schema.org/MediaObject](https://schema.org/MediaObject)) | Very active, but uses `domainIncludes`/`rangeIncludes` rather than RDFS domain/range |
| **NIE/NFO (OSCAF)** | `http://www.semanticdesktop.org/ontologies/2007/01/19/nie#`, `…/2007/03/22/nfo#` | Revision 1.2, "OSCAF Recommendation 28.08.2013", yet the same page says "DRAFT … for discussion only" ([nie](https://www.semanticdesktop.org/ontologies/2007/01/19/nie/), [nfo](https://www.semanticdesktop.org/ontologies/2007/03/22/nfo/)) | Frozen since 2013 |
| **NIE/NFO (GNOME TinySPARQL)** | `http://tracker.api.gnome.org/ontology/v3/nie#`, `…/v3/nfo#` | Part of TinySPARQL 3.x ([nfo-ontology](https://gnome.pages.gitlab.gnome.org/tinysparql/nfo-ontology.html), [nie-ontology](https://gnome.pages.gitlab.gnome.org/tinysparql/nie-ontology.html)) | Maintained as part of GNOME's indexer. Changes track Tracker's needs |

### 1.1 What is actually installed here (empirical)

- Packages: `tinysparql 3.11.0-1`, `libtinysparql-3.0-0 3.11.0-1`, `localsearch 3.11.0-1ubuntu1.1`
  (`dpkg -l`). `/usr/share/tracker3` does not exist. `/usr/share/localsearch3` holds only `extract-rules`.
- **There are no ontology files on disk.** The ontologies are compiled into the library as a
  GResource: `gresource list /usr/lib/x86_64-linux-gnu/libtinysparql-3.0.so.0` lists
  `/org/freedesktop/tracker/nepomuk/30-nie.ontology`, `33-nfo.ontology`, `31-nao.ontology` and others,
  and `gresource extract` returns them as Turtle.
- In the copy Ubuntu ships, which differs from OSCAF:
  - The namespaces are `http://tracker.api.gnome.org/ontology/v3/{nie,nfo,nao,nrl}#`.
    `nie:` has `nrl:lastModified "2018-08-25T11:00:00Z"` and `nfo:` has `"2014-10-06T13:05:00Z"`.
  - Classes are `rdfs:Class`, and cardinality and indexing are expressed with Tracker's own `nrl:`
    terms (`nrl:maxCardinality`, `nrl:InverseFunctionalProperty`, `nrl:indexed`, `nrl:weight`), not OWL.
  - `nie:url` has `rdfs:range xsd:string`, so the location is a **string**. OSCAF NIE declares the
    range `rdfs:Resource`.
  - `nfo:fileUrl` is gone (0 occurrences). OSCAF NFO has it as a subproperty of `nie:url`.
  - Tags are `nao:Tag`/`nao:hasTag`, not SKOS.
- How LocalSearch actually describes a file. This is the output of `localsearch info -o turtle` on an
  indexed `README.md`, abridged:

  ```turtle
  <file:///home/nmarks/go/pkg/mod/github.com/spf13/pflag@v1.0.10/README.md>
      rdf:type nie:DataObject, nfo:FileDataObject ;
      nie:url "file:///home/nmarks/go/pkg/mod/github.com/spf13/pflag@v1.0.10/README.md" ;
      nfo:fileName "README.md" ; nfo:fileSize 10960 ;
      nie:interpretedAs <urn:fileid:e3492143-f270-4ceb-8fb7-a13f89cf6f54:3313804> ;
      nfo:belongsToContainer <urn:fileid:e3492143-…:3313793> ;
      tracker:extractorHash "020e92…" .

  <urn:fileid:e3492143-f270-4ceb-8fb7-a13f89cf6f54:3313804>
      rdf:type nie:InformationElement, nfo:PlainTextDocument ;
      nie:mimeType "text/markdown" ;
      nie:isStoredAs <file:///home/nmarks/go/pkg/mod/github.com/spf13/pflag@v1.0.10/README.md> .
  ```

  Three things to note. The file (DataObject) IRI **is** its `file://` URL. The content
  (InformationElement) IRI is `urn:fileid:<filesystem-uuid>:<inode>`. No content hash is recorded
  (`nfo:hasHash` is not populated; `tracker:extractorHash` is internal). For our purposes, Tracker's
  identity is location-based, which is the property `relink` has to get away from.

## 2. How each vocabulary models the five things the issue asks about

### 2.1 Location: `file://` IRI or path literal

| Vocabulary | Property | Value |
|---|---|---|
| DCAT 3 | `dcat:downloadURL` "The URL of the downloadable file in a given format" | range `rdfs:Resource` (an IRI) |
| DCAT 3 | `dcat:accessURL` (landing page, feed, endpoint) | IRI, the wrong meaning for a local file |
| schema.org | `schema:contentUrl` "Actual bytes of the media object" | `URL` |
| OSCAF NIE/NFO | `nie:url` / `nfo:fileUrl` | `rdfs:Resource` |
| Tracker NIE | `nie:url` | `xsd:string` (and the subject IRI is the same URL) |
| PROV-O | `prov:atLocation` | `prov:Location`, geographic or not. Too generic |
| DCTerms | no location property (`dcterms:identifier` is a literal "unambiguous reference") | `rdfs:Literal` |

On `file:` IRIs, RFC 8089 (Standards Track, Feb 2017,
[rfc8089](https://www.rfc-editor.org/rfc/rfc8089.html)) defines `file:///path` (empty authority) as the
traditional form, and treats an empty host and `localhost` as "the machine from which the URI is being
interpreted". Non-ASCII paths "SHOULD be encoded as octets according to the UTF-8 character encoding
scheme" before percent-encoding. "A file URI can be dependably dereferenced or translated to a local
file path only if it is local." So a `file:` IRI is a correct, standard way to say where a file is on
*this* machine. It is not an identity: it changes on move and means something different on another machine.

**Recommendation:** store the location as **one `dcat:downloadURL` IRI**, not a path literal. It is
standard, it is typed (an IRI, not a string to parse), SPARQL can still use
`STRSTARTS(STR(?u), "file:///home/…")` for prefix filters, and the CLI converts it to an absolute path
in its JSON output. Normalise when minting: absolute path, symlinks policy decided once,
percent-encoding as RFC 8089 says. A plain path literal would need an app-local property, which loses
standards reuse for no gain.

### 2.2 Media type

- DCAT 3: `dcat:mediaType`, range **`dcterms:MediaType`** (tightened in DCAT 3 from
  `dcterms:MediaTypeOrExtent`). "This property SHOULD be used when the media type of the distribution is
  defined in IANA, otherwise `dcterms:format` MAY be used with different values" (the same rule appears
  in the French, Spanish, Japanese and Greek comments in [dcat3.ttl](https://www.w3.org/ns/dcat3.ttl)).
  DCAT's own examples use IRIs of the form `http://www.iana.org/assignments/media-types/text/csv`.
- DCTerms: `dcterms:format` "file format, physical medium, or dimensions", range includes
  `dcterms:MediaType`. `dcterms:IMT` is the vocabulary encoding scheme for IANA media types.
- schema.org: `schema:encodingFormat`, Text or URL, "usually a MIME type".
- NIE: `nie:mimeType`, `xsd:string`, on the InformationElement.

**Recommendation:** `dcat:mediaType <http://www.iana.org/assignments/media-types/{type}/{subtype}>` and
declare each value used `a dcterms:MediaType` in the TBox. This fits the shared-mime-info decision in
[#51](https://github.com/natemarks/mcp-local-notes/issues/51) with one caveat: freedesktop types
outside the IANA registry (`text/x-…`, `application/x-…`) must go in `dcterms:format` with an app-minted
`dcterms:MediaType` IRI instead, as DCAT's rule says. `text/markdown` (RFC 7763) and
`application/pdf` are both IANA-registered.

### 2.3 Content hash

- DCAT 3 adds `spdx:checksum` to Distribution: "can be used to verify that the contents of a file or
  package have not changed", range `spdx:Checksum`. `spdx:algorithm` takes an `spdx:ChecksumAlgorithm`
  individual. `spdx:checksumValue` "provides a lowercase hexadecimal encoded digest value", range
  **`xsd:hexBinary`**. The namespace is `http://spdx.org/rdf/terms#`, and the SHA-256 individual is
  `http://spdx.org/rdf/terms#checksumAlgorithm_sha256` (present in the SPDX 2.3 terms page).
- schema.org: `schema:sha256` (Text).
- NFO: `nfo:hasHash` pointing to an `nfo:FileHash` with `nfo:hashAlgorithm` (free string, e.g. "MD5")
  and `nfo:hashValue` (string). That is the same structure as SPDX but untyped.
- RFC 6920 `ni:` URIs (Standards Track, Apr 2013, [rfc6920](https://www.rfc-editor.org/rfc/rfc6920.html)):
  `ni:///sha-256;<base64url, no padding>`, a location-independent *name* for content. This is the
  standard way to make a hash into an IRI (see 2.5).

**Recommendation:** SPDX checksum via DCAT, SHA-256. One practical point for the git-friendly export:
the checksum is a blank node in the obvious modelling. Blank nodes make sorted Turtle diffs and
SPARQL `DELETE` of one Resource's hash harder. Either skolemise it (mint
`<urn:uuid:…>` or `<{resource}#checksum>`; RDF 1.1 Concepts §3.5 explicitly allows replacing blank
nodes with Skolem IRIs) or accept blank nodes and let the exporter canonicalise. That choice belongs
with the export-format ticket.

### 2.4 Title

All of `dcterms:title` (range `rdfs:Literal`), `schema:name`, and `nie:title` (Tracker:
`rdfs:subPropertyOf dc:title`; OSCAF also lists `rdfs:label` and `nao:prefLabel`) mean the same thing.
DCAT uses `dcterms:title` on Distribution (§6.8.1). **Use `dcterms:title`.**

### 2.5 Relations between files

- DCTerms has the general-purpose set. None have a formal range ("non-literal values intended"):
  `dcterms:relation`, `references`, `isPartOf`/`hasPart`, `requires`, `source`, plus versioning
  (`isVersionOf`, `replaces`). DCAT reuses them (`dcterms:hasPart`, `dcterms:replaces`, …).
- PROV-O: `prov:wasDerivedFrom` ("a transformation of an entity into another"), `prov:wasRevisionOf`,
  `prov:wasQuotedFrom`, `prov:alternateOf` ("two alternate entities present aspects of the same
  thing"), `prov:specializationOf`.
- NIE: `nie:relatedTo` (subproperty of `dc:relation`), `nie:links`, `nie:hasPart`/`nie:isPartOf`.

**Recommendation:** every user-defined relation kind is an `owl:ObjectProperty` with
`rdfs:subPropertyOf` the closest standard term (e.g. `:annotates rdfs:subPropertyOf
dcterms:references`, `:exportedFrom rdfs:subPropertyOf prov:wasDerivedFrom`). Then
`?a dcterms:relation ?b`-style generic queries work under RDFS entailment (or with an explicit
`rdfs:subPropertyOf*` path), and the CLI's `describe` can list the relation kinds from the TBox.

### 2.6 Tags

SKOS (`skos:Concept`, `skos:inScheme`, `skos:prefLabel`, `skos:broader`), linked from the Resource by
`dcterms:subject`. DCMI recommends a URI value for `subject`. DCAT's `dcat:theme` ("A main
category of the resource", a subproperty of `dcterms:subject`, values organised in a
`skos:ConceptScheme`) has no formal domain, but DCAT lists it only under Cataloged Resource
(§6.4.12), not under Distribution. Use `dcterms:subject` directly on a file. `dcat:theme` gives a DCAT
consumer nothing extra here. Narrower-concept
matching is the SPARQL 1.1 property path `dcterms:subject/skos:broader*` (shown working in §9). Tracker's
`nao:Tag` is the non-standard alternative and should be skipped.

### 2.7 Provenance (who or what added a Resource)

Keep two dates apart. The *file's* dates (`dcterms:modified` = mtime) and the *catalog entry's* dates
are different facts. DCAT's `dcat:CatalogRecord` is "a record in a catalog, describing the registration
of a single `dcat:Resource`". Its `dcterms:issued` is "the date of listing … in the catalog and not
the publication date", it has `foaf:primaryTopic` (functional), and its usage note says "the W3C PROV
Ontology allows describing further provenance information such as the details of the process and the
agent involved". So:

- record `prov:wasAttributedTo` agent. `prov:Person` is the user and `prov:SoftwareAgent` ("running
  software") is the CLI or an AI agent. `prov:actedOnBehalfOf` says an agent was working for the user.
- Do **not** put `prov:wasAttributedTo` or `prov:generatedAtTime` on the Resource to mean "added by".
  On the Resource they would claim the agent *made the file* and give the time the file came into existence.
- If you later want the activity itself (`add`, `scan`, `relink`), use `prov:Activity` with
  `prov:wasAssociatedWith` and `prov:startedAtTime`, and point to it from the record with `prov:wasGeneratedBy`.

Strictly speaking, `foaf:primaryTopic`'s DCAT definition says the topic is a `dcat:Resource`. A
Distribution is not one. Using a CatalogRecord per file is therefore a small, harmless stretch of
DCAT. The stricter alternative is to wrap each file in a `dcat:Dataset` (see 3.1), which is not worth it
for v1.

## 3. The file-versus-content split (NIE's main idea)

NIE separates `nie:DataObject` (bytes somewhere: a file, part of a file, a remote object) from
`nie:InformationElement` (the content the user works with), linked by `nie:interpretedAs`/
`nie:isStoredAs`, "in order to make the interpretation independent of the representation" (OSCAF NIE
§6.2). DCAT's `dcat:Dataset` (abstract) and `dcat:Distribution` (a concrete form, "such as a
downloadable file") draw the same line, and DCAT's schema.org appendix maps them to
`schema:Dataset`/`schema:DataDownload`. FRBR-style work/item modelling is the library-science
version of the same split.

### 3.1 Should v1 split?

No. The map defines a Resource as *a file*. The split pays off only when one work has several
files (a paper as PDF and EPUB, a note and its rendered HTML), and the standard
`prov:alternateOf` or `dcterms:hasFormat` between Resources covers that case well enough. Because
`:Resource` is already a `dcat:Distribution`, adding a `dcat:Dataset`/`:Work` layer later is additive.
Each new Work would get `dcat:distribution` links to existing Resources, and nothing would be re-minted.

## 4. Minting stable IRIs for local files

| Pattern | Who uses it | Survives move/rename | Survives edit | Survives copy to another FS / machine |
|---|---|---|---|---|
| `file:///abs/path` as the subject | Tracker DataObject | no | yes | no (RFC 8089: "local" only) |
| `urn:fileid:<fs-uuid>:<inode>` | Tracker InformationElement | rename on the same FS only. Atomic-save editors (write temp, rename over) change the inode | depends on the editor | no |
| `ni:///sha-256;…` (RFC 6920) | content-addressed stores | yes | **no** (new content, new name) | yes |
| path-derived HTTP IRI (`…/id/home/alice/x.pdf`) | ad hoc | no | yes | no |
| **opaque minted ID** (`urn:uuid:<v7>` or `https://<ns>/id/<uuid>`) | DCAT catalogues, most KGs | **yes** | **yes** | **yes** |

The deciding rule comes from TimBL's [Cool URIs don't change](https://www.w3.org/Provider/Style/URI):
"After the creation date, putting any information in the name is asking for trouble one way or
another", which specifically includes file names and subjects. The map's identity model is
"path + content hash, with `relink`". Both of those are *mutable attributes*, so neither can be the
IRI. Mint an opaque IRI once at `add`/`scan`. Store path (`dcat:downloadURL`) and hash
(`spdx:checksum`) as properties. `relink` then rewrites one triple and leaves every relation,
tag and record intact. The same choice is what makes the "cross-machine sync" future direction possible.

Which opaque form:

- **`urn:uuid:` with UUIDv7** (RFC 9562, Standards Track, May 2024, obsoletes RFC 4122,
  [rfc9562](https://www.rfc-editor.org/rfc/rfc9562.html)). "Implementations SHOULD utilize UUIDv7
  instead of UUIDv1 and UUIDv6 if possible". The 48-bit millisecond timestamp prefix also makes IRIs sort
  by creation time in a sorted Turtle export. A `urn:` is honest that the IRI is not dereferenceable, and
  it needs no domain. Caveat (RFC 9562): UUIDs "SHOULD NOT" be assumed hard to guess, which does not
  matter here.
- `https://<domain-you-control>/<app>/id/<uuid>` (slash IRIs) is the Linked Data purist option. The W3C
  Cool URIs note favours HTTP IRIs and slash IRIs for large sets of instances
  ([TR/cooluris](https://www.w3.org/TR/cooluris/)), but nothing will ever serve them on a single
  machine.

**Recommendation:** `urn:uuid:` (v7) for ABox individuals (Resources, records, agents). Keep a hash
namespace you control for the TBox and SKOS concepts (`https://…/ontology#`, as in this repo's
`notes/tbox.ttl`), because those are a small vocabulary that changes as one unit, which is exactly the
Cool URIs §4.4 case. Optionally also record the content-addressed name as a literal
(`dcterms:identifier "ni:///sha-256;…"`) for interop, but the SPDX checksum already carries that information.

## 5. Why not build on NIE/NFO

NFO has the best file *class taxonomy* (`nfo:PaginatedTextDocument` for "PDF, DOC, PS, DVI",
`nfo:PlainTextDocument`, `nfo:SourceCode`, `nfo:Folder`, …), and the DataObject/InformationElement
split is good thinking. But:

1. **No canonical namespace.** OSCAF's `semanticdesktop.org` copy is frozen and labels itself DRAFT.
   The maintained copy (`tracker.api.gnome.org/ontology/v3/`) is GNOME's API, versioned with the
   library ("v3"), and has already changed semantics (`nie:url` is now a string, `nfo:fileUrl` is gone).
   Whichever you pick, you are tied to something that is either dead or controlled by someone else.
2. **Not W3C-standard modelling.** Tracker expresses constraints in its own `nrl:` terms, not
   OWL 2 or SHACL. Learning from it teaches Tracker, not the standards stack the map chose.
3. **Its identity model is location- and inode-based** (section 1.1), the opposite of what `relink` needs.
4. Coexistence costs nothing: the tool never writes into Tracker, and Tracker's store is separate.

If the learning goal wants it, put an *alignment* file next to the TBox, e.g.
`:Resource rdfs:subClassOf <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#FileDataObject>` and
`:Paper rdfs:subClassOf <…nfo#PaginatedTextDocument>`. OWL 2 lets you do this without importing
NFO, and it can be dropped without touching data.

## 6. Why not build on schema.org

schema.org is alive and widely understood (V30.1, Sept 2026). `schema:MediaObject` (Thing >
CreativeWork > MediaObject) has `contentUrl`, `encodingFormat`, `sha256` and `contentSize`, and
`schema:DigitalDocument` (Thing > CreativeWork, with subtypes `NoteDigitalDocument`,
`TextDigitalDocument`, …) is close to "a document". But it uses `schema:domainIncludes`/`rangeIncludes`
(non-RDFS, non-entailing), types `sha256` and `contentSize` as Text ("kilobytes or megabytes"), and is
designed for publishing markup on web pages. That makes it a poor base for practising RDFS, OWL and
SHACL. As with NFO, an optional alignment file works (`:Resource rdfs:subClassOf schema:MediaObject`,
`dcat:downloadURL` ↔ `schema:contentUrl`, `dcat:mediaType` ↔ `schema:encodingFormat`). DCAT 3
Appendix B is W3C's own DCAT↔schema.org alignment.

## 7. What RDFS/OWL will and won't enforce: SHACL

DCAT gives no cardinalities, and RDFS/OWL are open-world, so a Resource with no `dcat:downloadURL`
is not inconsistent to a reasoner, just incomplete. The map's `validate` command checks things like
"exactly one location, one media type, one checksum", and those rules are SHACL shapes. A minimal shape
(validated in §9):

```turtle
@prefix :        <https://example.org/fileont/ontology#> .
@prefix dcat:    <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix sh:      <http://www.w3.org/ns/shacl#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix spdx:    <http://spdx.org/rdf/terms#> .

:ResourceShape a sh:NodeShape ;
    sh:targetClass :Resource ;
    sh:property [ sh:path dcat:downloadURL ; sh:minCount 1 ; sh:maxCount 1 ;
                  sh:nodeKind sh:IRI ; sh:pattern "^file:///" ] ;
    sh:property [ sh:path dcat:mediaType ; sh:minCount 1 ; sh:maxCount 1 ; sh:nodeKind sh:IRI ] ;
    sh:property [ sh:path spdx:checksum ; sh:minCount 1 ; sh:maxCount 1 ] ;
    sh:property [ sh:path dcterms:subject ; sh:class skos:Concept ] .
```

`sh:targetClass :Resource` also targets instances of `:Paper` and `:Note`, because SHACL follows
`rdfs:subClassOf` in the data graph.

## 8. Recommended combination for v1

1. **TBox (one hash namespace you control):** `:Resource` (`rdfs:subClassOf dcat:Distribution,
   prov:Entity`). Resource types are `owl:Class` subclasses of `:Resource`. Relation kinds are
   `owl:ObjectProperty` with `rdfs:subPropertyOf` a DCTerms/PROV term. Topics are a `skos:ConceptScheme`
   of `skos:Concept`s with `skos:broader`. Media types are `dcterms:MediaType` IANA IRIs.
2. **Per Resource:** `dcterms:title`, `dcat:downloadURL` (file IRI), `dcat:mediaType` (or
   `dcterms:format`), `dcat:byteSize`, `spdx:checksum` (SHA-256), `dcterms:modified` (file mtime),
   `dcterms:subject` → concepts, relations.
3. **Per catalog entry:** `dcat:CatalogRecord` with `foaf:primaryTopic`, `dcterms:issued`,
   `dcterms:modified`, `prov:wasAttributedTo` → `prov:Person`/`prov:SoftwareAgent`.
4. **Identity:** `urn:uuid:` UUIDv7, minted once, never derived from path, inode or hash.
5. **Constraints:** SHACL shapes for what `validate` enforces.
6. **Optional, learning-only:** a separate alignment file to NFO and schema.org.

Prefixes used: `dcat`, `dcterms`, `foaf` (only for `primaryTopic`/`name`), `owl`, `prov`, `rdf`,
`rdfs`, `sh`, `skos`, `spdx`, `xsd`. All are W3C, DCMI, or (for SPDX) cited normatively by a W3C Recommendation.

## 9. Example graph: one PDF and one markdown file

Checked with rdflib 7.1.4 and pySHACL 0.31.0 in a throwaway venv (`/tmp/rdfv`, not part of this
repo): parses to 65 triples, conforms to the §7 shape (with `inference="rdfs"`), fails the shape once the
PDF's `dcat:downloadURL` is removed, and
`SELECT ?r WHERE { ?r dcterms:subject/skos:broader* :semantic-web }` returns both Resources (the note
is tagged with the narrower `:linked-data`). The hashes and sizes are illustrative.

```turtle
@prefix :        <https://example.org/fileont/ontology#> .
@prefix dcat:    <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix foaf:    <http://xmlns.com/foaf/0.1/> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix prov:    <http://www.w3.org/ns/prov#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix spdx:    <http://spdx.org/rdf/terms#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

# ------------------------------------------------------------------ TBox
:Resource a owl:Class ;
    rdfs:subClassOf dcat:Distribution , prov:Entity ;
    rdfs:label "Resource"@en ;
    rdfs:comment "A local file that the ontology describes in place."@en .

:Paper a owl:Class ; rdfs:subClassOf :Resource ; rdfs:label "Paper"@en .
:Note  a owl:Class ; rdfs:subClassOf :Resource ; rdfs:label "Note"@en .

:annotates a owl:ObjectProperty ;
    rdfs:subPropertyOf dcterms:references ;
    rdfs:domain :Resource ;
    rdfs:range  :Resource ;
    rdfs:label "annotates"@en .

:topics a skos:ConceptScheme ;
    dcterms:title "Topics"@en .

:semantic-web a skos:Concept ;
    skos:inScheme :topics ;
    skos:topConceptOf :topics ;
    skos:prefLabel "semantic web"@en .

:linked-data a skos:Concept ;
    skos:inScheme :topics ;
    skos:prefLabel "linked data"@en ;
    skos:broader :semantic-web .

<http://www.iana.org/assignments/media-types/application/pdf> a dcterms:MediaType .
<http://www.iana.org/assignments/media-types/text/markdown>   a dcterms:MediaType .

# ------------------------------------------------------------------ ABox
# One PDF ...
<urn:uuid:0192f3a0-6c1e-7b2a-9d4f-3e8a1c5b7d01> a :Paper ;
    dcterms:title "Cool URIs for the Semantic Web" ;
    dcat:downloadURL <file:///home/alice/Documents/papers/Cool%20URIs%20for%20the%20Semantic%20Web.pdf> ;
    dcat:mediaType <http://www.iana.org/assignments/media-types/application/pdf> ;
    dcat:byteSize "482113"^^xsd:nonNegativeInteger ;
    spdx:checksum [
        a spdx:Checksum ;
        spdx:algorithm spdx:checksumAlgorithm_sha256 ;
        spdx:checksumValue "7cf1c0c154294dfc763ca6841939f1b5b69c2191099a977daac16b961b169f52"^^xsd:hexBinary
    ] ;
    dcterms:modified "2025-11-02T09:14:00Z"^^xsd:dateTime ;
    dcterms:subject :semantic-web .

# ... and one markdown note that annotates it.
<urn:uuid:0192f3a2-1f4d-7c88-a0b3-55e2d9f04a12> a :Note ;
    dcterms:title "Reading notes: Cool URIs" ;
    dcat:downloadURL <file:///home/alice/notes/cool-uris.md> ;
    dcat:mediaType <http://www.iana.org/assignments/media-types/text/markdown> ;
    dcat:byteSize "3172"^^xsd:nonNegativeInteger ;
    spdx:checksum [
        a spdx:Checksum ;
        spdx:algorithm spdx:checksumAlgorithm_sha256 ;
        spdx:checksumValue "245fd9a0a97d6bc60d726ef69877f1a243a64909d92882c240ad50fff0b1855e"^^xsd:hexBinary
    ] ;
    dcterms:modified "2026-10-20T18:40:12Z"^^xsd:dateTime ;
    dcterms:subject :linked-data ;
    :annotates <urn:uuid:0192f3a0-6c1e-7b2a-9d4f-3e8a1c5b7d01> .

# Catalog records: who or what added each Resource, and when.
<urn:uuid:0192f3a0-6c1f-7e01-8a77-0b9c2d3e4f50> a dcat:CatalogRecord ;
    foaf:primaryTopic <urn:uuid:0192f3a0-6c1e-7b2a-9d4f-3e8a1c5b7d01> ;
    dcterms:issued "2026-10-18T10:02:31Z"^^xsd:dateTime ;
    prov:wasAttributedTo <urn:uuid:0192f39f-0000-7000-8000-000000000001> .

<urn:uuid:0192f3a2-1f4e-7a10-b2c4-6d7e8f901a23> a dcat:CatalogRecord ;
    foaf:primaryTopic <urn:uuid:0192f3a2-1f4d-7c88-a0b3-55e2d9f04a12> ;
    dcterms:issued "2026-10-20T18:41:05Z"^^xsd:dateTime ;
    prov:wasAttributedTo <urn:uuid:0192f39f-0000-7000-8000-000000000002> .

<urn:uuid:0192f39f-0000-7000-8000-000000000001> a prov:Person , foaf:Person ;
    foaf:name "Alice" .

<urn:uuid:0192f39f-0000-7000-8000-000000000002> a prov:SoftwareAgent ;
    rdfs:label "claude-code" ;
    prov:actedOnBehalfOf <urn:uuid:0192f39f-0000-7000-8000-000000000001> .
```

## 10. Open points handed to other tickets

- **Export format:** skolemise checksum blank nodes or canonicalise them; one named graph per
  CatalogRecord is DCAT's own suggestion ("The name of that graph SHOULD be the IRI of the catalog
  record") if TriG is chosen.
- **`scan`:** non-IANA freedesktop types need minted `dcterms:MediaType` IRIs under `dcterms:format`.
- **Agent identity:** how the CLI learns which `prov:SoftwareAgent` is calling it (flag or env var) is a
  CLI-design question, not a vocabulary one.

## Sources consulted (primary)

- W3C, *Data Catalog Vocabulary (DCAT) – Version 3*, Recommendation 22 Aug 2024 — https://www.w3.org/TR/vocab-dcat-3/ and https://www.w3.org/ns/dcat3.ttl
- DCMI, *DCMI Metadata Terms*, 2020-01-20 — https://www.dublincore.org/specifications/dublin-core/dcmi-terms/
- W3C, *SKOS Reference*, Recommendation 18 Aug 2009 — https://www.w3.org/TR/skos-reference/
- W3C, *PROV-O*, Recommendation 30 Apr 2013 — https://www.w3.org/TR/prov-o/
- SPDX 2.3 RDF terms — https://spdx.org/rdf/terms/
- schema.org V30.1 — https://schema.org/MediaObject, https://schema.org/DigitalDocument
- OSCAF, *NEPOMUK Information Element Ontology* v1.2 — https://www.semanticdesktop.org/ontologies/2007/01/19/nie/
- OSCAF, *NEPOMUK File Ontology* v1.2 — https://www.semanticdesktop.org/ontologies/2007/03/22/nfo/
- GNOME TinySPARQL docs (v3.12) — https://gnome.pages.gitlab.gnome.org/tinysparql/ (nie-ontology, nfo-ontology, ontologies pages)
- Installed TinySPARQL 3.11.0 ontologies, extracted with `gresource extract /usr/lib/x86_64-linux-gnu/libtinysparql-3.0.so.0 /org/freedesktop/tracker/nepomuk/{30-nie,33-nfo,31-nao}.ontology`, and `localsearch info -o turtle` output (this machine)
- IETF RFC 8089 *The "file" URI Scheme* — https://www.rfc-editor.org/rfc/rfc8089.html
- IETF RFC 6920 *Naming Things with Hashes* — https://www.rfc-editor.org/rfc/rfc6920.html
- IETF RFC 9562 *Universally Unique IDentifiers (UUIDs)* — https://www.rfc-editor.org/rfc/rfc9562.html
- T. Berners-Lee, *Cool URIs don't change* — https://www.w3.org/Provider/Style/URI
- W3C, *Cool URIs for the Semantic Web* — https://www.w3.org/TR/cooluris/
- Prior art: [`docs/research/skos-owl-personal-kb-conventions.md`](skos-owl-personal-kb-conventions.md), `notes/tbox.ttl`
