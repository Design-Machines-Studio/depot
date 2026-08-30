# Depot Role Benchmark

`depot-role-v2` is a project-specific complement to public coding-agent
benchmarks, not a replacement for them. Its 18 distinct cases cover all nine
Depot roles with two cases each: `architect`, `builder-deep`, `builder-fast`,
`editorial`, `plan-critic`, `research-fast`, `review-deep`, `review-fast`, and
`security-review`. Each case declares its revision, prompt revision, required
capabilities, applicability, visible output contract, semantic assertions, and
code-owned deterministic validator.

The suite is manual and one-candidate-at-a-time. It never schedules a sweep,
chooses a model for an orchestrator, changes candidate order, or uses another
model as a judge. A one-attempt screen may discover a quality, latency, context,
capability, or cost opportunity. A screen cannot promote or demote a model.
Promotion requires three comparable successful attempts on every applicable
distinct role case plus the existing policy review, capability, family,
production-canary, validation, and subscription-preference gates. Retain every
attempt, including failures and incomplete directories, to avoid selection
bias.

```shell
./depot-role-benchmark.sh --list
./depot-role-benchmark.sh --run \
  --case pipeline-legacy-translation \
  --model deepseek/deepseek-v4-flash-0731 \
  --role-policy ../../../../model-router/skills/model-router/references/role-policy.json \
  --result-dir /home/ned/benchmark-results/depot-role-v2/manual/openrouter/deepseek-v4-flash/pipeline-legacy-translation/run-1
```

`--run` requires the explicit checked-in role policy, rejects substituted live
suite/matrix/wrapper assets, validates the exact slug against both the policy
and checked-in OpenRouter matrix, uses the same input eligibility as a native
Claude/Codex candidate, disables model fallback, and retains endpoint-provider
and requested/served/fallback identity provenance. The explicit model is
permitted because this is an operator measurement command, not orchestration.
Offline fixture scoring uses `--prepare`, `--score`, or `--offline-run` and
makes no provider call.

## Evidence and comparability

Each attempt directory contains the prompt, system message, raw `output.json`,
private `receipt.json`, and scored `result.json`. The result preserves raw
output and its digest, a normalized JSON output when normalization succeeds,
strict and normalized parse outcomes, requested and served identity,
endpoint-provider provenance, fallback proof, duration and reported usage,
deterministic assertions, validation, and stage-attributed failure evidence.

Comparable evidence must have matching suite, case, prompt, scorer, normalizer,
and behavioral-contract revisions and digests; an eligible role/capability
binding; a matching receipt; successful transport; confirmed served identity;
and closed no-model-fallback provenance. Keep incompatible v2 and historical v1
attempts, but never aggregate them into a current model comparison.

Failures are attributed to `prompt/contract`, `parser/normalizer`, `scorer`,
`harness`, `transport`, `identity`, `format/contract`, `mandatory`, `semantic`,
or `validation`. Benchmark-owned prompt, parser, scorer, binding, and harness
faults set `benchmarkFault:true`, `comparable:false`, and
`modelConclusion:null`. Stop new benchmark calls, preserve the faulty evidence,
repair the benchmark locally, and pass its offline fixtures before collecting
new evidence. Never count these faults, transport failures, unknown identity,
or incompatible digests against a model. Only a compatible, identity-confirmed
attempt can produce a model conclusion.

Lead comparisons with validated quality and contextual efficiency: validation
rate, first-pass validation, deterministic quality by distinct case, attempts
and time to first validated output, model-attributable rework, latency, token
and context coverage, tool/correction/finding telemetry, and production quality
signals. Provider-billed spend, subscription marginal cost, API-equivalent
cost, availability, and access are separate secondary views. Missing evidence
stays null; do not collapse the axes into an opaque leaderboard.

## Blinded editorial human evidence

The two editorial cases may carry one bounded human receipt at
`<attempt-directory>/human-rubric.json`, but the editor must never receive that
model-bearing path. A coordinator exports only the normalized output under a
generic filename plus the exact case rubric to an opaque digest-named handoff
outside the benchmark result tree. The editor writes the receipt there; the
coordinator verifies it and joins it back to the attempt. It has this closed
schema:

```json
{
  "schemaVersion": 1,
  "suiteId": "depot-role-v2",
  "caseId": "editorial-member-update",
  "caseRevision": 2,
  "rubricRevision": 1,
  "outputArtifactSha256": "sha256:<normalized-output-artifact-digest>",
  "blindToCandidate": true,
  "observedAt": "2026-08-29T00:00:00Z",
  "criterionScores": {
    "member-clarity": 5,
    "member-voice": 4
  }
}
```

Join the receipt only to the normalized output artifact digest and matching
suite, case, case revision, and rubric revision. `blindToCandidate` must be
`true`; neither keys nor values may carry candidate, model, provider, or
transport identity, and neither the handoff path nor its contents may reveal
them. Criterion IDs must exactly equal the case rubric and each score must be
numeric from 1 through 5. Reject malformed, unblinded,
identity-bearing, unknown-criterion, invalid-score, digest-mismatched,
case-mismatched, or rubric-mismatched receipts. If the receipt is absent or
rejected, human quality remains null.

Accepted editorial evidence is a separate human quality axis. It never changes
strict parsing, deterministic assertions, validation, comparability,
`overallSuccess`, or any model-judge/deterministic promotion gate.

## Optima mapping

Artificial Analysis Optima can be an optional hosted measurement surface. Copy
or trace a case manually, keep its prompt and deterministic expected result
unchanged, and record the Optima benchmark version beside Depot's local result.
Hosted or pairwise judging must not replace the closed scorers or the blinded
editorial receipt contract.

Depot does not depend on Optima and does not automate hosted spend. If a stable
import format becomes available, add an export adapter—not a scheduler,
service, database, or generic benchmark framework.
