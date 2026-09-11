Feature: Archive and delete notes safely
  As Nate, the notes maintainer
  I want retiring a note to default to a safe, reversible action
  So that I don't silently break links from other notes

  Background:
    Given a note "sparql-basics" exists

  Scenario: Archiving sets status without removing the note
    When I archive note "sparql-basics"
    Then its "status" should be "archived"
    And the note file "sparql-basics.md" should still exist
    And the ABox block for "sparql-basics" should still exist

  Scenario: Deleting a note with no inbound references
    Given no other note references "sparql-basics"
    When I request to delete "sparql-basics"
    Then the note file should be removed
    And its ABox block should be removed from abox.ttl

  Scenario: Deleting a note with inbound references warns before proceeding
    Given a note "intro-to-sparql" has "related" referencing "sparql-basics"
    When I request to delete "sparql-basics" without confirmation
    Then the request should be rejected
    And I should be told that "intro-to-sparql" references "sparql-basics"

  Scenario: Confirmed delete removes the note despite inbound references
    Given a note "intro-to-sparql" has "related" referencing "sparql-basics"
    When I confirm deletion of "sparql-basics" despite the warning
    Then the note file "sparql-basics.md" should be removed
    And its ABox block should be removed from abox.ttl
    And a subsequent validation run should report a "dangling reference" issue for "intro-to-sparql"
