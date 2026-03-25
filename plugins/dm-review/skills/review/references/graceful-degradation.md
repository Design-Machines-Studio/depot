# Graceful Degradation

Decision table for classifying agent failures and determining review completeness. Referenced by the consolidator during Phase 5 and by the guardrails during Phase 3.5.

---

## Minimum Viable Review

All 5 core agents must complete successfully for the review to be considered valid:

1. security-auditor
2. architecture-reviewer
3. code-simplicity-reviewer
4. pattern-recognition-specialist
5. doc-sync-reviewer

If all 5 complete, the review is valid regardless of conditional agent status. If any core agent fails, the review is flagged as incomplete.

---

## Failure Classification

### Review Compromised (core agent failure)

| Failed Agent | Impact | Merge Recommendation |
|---|---|---|
| security-auditor | Security coverage lost. Vulnerabilities may go undetected. | REVIEW INCOMPLETE -- security-auditor unavailable |
| architecture-reviewer | Structural issues unreviewed. Layer violations may pass. | REVIEW INCOMPLETE -- architecture-reviewer unavailable |
| code-simplicity-reviewer | Complexity and dead code unreviewed. | REVIEW INCOMPLETE -- code-simplicity-reviewer unavailable |
| pattern-recognition-specialist | Anti-patterns and naming issues unreviewed. | REVIEW INCOMPLETE -- pattern-recognition-specialist unavailable |
| doc-sync-reviewer | Documentation drift undetected. | REVIEW INCOMPLETE -- doc-sync-reviewer unavailable |

Multiple core failures compound: "REVIEW INCOMPLETE -- security-auditor, architecture-reviewer unavailable."

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

### All Conditional Agents Failed

The review is degraded but still valid. Add to report header:

```
Degraded: all conditional agents unavailable. Review covers core concerns
(security, architecture, simplicity, patterns, documentation) only.
```

---

## Merge Recommendation Modifications

The standard merge recommendation logic (from severity-mapping.md) applies first:

```
if any P1 → BLOCKS MERGE
elif any P2 → APPROVE WITH FIXES
else → CLEAN
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
| 1 | security-auditor | Core | NEVER |
| 2 | architecture-reviewer | Core | NEVER |
| 3 | code-simplicity-reviewer | Core | NEVER |
| 4 | pattern-recognition-specialist | Core | NEVER |
| 5 | doc-sync-reviewer | Core | NEVER |
| 6 | go-build-verifier | HIGH | Yes, last resort |
| 7 | a11y-html-reviewer | HIGH | Yes, last resort |
| 8 | a11y-css-reviewer | MEDIUM | Yes |
| 9 | css-reviewer | MEDIUM | Yes |
| 10 | a11y-dynamic-content-reviewer | MEDIUM | Yes |
| 11 | governance-domain | MEDIUM | Yes |
| 12 | craft-reviewer | MEDIUM | Yes |
| 13 | test-coverage-reviewer | LOW | Yes |
| 14 | voice-editor | LOW | Yes |
| 15 | visual-browser-tester | LOW | Yes |
