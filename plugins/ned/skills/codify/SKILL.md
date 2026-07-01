---
name: codify
description: Use at the end of a pipeline run, code review, debugging session, or any substantial work session to turn what was learned into permanent improvements. Trigger when Travis says "codify", "compound", "capture the lessons", "what should we learn from this", "turn this into a rule", "make sure this never happens again", after a postmortem, when a mistake or review finding recurs, or when a one-off fix should become a standing guardrail instead of being forgotten. Also offer proactively when a session surfaced a repeatable mistake, a new failure mode, or a correction that future runs should inherit.
allowed-tools:
  - mcp__ai-memory__search_entities
  - mcp__ai-memory__get_entity
  - mcp__ai-memory__add_observation
  - mcp__ai-memory__add_entity
  - mcp__ai-memory__save
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# Codify

Turn a finished work session into permanent, encoded improvements so the next run inherits the
lesson instead of relearning it. This is the **compounding step**: every run should leave the system
a little better than it found it.

`recorder` captures *what happened* (decisions, todos, facts). `codify` captures *what to change* so
it doesn't happen again -- rules, tests, guardrails, defaults. Use `recorder` to remember a session;
use `codify` to make the system smarter because of it.

## When to run

- After a pipeline run, dm-review, debugging session, or any task where something was harder than it
  should have been.
- When a mistake or review finding shows up that you have seen before.
- After a postmortem -- to make sure its lessons land as enforceable changes, not just prose.
- Whenever Travis says "codify", "compound", "make this a rule", or "never again".

A session where nothing was confusing and nothing recurred does **not** need codify. Say so and stop.
Do not invent lessons to fill the checklist.

## The 5-Minute Codify Checklist

Review the session (or the named run) and answer four questions. Be concrete -- vague answers produce
useless encodings.

1. **What confused us, broke, or surprised us?** The friction. A wrong turn, a silent failure, a
   review finding, an ambiguous prompt, a tool that behaved unexpectedly. State the specific event,
   not a category.
2. **What instruction prevents recurrence?** The rule that, had it existed, would have avoided #1.
   Phrase it as a directive an agent would follow.
3. **What automated check catches it earlier?** A test, a lint rule, a grep guard, a hook, a
   pre-flight check. Automation beats instruction -- prefer it when one exists.
4. **What pattern becomes a new default?** If the right approach should be the standing default going
   forward, name the default and where it lives.

## Classify each lesson by encoding target

Every lesson maps to exactly one durable home. Route it there.

| Lesson type | Encoding target | Applied how |
|---|---|---|
| Situational / project fact, one-off context | ai-memory observation | **Auto-write** (see below) |
| Pipeline failure pattern (novel) | `CLAUDE.md` "Known Pipeline Failure Modes" + `docs/post-mortems/` stub | **Propose** -- draft, human approves |
| Process / discipline fix | the relevant `SKILL.md` rule or agent instruction | **Propose** -- draft the edit, human approves |
| Mechanical / recurring defect | new guardrail, Live Wires lint rule, or anti-pattern scan entry | **Propose** -- draft, human approves |

**Auto-write vs propose:** durable *situational* lessons go straight to ai-memory (low risk, additive).
Everything that edits `CLAUDE.md`, a `SKILL.md`, an agent file, or a guardrail is **proposed, not
applied** -- present it as an approval checklist and apply with Edit only after Travis approves.

### Recurrence check (do this before classifying)

A lesson is far more valuable if it has happened before. Check:

- ai-memory: `search_entities` for the project entity and for `DepotPlugin:pipeline`; read recent
  observations (`[YYYY-MM-DD] Code review:` / `Pipeline:` / `Architecture:` lines) for the same theme.
- `docs/post-mortems/` and `CLAUDE.md` "Known Pipeline Failure Modes": grep for the pattern.

If the pattern already has a home, **strengthen the existing entry** (sharpen the rule, add the
automated check it was missing) rather than adding a duplicate. If it is genuinely novel, it earns a
new entry.

## Writing the durable observation

For situational lessons, write to ai-memory via the `ai-memory` skill's tools (auto-saves):

- Project-specific lesson -> observation on the project entity.
- Pipeline/review process lesson -> observation on `DepotPlugin:pipeline` (create if missing,
  type: Tool).
- Format: `[YYYY-MM-DD] Lesson: <what broke> -> <the rule/check that prevents it>. Encoded in: <target or "proposed">.`
- Keep under 300 characters. One observation per distinct lesson. Check the entity first to avoid
  duplicates.

Example:
```
[2026-06-19] Lesson: new JS module shipped but 404'd at runtime (dev module map not updated) -> verify module attaches via browser_evaluate before claiming done. Encoded in: execution-orchestrator Step 0c.
```

## Output: the Codify Report

Present a single terse report. No preamble.

```markdown
# Codify Report: <session or run-slug>

## Friction
- <the specific thing that broke/confused/recurred>

## Lessons -> Encodings
| # | Lesson | Target | Status | Recurrence |
|---|--------|--------|--------|------------|
| 1 | <rule> | ai-memory: <entity> | written | first seen |
| 2 | <rule> | CLAUDE.md Known Failure Mode #N | PROPOSED | seen 3x |
| 3 | <rule> | dm-review severity-mapping.md | PROPOSED | seen 2x |

## Proposed encodings (await approval)
### #2 -> CLAUDE.md Known Pipeline Failure Modes
<exact text to add>

### #3 -> <file>
<exact edit>

## Auto-written
- <N> ai-memory observations on <entities>
```

After presenting, apply approved proposals with Edit/Write. Leave un-approved ones as the report
record. Do not apply edits Travis has not approved.

## Pressure-test new guardrails

When a proposal is a new *rule* meant to enforce behavior under pressure (a pipeline gate, a
zero-deferral clause, a discipline directive), the wording itself can be ignored or rationalized
away. Before treating it as done, pressure-test it via the **`superpowers:writing-skills`**
RED-GREEN-REFACTOR loop -- establish the rationalizations an agent uses without the rule, then confirm
the rule's wording actually closes them. See `docs/skill-authoring.md` for the two-axis testing model.
A guardrail that has not been pressure-tested is a guess, not a guarantee.

## Rules

1. No invented lessons. If the session was clean, report "Nothing to codify" and stop.
2. Auto-write only situational ai-memory observations. Everything that edits a tracked doc, skill,
   agent, or guardrail is proposed and human-gated.
3. Always run the recurrence check before classifying -- strengthen existing entries over duplicating.
4. Prefer an automated check (#3) over an instruction (#2) when both would work.
5. Keep observations under 300 characters, ISO dates, one lesson each.
6. If ai-memory is unavailable, skip the auto-write, still produce the report, and note the skip.
