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
<For each retained P1/P2, once only: `path:anchor -- problem -- smallest adequate fix`>
<If none: `None.`>

### Coverage gap requiring action
<Only gaps that require human action. If none: `None.`>

### Recommended next action
<One action.>

### Complete evidence
`Full report: .claude/ux-review/report.md`.
<If P3 exists: `P3 advisories: N -- <evidence pointer>.`>
```

When there are at most eight P1/P2 findings, list each exactly once. When there
are more than eight, list the highest-impact eight, state `N additional P1/P2
findings` with the exact remaining count, and point to the complete report.
Never imply that omitted findings do not exist. P3 advisories appear only as an
exact count and evidence pointer in this handoff; they remain fully detailed in
the report and never enter the fix queue.

Do not repeat provider tables, agent transcripts, synthesis ledgers, cleanup
tables, or raw reports in the handoff. Write them to the established durable
artifact `.claude/ux-review/report.md` before delivery. Coverage gaps, blocked
browser evidence, cleanup truth, finding IDs, and
literal provider/model provenance remain in that complete evidence flow.

### Representative handoffs

Clean review:

```markdown
## CLEAN
No P1/P2 findings were found, and all required lanes completed.
### Actionable findings
None.
### Coverage gap requiring action
None.
### Recommended next action
Merge the reviewed head.
### Complete evidence
Full report: `.claude/ux-review/report.md` (P3 advisories: 0).
```

Review with actionable findings:

```markdown
## APPROVE WITH FIXES
Two P2 findings must be fixed before merge.
### Actionable findings
- `internal/members/handler.go:Create` -- validation accepts an empty name -- reject an empty trimmed value.
- `web/templates/member.templ:member-form` -- error text is not associated with the field -- add the existing error ID to `aria-describedby`.
### Coverage gap requiring action
Safari browser evidence is blocked -- run the retained case on a Safari-capable host.
### Recommended next action
Fix the two P2 findings, then rerun their affected lanes and the blocked browser case.
### Complete evidence
Full report: `.claude/ux-review/report.md` (P3 advisories: 2).
```

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

### P3 -- Advisory

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
| `finding-v1:sha256(bbbb...)` | disputed | `finding-v1:sha256(aaaa...)` via reciprocal `cross_id_link` | discarded in favor of stronger evidence | `source-id-b`: lane=`openrouter`, requested=`OpenRouter`, attempted=`OpenRouter`, implemented-by=`OpenRouter`, model=`z-ai/glm-5.2`, agent=`pattern-recognition-specialist`, severity=`P3`, evidence=`static inspection attributes the write to a different root cause`, disposition/reason=`discarded/superseded-by-stronger-evidence`, raw_ref=`raw/patterns.md#finding-2`, rationale=`runtime reproduction contradicts this root-cause position` | The contradictory source position and its evidence remain visible despite the discarded outcome. |

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

The machine-readable synthesis companion is an exact JSON object with
`schema_version: 1`, `artifact_role: "synthesis_decisions"`, the review
`run_id`, integer `source_finding_count`, normalized UTC `occurred_at`, and
`decisions`. There is
exactly one decision per raw source finding. Each decision contains:
`source_finding_id`, `finding_path`, `finding_anchor`, `finding_category`,
`finding_root_cause`, `finding_disposition`, `agreement`,
`decision_reason_code`, `reviewer`, `lane`, `requested_provider`,
`attempted_provider`, `implemented_by`, `provider`, `model`,
`implementer_family`, `reviewer_family`, `resolution_reason`, `source_severity`,
`evidence_ref`, positive integer `attempt`, and `occurred_at`. Use literal provider/model values
from the lane receipt; use `not_reported` when that receipt does not name one.
Every decision records normalized family provenance. Ordinary lanes may record
the same implementer and reviewer family with a resolution such as
`ordinary-lane-same-family-review`; required independent lanes must use
disjoint families, including disjoint members of `mixed(<sorted families>)`,
and their `reviewer_family` must match the closed family derived from the
recorded reviewer model.
The kernel normalizes the four identity inputs, recomputes the exact
`finding-v1:sha256(<64 lowercase hex>)` identifier, checks cardinality, and
appends the ordered contribution receipts.

