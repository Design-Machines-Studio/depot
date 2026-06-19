---
name: compound
description: Turn a finished work session into permanent encoded improvements (rules, tests, guardrails, defaults)
argument-hint: "[run-slug]"
---

# Compound

Run the codify loop over the current session, or over a named pipeline/review run if a slug is given.
This is the standalone entry point to depot's compounding step (the analogue of Compound Engineering's
`/ce-compound`).

## Process

1. **Scope.** If `$ARGUMENTS` names a run-slug, target that run's artifacts (`plans/<slug>/`,
   `final-requirements-crosscheck.md`, receipt, review todos). Otherwise target the current
   conversation/session.

2. **Load the codify skill.** Invoke the `ned:codify` skill and follow it exactly -- the 5-Minute
   Codify Checklist, the recurrence check, lesson classification, the auto-write vs propose split, and
   the Codify Report format all live there.

3. **Deliver.** Present the Codify Report. Auto-write situational ai-memory observations; present every
   doc/skill/guardrail change as an approval checklist. Apply approved proposals with Edit only after
   Travis approves.

If the session surfaced no friction and nothing recurred, report "Nothing to codify" and stop. Do not
manufacture lessons.
