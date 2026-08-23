# Lane fallback

Load only when a selected lane fails, declines, or is unavailable.

### Phase 4.5: Lane Fallback

A **lane** is a review path with its own provider and absence mode: Codex, OpenRouter, optional native Claude, second perspective, independent-family security sign-off, and evidence. An unavailable lane must be named.

#### Lane failure modes

| Lane | Failure signal | Resolution |
|------|----------------|------------|
| Independent-family security sign-off | any failure, full decline, partial-coverage marker, or no non-implementing family completes | Continue only through remaining non-implementing families; otherwise REVIEW INCOMPLETE; never substitute the implementing family |
| OpenRouter (ordinary lane) | `### RUNNER FAILURE` in agent output | Retry on Codex (procedure below) |
| OpenRouter full disclosure decline (ordinary lane) | `### RUNNER DECLINED -- SENSITIVE CONTENT` or `host_disclosure_declined` | Run the complete same logical lane on Codex; preserve the declined external attempt |
| OpenRouter partial (ordinary lane) | `### CODEX PARTIAL COVERAGE REQUIRED` in agent output | Run the same agent criteria on Codex for the named locally held paths |
| Second perspective | disabled by `DM_REVIEW_SECOND_PERSPECTIVE=0` or legacy `DM_REVIEW_CODEX_PERSPECTIVE=0`, or no independent family completes | Lane skipped -- **must** appear in Coverage Gaps, not omitted |
| Evidence (PR threads) | `gh pr view` returns no comments/reviews | Phase 1b source fallback; report which source was used |
| Codex-native coding agent | Agent errored or timed out | No Claude retry; apply guardrails immediately |

Coding fallback moves only among policy-derived eligible families. Security
analysis starts on the matrix security head when eligible and always has an
independent-family full-diff sign-off. OpenRouter lanes remain content-gated:
exact file sections containing actual secret/private bytes stay local, while
every safe section remains eligible regardless of path or security subject
matter. One held section never cancels the completed OpenRouter review of the
safe remainder.

#### Phase 4.5 coding-lane exhaustion ask

When a CODING lane finds its provider AND its declared fallback both unavailable, the lane is exhausted, not merely degraded. Ask the operator whether to wait or record the Coverage Gap and continue. There is no additional authorization or fallback rail.

The operator is the human at the top-level interactive session. An agent, subagent, hook, auto-answer configuration, or automated harness is not an operator and can never authorize a fallback lane; an ask answered by any of them is an unanswered ask. When the reviewing context cannot reach the operator, do not fabricate the exchange -- record the gap and continue, or escalate `human_help_required` through the caller that can reach the human.

Collect live rail status at ask time and display it only to inform timing. Offer exactly: wait until the named reset, or record the Coverage Gap and continue -- the review equivalent of park. A context that cannot reach the operator returns `human_help_required` through a reaching caller or records the gap under the headless rule. No provider identifier is an executable answer.

Ask-then-default-gap is the only headless behavior for an ordinary standalone review: a non-interactive session or unanswered ask records the Coverage Gap and continues. Independent-family sign-off and literal disclosure rules remain non-overridable; configured-key OpenRouter lanes never enter this approval path.

**When this review is the pipeline's final full dm-review, “record the gap and continue” and the headless gap-and-continue default are unavailable for coding-lane exhaustion.** The only outcome is REVIEW INCOMPLETE and the branch waits. Ordinary in-policy OpenRouter/Codex routing remains unaffected; it is not exhaustion authorization.

A skipped lane is a coverage gap, and a coverage gap is reported. "All agents completed" while a required independent-family lane never ran is a false clean.

Every lane receipt records `requestedProvider`, `attemptedProvider`, `implementedBy`, `fallback`, and `fallbackReason`. Every machine-readable contribution decision and lane companion also records normalized `implementer_family`, `reviewer_family`, and `resolution_reason`; ordinary lanes may name the same family with an ordinary-lane resolution. Second-perspective and sign-off receipts require disjoint families, including no overlap with any member of `mixed(<sorted families>)`. Preserve failed attempts across Codex, OpenRouter, optional native Claude, and generic hosts.

