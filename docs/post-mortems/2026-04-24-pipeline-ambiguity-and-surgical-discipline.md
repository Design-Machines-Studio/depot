# Post-Mortem: Silent Mid-Execution Ambiguity and Drive-By Refactors (Pipeline v1.10.0)

**Date:** 2026-04-24
**Project:** depot (pipeline + scaffolder plugin work)
**Pipeline mode:** N/A (this post-mortem covers harness changes themselves)
**Model:** Opus 4.7 (1M context)
**Outcome:** Two implicit failure modes in pipeline v1.9.0 surfaced during a third-party skills review (forrestchang/andrej-karpathy-skills). Pipeline v1.10.0 added three-layer ambiguity defence and in-file surgical-change discipline. No production incident; analysis-driven hardening.

## What Happened

The user asked whether anything in Andrej Karpathy's published LLM-coding pitfalls (via the forrestchang skills repo) could improve our pipeline. The analysis surfaced two blind spots our existing methodology didn't cover:

1. **Mid-execution ambiguity.** The pipeline's `superpowers:brainstorming` skill catches pre-plan design ambiguity, and `plan-adversary.md` catches structural ambiguity at prompt-review time. But between those two gates and the orchestrator's merge, **subagents routinely encounter chunk prompts that admit multiple reasonable interpretations** (e.g., "make the members page faster" → server-side query vs progressive rendering vs bundle-size reduction) and silently pick one. The chosen interpretation is invisible in diffs and commit messages; the orchestrator's per-chunk review validates the code, not the decision. Rework surfaces later when the user notices the chosen path wasn't the intended one.

2. **Drive-by in-file refactors.** The `prompt-template.md` Constraints block said "Only modify the files listed above" (file-scope discipline) and "Do not refactor surrounding code unless required" (general directive). Neither covered **in-file scope**: a subagent editing `validator.go` for a bug fix could still tidy adjacent functions, reformat imports, tighten unrelated type annotations, and rewrite docstrings — all within the listed file. Every Karpathy example 1 ("fix empty-email crash" → LLM rewrites email regex, adds username rules, reformats docstrings) is this class of failure.

Both are failure modes documented in Karpathy's public observations. Neither had explicit hardening in our harness.

## Root Cause Analysis

### 1. Mid-Execution Ambiguity

**What happened:** No protocol existed for a subagent to surface a forced interpretation choice. The only guidance was "don't over-engineer" and "follow the Fix Philosophy" — neither of which address *undecidable-at-author-time* prompts. Under auto-mode / autonomous-mode execution the subagent cannot ask the user, so the only safe path (pick and state why) was unspecified, leaving subagents to invent ad-hoc wording or skip the signal entirely.

**Why the existing gates didn't catch it:** Brainstorming runs before planning when the user is still shaping intent; it cannot pre-resolve prompts that were authored after it ran. Plan-adversary runs after promptcraft but its perspectives were Feasibility / Completeness / DM Standards / Visual Verification — none focused on prompt-language ambiguity specifically.

**Fix (v1.10.0):** Three-layer defence, cheapest catch first:
- `plan-adversary.md` — added `Ambiguity surfacing` perspective in Sprint Contract Negotiation. Inspects prompt phrases for comparative adjectives without baselines, unqualified verbs ("improve/fix/clean up"), and noun phrases like "the right way" / "better UX". Emits `INSERT` findings that force the promptcraft to name interpretations explicitly. **Cheapest catch: prompt-review time, pre-execution.**
- `promptcraft/references/prompt-template.md` — added `Ambiguity Protocol` block that ships into every chunk prompt. Three rules: name the interpretations, choose with rationale, record in commit trailers. Always present; invariant per Guidance item 9.
- `execution-orchestrator.md` — added `Ambiguity Handling (autonomous mode)` section in the subagent dispatch template. Runtime safety net: two-trailer format (`Chose: <path>` + `Rejected: <alt-1>; <alt-2>`) parseable by `git interpret-trailers --parse`; receipt flag `ambiguity_resolved: true` with summary; fabricating certainty classified P1. **Last-resort catch: subagent runtime.**

All three layers explicitly cross-reference each other to prevent wording drift.

