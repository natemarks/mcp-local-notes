Feature: Validate notes and ontology consistency
  As Nate, the notes maintainer
  I want one command that surfaces every consistency problem in the corpus
  So that I can trust my notes and their ontology without manually cross-checking

  Scenario: Clean corpus passes validation
    Given all notes have required fields, unique ids/titles/aliases, valid tags and types, valid references, and up-to-date ABox blocks
    When I run validation
    Then the report should show zero issues
    And validation should exit with a zero (success) status

  Scenario: Detect a missing required field
    Given a note is missing its "tags" field
    When I run validation
    Then the report should list a "missing required field: tags" issue naming that note

  Scenario: Detect a duplicate title or alias
    Given two notes share the same title
    When I run validation
    Then the report should list a "duplicate title" issue naming both notes
    And validation should exit with a non-zero status

  Scenario: Detect a tag not in the controlled vocabulary
    Given a note uses a tag that is not declared in tbox.ttl
    When I run validation
    Then the report should list an "unknown topic" issue naming that note and tag

  Scenario: Detect an unknown type
    Given a note's "type" is not declared as a class in tbox.ttl
    When I run validation
    Then the report should list an "unknown type" issue naming that note and type

  Scenario: Detect a dangling related/part_of reference
    Given a note's "related" field references an id that does not exist
    When I run validation
    Then the report should list a "dangling reference" issue naming the note and the missing id

  Scenario: Detect a stale ABox entry
    Given a note's frontmatter differs from its current ABox block in abox.ttl
    When I run validation
    Then the report should list a "stale ABox entry" issue naming that note

  Scenario: Detect a filename that doesn't match its id
    Given a note file is named differently from its frontmatter "id"
    When I run validation
    Then the report should list a "filename/id mismatch" issue naming that note

  Scenario: Validation never modifies files
    Given the corpus has one or more issues
    When I run validation
    Then no note file should be changed
    And tbox.ttl and abox.ttl should be unchanged

  Scenario: Validation output is available as structured data
    When I run validation with structured output requested
    Then I should receive a machine-readable (e.g. JSON) list of issues
    And each issue should include a type, an affected note id, and a human-readable message
