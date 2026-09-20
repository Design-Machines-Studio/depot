# Codex efficiency inspection — 2026-09-20

## Observed usage

Read-only inspection of NED's local Codex session and archived-session JSONL.
The recent window is September 13 through the September 20 inspection (UTC),
not a complete account billing period. No transcript content is published here.

| Measurement | Locally recorded value |
|---|---:|
| Sessions with usage increments | 83 |
| Distinct usage increments | 12,919 |
| Input tokens, including cached input | 2,261,589,601 |
| Cached input tokens (subset of input) | 2,214,516,608 (97.9%) |
| Non-cached input tokens | 47,072,993 |
| Output tokens | 4,721,912 |
| Reasoning output (subset of output) | 1,511,337 |
| Input + output | 2,266,311,513 |
| Median last-request input | 163,163 |
| Usage updates with last-request input above 100,000 | 9,628 (74.5%) |
| Usage updates with last-request input above 272,000 | 2,357 (18.2%) |

| Context-reported model | Input + output tokens |
|---|---:|
| GPT-5.6 Sol | 1,455,222,893 |
| GPT-6 Astra | 515,766,270 |
| GPT-5.6 Luna | 279,948,839 |
| GPT-5.6 Terra | 15,373,511 |

These are repeated processed tokens, not unique source text. Model attribution
uses the most recent `turn_context`, not verified provider-served identities.
Sol accounts for most recorded raw tokens in this window; the logs do not
establish that Astra alone caused the reported two-day allowance exhaustion.

Method: scan local `sessions` and `archived_sessions`; inspect metadata,
`turn_context` and `event_msg/token_count`. Difference increasing cumulative
`total_token_usage` counters; ignore unchanged snapshots. Use `last_token_usage`
for first observations and counter resets. Deduplicate identical timestamp and
usage payloads across files before aggregation. Process pre-window records for
baselines, then select events by UTC timestamp. Cached input and reasoning output
are subsets and are not added again. First observations or resets can undercount
unobserved work; imported logs and missing events prevent account reconciliation.

Private aggregate and event extracts were kept locally under `/tmp`, not committed.
Other machines, cloud usage, removed logs, actual billing, per-task quality and
subscription allowance weights are not measured. Do not convert these totals into
an invoice or claim a specific percentage of future savings.

## Configuration observed

The local default is `gpt-6-astra` / `low`, with a requested 1,000,000-token context
and 400,000-token compaction threshold. A sampled session reported an 828,400-token
usable context. These settings were inspected but not changed. They are not
portable defaults for smaller models. Lower effort alone does not remove large
repeated input.

## Changes and next operating choices

Optimize total cost of correct, complete delivery, including defects, rework,
latency and maintainer time. Astra or another stronger initial model remains valid
when a concrete task-specific benefit justifies it; cheapest tokens are not the goal.

1. Shared role policy starts bounded implementation on Luna, deeper implementation
   on Terra, and architecture on Sol. Astra remains selective escalation.
   Routine planning/evidence collection uses the research role, not architecture.
2. Ordinary logic and integration no longer automatically select a deep worker or
   long-context capability. The two reported bounded tasks are renderer fixtures:
   builder-fast/high and research-fast/medium, with exact native fallbacks.
3. Claude is excluded from the default policy; compatibility code remains tested
   through explicit opt-in test policies. No account or paid-overage settings change.
4. Refresh only changed evidence on planning follow-ups. Prefer targeted reads,
   compact handoffs, direct execution for small tasks and exact verification reuse.
5. For routine new sessions, choose Luna Medium rather than the observed Astra Low
   default; use Luna High for substantive bounded implementation. Escalate when
   actual uncertainty or a failed focused attempt warrants it.
6. At a task boundary, replace very long planning histories with a compact current
   handoff. Trial earlier compaction or model-default context on representative work;
   do not blindly copy the million-token override into every model. Fresh sessions
   on every turn would also waste useful cached context.
7. Disable irrelevant plugins/MCP integrations per project when their instructions
   are not needed. Keep required domain guidance, credentials and verification intact.
   No installation changes were made in this source task.

[Official Codex usage guidance](https://learn.chatgpt.com/docs/pricing) confirms
that model, context, reasoning, tools and caching affect allowance. It recommends
smaller models, tighter source scope and smaller instruction/MCP context. Its
published credit rates distinguish cached input from uncached input; they are
not measurements of this operator's subscription deductions.

## Delivery boundary

This report accompanies source changes, not a performance benchmark or installed
consumer canary. Publication and plugin-cache synchronization require separate
authorization. Existing long-lived planning sessions need to reload updated
instructions after installation; changing a source branch cannot alter them.

## Review delivery correction

The same change repairs dm-review-fix's obsolete “suggest committing” pause and
its broad deletion of completed todos. Authorized repairs now commit/push their
own changes, verify the remote PR head and preserve unrelated residue. Shared
browser guidance binds each maintained instance separately and leaves the final
reviewed head available. Baseplate's exact two-instance mapping belongs in its own
AGENTS.md; a separate consumer documentation PR supplies it. No dev servers or
serving checkouts were changed or live browser proof claimed in this task.
