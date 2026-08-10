# Unusable comparison baseline: r1-review-burn-cuts

The former `2026-08-08-r1-review-burn-cuts.json` was removed so `*.json`
baseline discovery cannot consume it. This notice preserves why it cannot bound
the R1 input-reduction comparison; the underlying artifacts remain historical
evidence.

The deleted JSON is valid evidence for run4. It was byte-identical to
`plans/r1-review-burn-cuts/run4/run-cost-summary.json` and is reproducible from
run4's receipts:

- Codex implemented chunks 01-05;
- chunk 06 was not started; and
- five expected and five measured attempts is complete coverage for run4.

The separately bound, observation-only independent prediction forecast a
different six-chunk attempt using Claude Opus after a Codex usage cap. It is not
execution evidence for run4. Reusing `r1-review-burn-cuts` as the run ID for both
artifacts makes filename-only attribution ambiguous, but does not merge their
histories or invalidate run4's receipts.

The R1 input-reduction gate requires a new comparable pair from a real
`dm-review-loop`: one full pass and one selective pass using the same logical
lane set, byte-accounting method, and exact run binding. Implementation-chunk
input bytes are not comparable to review-lane input bytes. That workflow-boundary
mismatch is the sole reason the deleted JSON is unusable for this gate.
