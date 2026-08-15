# Graceful Degradation

Decision table for classifying agent failures and determining review completeness. Referenced by the consolidator during Phase 5 and by the guardrails during Phase 3.5.

---

## Minimum Viable Full Review

All 5 core criteria must complete successfully. Security has two logical lanes
when OpenRouter is selected: both must complete independently.

1. security-auditor-codex-signoff (always required)
   - security-auditor-openrouter (also required when selected; may complete via its explicit Codex fallback)
2. architecture-reviewer
3. code-simplicity-reviewer
4. pattern-recognition-specialist
5. doc-sync-reviewer

If all required logical lanes complete, the review is valid regardless of
conditional status. One security output never satisfies both security lanes.

---

## Failure Classification

### Lane Fallback (pre-classification)

Before classifying an agent failure as "Review Compromised" or "Safe to Skip," resolve the lane. Phase 4.5 owns this. Only classify a failure after its lane's fallback has been attempted.

| Lane | Failure signal | Resolution | Reported as |
|---|---|---|---|
| Independent-family security sign-off | Any provider failure, disclosure decline, or partial-coverage marker | Continue only through non-implementing families; otherwise REVIEW INCOMPLETE | Never same-family fallback completion |
| OpenRouter ordinary lane | `### RUNNER FAILURE` or disclosure decline | Retry the same logical lane on Codex (Phase 4.5) | "Completed (fallback)" or classify below |
| Second perspective | `DM_REVIEW_SECOND_PERSPECTIVE=0`, legacy `DM_REVIEW_CODEX_PERSPECTIVE=0`, or no eligible non-implementing family completes | None -- lane is optional | Coverage Gaps: `second-perspective: skipped|unavailable` with family-resolution evidence |
| Evidence (PR threads) | `gh pr view` returns no comments/reviews | Phase 1b source fallback | Header: `**Evidence source:** <source>` |
| Codex-native coding agent | Errored or timed out | No Claude retry | Classify immediately below |

Ordinary coding fallback moves between OpenRouter and Codex. The independent
sign-off lane excludes the implementing family on every retry. Sensitive sections
stay local; eligible sections may enter the distinct external security lane.

A skipped lane is a coverage gap, and a coverage gap is reported. Reporting "all agents completed" while the required independent sign-off lane never ran is a false clean.

Ordinary agents that succeed via Codex fallback are reported as "Completed (fallback)" and tagged `[codex-fallback/{agent-name}]`. The independent sign-off lane may use this status only when Codex is not the implementer.

### Review Compromised (core agent failure)

| Failed Agent | Impact | Merge Recommendation |
|---|---|---|
| security-auditor-codex-signoff | Independent full-diff security coverage lost. | REVIEW INCOMPLETE -- security-auditor-codex-signoff unavailable |
| security-auditor-openrouter (when selected) | Required external security lens/fallback lane incomplete. | REVIEW INCOMPLETE -- security-auditor-openrouter unavailable |
| architecture-reviewer | Structural issues unreviewed. Layer violations may pass. | REVIEW INCOMPLETE -- architecture-reviewer unavailable |
| code-simplicity-reviewer | Complexity and dead code unreviewed. | REVIEW INCOMPLETE -- code-simplicity-reviewer unavailable |
| pattern-recognition-specialist | Anti-patterns and naming issues unreviewed. | REVIEW INCOMPLETE -- pattern-recognition-specialist unavailable |
| doc-sync-reviewer | Documentation drift undetected. | REVIEW INCOMPLETE -- doc-sync-reviewer unavailable |

Multiple core failures compound: "REVIEW INCOMPLETE -- security-auditor-codex-signoff, architecture-reviewer unavailable."

### Safe to Skip (conditional agent failure)

| Failed Agent | Impact | Report Note |
|---|---|---|
| go-build-verifier | Build verification skipped. Run `go build` manually. | "Skipped -- verify build manually" |
| a11y-html-reviewer | HTML accessibility unchecked. | "Skipped -- run a11y audit separately" |
| a11y-css-reviewer | CSS accessibility unchecked. | "Skipped" |
| css-reviewer | Live Wires compliance unchecked. | "Skipped" |
| a11y-dynamic-content-reviewer | Datastar accessibility unchecked. | "Skipped" |
| governance-domain | Governance compliance unchecked. | "Skipped" |
| craft-reviewer | Craft CMS patterns unchecked. | "Skipped" |
| test-coverage-reviewer | Test coverage unverified. | "Skipped" |
| voice-editor | Voice/tone unreviewed. | "Skipped" |
| visual-browser-tester | Visual testing skipped. | "Skipped -- has its own fallback chain" |
| ux-quality-reviewer | UX/design quality unreviewed. | "Skipped" |
| openrouter-bulk-analyst | Full diff analysis unavailable. Review uses truncated diff. | "Skipped -- OpenRouter unavailable" |

### All Conditional Agents Failed

The review is degraded but still valid. Add to report header:

```
Degraded: all conditional agents unavailable. Review covers core concerns
(security, architecture, simplicity, patterns, documentation) only.
```

---

## Merge Recommendation Modifications

The standard merge recommendation logic (from severity-mapping.md §Escalation Rules and output-format.md §Merge Recommendation Logic) applies first:

```text
if any P1:
  BLOCKS MERGE
elif any P2:
  APPROVE WITH FIXES
elif any P3:
  APPROVE WITH FIXES
else:
  CLEAN
```

Then overlay failure status:

| Failure State | Override |
|---|---|
| All agents completed | No override. Use standard logic. |
| Conditional agents failed | Append "(degraded)" to recommendation. E.g. "CLEAN (degraded)" |
| One core agent failed | Replace with "REVIEW INCOMPLETE -- [agent] unavailable" |
| Multiple core agents failed | Replace with "REVIEW INCOMPLETE -- [agent1], [agent2] unavailable" |
| Consolidator failed | Replace with "REVIEW FAILED -- consolidation error, raw findings attached" |

---

## Priority Ranking

Full degradation priority from guardrails.md. Agents are dropped in this order when token budgets are tight or when failures require triage:

| Rank | Agent | Criticality | Droppable? |
|---|---|---|---|
| 1 | security-auditor-codex-signoff | Core | NEVER |
| 2 | security-auditor-openrouter (when selected) | Core logical lane | NEVER; Codex fallback allowed |
| 3 | architecture-reviewer | Core | NEVER |
| 4 | code-simplicity-reviewer | Core | NEVER |
| 5 | pattern-recognition-specialist | Core | NEVER |
| 6 | doc-sync-reviewer | Core | NEVER |
| 7 | go-build-verifier | HIGH | Yes, last resort |
| 8 | a11y-html-reviewer | HIGH | Yes, last resort |
| 9 | a11y-css-reviewer | MEDIUM | Yes |
| 10 | css-reviewer | MEDIUM | Yes |
| 11 | a11y-dynamic-content-reviewer | MEDIUM | Yes |
| 12 | governance-domain | MEDIUM | Yes |
| 13 | craft-reviewer | MEDIUM | Yes |
| 14 | openrouter-bulk-analyst | MEDIUM | Yes (requires openrouter plugin + OPENROUTER_API_KEY) |
| 15 | test-coverage-reviewer | LOW | Yes |
| 16 | voice-editor | LOW | Yes |
| 17 | visual-browser-tester | LOW | Yes |
| 18 | ux-quality-reviewer | LOW | Yes |
