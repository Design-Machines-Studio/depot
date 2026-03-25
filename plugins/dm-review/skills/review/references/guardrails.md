# Review Guardrails

Rules for validating agent inputs, outputs, and failure states during the dm-review orchestration. Referenced by Phase 3.5 (input guardrails), Phase 4 (failure handling), and Phase 5 (output guardrails).

---

## Input Guardrails (Pre-Dispatch)

Apply these checks after agent selection (Phase 3) and before agent launch (Phase 4).

### Diff Size

**Threshold:** >5000 lines

**Action:** Truncate the diff. Pass each agent the file list plus the first 200 lines per file. Add a note to the agent prompt: "Diff truncated to 200 lines per file. Focus on the visible code; flag areas where truncation may hide issues."

### Sensitive File Filter

**Pattern:** `.env`, `*credentials*`, `*secret*`, `*.key`, `*.pem`

**Action:** Strip matching files from the diff before dispatching to all agents EXCEPT security-auditor. The security-auditor receives the full diff -- its job is to catch committed secrets. All other agents get the stripped version.

Log exclusions:
```
Stripped 2 sensitive files from non-security agents: .env, config/secrets.yml
```

### Per-Agent Token Budget

Each agent runs in its own context. They don't share a budget.

**Estimate per agent:** (~2K system prompt) + (diff lines x ~4 tokens) + (~4K output headroom)

**Threshold:** If per-agent input exceeds ~80K tokens, start dropping the lowest-priority conditional agents to reduce wall-clock time and cost. Core agents are never dropped.

**Drop order** (first dropped → last dropped):

1. visual-browser-tester (LOW -- has its own fallback chain, requires dev server)
2. voice-editor (LOW -- style, not correctness)
3. test-coverage-reviewer (LOW -- advisory only)
4. craft-reviewer (MEDIUM -- domain-specific)
5. governance-domain (MEDIUM -- domain-specific)
6. a11y-dynamic-content-reviewer (MEDIUM)
7. a11y-css-reviewer (MEDIUM)
8. css-reviewer (MEDIUM)
9. a11y-html-reviewer (HIGH -- legal compliance)
10. go-build-verifier (HIGH -- catches compilation failures)

Core agents (NEVER dropped): security-auditor, architecture-reviewer, code-simplicity-reviewer, pattern-recognition-specialist, doc-sync-reviewer.

---

## Output Guardrails (Post-Return)

Apply these checks after all agents complete and before the consolidator merges findings (Phase 5).

### Structure Validation

**Check:** Agent output must contain at least one severity classification (P0/P1/P2/P3 or Critical/Serious/Moderate) OR an explicit no-findings indicator (Clean, No issues, Approved, No Issues Found).

Don't match exact header text -- agents use different formatting (`## Findings`, `### P0`, `### No Issues Found`, etc.). Look for the underlying signal.

**If neither found:** Flag as "malformed output" in the Agent Summary table. Include the raw output in a collapsible detail section so nothing is lost.

### Max Findings Per Agent

**Threshold:** >25 findings from a single agent

**Action:** Truncate to top 25 by severity (all P1s first, then P2s, then P3s). Note in the report: "Truncated from N to 25 findings (showing highest severity)."

### Ghost File Detection

**Check:** Each finding references a file path. That path must appear in the changed files list.

**Action:** Discard findings referencing files not in the diff. Log: "Discarded N findings referencing files not in changeset (hallucinated references)."

### Line Number Validation

**Check:** If a finding references a specific line number, that line should appear in the diff hunks for that file.

**Action:** If the line number doesn't appear in the diff hunks, add a warning to the finding: "Line N not in diff -- may be a context reference or hallucination." Don't discard -- context-line references are sometimes legitimate.

---

## Failure Guardrails

### Failure Policies

| Scenario | Policy |
|----------|--------|
| Agent timeout (>120s) | Skip. Record "Timed out" in Agent Summary. No retry. |
| Agent returns empty | Treat as "Clean (empty response)" in Agent Summary. |
| Agent returns error | Record error message in Agent Summary. Don't retry. |
| All conditional agents fail | Review proceeds with core agents only. Note "Degraded: conditional agents unavailable" in report header. |
| Core agent fails | Flag: "REVIEW INCOMPLETE -- [agent-name] failed." Change merge recommendation accordingly. |
| Consolidator fails | Output raw agent findings as unmerged list. Prefix: "Consolidation failed -- raw findings below." |

### Core vs Conditional Failure Impact

**Core agent failure = review compromised.** The merge recommendation changes to "REVIEW INCOMPLETE" with the failed agent named. The review still produces findings from agents that succeeded, but the user must know coverage is incomplete.

**Conditional agent failure = degraded but valid.** The review proceeds. The Agent Summary table shows which agents were skipped and why.

See `${CLAUDE_SKILL_DIR}/references/graceful-degradation.md` for the full decision table.

---

## Deduplication Precision Rules

Used by the consolidator (Phase 5) when merging findings from multiple agents.

### Same file + same line (exact match)
Merge into one finding. Keep the higher severity. List all source agents.

### Same file + adjacent lines (within 3 lines)
Merge if descriptions reference the same logical issue. Consolidator judges based on description similarity. If in doubt, keep separate.

### Same file + different lines
Keep as separate findings, even if descriptions are similar. Different locations = different findings.

### Different files, same issue pattern
Keep both. Note the pattern: "This issue appears in N files."

### Same finding, different severity
Two agents flag the same issue on the same line at different severities. Escalate to the higher severity. Note the disagreement: "security-auditor: P1, code-simplicity-reviewer: P3 -- escalated to P1." Severity disagreements signal that human judgment is needed.

### Contradicting findings
Keep both with a note: "Agents disagree -- manual review recommended."