### 2. Drive-By In-File Refactors

**What happened:** No guardrail forbade in-file line-scope expansion. The subagent dispatch template carried the Fix Philosophy (right approach, replace don't preserve), which *encourages* refactoring — and without an explicit in-file scope limit, Fix Philosophy spills over into adjacent untouched code. The resulting diffs mix the authored change with drive-by edits, making review harder, multiplying merge-conflict surface, and introducing regressions in code that wasn't supposed to change.

**Why existing controls didn't catch it:** File-scope discipline in `prompt-template.md` Constraints covered cross-file leakage. The `code-simplicity-reviewer` and `pattern-recognition-specialist` agents flag unnecessary complexity but don't measure "lines changed vs lines needed for acceptance criteria." No agent had a mandate to flag drive-by churn.

**Fix (v1.10.0):** Extended Constraints block in `prompt-template.md` with two lines that ship into every chunk prompt:
- "Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as 'Noted, not fixed.'"
- "Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk."

Added matching `Surgical Change Discipline` section in `execution-orchestrator.md` dispatch template so the subagent sees the discipline twice (template + system prompt).

## Changes Shipped

- `plugins/pipeline/.claude-plugin/plugin.json` 1.9.0 → 1.10.0 (synced in `.claude-plugin/marketplace.json`)
- `plugins/pipeline/skills/promptcraft/references/prompt-template.md` — new Ambiguity Protocol block + two Constraints bullets + invariance note (Guidance item 9)
- `plugins/pipeline/agents/workflow/execution-orchestrator.md` — new Ambiguity Handling + Surgical Change Discipline sections in dispatch template
- `plugins/pipeline/agents/workflow/plan-adversary.md` — new Ambiguity surfacing perspective in Sprint Contract Negotiation + principle paragraph
- `plugins/pipeline/commands/pipeline.md` — new Ambiguity Protocol Check subsection in Phase 7 (trailer parsing + receipt flag extraction + caller review)
- `CLAUDE.md` — added item 14 to Known Pipeline Failure Modes

Cross-references added between all three ambiguity-protocol locations to prevent drift.

## Adoption Validation

The v1.10.0 changes themselves were reviewed by `/dm-review-quick` during their implementation session. Zero P1/P2 findings against the core additions; only minor P3 naming polish. A follow-on full `/dm-review` surfaced tooling-corruption P1s in unrelated files (ghostwriter + design-machines) plus cross-reference P2s which were then fixed in `/dm-review-fix`.

**Open validation:** No pipeline run has yet exercised the Ambiguity Protocol on a deliberately ambiguous feature description (e.g., "make the members page faster"). Next opportunity: the first UI-facing feature executed under v1.10.0 will confirm whether subagents actually emit the Chose/Rejected trailers and whether the orchestrator surfaces them in Phase 7 delivery.

## Prevention Going Forward

1. **Karpathy-style LLM failure catalogue as design input.** The Karpathy observations surfaced blind spots we couldn't see from our own practice. Worth periodically cross-referencing published LLM-coding failure modes against our harness.
2. **Layered defence over single-gate checks.** Both fixes deliberately have three layers (plan-adversary → prompt-template → orchestrator) or two (prompt-template + orchestrator system prompt) because silent-pass behaviour is hardest to detect in a single gate.
3. **Cross-reference invariants.** When the same rule needs to appear in multiple files, add explicit cross-references naming the sibling locations. Drift between copies is the second-most-likely failure mode after the original.

## Related Postmortems

- `docs/post-mortems/2026-04-07-pipeline-ui-refinement-postmortem.md` — 6 failure modes from Assembly UI refinement (P3 deferral, visual verification gaps, evidence-free assertions)
- `docs/post-mortems/2026-04-10-pipeline-visual-testing-postmortem.md` — 7 failure modes from Assembly pipeline bypass and curl-fallback silent merges

## References

- Karpathy's observations: https://x.com/karpathy/status/2015883857489522876
- Upstream skills repo: https://github.com/forrestchang/andrej-karpathy-skills
- Internal analysis plan: `/Users/trav/.claude/plans/here-is-there-anything-humming-stonebraker.md`
