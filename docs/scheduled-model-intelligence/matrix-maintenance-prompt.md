# Depot weekly whole-matrix maintenance — T3 prompt

Run this task Sunday at 05:30 Asia/Makassar except when the monthly full-matrix
portfolio audit replaces it. Select GPT-5.6 Sol in the T3 session UI.

Follow `daily-prompt.md`, `weekly-prompt.md`, and the safety, evidence, and
artifact boundaries in `full-matrix-prompt.md`. Work in a clean isolated Depot
worktree. Treat the NED Depot and Baseplate source checkouts as read-only and
store raw evidence only under `/home/ned/benchmark-results`.

This is a whole-matrix evaluation with bounded new calls. Reconstruct every
model-role cell from the live catalog, matrix, role policy, portfolio contract,
latest full audit, weekly evidence, and attributable production metrics.

## Required maintenance sequence

1. Refresh exact catalog identity, availability, price, context, parameters,
   provider limits, and reasoning support.
2. Detect changes in matrix, role policy, harness, cases, scorers, Baseplate
   pins, source selectors, and production evidence.
3. Reclassify every model-role cell as current, stale, missing, excluded,
   screen-failed, screened, benchmarked, canary, incumbent, or
   promotion-blocked.
4. Rotate one sealed incumbent health case per covered role.
5. Screen new candidates only against plausible eligible roles.
6. Re-run cells invalidated by relevant model, case, scorer, dependency, or
   source changes.
7. Continue incomplete three-attempt comparisons only when they remain
   decision-relevant.
8. Recompute provider-billed spend after every paid call and stop on provider
   refusal.
9. Import production completion, fallback, retry, first-pass validation,
   rework, and finding-contribution evidence.
10. Do not rerun current low-value cells merely to create activity.

The report must still show the complete portfolio, including unchanged and
excluded cells. Identify newly opened and closed gaps, degrading incumbents,
newly competitive candidates, redundant paid routes, subscription-capacity
opportunities, evidence approaching staleness, missing roles, and every failed
promotion gate.

Commit only durable contracts and content-free aggregates. Keep raw prompts,
private excerpts, model outputs, receipts, key-state files, and stderr outside
Git. Run the full weekly validation set. Never merge automatically.

Always return `no routing change justified` when appropriate and exactly one
recommended next benchmark or instrumentation improvement.
