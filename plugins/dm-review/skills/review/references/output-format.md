# Review Output Format

The canonical unified report and compact human handoff produced by the
review-consolidator after all agents complete. The handoff is a projection of
the complete report, never a replacement for it.

---

## Compact Human Handoff

Every visible result begins with this compact handoff. Use the exact mechanical
verdict from the complete report. Keep the explanation to one plain sentence.

```markdown
## <CLEAN | APPROVE WITH FIXES | BLOCKS MERGE | REVIEW INCOMPLETE>

<One plain sentence explaining the verdict.>

### Actionable findings
<For each retained P1/P2/P3, once only: `path:anchor -- problem -- smallest adequate fix`>
<If none: `None.`>

### Coverage gap requiring action
<Only gaps that require human action. If none: `None.`>

### Recommended next action
<One action.>

### Complete evidence
`Full report: .claude/ux-review/report.md`.
<If findings exist: `Open findings: N -- <evidence pointer>.`>
```

When there are at most eight retained findings across all severities, list each
exactly once. When there are more than eight, list the highest-impact eight,
state `N additional findings` with the exact remaining count, and point to the
complete report. Never imply that omitted findings do not exist. Chat keeps P3
compact, but it follows the same fix queue and convergence path as P1/P2.

Do not repeat provider tables, agent transcripts, synthesis ledgers, cleanup
tables, or raw reports in the handoff. Write them to the established durable
artifact `.claude/ux-review/report.md` before delivery. Coverage gaps, blocked
browser evidence, cleanup truth, finding IDs, and
literal provider/model provenance remain in that complete evidence flow.

Clean review: use `CLEAN` only when every required lane completed and no
retained P1/P2/P3 finding remains.

Review with actionable findings: use `APPROVE WITH FIXES` or `BLOCKS MERGE` and
keep every retained finding in the repair queue.

## Complete Report Template

```markdown
## Code Review Report

**Date:** YYYY-MM-DD
**Target:** [PR #X / branch-name / N files changed]
**Mode:** [Full / Quick]
**Project Type:** [Go+Templ+Datastar / Craft CMS / CSS Framework / Mixed]
**Agents Launched:** X of Y applicable
**Lanes:** codex: ran | openrouter: fallback:codex | claude-noncoding: ran | second-perspective: unavailable:no-independent-family
**Evidence source:** PR threads | receipts | merge bodies | closed issues | verification files | none found

---

### Merge Recommendation

[BLOCKS MERGE / APPROVE WITH FIXES / CLEAN]

[One-sentence summary of the most important finding, or "No issues found."]

---

### P1 -- Critical (Blocks Merge)

#### [Finding Title]
- **Finding ID:** `finding-v1:sha256(<normalized-key>)`
- **Source:** [agent-name]
- **Source findings:** [source-id -> lane/requested-provider/attempted-provider/implemented-by/model/agent; evidence; raw_ref]
- **File:** path/to/file.ext:line
- **Issue:** Clear description of the problem
- **Fix:** Specific remediation steps
- **Reference:** WCAG 2.4.7 / OWASP A03:2021 / etc.

[Repeat for each P1 finding]

---

### P2 -- Important (Should Fix)

#### [Finding Title]
- **Finding ID:** `finding-v1:sha256(<normalized-key>)`
- **Source:** [agent-name]
- **Source findings:** [source-id -> lane/requested-provider/attempted-provider/implemented-by/model/agent; evidence; raw_ref]
- **File:** path/to/file.ext:line
- **Issue:** Description
- **Fix:** Remediation

[Repeat for each P2 finding]

---

### P3 -- Required Fix

#### [Finding Title]
- **Finding ID:** `finding-v1:sha256(<normalized-key>)`
- **Source:** [agent-name]
- **Source findings:** [source-id -> lane/requested-provider/attempted-provider/implemented-by/model/agent; evidence; raw_ref]
- **File:** path/to/file.ext:line
- **Issue:** Description
- **Fix:** Remediation

[Repeat for each P3 finding -- same detail format as P1/P2]

---

### Synthesis Decisions

| Finding ID | Agreement | Disputed with | Selected outcome | Source decisions | Evidence rationale |
|------------|-----------|---------------|------------------|------------------|--------------------|
| `finding-v1:sha256(aaaa...)` | disputed | `finding-v1:sha256(bbbb...)` via reciprocal `cross_id_link` | retained as P1 | `source-id-a`: lane=`openrouter-fallback`, requested=`OpenRouter`, attempted=`OpenRouter`, implemented-by=`Codex`, model=`gpt-5`, agent=`security-auditor`, severity=`P1`, evidence=`runtime test reproduces unsafe write`, disposition/reason=`retained/retained-disagreement`, raw_ref=`raw/security.md#finding-1`, rationale=`runtime evidence establishes this root cause` | Reproducible runtime evidence supports source A and outranks the linked static hypothesis. |
| `finding-v1:sha256(bbbb...)` | disputed | `finding-v1:sha256(aaaa...)` via reciprocal `cross_id_link` | discarded in favor of stronger evidence | `source-id-b`: lane=`openrouter`, requested=`OpenRouter`, attempted=`OpenRouter`, implemented-by=`OpenRouter`, model=`deepseek/deepseek-v4-pro-0813`, agent=`pattern-recognition-specialist`, severity=`P3`, evidence=`static inspection attributes the write to a different root cause`, disposition/reason=`discarded/superseded-by-stronger-evidence`, raw_ref=`raw/patterns.md#finding-2`, rationale=`runtime reproduction contradicts this root-cause position` | The contradictory source position and its evidence remain visible despite the discarded outcome. |

