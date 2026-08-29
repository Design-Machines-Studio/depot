# Depot model intelligence

Depot model intelligence combines three evidence classes without pretending
they are interchangeable:

1. Controlled `depot-role-v2` evidence: validated quality, stage-attributed
   reliability, time/rework to valid, latency, context and telemetry coverage,
   exact identity provenance, and compatible evaluator digests for 18 distinct
   cases across all nine roles.
2. Production evidence: Workflow Kernel `metrics.json` and
   `run-cost-summary.json` artifacts from actual Pipeline and dm-review runs.
3. Provider catalog and access facts: exact availability, capabilities,
   context limits, provider limits, pricing, and billed spend.

Lead interpretation with validated quality and contextual efficiency. Public
benchmarks and OpenRouter rankings may nominate a screen; they do not promote
models. Provider spend, subscription marginal cost, API-equivalent opportunity
cost, and access remain separately labeled secondary views.

## Commands

Capture the live catalog outside the repository, then compare it with the
checked-in matrix:

```sh
STATE_ROOT=/home/ned/.local/state/openrouter-model-pulse
OBSERVED_AT="$(date --iso-8601=seconds)"
CATALOG="$STATE_ROOT/catalog/models-$(date +%Y%m%dT%H%M%S%z).json"

mkdir -p "$STATE_ROOT/catalog" "$STATE_ROOT/receipts"
curl -fsS https://openrouter.ai/api/v1/models -o "$CATALOG"
jq -e '.data | type == "array" and length > 0' "$CATALOG" >/dev/null

./tools/model-intelligence.py catalog-refresh \
  --catalog "$CATALOG" \
  --observed-at "$OBSERVED_AT" \
  --output "$STATE_ROOT/receipts/catalog-$(date +%F).json"
```

Add `--write` only in a clean automation worktree. It refreshes existing exact
matrix entries when material catalog facts changed. It never adds a new model
or edits `role-policy.json`; `new_candidates[]` is a nomination list.

Aggregate local production artifacts and retained v2 benchmark evidence:

```sh
./tools/model-intelligence.py report \
  --run-root /home/ned/ai/depot/plans \
  --run-root /home/ned/ai/depot/.workflow-kernel/runs \
  --benchmark-root /home/ned/benchmark-results/depot-role-v2 \
  --json-output docs/model-intelligence/latest.json \
  --markdown-output docs/model-intelligence/latest.md
```

The report groups current evidence only when suite, case, prompt, scorer,
normalizer, and behavioral-contract revisions and digests match. It reports all
nine policy roles and their distinct-case coverage. Historical v1, incompatible
v2, incomplete, transport, and unknown-identity attempts remain visible but do
not enter current model quality comparisons.

Run an exact OpenRouter model through one v2 case:

```sh
BENCH=./plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh
"$BENCH" --run \
  --case review-zero-deferral \
  --model deepseek/deepseek-v4-flash-0731 \
  --role-policy ./plugins/model-router/skills/model-router/references/role-policy.json \
  --result-dir /home/ned/benchmark-results/depot-role-v2/manual/openrouter/deepseek-v4-flash/review-zero-deferral/run-1
```

Run one admitted native subscription identity or policy alias through the same
prompt and scorer. The receipt retains the actual served identity when the CLI
reports it:

```sh
./tools/run-native-depot-role-benchmark.sh \
  --case review-zero-deferral \
  --transport codex-cli \
  --model gpt-5.6-luna \
  --effort medium \
  --result-dir /home/ned/benchmark-results/depot-role-v2/manual/codex-cli/gpt-5.6-luna/review-zero-deferral/run-1
```

Use `--case assembly-next-chunk --transport claude-cli --model fable` for an
admitted Claude architect candidate. Native results record subscription billing and any CLI-reported
tokens. Missing counters remain missing; billed cost is never invented.

## Interpretation, faults, and promotion

- A one-attempt screen discovers opportunities only. It cannot promote or
  demote a model.
- Require three comparable successful attempts on every applicable distinct
  role case plus all current production, policy-review, capability,
  family-independence, subscription-preference, and validation gates.
- Count all retained attempts. Compare validated case quality, first-pass rate,
  model-attributable rework, time and attempts to valid, latency, context,
  telemetry coverage, and production quality before provider economics.
- A benchmark prompt, parser/normalizer, scorer, binding, or harness fault has
  `benchmarkFault:true` and `modelConclusion:null`. Stop benchmark calls,
  preserve the attempt, repair the benchmark, and pass offline fixtures before
  collecting more evidence. Never count it against a model.
- Transport failures, unknown served identity, incompatible digests, and
  historical v1 results also produce no model conclusion. Keep them in the
  reliability/coverage record rather than treating them as model failures.
- Keep token counts and deterministic input bytes as different units. Keep
  provider-billed cost, subscription marginal cost, and subscription
  API-equivalent cost separately labeled. Missing coverage stays null.
- A new OpenRouter model may enter a role only as a later canary rung after the
  controlled gate. Moving it ahead of an incumbent additionally requires the
  existing attributable production evidence from that canary position.
- Routing edits occur only on an isolated automation branch, pass the complete
  validators, and never merge themselves.

## Blinded editorial evidence

Editorial attempts may include `<attempt-directory>/human-rubric.json`, but the
editor must never receive that model-bearing path. A coordinator exports only
the normalized output under a generic filename plus the exact rubric to an
opaque digest-named handoff outside the benchmark tree, then joins the returned
receipt to the attempt after verifying its digest and revisions. The closed
receipt contains only
`schemaVersion`, `suiteId`, `caseId`, `caseRevision`, `rubricRevision`,
`outputArtifactSha256`, `blindToCandidate`, `observedAt`, and
`criterionScores`. Join it to the normalized `output.json` artifact SHA-256 and
matching case and rubric revisions. `blindToCandidate` must be `true`; candidate,
model, provider, and transport identity are prohibited from the handoff and
receipt.

Reject malformed, unblinded, identity-bearing, unknown-criterion,
invalid-score, digest-mismatched, case-mismatched, or rubric-mismatched
receipts. Absence or rejection leaves human quality null. An accepted receipt
is a separate human editorial-quality axis; it never changes deterministic
parsing, assertions, validation, comparability, overall success, or promotion
gates and is never a model judge.

## Focused verification

```sh
./tools/test-benchmark-evidence-contract.sh
./tools/test-openrouter-role-benchmark.sh
python3 tests/test_model_intelligence.py -v
./tools/validate-provider-neutral-routing.sh
./tools/validate-routing-economics.sh
```

Run `./tools/validate-composition.sh --all` before committing a matrix, policy,
plugin-version, or generated-manifest change.
