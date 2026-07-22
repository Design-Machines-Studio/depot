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

**Drop order** (first dropped -> last dropped):

1. visual-browser-tester (LOW -- has its own fallback chain, requires dev server)
2. voice-editor (LOW -- style, not correctness)
3. test-coverage-reviewer (LOW -- advisory only)
4. openrouter-bulk-analyst (MEDIUM -- supplementary full-diff analysis, requires the OpenRouter provider plugin)
5. craft-reviewer (MEDIUM -- domain-specific)
6. governance-domain (MEDIUM -- domain-specific)
7. a11y-dynamic-content-reviewer (MEDIUM)
8. a11y-css-reviewer (MEDIUM)
9. css-reviewer (MEDIUM)
10. a11y-html-reviewer (HIGH -- legal compliance)
11. go-build-verifier (HIGH -- catches compilation failures)

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
| Agent timeout (>120s) | Skip. Record "Timed out" in Agent Summary. No retry. The 120s threshold provides a buffer above the routed-agent ceilings (90s or 60s, per dm-review Phase 3.75). If those ceilings are ever raised above 120s, this guardrail must be raised in lockstep or it will silently pass timed-out agents. |
| Agent returns empty | Treat as "Clean (empty response)" in Agent Summary. |
| Agent returns error | Record error message in Agent Summary. Don't retry. |
| Agent output contains `### RUNNER FAILURE` | External-LLM-routed runner failed. See Phase 4.5 for fallback procedure. If fallback also fails, apply core/conditional failure policies (REVIEW INCOMPLETE for core agents, degraded for conditional). Extract failure reasons from both runs for the Agent Summary. |
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

### Canonical identity (required before matching)

Every candidate receives the canonical identity exact form
`finding-v1:sha256(<normalized-key>)`. The normalized key is serialized in
this order: lowercase POSIX path; smallest stable structural anchor (normalized
line span only if no anchor exists); normalized issue category; and
whitespace-collapsed root-cause invariant. Reviewer, provider, model, severity,
remediation, and discovery order are excluded.

Use the most specific durable symbol, heading, test name, selector, or data path
as the structural anchor. Normalize anchor/category/root-cause text to lowercase
with leading/trailing whitespace removed and internal whitespace collapsed.
Normalize the line fallback as `lines=<start>-<end>`. Hash the labeled UTF-8
fields in the order and serialization specified by the consolidator contract.

Input permutations preserve IDs and decision ordering. Severity disagreement
changes the ledger, not identity. A severity-derived ID is invalid.

### Same canonical identity

Merge exact duplicates without count inflation. Use `exact-duplicate` when the
normalized descriptions and evidence are equivalent, or
`same-root-cause-merge` when independently worded findings describe the same
root cause. List all source IDs, agents, providers, models, evidence, and raw
artifact references.

### Same file + same line

Treat as a merge candidate only. If category or root-cause invariant differs,
keep separate canonical findings.

### Same file + adjacent lines (within 3 lines)
Treat as a merge candidate only. Merge only when the structural anchor,
category, and root-cause invariant identify the same issue. If in doubt, keep
separate.

### Same file + different lines
Keep as separate findings, even if descriptions are similar. Different locations = different findings.

### Different files, same issue pattern
Keep both. Note the pattern: "This issue appears in N files."

### Same finding, different severity
Preserve both source severities and set `agreement: disputed`. Select the
canonical severity using reproducible test/runtime evidence first, then direct
HEAD evidence, diff/context evidence, standards-based reasoning, and finally
reviewer consensus. If evidence is otherwise tied, choose the higher severity.
Record the chosen severity and evidence rationale. Severity disagreement
changes the ledger, not the finding ID.

### Contradicting findings
Contradictions never disappear. Keep both source positions, evidence, raw refs,
and severities visible in `Synthesis Decisions`; use `agreement: disputed`.
When competing root-cause positions have different canonical IDs, emit sorted
reciprocal `cross_id_link=<finding-id>|<finding-id>` entries and mark both rows
disputed. Distinct identity is not evidence of uniqueness.
Unresolved positions are `retained` with `retained-disagreement`. A position
may be `discarded` with `superseded-by-stronger-evidence` only when the
deterministic evidence priority resolves it, and the discarded position still
remains visible in the ledger.

### Decision validation

`agreement: unique|corroborated|disputed` is independent of
`finding_disposition: retained|merged|discarded`. Every source finding must
have exactly one non-empty source ID, lane, requested provider, attempted
provider, implemented-by provider, model, agent, source severity, evidence,
`raw_ref`, disposition, reason code, and rationale. Source severities are
`P1|P2|P3`. Every source ID is unique within the canonical decision. `unique`
requires exactly one source; `corroborated` requires at least two independent
sources. A within-ID `disputed` decision requires at least two local source
positions; a cross-ID `disputed` decision requires at least one local source
plus reciprocal links to the competing finding rows and their source positions.

Each source uses exactly one closed reason code:
`retained-unique`, `retained-corroborated`, `retained-disagreement`,
`exact-duplicate`, `same-root-cause-merge`,
`superseded-by-stronger-evidence`, `out-of-scope`, `not-reproducible`, or
`agent-findings-cap`.
Reject missing, duplicate, or free-form reason codes; empty or duplicate source
IDs; missing source severities; agreement/source-count mismatches; one-way,
self-referential, malformed, or missing cross-ID dispute links; flattened
contradictions; severity-derived IDs; missing raw refs; and reports missing the
`Synthesis Decisions` section.

Raw outputs are immutable: reference them, never rewrite or delete them. A
consolidated summary cannot substitute for absent raw evidence.