One row per canonical finding, sorted by finding ID. Within a row, sort source
decisions by source finding ID. Sort cross-ID links by ordered ID pair and emit
them reciprocally on every linked row. Use
`agreement: unique|corroborated|disputed`
independently from `finding_disposition: retained|merged|discarded`. Each source
decision names its literal lane, requested/attempted/implemented-by provider,
model, agent, source evidence, source severity, disposition, closed
`decision_reason_code`, raw artifact reference, and a compact rationale. For
severity disagreement, show every source severity, the chosen severity, and why
the selected evidence outranks the alternatives.
Contradictions and discarded positions remain visible.

If there are zero raw findings, emit `Synthesis Decisions: none -- no source
findings required a decision.` The section is still required.

The four machine-readable companions are exact JSON objects. Every one carries
`schema_version: 1`, its `artifact_role`, and the same review `run_id`. The
kernel normalizes the four identity inputs, recomputes the exact
`finding-v1:sha256(<64 lowercase hex>)` identifier, checks cardinality, and
appends the ordered contribution receipts.

| Companion | `artifact_role` | Also carries | Per-entry fields |
|---|---|---|---|
| Synthesis decisions | `synthesis_decisions` | integer `source_finding_count`, normalized UTC `occurred_at`, `decisions` (exactly one per raw source finding) | `source_finding_id`, `finding_path`, `finding_anchor`, `finding_category`, `finding_root_cause`, `finding_disposition`, `agreement`, `decision_reason_code`, `reviewer`, `lane`, `requested_provider`, `attempted_provider`, `implemented_by`, `provider`, `model`, `implementer_family`, `reviewer_family`, `resolution_reason`, `source_severity`, `evidence_ref`, positive integer `attempt`, `occurred_at` |
| Raw inventory | `raw_finding_inventory` | `findings` | `source_finding_id`, `reviewer`, `lane`, `source_severity`, `evidence_ref`, and the four identity inputs |
| Lane receipts | `review_lane_receipts` | `lanes` (one entry per required lane) | `reviewer`, `lane`, `requested_provider`, `attempted_provider`, `implemented_by`, `provider`, `model`, `implementer_family`, `reviewer_family`, `resolution_reason`, nonempty `evidence_refs`, nonnegative integer `finding_count`, content-addressed `raw_output_ref` and `raw_output_digest` |
| Raw lane outputs | `review_lane_raw_outputs` | `outputs` (one per requested lane) | only `reviewer`, `lane`, and `findings`; `findings` uses the raw inventory shape and may be empty |

Use literal provider/model values from the lane receipt, or `not_reported` when
it names none. Every decision records normalized family provenance: ordinary
lanes may record the same implementer and reviewer family with a resolution such
as `ordinary-lane-same-family-review`; required independent lanes must use
disjoint families, including disjoint members of `mixed(<sorted families>)`, and
their `reviewer_family` must match the closed family derived from the recorded
reviewer model. Lane names and reviewer/lane identities are unique, and family
values and resolution must exactly match every decision sourced from that lane.
Every raw finding's `reviewer`/`lane` and `evidence_ref` must resolve to that
literal lane entry, and the independently parsed union of all raw lane outputs
must equal the raw inventory and decisions exactly. All four inputs must contain
no credential-shaped value, URL userinfo, credential query, authorization
string, or compound credential assignment; the exporter validates them before
hashing or creating any sealed artifact.

---

### Raw Evidence Index

One compact row per selected lane, projected from existing lane and coverage
receipts. Do not copy reviewer output into this report.

