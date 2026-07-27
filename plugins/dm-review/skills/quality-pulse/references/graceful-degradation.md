# Quality-Pulse Graceful Degradation

Degradation is evidence, not permission to imply a complete or passing pulse.

## Lane Evidence States

| State | Meaning | Pulse treatment |
|---|---|---|
| `available` | Primary lane completed with admissible evidence. | Classify its observations at primary confidence. |
| `unavailable` | Primary lane could not start because a declared runtime/tool prerequisite was absent. | Preserve the primary receipt; try only its declared fallback. |
| `failed` | Primary lane started but did not produce valid complete evidence. | Preserve failure evidence; try only its declared fallback. |
| `fallback` | Declared fallback completed after its named primary was unavailable or failed. | Keep `primary_lane_id`, fallback reason, and lower confidence visible. |
| `skipped` | A declared fallback was not needed, or a profile-declared optional lane was not requested. | Record it explicitly; never rewrite it as success. |

Requested, attempted, and actual lane/tool identities are required in every
case. Missing lanes are coverage gaps, never implicit clean evidence.

## Failure Table

| Failure | Result |
|---|---|
| Profile absent or unreadable | Blocked profile preflight; no lane execution. |
| Profile schema/path/argv/output invalid | Blocked profile preflight; no lane execution. |
| Catalog absent, malformed, mismatched, or unknown references | Blocked profile preflight; no lane execution. |
| Trust attestation absent, repository-held, stale, self-asserted, or mismatched | Blocked authority; no lane execution. |
| Kernel/runtime unavailable or incompatible | Pulse unavailable; report safe reason and start no lanes. |
| Primary unavailable/failed, declared fallback succeeds | Partial evidence with `fallback` status and fallback confidence. |
| Lane exits zero without a fresh valid lane-bound observation envelope | `failed` with a stable evidence reason; never `available`. |
| Primary and fallback unavailable/failed | Partial report blocker; preserve both receipts and fail the pulse. |
| Redaction refuses unsafe evidence | Preserve a refusal receipt, omit unsafe bytes, and fail the pulse. |
| Observation uses unknown schema/path/surface/metric/rule/classification/evidence state | Retain redacted raw telemetry, classify `unknown`, set actionability `actionable`, and fail the pulse. |
| Authoritative JSON emission or validation fails | Publish no new Markdown digest. |
| Markdown rendering fails after JSON succeeds | JSON remains authoritative; report digest publication failure. |
| Baseline identity is incompatible or incomplete | Emit baseline discontinuity; calculate no trend delta. |

## Partial Reports

A partial authoritative JSON artifact may be retained only when it validates,
names every missing/failed/unavailable lane, contains safe redacted evidence,
and marks the pulse failed or blocked. It must list exact blockers and coverage
gaps.

Partial evidence cannot become:

- a passing pulse;
- primary-equivalent evidence;
- a merge recommendation;
- an informational coercion for unknown data;
- a Markdown-only authority.

If safe authoritative JSON cannot be produced, report the blocker without
publishing a digest.
