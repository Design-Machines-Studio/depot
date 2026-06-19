# Skill Authoring: Two-Axis Testing, SDO, and the Compounding Disciplines

How depot authors and hardens skills. Adapted from Superpowers (obra) `writing-skills` and the
Compound Engineering (Klaassen/Every) codify loop, tuned to depot's `eval-descriptions.sh` tooling
and the installed `superpowers` plugin.

Two failure modes hit every skill, and they need different tests:

1. **It never fires** when it should (a *trigger* failure).
2. **It fires but the agent ignores or shortcuts it** under pressure (a *compliance* failure).

Depot has historically tested only #1. This doc adds #2 and reconciles the two where they conflict.

---

## Axis 1 -- Trigger accuracy

Does the `description:` field carry enough vocabulary that real user queries activate the skill?

- Tool: `./tools/eval-descriptions.sh <plugin>-<skill>.json` (every skill has an eval file in
  `description-evals/`). Threshold: **>= 70%**.
- Trigger vocabulary = the symptoms, contexts, nouns, error strings, and tool names a user would type.
  Keep these rich. This is why depot descriptions list synonyms and phrasings.
- When you edit a `description:`, re-run that skill's eval before committing.

## Axis 2 -- Compliance robustness

Does the agent actually *follow* the skill once it fires, even when time pressure, sunk cost, or a
plausible shortcut argue against it?

This axis matters for **discipline skills** -- the ones that enforce behavior rather than supply
reference knowledge:

- pipeline gates (assess/research/plan/review GATEs, the self-audit)
- zero-deferral and severity policy (`dm-review`)
- the codify loop (`ned:codify`)
- council compliance (BC Act thresholds, decolonial language rules)
- any "always / never / must" rule

For these, run the **`superpowers:writing-skills`** RED-GREEN-REFACTOR loop before shipping:

1. **RED** -- run the target scenario *without* the rule, applying realistic pressure (time urgency,
   sunk cost, an authority telling the agent to skip it). Record verbatim the rationalizations the
   agent uses to justify skipping.
2. **GREEN** -- write the minimal rule that closes exactly those rationalizations. Not a general
   lecture -- the specific counter.
3. **REFACTOR** -- re-test under the same pressure. New rationalizations will surface; add explicit
   counters (a rationalization table, a red-flags list). Repeat until the agent complies.

Superpowers' own finding: persuasion pressure defeats un-tested rules. A guardrail you have not
pressure-tested is a guess, not a guarantee. This applies equally to **new guardrails added to close a
postmortem failure mode** -- when the codify loop (`ned:codify`, pipeline Step 5.2) proposes a new
"Known Pipeline Failure Modes" entry or gate, pressure-test its wording before treating it as solved.

Compliance testing is not automated in depot tooling -- it is a manual loop run via the installed
`superpowers` plugin. Reserve it for discipline skills; reference/knowledge skills do not need it.

---

## SDO -- Skill Description Optimization

The two axes can pull in opposite directions, and SDO is how depot resolves it.

**The trap:** if a `description:` summarizes the skill's *workflow*, the agent may follow the summary
instead of reading the full skill -- doing one review step where the skill specifies two, skipping the
gate the body enforces. Superpowers documents this directly.

**The tension with Axis 1:** depot deliberately loads descriptions with vocabulary for eval scores.
That is correct -- but vocabulary is not the same as workflow steps.

**The rule:** a description may carry trigger vocabulary (symptoms, contexts, nouns, tool names) but
must **not** contain actionable workflow steps.

- State *when to use* the skill. Never *how it works*.
- Good (triggers only): `Use when executing an implementation plan with independent tasks in the
  current session.`
- Bad (summarizes workflow -- agent may shortcut it): `Use when executing plans -- dispatches a
  subagent per task with code review between each task.` The agent reads "a review" and does one
  review instead of the skill's two-stage gate.

**Where this bites hardest:** *process / discipline* skills, where shortcutting the real workflow
causes harm. Audit these descriptions for imperative step-sequences and strip them, keeping the
trigger vocabulary:

- `pipeline`, `promptcraft`, `assess` (pipeline plugin)
- `review` (dm-review)
- `codify` (ned)

**Where it does not matter:** *domain-knowledge* skills (livewires, governance, typography, layout,
design-machines, strategy). These are reference, not enforced process -- an agent "following the
description" is harmless because there is no workflow to shortcut. Leave their vocabulary-rich
descriptions alone; they earn their eval scores honestly.

After any SDO edit, re-run `./tools/eval-descriptions.sh` for that skill to confirm trigger accuracy
still clears 70%. Stripping *workflow steps* should not drop *trigger vocabulary* -- if the score
falls, you removed a noun you needed, not a workflow step.

---

## The compounding disciplines (use the installed Superpowers skills)

Three cross-cutting disciplines are enforced inside the pipeline today but apply to **all** depot
work. Rather than reimplement them, invoke the installed `superpowers` versions:

- **`superpowers:systematic-debugging`** -- before any fix. Root cause before patch; after 3 failed
  fixes, stop and question the architecture instead of trying a 4th. Invoke for any debugging or
  fix-pass work, not just pipeline runs (`dm-review:dm-review-fix`, `pipeline:pipeline-fix`).
- **`superpowers:verification-before-completion`** -- before any "done" / "fixed" / "passing" claim.
  Run the verifying command fresh, read the output, then claim. Evidence over assertion. The
  pipeline's native evidence protocol (visual-parity diff, screenshots, `browser_evaluate`,
  computed-style comparison) is the *depot-specific specialization* of this discipline for UI work --
  richer, not competing.
- **`superpowers:writing-skills`** -- when authoring or hardening a discipline skill (Axis 2 above).

These compose with depot's stricter, stack-specific protocols; they do not replace them.

---

## Checklist for a new or edited skill

- [ ] `description:` states triggers, not workflow steps (SDO).
- [ ] `name:` matches the skill folder exactly.
- [ ] Trigger eval exists in `description-evals/` and clears 70% (`eval-descriptions.sh`).
- [ ] If it is a discipline skill: pressure-tested for compliance via `superpowers:writing-skills`.
- [ ] Capabilities added to `plugin.json` (and `.codex-plugin/plugin.json` where mirrored).
- [ ] Version bumped in `plugin.json` **and** `marketplace.json`.
- [ ] Search index regenerated (`./tools/validate-composition.sh --generate-index`).
- [ ] `.githooks/pre-commit` SKILL.md corruption check passes.