| Reviewer | Lane | Status | Findings | Provider / model | Evidence references | Raw output reference | Raw output digest |
|----------|------|--------|----------|------------------|---------------------|----------------------|-------------------|
| code-simplicity-reviewer | codex | Done | 2 | Codex / gpt-5 | `raw/simplicity.md#finding-1` | `contribution-inputs/raw-lane-outputs/<digest>.json` | `sha256:<digest>` |
| security-auditor | openrouter-fallback | Partial | 0 | requested=OpenRouter; implemented-by=Codex / gpt-5 | `raw/security.md` | `contribution-inputs/raw-lane-outputs/<digest>.json` | `sha256:<digest>` |

Use literal receipt values, including provenance, references, `raw_output_ref`,
and `raw_output_digest`. Incomplete required lanes stay visible here and in
Coverage Gaps; they never support clean. This index creates no transcript.

---

### Coverage Gaps

List incomplete required coverage, its evidence pointer, and one next action.
If none, state `Coverage Gaps: none -- all required lanes completed.`

---

### Agent Summary

| Agent | Findings | P1 | P2 | P3 | Status |
|-------|----------|----|----|----|----|
| <one row per selected lane> | | | | | |

**Total:** X findings (Y P1, Z P2, W P3)
**Agents run:** M of N applicable
**Agents skipped:** [list with reason]

---

### Repository Cleanup

Emitted by Phase 8. Two tables, matching `repo-cleanup-contract.md` section 7 verbatim -- a deleted ref carries **proof**, a kept ref carries a **follow-up command**, and those are different columns. A blocked ref is never reported as deleted.

#### Created this run
| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| review/cleanup-findings | review-branch | deleted | merged into main |

#### Remaining after cleanup
| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| .worktrees/pipeline/auth-map/04-views | worktree | not ours -- created by an interrupted pipeline run | `git worktree remove --force .worktrees/pipeline/auth-map/04-views` |

- Worktrees before: N   after: M   pruned: K
- Branches deleted: N   blocked: M   left (foreign): K
- `git status --porcelain`: clean | <residue>

If the review created and left nothing, state `Repository cleanup: nothing created, tree clean, N worktrees pruned.`

---

```

---

## Citation Formats

Agents use different citation styles depending on whether they analyze code or rendered pages:

- **Code agents:** `path/to/file.ext:line` -- file path and line number
- **Browser agents (visual-browser-tester):** `[url @ breakpoint]` -- page URL and viewport width

Browser agent citation examples:

- `[/proposals @ 320px]` -- issue at a specific viewport
- `[/proposals @ all]` -- issue at all viewports
- `[/proposals > button.submit]` -- issue with a specific element
- `[/proposals > dialog#confirm]` -- issue with a specific component

The consolidator preserves the original citation format from each agent.

---

## Rules

1. **P1 findings get full detail blocks** -- file, issue, fix, reference
2. **P2 findings get detail blocks** -- same format as P1
3. **P3 findings get full detail blocks** -- same format as P1/P2. Preserve source identity, raw reference, evidence, synthesis disposition, counts, and provenance; every retained P3 enters the fix queue.
4. **Clean agents are noted** in the summary table but don't get detail sections
5. **Skipped agents are listed** with the reason (file type not changed, project type mismatch)
6. **Deduplicated findings** show all source agents: `**Source:** a11y-css-reviewer, css-reviewer`
7. **Raw evidence is indexed once** -- use the existing raw findings, lane
   outputs, receipts, references, and digests; never paste reviewer output or
   create a transcript replacement
8. **No sugar-coating** -- if the code has problems, say so directly
9. **Stable identity is mandatory** -- every retained canonical finding uses
   `finding-v1:sha256(<normalized-key>)`, derived without reviewer, provider,
   model, severity, remediation, or discovery order
10. **Synthesis decisions are complete** -- every source finding appears with
    provenance, evidence, raw ref, agreement, disposition, closed reason code,
    and rationale; the compact Raw Evidence Index preserves raw-output access
11. **Human delivery is compact** -- the exact verdict, one-sentence explanation,
    actionable P1/P2/P3 findings, human-action coverage gaps, one recommended next
    action, and complete-evidence pointer appear before the report

## Merge Recommendation Logic

```text
if any P1 findings:
  recommendation = "BLOCKS MERGE"
  summary = "X critical issues must be fixed before merging."
elif any P2 or P3 findings:
  recommendation = "APPROVE WITH FIXES"
  summary = "X issue(s) must be addressed before merging."
else:
  recommendation = "CLEAN"
  summary = "No issues found. Ready to merge."
```
