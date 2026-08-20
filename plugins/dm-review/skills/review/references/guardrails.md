# Review Guardrails

Rules for validating agent inputs, outputs, and failure states during the dm-review orchestration. Referenced by Phase 3.5 (input guardrails), Phase 4 (failure handling), and Phase 5 (output guardrails).

---

## Input Guardrails (Pre-Dispatch)

Apply these checks after agent selection (Phase 3) and before agent launch (Phase 4).

### Diff Size

**Threshold:** >5000 lines

**Action:** Truncate the diff. Pass each agent the file list plus the first 200 lines per file. Add a note to the agent prompt: "Diff truncated to 200 lines per file. Focus on the visible code; flag areas where truncation may hide issues."

### Content-Based Disclosure Filter

When an OpenRouter lane is dispatched, load
`${CLAUDE_SKILL_DIR}/references/disclosure-filter.md` and apply it to that
lane's outbound bytes. Codex lanes receive the complete review diff and do not
load it; path names alone never remove content from Codex review.

### Per-Agent Token Budget

Each agent runs in its own context. They don't share a budget.

**Estimate per agent:** (~2K system prompt) + (diff lines x ~4 tokens) + (~4K output headroom)

**Threshold:** If per-agent input exceeds ~80K tokens, start dropping the lowest-priority conditional agents to reduce wall-clock time and cost. Core agents are never dropped.

**Drop order** (first dropped -> last dropped):

1. visual-browser-tester (LOW -- has its own fallback chain, requires dev server)
2. voice-editor (LOW -- style, not correctness)
3. test-coverage-reviewer (LOW -- supplementary changed-path coverage)
4. openrouter-bulk-analyst (MEDIUM -- supplementary full-diff analysis, requires the OpenRouter provider plugin)
5. craft-reviewer (MEDIUM -- domain-specific)
6. governance-domain (MEDIUM -- domain-specific)
7. a11y-dynamic-content-reviewer (MEDIUM)
8. a11y-css-reviewer (MEDIUM)
9. css-reviewer (MEDIUM)
10. a11y-html-reviewer (HIGH -- legal compliance)
11. go-build-verifier (HIGH -- catches compilation failures)

Core criteria are never dropped. Required logical lanes are
security-auditor-codex-signoff; security-auditor-openrouter when selected;
architecture-reviewer; code-simplicity-reviewer;
pattern-recognition-specialist; and doc-sync-reviewer.

---

## Output Guardrails (Post-Return)

Apply these checks after all agents complete and before the consolidator merges findings (Phase 5).

### Structure Validation

**Check:** Agent output must contain at least one severity classification (P0/P1/P2/P3 or Critical/Serious/Moderate) OR an explicit no-findings indicator (Clean, No issues, Approved, No Issues Found).

Don't match exact header text -- agents use different formatting (`## Findings`, `### P0`, `### No Issues Found`, etc.). Look for the underlying signal.

**If neither found:** Mark `Malformed`; report a fixed content-safe reason, raw
evidence reference when available, incomplete coverage, and one next action.

### Max Findings Per Agent

**Threshold:** >25 findings from a single agent

**Action:** Limit the canonical finding count to the top 25 by severity (all
P1s first, then P2s, then P3s). Preserve the full raw output. Put every source
finding beyond the cap in `Synthesis Decisions` as
`discarded/agent-findings-cap` with its raw ref; do not silently erase it. Note
in the report: "Truncated from N to 25 findings (showing highest severity)."

### Ghost File Detection

**Check:** Each finding references a file path. That path must appear in the changed files list.

**Action:** Exclude findings referencing files not in the diff from canonical
counts, but keep each source position in `Synthesis Decisions` as
`discarded/out-of-scope` with evidence, rationale, and raw ref. Log: "Discarded
N findings referencing files not in changeset (hallucinated references)."

### Line Number Validation

**Check:** If a finding references a specific line number, that line should appear in the diff hunks for that file.

**Action:** If the line number doesn't appear in the diff hunks, add a warning to the finding: "Line N not in diff -- may be a context reference or hallucination." Don't discard -- context-line references are sometimes legitimate.

---

## Failure Guardrails

### Failure Policies

| Scenario | Policy |
|----------|--------|
| Agent timeout (>7500s) | Skip. Record "Timed out" in Agent Summary. No retry. The 7500s threshold provides a five-minute buffer above the largest 7200s routed-agent ceiling in dm-review Phase 3.75. If that ceiling changes, this guardrail must change in lockstep or it will silently preempt a valid long-running lane. |
| Agent returns empty | Mark `Partial` with fixed reason `empty response`; required coverage remains incomplete. |
| Agent returns error | Mark `Failed` with a fixed, content-safe reason. Don't retry. |
| Agent output contains `### RUNNER FAILURE` | External-LLM-routed runner failed. See Phase 4.5 for fallback procedure. If fallback also fails, apply core/conditional failure policies (REVIEW INCOMPLETE for core agents, degraded for conditional). Extract failure reasons from both runs for the Agent Summary. |
| All conditional agents fail | Review proceeds with core agents only. Note "Degraded: conditional agents unavailable" in report header. |
| Core agent fails | Flag: "REVIEW INCOMPLETE -- [agent-name] failed." Change merge recommendation accordingly. |
| Consolidator fails | Report the exact total and a bounded list of actionable unmerged findings with evidence pointers; do not dump raw output. |

### Core vs Conditional Failure Impact

**Core agent failure = review compromised.** The merge recommendation changes to "REVIEW INCOMPLETE" with the failed agent named. The review still produces findings from agents that succeeded, but the user must know coverage is incomplete.

**Conditional agent failure = degraded but valid.** The review proceeds. The Agent Summary table shows which agents were skipped and why.

For every malformed, failed, partial, timed-out, missing, or unavailable lane,
report lane/reviewer, status, fixed content-safe reason, raw reference when one
exists, incomplete coverage, and one next action. Another clean lane never
makes required coverage clean.

See `${CLAUDE_SKILL_DIR}/references/graceful-degradation.md` for the full decision table.

---

## Deduplication Precision Rules

`agents/workflow/review-consolidator.md` Steps 2 and 2.5 are the single
authoritative owner of canonical identity, grouping, cross-ID dispute links,
`agreement`, `finding_disposition`, the closed reason-code vocabulary, and
evidence priority. Do not restate them here. This file owns only the guardrail
that rejects a consolidation which violates them.

**Rejection guardrail.** Reject missing, duplicate, or free-form reason codes; empty or duplicate source IDs; missing source severities; agreement/source-count mismatches; one-way, self-referential, malformed, or missing cross-ID dispute links; flattened contradictions; severity-derived IDs; missing raw refs; and reports missing the `Synthesis Decisions` section.

Raw outputs are immutable: reference them, never rewrite or delete them. A
consolidated summary cannot substitute for absent raw evidence.
