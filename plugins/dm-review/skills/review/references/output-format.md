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

---

### Merge Recommendation

[BLOCKS MERGE / APPROVE WITH FIXES / CLEAN]

[One-sentence summary of the most important finding, or "No issues found."]

---

### P1 — Critical (Blocks Merge)

#### [Finding Title]
- **Source:** [agent-name]
- **File:** path/to/file.ext:line
- **Issue:** Clear description of the problem
- **Fix:** Specific remediation steps
- **Reference:** WCAG 2.4.7 / OWASP A03:2021 / etc.

[Repeat for each P1 finding]

---

### P2 — Important (Should Fix)

#### [Finding Title]
- **Source:** [agent-name]
- **File:** path/to/file.ext:line
- **Issue:** Description
- **Fix:** Remediation

[Repeat for each P2 finding]

---

### P3 — Fix This Session

#### [Finding Title]
- **Source:** [agent-name]
- **File:** path/to/file.ext:line
- **Issue:** Description
- **Fix:** Remediation

[Repeat for each P3 finding — same detail format as P1/P2]

---

### Agent Summary

| Agent | Findings | P1 | P2 | P3 | Status |
|-------|----------|----|----|----|----|
| code-simplicity-reviewer | 2 | 0 | 1 | 1 | Done |
| security-auditor | 0 | 0 | 0 | 0 | Clean |
| a11y-html-reviewer | 3 | 1 | 2 | 0 | Done |
| css-reviewer | 1 | 0 | 0 | 1 | Done |
| voice-editor | — | — | — | — | Skipped (no .md files changed) |
| ... | | | | | |

**Total:** X findings (Y P1, Z P2, W P3)
**Agents run:** M of N applicable
**Agents skipped:** [list with reason]

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

- **Code agents:** `path/to/file.ext:line` — file path and line number
- **Browser agents (visual-browser-tester):** `[url @ breakpoint]` — page URL and viewport width

Browser agent citation examples:

- `[/proposals @ 320px]` — issue at a specific viewport
- `[/proposals @ all]` — issue at all viewports
- `[/proposals > button.submit]` — issue with a specific element
- `[/proposals > dialog#confirm]` — issue with a specific component

The consolidator preserves the original citation format from each agent.

---

## Rules

1. **P1 findings get full detail blocks** — file, issue, fix, reference
2. **P2 findings get detail blocks** — same format as P1
3. **P3 findings get full detail blocks** — same format as P1/P2. P3 issues must be fixed, not glossed over.
4. **Clean agents are noted** in the summary table but don't get detail sections
5. **Skipped agents are listed** with the reason (file type not changed, project type mismatch)
6. **Deduplicated findings** show all source agents: `**Source:** a11y-css-reviewer, css-reviewer`
7. **Full agent reports** are always included in collapsible sections for reference
8. **No sugar-coating** — if the code has problems, say so directly

## Merge Recommendation Logic

```
if any P1 findings:
  recommendation = "BLOCKS MERGE"
  summary = "X critical issues must be fixed before merging."
elif any P2 findings:
  recommendation = "APPROVE WITH FIXES"
  summary = "X issues should be addressed. None block merge."
else:
  recommendation = "CLEAN"
  summary = "No issues found. Ready to merge."
```

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
