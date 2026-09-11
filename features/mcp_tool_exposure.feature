Feature: Expose ontology operations as local MCP tools
  As Nate, the notes maintainer
  I want these operations available as typed, discoverable tools
  So that any assistant can invoke them reliably without reconstructing shell commands

  Background:
    Given a local MCP server named "local-ontology" is registered with the desktop app
    And it is connected to the current session

  Scenario: Tools are discoverable under a clear category
    When an assistant lists available tools
    Then it should see tools named with the "local-ontology" prefix
    And that group should include at least: new_note, update_note, add_topic, add_class, sync_note, rebuild_abox, validate, list_topics, list_types

  Scenario: Creating a note via the MCP tool matches the CLI behavior
    Given identical input is used for both interfaces
    When a note is created once via the "new_note" MCP tool and once via the equivalent CLI command
    Then both should produce an identical note file
    And both should produce an identical ABox block

  Scenario: The server operates only on local files
    When any "local-ontology" tool is invoked
    Then it should read and write only files under the configured notes directory on the local device
    And it should make no network calls

  Scenario: The server surfaces validation errors as structured tool errors
    Given a request that would violate a uniqueness or vocabulary rule
    When the corresponding "local-ontology" tool is invoked
    Then it should return a structured error naming the specific rule violated
    And it should make no partial writes to any note file or ontology file

  Scenario: The server is unavailable gracefully
    Given the "local-ontology" MCP server is not running or not registered
    When an assistant looks for "local-ontology" tools
    Then it should find none
    And it should fall back to telling Nate the local ontology tools aren't available
    Rather than guessing at file edits by hand

  Scenario: CLI remains usable without any assistant or MCP server
    Given no MCP client is involved
    When "validate" is run directly from a terminal or CI job
    Then it should behave identically to being invoked through the MCP tool
    And it should not require network access or an MCP server to be running
