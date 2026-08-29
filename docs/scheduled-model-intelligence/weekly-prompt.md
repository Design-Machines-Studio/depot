# Weekly Depot benchmark and routing review — scheduled-task prompt

Run this task Sunday at 05:00 Asia/Makassar in an isolated Git worktree for
`/home/ned/ai/depot`. It replaces Sunday's daily pulse. Always return findings,
including a clean "no routing change justified" result.

You are running Depot's weekly controlled benchmark and routing-effectiveness
review. Work only in the scheduled task's isolated worktree. Treat
`/home/ned/ai/depot` as a read-only source of local production evidence. Never
modify, clean, reset, stash, commit, or switch branches in that source checkout;
another process may be using it.

Use the same catalog-refresh, reporting, evidence-interpretation, versioning,
validation, privacy, and no-auto-merge rules in
`docs/scheduled-model-intelligence/daily-prompt.md`, plus the procedure below.

## 1. Preflight and daily pulse

Run the daily prompt's preflight, live catalog capture, existing-entry matrix
refresh, and production report first. Stop before paid calls if the catalog is
unavailable, the worktree was not clean, a routed exact slug is absent, or the
OpenRouter credential cannot be resolved and its dedicated weekly limit cannot
be verified by:

```sh
CREDENTIAL=plugins/openrouter/skills/openrouter-delegate/references/openrouter-credential.sh
KEY_STATE="/home/ned/benchmark-results/depot-role-v2/key-state-$(date +%F).json"
(
  set +x
  . "$CREDENTIAL"
  load_openrouter_api_key
  umask 077
  curl -fsS https://openrouter.ai/api/v1/key \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -o "$KEY_STATE"
)
jq -e '.data.limit == 10 and .data.limit_reset == "weekly" and
  (.data.limit_remaining | type) == "number" and .data.limit_remaining >= 0' \
  "$KEY_STATE" >/dev/null
jq '{limit:.data.limit,limit_remaining:.data.limit_remaining,
  limit_reset:.data.limit_reset,usage_weekly:.data.usage_weekly}' "$KEY_STATE"
```

Use a dedicated OpenRouter key with a provider-side weekly limit of USD $10.
The local receipt sum is a secondary guard, not a hard cap: one in-flight call
can exceed a local pre-call total. If a provider-side $10 limit cannot be
verified, do not run paid benchmarks; finish the production review and report
`benchmark blocked: hard spend cap not proven`.

Set:

```sh
RUN_DATE="$(date +%F)"
BENCH=./plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh
NATIVE_BENCH=./tools/run-native-depot-role-benchmark.sh
SUITE=./plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json
MATRIX=./plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json
POLICY=./plugins/model-router/skills/model-router/references/role-policy.json
BENCH_ROOT="/home/ned/benchmark-results/depot-role-v2"
WEEK_ROOT="$BENCH_ROOT/$RUN_DATE"
ELIGIBILITY="$BENCH_ROOT/eligibility-$RUN_DATE.json"
PAID_STOP="$WEEK_ROOT/paid-calls.stopped"
BENCH_STOP="$WEEK_ROOT/all-benchmark-calls.stopped"
BUDGET_USD=10
mkdir -p "$WEEK_ROOT"

rtk "$BENCH" --list
jq -r '.roles | to_entries[] | .key as $role | .value[] |
  [$role,.transport,.model,.billing] | @tsv' "$POLICY"
```

## 2. Choose the bounded comparison set

Use exact OpenRouter identities only. For native subscription transports, use
only identities or aliases already admitted by `role-policy.json`, and require
the native benchmark receipt to retain the actual served model when the CLI
reports it. Build a written candidate plan at
`$WEEK_ROOT/benchmark-plan.json` containing:

- at most two newly nominated OpenRouter models from the fresh catalog receipt,
  recorded as nomination-only and not as runnable targets;
- the current first OpenRouter candidate for each suite role;
- the current first native subscription candidate for each suite role;
- the precomputed v2 eligibility record, current compatible distinct-case
  coverage from the daily report, and case/evaluator revision digests;
- case IDs, three target attempts, effort, rationale, estimated call count, and
  the order in which budget will be spent.

Verify that `$ELIGIBILITY` names `depot-role-v2`, all 18 distinct cases, and all
nine roles before any paid call. Every runnable candidate/case pair must appear
as eligible for that case's role and required capabilities. If eligibility or
coverage is missing, malformed, or inconsistent with the checked-in suite and
policy, stop before paid calls and repair the planning evidence. Do not infer
eligibility from price, public rankings, or a retired evidence contract.

Public rankings and external benchmarks are nomination evidence only. Record
the exact model/harness variant, source version/date, and incompatibilities.
Never transfer a score from a different version or harness.

A nominated OpenRouter model may be recorded in the matrix without becoming a
runnable benchmark target. Add only candidates selected in the bounded plan.
Populate exact catalog identity, price, context, feature/parameter,
provider-limit, reasoning, and source fields from the captured snapshot; use:

- `recommendation_status: "catalogued-awaiting-local-benchmark"`
- `quality_rank: null` unless exact comparable evidence exists
- `local_evidence: "No local benchmark evidence before <RUN_DATE>."`
- a role sentence that explicitly says the model is not routed

Do not add aliases, `anthropic/*`, unpriced entries, or models lacking required
case capabilities. Admission to the matrix is not admission to role policy and
does not authorize the benchmark runner. Keep those entries as untested
nominations. A future screen requires a separately reviewed, non-routing
benchmark-admission contract; never add an untested model to executable role
policy just to make a call pass.

## 3. Run controlled comparisons

For each already policy-admitted OpenRouter candidate and applicable case, use a
unique directory and disable model fallback through the existing runner.
Same-model provider fallback must remain enabled so endpoint capacity does not
masquerade as model failure:

```sh
[ ! -f "$PAID_STOP" ] && [ ! -f "$BENCH_STOP" ] || {
  [ ! -f "$PAID_STOP" ] || cat "$PAID_STOP" >&2
  [ ! -f "$BENCH_STOP" ] || cat "$BENCH_STOP" >&2
  exit 1
}
"$BENCH" --run \
  --case "$CASE_ID" \
  --model "$MODEL" \
  --role-policy "$POLICY" \
  --result-dir "$WEEK_ROOT/openrouter/$MODEL/$CASE_ID/run-$ATTEMPT" || {
    printf 'paid benchmark call failed; no later paid call is authorized\n' \
      > "$PAID_STOP"
    exit 1
  }
```

For each native incumbent, run the same prompt and deterministic scorer:

```sh
[ ! -f "$BENCH_STOP" ] || {
  cat "$BENCH_STOP" >&2
  exit 1
}
"$NATIVE_BENCH" \
  --case "$CASE_ID" \
  --transport "$TRANSPORT" \
  --model "$MODEL" \
  --effort "$EFFORT" \
  --result-dir "$WEEK_ROOT/$TRANSPORT/$MODEL/$CASE_ID/run-$ATTEMPT"
```

Run a one-attempt screen first. It discovers opportunities only and cannot
promote or demote a candidate. Count failures and incomplete directories.
Proceed only when the first attempt is comparable and identity-confirmed, has
`fallback.used == false`, satisfies every closed assertion, and remains plausible
on latency, context, capability, and cost. Do not discard failed
runs or rerun into the same directory.

Inspect `result.json` after every native or paid attempt. The following conditions
stop all native and OpenRouter benchmark calls:

- `benchmarkFault` is `true`;
- any evidence binding has `match:false`;
- `failureStage` is `prompt/contract`, `parser/normalizer`, `scorer`, or `harness`.

Write the reason to `$BENCH_STOP`. Preserve and report the evidence as
incompatible or benchmark-owned; never count it against the candidate. Repair the benchmark
locally and run both offline benchmark fixture validators plus the Python
intelligence/native test. Do not make any benchmark rerun during this weekly
task; a later run may collect new evidence after the repair is reviewed and
validated.

After every paid OpenRouter attempt, recalculate actual measured spend from all
`result.json` files under `$WEEK_ROOT`. Every paid retained result must contain
a numeric provider-reported `.usage.cost`; missing or non-numeric cost telemetry
is an instrumentation fault, not zero spend. Preserve that attempt, stop paid
calls, and report the missing coverage. Record the aggregate in
`$WEEK_ROOT/spend.json`, and also stop paid calls when the provider key refuses
the next call or the measured sum reaches $10. Never substitute list price for
provider-reported billed cost. Use this exact rollup after each paid attempt:

```sh
rtk ./tools/validate-paid-benchmark-costs.sh "$WEEK_ROOT/openrouter" || {
  printf 'weekly benchmark spend telemetry is incomplete; stopping paid calls\n' \
    > "$PAID_STOP"
  exit 1
}
rtk python tools/model-intelligence.py report \
  --run-root "$WEEK_ROOT/no-production-evidence" \
  --benchmark-root "$WEEK_ROOT" \
  --json-output "$WEEK_ROOT/spend.json" >/dev/null
SPEND_USD="$(jq -r '.benchmarks.measured_cost_usd' "$WEEK_ROOT/spend.json")"
[ "$SPEND_USD" != "null" ] || {
  printf 'weekly benchmark spend telemetry is incomplete; stopping paid calls\n' \
    > "$PAID_STOP"
  exit 1
}
rtk awk -v spend="$SPEND_USD" -v cap="$BUDGET_USD" \
  'BEGIN { if (spend >= cap) exit 1 }' || {
    printf 'weekly benchmark spend cap reached: %s\n' "$SPEND_USD" \
      > "$PAID_STOP"
    exit 1
  }
```

Report untested candidates and cases.

For editorial cases, a coordinator—not the editor—creates an opaque,
digest-named handoff outside the model-bearing benchmark tree. It contains only
the normalized output under a generic filename and the exact case rubric; its
path and contents expose no candidate, model, provider, or transport identity.
The editor returns the closed receipt inside that opaque handoff. The
coordinator verifies its output digest and case/rubric revisions, then joins it
to `<attempt-directory>/human-rubric.json`. Require `blindToCandidate:true`;
reject malformed, unblinded, unknown-criterion, or mismatched receipts; and keep
absence null. This separate human-quality axis never changes deterministic
gates or supplies a model-judge conclusion.

