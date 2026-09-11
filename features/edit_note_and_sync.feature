Feature: Edit a note and keep the ontology synced
  As Nate, the notes maintainer
  I want edits to a note's frontmatter to be reflected in the ontology automatically
  So that the ABox never drifts from what my notes actually say

  Background:
    Given a note "sparql-basics" exists with title "SPARQL basics" and tags "knowledge-graphs"
    And its ABox block in abox.ttl matches its current frontmatter

  Scenario: Editing tags regenerates the ABox block
    When I update note "sparql-basics" to add the tag "semantic-web"
    Then the note's "modified" date should be updated to today
    And the ABox block for "sparql-basics" should list both "knowledge-graphs" and "semantic-web"
    And there should be exactly one ABox block for "sparql-basics"

  Scenario: Renaming a note preserves the old title as an alias
    When I rename note "sparql-basics" to "Intro to SPARQL"
    Then the note's "title" should be "Intro to SPARQL"
    And the note's "aliases" should include "SPARQL basics"
    And the note's "id" should remain "sparql-basics"
    And the note's filename should remain "sparql-basics.md"
    And the ABox block's dcterms:title for "sparql-basics" should be "Intro to SPARQL"

  Scenario: Renaming to a title that collides with another note is rejected
    Given a note "rdf-vs-property-graphs" exists with title "RDF vs. property graphs"
    When I rename note "sparql-basics" to "RDF vs. property graphs"
    Then the request should be rejected with a "duplicate title" error
    And note "sparql-basics" should keep its original title

  Scenario: Adding a related note that does not exist is rejected
    When I update note "sparql-basics" to add "related: does-not-exist"
    Then the request should be rejected with a "related note not found" error

  Scenario: Adding a valid related note updates the ABox
    Given a note "intro-to-sparql" exists
    When I update note "sparql-basics" to add "related: intro-to-sparql"
    Then the ABox block for "sparql-basics" should include ":relatesTo :intro-to-sparql"

  Scenario: Re-syncing a single note after a hand edit
    Given note "sparql-basics" was hand-edited outside any tool session to add tag "rdf"
    And its ABox block still only lists "knowledge-graphs"
    When I sync note "sparql-basics"
    Then the ABox block for "sparql-basics" should be regenerated to include "rdf"

  Scenario: Rebuilding the entire ABox from all notes' frontmatter
    Given multiple notes have been hand-edited outside any tool session
    And abox.ttl no longer matches some of their frontmatter
    When I run a full rebuild
    Then every note's ABox block should be regenerated from its current frontmatter
    And abox.ttl should contain no block for a note id that no longer has a corresponding file