The raw companion is an exact object with `schema_version: 1`,
`artifact_role: "raw_finding_inventory"`, the same `run_id`, and `findings`.
Every finding has `source_finding_id`, `reviewer`, `lane`, `source_severity`,
`evidence_ref`, and the four `finding_path`/`finding_anchor`/
`finding_category`/`finding_root_cause` identity inputs. The lane companion is
an exact object with `schema_version: 1`,
`artifact_role: "review_lane_receipts"`, the same `run_id`, and one `lanes`
entry for every required lane. Each entry has `reviewer`, `lane`,
`requested_provider`, `attempted_provider`, `implemented_by`, `provider`,
`model`, `implementer_family`, `reviewer_family`, `resolution_reason`, nonempty
`evidence_refs`, nonnegative integer `finding_count`, and the
content-addressed `raw_output_ref` and `raw_output_digest`. Lane names and
reviewer/lane identities must be unique. Family values and resolution must
exactly match every decision sourced from that lane. The raw-output companion is an exact
object with `schema_version: 1`,
`artifact_role: "review_lane_raw_outputs"`, the same `run_id`, and one
`outputs` entry per requested lane. Each output contains only `reviewer`,
`lane`, and `findings`; `findings` uses the raw inventory finding shape and may
be empty. Every raw finding's `reviewer`/`lane` and `evidence_ref` must resolve
to that literal lane entry, and the independently parsed union of all raw lane
outputs must equal the raw inventory and decisions exactly. All four inputs
must contain no credential-shaped value, URL userinfo, credential query,
authorization string, or compound credential assignment; the exporter
validates them before hashing or creating any sealed artifact.

---

### Agent Summary

| Agent | Findings | P1 | P2 | P3 | Status |
|-------|----------|----|----|----|----|
| code-simplicity-reviewer | 2 | 0 | 1 | 1 | Done |
| security-auditor | 0 | 0 | 0 | 0 | Clean |
| a11y-html-reviewer | 3 | 1 | 2 | 0 | Done |
| css-reviewer | 1 | 0 | 0 | 1 | Done |
| voice-editor | -- | -- | -- | -- | Skipped (no .md files changed) |
| ... | | | | | |

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

### Detailed Agent Reports

<details>
<summary>code-simplicity-reviewer (2 findings)</summary>

[Full agent output verbatim]

</details>

<details>
<summary>a11y-html-reviewer (3 findings)</summary>

[Full agent output verbatim]

</details>

[Collapsible section for each agent that produced findings]
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
3. **P3 findings get full detail blocks** -- same format as P1/P2. Preserve source identity, raw reference, evidence, synthesis disposition, counts, and provenance even though P3 is advisory.
4. **Clean agents are noted** in the summary table but don't get detail sections
5. **Skipped agents are listed** with the reason (file type not changed, project type mismatch)
6. **Deduplicated findings** show all source agents: `**Source:** a11y-css-reviewer, css-reviewer`
7. **Full agent reports** are always included in collapsible sections in the complete evidence, not expanded in the compact handoff
8. **No sugar-coating** -- if the code has problems, say so directly
9. **Stable identity is mandatory** -- every retained canonical finding uses
   `finding-v1:sha256(<normalized-key>)`, derived without reviewer, provider,
   model, severity, remediation, or discovery order
10. **Synthesis decisions are complete** -- every source finding appears with
    provenance, evidence, raw ref, agreement, disposition, closed reason code,
    and rationale; raw reviewer reports remain verbatim below
11. **Human delivery is compact** -- the exact verdict, one-sentence explanation,
    actionable P1/P2 findings, human-action coverage gaps, one recommended next
    action, and complete-evidence pointer appear before the report

## Merge Recommendation Logic

```text
if any P1 findings:
  recommendation = "BLOCKS MERGE"
  summary = "X critical issues must be fixed before merging."
elif any P2 findings:
  recommendation = "APPROVE WITH FIXES"
  summary = "X issue(s) must be addressed before merging."
else:
  recommendation = "CLEAN"
  if any P3 findings:
    summary = "No P1/P2 findings. X P3 advisory finding(s) retained below."
  else:
    summary = "No issues found. Ready to merge."
```