## 4. Rebuild and inspect the combined report

After attempts settle, run:

```sh
REPORT_DIR=docs/model-intelligence
WEEKLY_DIR="$REPORT_DIR/weekly"
SOURCE_REPO=/home/ned/ai/depot
mkdir -p "$WEEKLY_DIR"

rtk python tools/model-intelligence.py report \
  --run-root "$SOURCE_REPO/plans" \
  --run-root "$SOURCE_REPO/.workflow-kernel/runs" \
  --benchmark-root "$WEEK_ROOT" \
  --json-output "$WEEKLY_DIR/$RUN_DATE.json" \
  --markdown-output "$WEEKLY_DIR/$RUN_DATE.md"

rtk python tools/model-intelligence.py report \
  --run-root "$SOURCE_REPO/plans" \
  --run-root "$SOURCE_REPO/.workflow-kernel/runs" \
  --benchmark-root /home/ned/benchmark-results/depot-role-v2 \
  --json-output "$REPORT_DIR/latest.json" \
  --markdown-output "$REPORT_DIR/latest.md"

jq '.benchmarks.groups, .production.by_model, .production.quality' \
  "$WEEKLY_DIR/$RUN_DATE.json"
```

Review each axis separately:

- validated success rate and all retained failures, separated into
  model-attributable, operational, benchmark-owned, and incompatible evidence;
- deterministic quality by distinct case within one compatible evaluator
  cohort;
- median duration;
- prompt, completion, reasoning, and cache tokens when reported;
- deterministic input bytes as a separate native measurement unit;
- provider-billed OpenRouter cost;
- subscription API-equivalent cost, explicitly labeled and never called spend;
- quality per completion token and quality per measured dollar only when both
  denominators have complete compatible coverage;
- fallbacks, retries, completion rate, first-pass validation, rework, and
  finding contributions from production metrics;
- coverage gaps that prevent comparison.

Lead with validated quality and contextual efficiency. Keep provider spend,
subscription economics, and access as secondary views. Do not produce one
opaque weighted leaderboard. Benchmark-owned or incompatible attempts always
carry `no model conclusion` and cannot change candidate recommendations.

## 5. Guarded routing decisions

Update matrix evidence and recommendations automatically from the retained
results. A role-policy edit is allowed on this automation branch only when all
applicable gates pass:

1. The exact model remains available in the fresh matrix.
2. Every applicable distinct role case has at least three retained comparable
   successful attempts in one digest-compatible evaluator cohort, confirmed
   served identity, fallback false, no benchmark-owned fault, no case median
   below 90, and overall median quality not worse than the comparable incumbent
   by more than two points.
3. Duration/token/cost coverage is sufficient to support the claimed advantage;
   missing evidence cannot be scored as zero.
4. Family-independence and capability constraints remain satisfied.
5. An included-subscription native incumbent stays ahead when it is within the
   quality/reliability floor, unless the challenger proves a material latency,
   context, capability, or subscription-capacity preservation advantage.
6. A newly benchmarked OpenRouter model enters only as a later canary rung.
   Moving it to role head requires at least five attributable production
   attempts with acceptable completion, fallback, retry, and first-pass
   validation evidence from that canary position.
7. Security models remain confined to `security-review`; `anthropic/*` remains
   forbidden on OpenRouter; GLM remains excluded unless exact local evidence
   specifically reverses the existing constraint and validators are updated
   without weakening unrelated invariants.

When a gate fails, retain the evidence and write `no policy change` with the
exact failed gate. A screen, benchmark fault, incompatible digest, historical
v1 result, or missing human editorial receipt is never promotion or demotion
evidence. Do not promote by intuition.

When a gate passes, edit only
`plugins/model-router/skills/model-router/references/role-policy.json`, update
its `matrixSnapshot`, patch-bump model-router's Claude manifest and marketplace
entry, regenerate Codex manifests, and document before/after role order plus
rollback criteria in the weekly report. The branch commit is the review
surface; never merge it automatically.

## 6. Validate, commit, and report

Run all daily validations plus:

```sh
rtk ./tools/test-model-router.sh
rtk ./tools/validate-workflow-contracts.sh
rtk git diff --check
rtk git status --short
```

If any validation fails, do not commit. Never weaken a gate merely to land a
candidate. If all pass, stage only intentional files and commit with
`chore(models): weekly evidence $RUN_DATE`. Never use `git add -A`, never merge,
and never modify the source checkout.

Always return:

- candidates and incumbents tested, attempts, failures, and skipped work;
- actual OpenRouter spend against the $10 cap;
- per-axis benchmark findings and production findings;
- subscription-marginal-cost and API-equivalent views separately;
- strong and weak points in the current system;
- every matrix or role change with evidence and rollback condition;
- every failed promotion gate and instrumentation gap;
- validation, changed files, branch, and commit—or why no commit exists;
- exactly one recommended next benchmark or instrumentation improvement.
