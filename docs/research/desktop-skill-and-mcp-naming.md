# Research: Claude Desktop's Skill and MCP-tool-naming mechanics

**Date:** 2026-09-18
**Scope:** Primary-source research only. No code was changed as part of this
document. This follows on from
`docs/research/skill-and-mcp-server-integration.md` (Claude Code specific)
and answers GitHub issue #35's three questions for **Claude Desktop**, part
of the "jumpstart" wayfinder map (issue #30).

**Already confirmed this session, restated here for context (not
re-derived):** Claude Desktop's Skills mechanism is a ZIP upload through
Settings > Customize > Skills, gated on a "code execution enabled"
capability toggle, per
https://support.claude.com/en/articles/12512180-use-skills-in-claude -- a
completely different mechanism from Claude Code's `~/.claude/skills/<name>/
SKILL.md` file-copy. Claude Desktop has no plugin/marketplace system.

---

## Question 1: Does a Desktop-uploaded Skill trigger autonomously from `description`, or does it require explicit per-conversation selection?

**Finding: autonomous, purely `description`-driven -- same trigering model as Claude Code, once the skill is enabled.**

Primary source:
https://support.claude.com/en/articles/12512180-use-skills-in-claude states
directly, for Anthropic's built-in skills (and the same mechanism is used
for custom ones): "Claude will automatically use these tools when
relevant. You don't need to explicitly invoke them -- Claude determines
when each skill is needed based on your request," with the worked example:
"if you ask Claude to 'Create a PowerPoint presentation about Q3 results,'
Claude will automatically use the PowerPoint skill if the capability is
enabled." For custom (user-uploaded) skills specifically, the same article
ties this to the authored `description`: "Write clear descriptions when
writing custom skills. A specific description tells Claude when to invoke
your skill" -- i.e. the same description-to-task matching mechanism
Claude Code uses, not a special Desktop-only keyword or slash-command
requirement.

Corroborating primary source,
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
("Using Skills" section): "Both work the same way: once a Skill is
available in your environment, Claude uses it automatically when relevant
to your request" -- explicitly stated as true across claude.ai, Claude
Code, and the API alike (this is the "Level 1: Metadata (always loaded)"
mechanism the doc describes: the YAML frontmatter's `description` is
loaded into the system prompt at startup, unconditionally, and "Claude
loads this metadata at startup and includes it in the system prompt. The
`description` is what Claude matches your request against when
determining whether to trigger the Skill").

**What "enabled" actually gates, per the same source:** the *only*
per-conversation toggle in the entire Desktop mechanism is not per-skill,
per-conversation selection of *which skill to use* -- it's the
account-level/session-level "code execution enabled" capability switch
(Question 3) that must be on before *any* uploaded skill is reachable at
all. Once that capability is on and a skill has been uploaded, there is no
further explicit-selection step documented anywhere in either source; the
skill is live in the system prompt for every subsequent conversation and
fires on description-match alone, exactly as in Claude Code.

**Finding, stated plainly:** No, it does not require explicit
selection/toggling per conversation (beyond the one-time, account-wide
code-execution capability toggle). It triggers autonomously from
`description`-to-task matching, the same mechanism Claude Code uses and
that the platform docs describe as uniform "once a Skill is available in
your environment."

---

## Question 2: What does a Desktop custom connector's callable tool name look like to the model?

**Finding: no primary source documents a `mcp__<alias>__<tool>`-shaped (or any other specific) prefix for Claude Desktop/claude.ai -- and the closest primary-source evidence available suggests it is a *materially different* shape, not merely a different string in the same pattern.**

I checked every plausible primary source and none of them specify a
Desktop/claude.ai tool-naming convention:

- https://support.claude.com/en/articles/11175166-getting-started-with-model-context-protocol-mcp-on-claude-desktop
  -- no mention of tool naming, and no mention of the `mcp-remote` npm
  package this repo's own README uses as the stdio bridge.
- https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities,
  https://support.claude.com/en/articles/14503689-mcp-connectors -- neither
  discusses tool-name construction or display format.
- https://claude.com/docs/connectors/building (Anthropic's own "Building
  custom connectors" primary doc) -- covers transports, auth, and a
  technical-limits table, but says nothing about tool-name prefixing. It
  does, however, confirm Desktop is genuinely a separate client
  implementation from Claude Code, not a re-skin of it: "Claude.ai/Desktop
  max tool result size: ~150,000 characters" vs. "Claude Code max tool
  result size: 25,000 tokens (configurable via `MAX_MCP_OUTPUT_TOKENS`)"
  and "Claude.ai/Desktop tool call timeout: 240 seconds (4 minutes) per
  tool call" vs. "Claude Code timeout: Configurable via `MCP_TOOL_TIMEOUT`"
  -- different limits, different config knobs, strongly implying
  independently engineered client-side tool plumbing rather than shared
  code that would produce the same naming convention by construction.
- https://claude.com/docs/connectors/building/mcp -- general MCP
  conceptual overview (tools/resources/prompts, local vs. remote), no
  naming-format detail.

**The one piece of concrete, primary-source naming evidence found** is
from a *different* (but closely related) Anthropic MCP integration surface
-- the server-side **API MCP connector**
(https://platform.claude.com/docs/en/agents-and-tools/mcp-connector, beta
header `mcp-client-2025-11-20`), which is not Claude Desktop but is the
same company's other documented approach to exposing MCP tool names to the
model. There, the tool name is emphatically **not** a concatenated
`mcp__<server>__<tool>` string. The documented response shape keeps the
bare tool name and the server name as two separate fields:

```json
{
  "type": "mcp_tool_use",
  "id": "mcptoolu_014Q35RayjACSWkSj4X2yov1",
  "name": "echo",
  "server_name": "example-mcp",
  "input": { "param1": "value1", "param2": "value2" }
}
```

This is the opposite naming strategy from Claude Code's documented
`mcp__local-notes__new_note`-style single concatenated identifier (per the
prior research doc's Question 1/3 findings, sourced from
https://code.claude.com/docs/en/mcp). It is direct evidence that Anthropic
does *not* apply one universal MCP-tool-naming convention across every
Claude surface -- Claude Code's concatenated-prefix approach is a
Claude-Code-specific choice, not something implied by the MCP spec or
required by Anthropic's API. It is not, however, direct proof of what
Claude Desktop specifically does internally (Desktop is closed-source and
the fetched support/docs pages don't describe its internal tool-list
construction), since Desktop's own MCP client could plausibly follow
either the Claude-Code-style concatenation or the API-connector-style
`name`+`server_name` split, or something else again.

**Finding, stated plainly:** No primary source found that documents
Claude Desktop's exact tool-name string shape for a custom-connector tool.
What *is* documented (a) rules out assuming Claude Code's
`mcp__local-notes__<tool>` shape carries over unchanged -- Desktop's own
technical-limits table shows it is a distinct client implementation with
different configuration surfaces -- and (b) shows that Anthropic's other
own MCP-exposure mechanism (the API MCP connector) uses a *split*
`name`/`server_name` shape rather than a concatenated prefix, which is at
minimum a existence proof that "same shape as Claude Code" is not a safe
default assumption. Anyone building Desktop-parity tooling for this repo
that depends on the literal tool-name string (e.g. an `allowed-tools`-style
glob) should verify the actual string empirically inside a live Desktop
session with the `mcp-remote`-bridged `local-notes` connector attached,
rather than assuming the Claude Code prefix format.

(Separately: no Anthropic primary source found mentions the `mcp-remote`
npm package at all -- it appears to be a community/third-party bridge this
repo's own README documents using, not something Anthropic's own docs
reference or endorse by name.)

---

## Question 3: Does the "code execution enabled" gate cost anything at invocation time for a skill that does no real code execution, or does it only gate upload/creation?

**Finding: it is not upload-only -- invoking *any* Skill mechanically requires at least one code-execution (bash) call, so the gate's cost model is live at invocation time too, even for a skill (like this repo's) whose only real work is calling MCP tools.**

This required stitching together two primary sources, since neither one
alone states the conclusion directly.

**First, how a Skill is actually read at invocation time.** Per
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
("The Skills architecture" / "How Claude accesses Skill content"): "Skills
run in a code execution environment where Claude has filesystem access,
bash commands, and code execution capabilities... When a Skill is
triggered, Claude uses bash to read SKILL.md from the filesystem, bringing
its instructions into the context window." This is unconditional -- there
is no documented "lightweight" path that loads SKILL.md's body without
going through the code-execution/bash mechanism. So even a skill whose
entire body is "call `list_topics`, then `new_note`" (i.e., zero actual
Python/Bash logic of its own) still causes at least one code-execution
tool call the moment it's triggered, purely to read its own instructions
off the filesystem.

**Second, what that code-execution call costs**, per
https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool
("Usage and pricing"): "Code execution is free when used with web search or
web fetch... When used without these tools, code execution is billed by
execution time, tracked separately from token usage: Execution time has a
minimum of 5 minutes; Each organization receives 1,550 free hours of usage
per month; Additional usage beyond 1,550 hours is billed at $0.05 USD per
hour, per container." Also relevant: "If files are included in the request,
execution time is billed even if the tool is not called, because files are
preloaded onto the container" -- i.e., the container-provisioning cost can
be incurred even without an explicit tool call, reinforcing that this is a
live-session cost, not a one-time setup cost.

Putting these together: the "code execution enabled" toggle is not simply
a permission check performed once at Skill-upload time. Every time a
Skill is *triggered* in a conversation, Claude's documented mechanism for
reading that Skill's own SKILL.md is itself a code-execution/bash call,
which is billed under the code-execution tool's execution-time model
(minimum 5-minute billing window per the pricing doc, subject to the
1,550-free-hours/month allowance) -- regardless of whether the skill's own
instructions subsequently do "real" code execution or, as in this repo's
case, just call out to MCP tools with no Python/Bash of their own.

**Caveat -- exact consumer-facing cost exposure not found.** The pricing
text above (`$0.05/hour per container`, `1,550 free hours/month`) is
documented under the Claude Platform/API billing model
(platform.claude.com), which is metered, developer-facing billing. Neither
that page nor
https://support.claude.com/en/articles/12512180-use-skills-in-claude
states how -- or whether -- this same per-hour metering is itemized,
capped, or simply absorbed into a flat claude.ai/Desktop subscription for
an end user on Free/Pro/Max/Team/Enterprise. So: **the mechanism cost is
confirmed and invocation-time (not upload-only) by primary source; the
exact dollar/latency exposure to a Desktop *subscription* user specifically
(as opposed to an API/platform customer) is not stated in any primary
source found, and I did not find one that answers that narrower point.**
That gap should be stated explicitly rather than assumed either way.

---

## Sources

- https://support.claude.com/en/articles/12512180-use-skills-in-claude
  (Skill upload mechanics, autonomous-invocation language, code-execution
  enablement requirement)
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
  (Agent Skills overview: progressive disclosure, cross-surface "Using
  Skills"/"Where Skills work" sections, Skills architecture / how SKILL.md
  is read via bash)
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool
  ("Usage and pricing" section: execution-time billing, free-hours
  allowance, per-container hourly rate)
- https://platform.claude.com/docs/en/agents-and-tools/mcp-connector
  (API MCP connector: `mcp_tool_use` response block shape with separate
  `name`/`server_name` fields -- the one concrete primary-source
  tool-naming data point found, for a non-Desktop surface)
- https://claude.com/docs/connectors/building (Building custom connectors:
  transport/auth support, and the Claude.ai/Desktop-vs-Claude-Code
  technical-limits table used as evidence the two clients are
  independently implemented)
- https://claude.com/docs/connectors/building/mcp (MCP conceptual overview
  -- checked, no naming-format detail)
- Checked and found no tool-naming or `mcp-remote` detail:
  https://support.claude.com/en/articles/11175166-getting-started-with-model-context-protocol-mcp-on-claude-desktop,
  https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities,
  https://support.claude.com/en/articles/14503689-mcp-connectors
- This repo: `README.md` ("Use it from Claude Desktop" section, documenting
  the `mcp-remote` stdio-bridge workaround), `.claude/skills/local-notes/
  SKILL.md`
- Prior research in this repo (Claude-Code-specific baseline this document
  extends): `docs/research/skill-and-mcp-server-integration.md`
