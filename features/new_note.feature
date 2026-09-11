Feature: Create a new note
  As Nate, the notes maintainer
  I want to create a new note with validated metadata
  So that every note is uniquely identified and consistent with the controlled vocabulary

  Background:
    Given the notes directory contains a note titled "RDF vs. property graphs"
    And the topic vocabulary contains "knowledge-graphs"
    And the type vocabulary contains "Concept"

  Scenario: Successfully create a note with valid, existing metadata
    When I request a new note with title "SPARQL basics", tags "knowledge-graphs", and type "Concept"
    Then a new note file "sparql-basics.md" should exist
    And its frontmatter "id" should be "sparql-basics"
    And its frontmatter "title" should be "SPARQL basics"
    And its frontmatter "created" date should be set to today
    And an ABox block for "sparql-basics" should be appended to abox.ttl

  Scenario: Reject a duplicate title
    When I request a new note with title "RDF vs. property graphs"
    Then the request should be rejected with a "duplicate title" error
    And no new note file should be created
    And abox.ttl should be unchanged

  Scenario: Reject an alias that collides with another note's title
    Given a note titled "Intro to SPARQL" exists
    When I request a new note with title "SPARQL Intro" and alias "Intro to SPARQL"
    Then the request should be rejected with a "duplicate alias" error

  Scenario: Reject an unknown tag without explicit approval
    When I request a new note with title "Quantum SPARQL" and tags "quantum-computing"
    Then the request should be rejected with an "unknown topic" error
    And the error should name "quantum-computing" as not present in the topic vocabulary

  Scenario: Create a note while approving a new topic in the same request
    When I request a new note with title "Quantum SPARQL", tags "quantum-computing", and approve adding topic "quantum-computing"
    Then a new skos:Concept "quantum-computing" should be added to tbox.ttl
    And the note "quantum-sparql.md" should be created successfully
    And its frontmatter "tags" should include "quantum-computing"

  Scenario: Reject a note with no tags
    When I request a new note with title "Untagged note" and no tags
    Then the request should be rejected with a "missing required field: tags" error

  Scenario: Reject a note with an unknown type
    When I request a new note with title "Mystery Note" and type "Widget"
    Then the request should be rejected with an "unknown type" error
    And the error should name "Widget" as not declared in the ontology

  Scenario: Minted id is unique even for a duplicate slug base
    Given a note with id "sparql-basics" already exists
    When I request a new note with title "Sparql Basics" (different casing/punctuation)
    Then the request should be rejected with a "duplicate title" error
