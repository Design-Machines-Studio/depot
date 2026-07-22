# Review Output Format

The canonical unified report format produced by the review-consolidator after all agents complete.

---

## Report Template

```markdown
## Code Review Report

**Date:** YYYY-MM-DD
**Target:** [PR #X / branch-name / N files changed]
**Mode:** [Full / Quick]
**Project Type:** [Go+Templ+Datastar / Craft CMS / CSS Framework / Mixed]
**Agents Launched:** X of Y applicable
**Lanes:** codex: ran | openrouter: fallback:codex | claude-noncoding: ran | codex-perspective: skipped:cli-absent
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

### P3 -- Fix Before Merge

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
3. **P3 findings get full detail blocks** -- same format as P1/P2. P3 issues must be fixed, not glossed over.
4. **Clean agents are noted** in the summary table but don't get detail sections
5. **Skipped agents are listed** with the reason (file type not changed, project type mismatch)
6. **Deduplicated findings** show all source agents: `**Source:** a11y-css-reviewer, css-reviewer`
7. **Full agent reports** are always included in collapsible sections for reference
8. **No sugar-coating** -- if the code has problems, say so directly
9. **Stable identity is mandatory** -- every retained canonical finding uses
   `finding-v1:sha256(<normalized-key>)`, derived without reviewer, provider,
   model, severity, remediation, or discovery order
10. **Synthesis decisions are complete** -- every source finding appears with
    provenance, evidence, raw ref, agreement, disposition, closed reason code,
    and rationale; raw reviewer reports remain verbatim below

## Merge Recommendation Logic (zero-deferral default)

```text
if any P1 findings:
  recommendation = "BLOCKS MERGE"
  summary = "X critical issues must be fixed before merging."
elif any P2 findings or any P3 findings:
  # Zero-deferral: P3-only is NOT clean. P3s are mandatory fixes before merge.
  recommendation = "APPROVE WITH FIXES"
  if only_p3_findings:
    summary = "X P3 issue(s) mandatory under zero-deferral. Resolve before merge or pass --allow-defer-p3 with justification."
  else:
    summary = "X issue(s) must be addressed before merging."
else:
  recommendation = "CLEAN"
  summary = "No issues found. Ready to merge."
```

Under `--allow-defer-p3`, P3s may be explicitly deferred with a written justification and a tracking destination. In that mode only, P3-only can return `CLEAN` -- but the report must list every deferred P3 in a dedicated "Deferred Findings" section with tracking IDs.

## Ops Dashboard Write

After the report is generated and memory is captured (Phase 7c), a structured row is written to the Agent Activity Log database in Notion. This is a parallel write -- ai-memory remains the primary record.

The Notion row maps report data as follows:

| Report Field | Notion Property | Mapping |
|-------------|----------------|---------|
| Merge recommendation | Status | CLEAN -> "Clean", APPROVE WITH FIXES -> "Needs Attention", BLOCKS MERGE -> "Blocked" |
| Merge recommendation | Merge Rec | Verbatim string |
| Total findings | Findings | Number |
| P1 count | P1 Count | Number |
| Agents launched | Agents | Number (completed + skipped) |
| Target branch | Branch | Text |
| Review date | Date | Today |

If Notion MCP tools are unavailable, the dashboard write is skipped silently.
