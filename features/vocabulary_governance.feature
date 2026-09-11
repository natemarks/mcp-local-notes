Feature: Govern the controlled topic and type vocabulary
  As Nate, the notes maintainer
  I want growing the vocabulary to be an explicit, auditable action
  So that tags and types stay consistent instead of fragmenting

  Scenario: Add a new topic explicitly
    When I add the topic "semantic-web"
    Then tbox.ttl should contain a new skos:Concept "semantic-web" in the ":topics" scheme
    And "semantic-web" should now be usable as a tag on notes

  Scenario: Reject adding a topic that already exists
    Given the topic "knowledge-graphs" already exists
    When I try to add the topic "knowledge-graphs" again
    Then the request should be rejected with a "topic already exists" error

  Scenario: Add a new note type explicitly
    When I add the type "Recipe" as a subclass of "Note"
    Then tbox.ttl should contain a new owl:Class "Recipe" with rdfs:subClassOf ":Note"
    And "Recipe" should now be usable as a note's "type"

  Scenario: Reject adding a type that already exists
    Given the type "Concept" already exists
    When I try to add the type "Concept" again
    Then the request should be rejected with a "type already exists" error

  Scenario: List current topics
    Given the topic vocabulary contains "knowledge-graphs" and "semantic-web"
    When I request the list of topics
    Then I should receive exactly "knowledge-graphs" and "semantic-web"

  Scenario: List current types
    Given the type vocabulary contains "Note", "Person", "Project", "Meeting", "Reference", and "Concept"
    When I request the list of types
    Then I should receive all six declared types