#### When the external-LLM retry triggers

Applies to agents routed through OpenRouter. For ordinary lanes, `RUNNER
FAILURE` and a full disclosure/host decline trigger a full Codex retry under the
same logical lane ID; `CODEX PARTIAL COVERAGE REQUIRED` triggers bounded Codex
completion. For `security-auditor-codex-signoff`, all three signals instead
continue only to another non-implementing family; if none can complete every
required byte, the review is incomplete. Codex-native agents that fail are
classified immediately.

#### Retry procedure

For each agent whose output contains `### RUNNER FAILURE`,
`### RUNNER DECLINED -- SENSITIVE CONTENT`, or `host_disclosure_declined`:

1. **Resolve the lane before its provider.** If the lane is
   `security-auditor-codex-signoff`, re-dispatch only to the next eligible
   non-implementing family; if none exists, record `REVIEW INCOMPLETE`. For
   every ordinary lane, re-dispatch using Phase 4 Branch B on Codex with the
   same agent definition, diff, and project context.
2. **Tag fallback findings with the provider that actually reviewed them.**
   Ordinary Codex fallback uses `[codex-fallback/{agent-name}]`; independent
   sign-off fallback uses `[independent-family-fallback/{reviewer-family}/{agent-name}]`.
   For a disclosure decline, record
   `fallbackReason: disclosure-declined` or
   `fallbackReason: host-disclosure-declined`; never translate it into an
   OpenRouter success or omit the attempted lane.
3. **Timeout and attempt bound:** Use the same 120s ceiling from guardrails.md.
   Ordinary fallback is a single retry. Independent sign-off may try each
   policy-derived non-implementing family at most once, in order, and then is
   `REVIEW INCOMPLETE`; it never loops or retries the implementing family.

For each agent whose output contains `### CODEX PARTIAL COVERAGE REQUIRED`:

1. If the lane is `security-auditor-codex-signoff`, do not complete the held
   paths on the implementing Codex family. Resolve a non-implementing family
   that can review the complete required bytes or record `REVIEW INCOMPLETE`.
2. For ordinary lanes, parse only normalized path names from the marker; never recover or forward
   the declined bytes through OpenRouter.
3. Re-dispatch the same agent definition on Codex with the full local diff
   sections for those paths and the same project context.
4. Do not rerun the safe remainder or the whole ordinary lane on Codex. Tag
   findings `[codex-sensitive-section/{agent-name}]` and record both the
   OpenRouter eligible-content receipt and Codex held-content receipt.
5. Treat failure of this local completion exactly like failure of the original
   agent lane.

#### If fallback also fails

Apply the existing failure policies from `${CLAUDE_SKILL_DIR}/references/guardrails.md`:
- Core agent (security-auditor-codex-signoff, architecture-reviewer, code-simplicity-reviewer, pattern-recognition-specialist, doc-sync-reviewer): REVIEW INCOMPLETE
- Conditional agent: degraded but valid

#### Agent Summary reporting

Report the fallback in the Agent Summary table:

| Agent | Provider | Status |
|-------|----------|--------|
| pattern-recognition-specialist | OpenRouter `deepseek/deepseek-v4-pro-0813` | RUNNER FAILURE |
| pattern-recognition-specialist | Codex (fallback) | Completed |
| security-auditor-openrouter | OpenRouter `moonshotai/kimi-k3` | Completed (eligible sections) |
| security-auditor-codex-signoff | Resolved independent family | Completed (full diff) |

Summarize: "pattern-recognition-specialist: OpenRouter failed -> Codex fallback succeeded"

#### Cost note

This fallback exists for resilience. If it triggers frequently, investigate OpenRouter health rather than changing the coding boundary.

---
