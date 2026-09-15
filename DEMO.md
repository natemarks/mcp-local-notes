# Demo: a throwaway notes corpus you can safely experiment in

`make demo` gives you a brand-new, empty notes corpus in a temp directory
(no relation to this repo's own `notes/`) and runs the MCP server against
it on the usual port. Every prompt below is meant to be pasted, as-is,
into an AI assistant (Claude Desktop or Claude Code) that already has
this project's server registered under the `local-notes` key -- see
the main [README](README.md#use-it-from-claude-desktop) if you haven't
done that yet.

## Start the demo

```sh
make demo
```

This:

1. Checks that `MCP_PORT` (`8000` by default) isn't already in use --
   stop any other running server first (`make stop`, or whatever else
   is bound to that port) if it complains.
2. Creates a fresh temp directory (`mktemp -d`) and seeds it with this
   project's bootstrap `tbox.ttl`/`abox.ttl` -- the same starting
   ontology a fresh clone ships with: the `:Note` root plus the four
   Divio documentation types pre-declared (below), no topics yet.
3. Runs `mcp-local-notes-server` in the foreground, `NOTES_DIR` pointed
   at that temp directory. Because it's the same host/port your
   `local-notes` registration already points at, your assistant
   starts talking to this empty demo corpus immediately -- nothing to
   re-register.

Leave this running in its own terminal for the rest of the demo. Press
`Ctrl+C` when you're done; the temp directory is left in place (the
path is printed both at startup and again on exit) so you can look at
what got created -- `rm -rf` it whenever you're ready to throw it away.

## Phase 1: the four Divio documentation types

The [Divio documentation system](https://docs.divio.com/documentation-system/introduction/)
identifies four document purposes -- tutorial, how-to, reference,
explanation -- that should stay distinct rather than blended together.
They map onto this project's single-valued `type` field, and this
project's bootstrap `tbox.ttl` ships with all four already declared
(`Tutorial`, `How-to`, `Reference`, `Explanation`), so there's no
`add_class` step here -- just create one note of each type, all about
beginner lacrosse coaching.

This is exactly what the [`local-notes` skill](README.md#claude-skill)
is for: paste the prompts below to an assistant that has it installed
(`make deploy-skill`, or it's already available from this repo's own
`.claude/skills/`) and it checks `list_types`/`list_topics` itself
before creating anything -- seeing `Tutorial` already exists, it uses
it directly rather than asking you to add it first.

```
Create a note titled "Running Your First Beginner Practice", type
Tutorial, tagged lacrosse-coaching (approve the topic), covering the
practice in order: cradling warm-up, wall ball pairs, then a ground-ball
scramble.
```

```
Create a note titled "How to Run a Ground Ball Drill", type How-to,
tagged lacrosse-coaching, with the steps for a two-line
grounder-and-scoop drill and a common coaching cue for body position.
```

```
Create a note titled "Youth Lacrosse Positions and Field Terminology",
type Reference, tagged lacrosse-coaching, listing attack/midfield/
defense/goalie roles and basic field zones.
```

```
Create a note titled "Why Wall Ball Is the Foundation of Stick Skills",
type Explanation, tagged lacrosse-coaching, discussing why repetition
against a wall builds the muscle memory later drills depend on.
```

You should now have 4 notes, all tagged `lacrosse-coaching`, one of each
type.

## Phase 2: 10 more documents, across 3 topics

Same idea, spread across three topics -- `bash-scripting` and
`linux-backup-recovery` are brand new; `lacrosse-coaching` picks up
where phase 1 left off (reusing the same four types, since a topic can
have as many notes of a given type as you like).

**bash-scripting** (all 4 types):

```
Create a note titled "Writing Your First Bash Script", type Tutorial,
tagged bash-scripting (approve the topic), walking through the shebang
line, declaring a variable, and running the script with bash.
```

```
Create a note titled "How to Loop Over Files in a Directory", type
How-to, tagged bash-scripting, with a for-loop over a glob pattern and
a note about quoting the loop variable.
```

```
Create a note titled "Bash Comparison and Test Operators", type
Reference, tagged bash-scripting, listing the common test operators:
-eq, -lt, -f, -d, and string equality.
```

```
Create a note titled "Why You Should Always Quote Your Bash Variables",
type Explanation, tagged bash-scripting, discussing word splitting and
globbing as the reason unquoted variables misbehave.
```

**linux-backup-recovery** (3 of the 4 types):

```
Create a note titled "Backing Up Your Home Directory for the First
Time", type Tutorial, tagged linux-backup-recovery (approve the topic),
walking through a first tar -czvf backup of a home directory.
```

```
Create a note titled "How to Restore Files from a Tar Backup", type
How-to, tagged linux-backup-recovery, with the steps to extract just a
few specific files from a tar archive without overwriting everything
else.
```

```
Create a note titled "rsync and tar Flags Cheat Sheet", type Reference,
tagged linux-backup-recovery, listing rsync's -a/-v/-z/--delete and
tar's -czvf/-xzvf flags.
```

**lacrosse-coaching** (3 more notes, rounding out the topic):

```
Create a note titled "How to Teach Cradling to Total Beginners", type
How-to, tagged lacrosse-coaching, describing the fingertip-to-elbow
motion progression coaches use to introduce cradling.
```

```
Create a note titled "Common Lacrosse Penalties and Fouls", type
Reference, tagged lacrosse-coaching, listing common youth-level fouls
like illegal body checks and slashing.
```

```
Create a note titled "Why Youth Coaches Rotate Players Through Every
Position", type Explanation, tagged lacrosse-coaching, discussing the
player-development case for rotating position assignments at the
youth level.
```

You should now have 14 notes: 7 tagged `lacrosse-coaching`, 4 tagged
`bash-scripting`, 3 tagged `linux-backup-recovery`.

## Phase 3: see what you built

```
What topics are in my local-notes vocabulary?
```

```
Show me every note tagged bash-scripting.
```

```
Show me every note tagged lacrosse-coaching.
```

```
Show me every note tagged linux-backup-recovery.
```

```
Validate my local-notes corpus.
```

The topic counts should come back as 4 / 7 / 3, and validation should
report no issues -- every note's tags and type are declared vocabulary,
every reference resolves, and the ABox matches every note's frontmatter.

## Cleaning up

Press `Ctrl+C` in the terminal running `make demo`. It prints the temp
directory's path again on exit, along with an `rm -rf` command for that
exact path -- copy that line to remove it (it's a fresh `mktemp -d` path
each run, so there's no fixed one to write here).

Nothing here touches this repo's own `notes/` directory or its git
history -- the whole point of `make demo` is that it's disposable.
