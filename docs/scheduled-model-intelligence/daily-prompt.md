# Daily Depot model pulse — scheduled-task prompt

Run this task Monday through Saturday at 05:00 Asia/Makassar in an isolated Git
worktree for `/home/ned/ai/depot`. Always return findings, including a clean
"no material change" result.

You are maintaining Depot's factual model matrix and longitudinal model-system
report. Work only in the scheduled task's isolated worktree. Treat
`/home/ned/ai/depot` as a read-only source of local, Git-ignored production run
artifacts. Do not modify, commit, clean, stash, reset, or switch branches in
that source checkout; another process may be using it.

## Authority and boundaries

- You may refresh existing factual entries in
  `plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json`.
- You may update the dated catalog receipt, `model-selection.md`, the ongoing
  aggregate report, version metadata required by those edits, and generated
  Codex manifests.
- Do not add a new model to the matrix during the daily pulse.
- Do not edit `plugins/model-router/skills/model-router/references/role-policy.json`.
- Do not run paid model benchmarks.
- Never expose credentials, prompts, outputs, generation IDs, or concrete
  private-router receipt records. Aggregate model/provider metrics are allowed.
- Never merge to `main`. Commit only exact files created or changed by this run
  on the automation worktree's `ai/` branch. Do not push unless this scheduled
  task is separately configured to push.

## 1. Preflight

Run from the worktree root:

```sh
rtk git status --short --branch
rtk git rev-parse --show-toplevel
rtk python3 tests/test_model_intelligence.py -v
```

If the worktree contains changes that predate this run, stop without editing
and report the exact paths. Do not attempt to reconcile them.

Set the exact paths and capture one catalog snapshot:

```sh
SOURCE_REPO=/home/ned/ai/depot
STATE_ROOT=/home/ned/.local/state/openrouter-model-pulse
MATRIX=plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json
SUITE=plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json
POLICY=plugins/model-router/skills/model-router/references/role-policy.json
BENCH_ROOT=/home/ned/benchmark-results/depot-role-v2
OBSERVED_AT="$(date --iso-8601=seconds)"
RUN_DATE="$(date +%F)"
CATALOG="$STATE_ROOT/catalog/models-$(date +%Y%m%dT%H%M%S%z).json"
CATALOG_RECEIPT="$STATE_ROOT/receipts/catalog-$RUN_DATE.json"
ELIGIBILITY="$BENCH_ROOT/eligibility-$RUN_DATE.json"

mkdir -p "$STATE_ROOT/catalog" "$STATE_ROOT/receipts" "$BENCH_ROOT"
jq -n --slurpfile suite "$SUITE" --slurpfile policy "$POLICY" '
  {suite_id:$suite[0].suiteId,suite_revision:$suite[0].suiteRevision,
   distinct_cases:($suite[0].cases | length),
   roles:($suite[0].cases | map(.role) | unique),
   cases:[$suite[0].cases[] as $case |
     {case_id:$case.id,case_revision:$case.revision,prompt_revision:$case.promptRevision,
      role:$case.role,required_capabilities:$case.requiredCapabilities,
      eligible_candidates:[$policy[0].roles[$case.role][] as $candidate |
        select(all($case.requiredCapabilities[]; . as $cap |
          $candidate.capabilities | index($cap) != null)) |
        {transport:$candidate.transport,model:$candidate.model,billing:$candidate.billing}]}]}' \
  > "$ELIGIBILITY"
jq '{suite_id,suite_revision,distinct_cases,roles,
  cases:[.cases[] | {case_id,role,eligible_count:(.eligible_candidates|length)}]}' \
  "$ELIGIBILITY"
curl -fsS https://openrouter.ai/api/v1/models -o "$CATALOG"
jq -e '.data | type == "array" and length > 0' "$CATALOG" >/dev/null
sha256sum "$CATALOG"
```

If the catalog request or validation fails, retain the old matrix unchanged,
continue to the production report, and mark catalog evidence unavailable.

## 2. Compare and refresh the existing matrix

When the catalog is valid, run:

```sh
rtk python tools/model-intelligence.py catalog-refresh \
  --catalog "$CATALOG" \
  --matrix "$MATRIX" \
  --observed-at "$OBSERVED_AT" \
  --output "$CATALOG_RECEIPT" \
  --write

jq '{observedAt,expiresAt,models_observed,material_change_count,changes,new_candidates}' \
  "$CATALOG_RECEIPT"
rtk git diff -- "$MATRIX"
```

The tool may update existing exact entries only. Review every changed field
against the captured catalog. Do not infer quality, copy evidence from another
model/version, admit moving `latest` aliases, or overwrite
`native_api_equivalent_cost` dates.

If `material_change_count` is nonzero:

1. Create `docs/openrouter-model-matrix-refreshes/$RUN_DATE.md` with the exact
   source, observed/expires timestamps, SHA-256, observed count, field changes,
   new-candidate nominations, stale/unavailable evidence, and an explicit
   statement that no paid inference or role-policy change occurred.
2. Update the exact affected rows and snapshot reference in
   `plugins/openrouter/skills/openrouter-delegate/references/model-selection.md`.
3. Update the snapshot-date assertion in
   `tools/validate-routing-economics.sh`; do not weaken any other assertion.
4. Patch-bump `plugins/openrouter/.claude-plugin/plugin.json` and the matching
   openrouter entry in `.claude-plugin/marketplace.json`, then run:

```sh
rtk ./tools/generate-codex-manifests.py
rtk ./tools/generate-codex-command-skills.py --check
```

If there is no material catalog change, do not touch the matrix, selection
guide, validator, versions, generated manifests, or dated matrix-refresh docs.

## 3. Rebuild the ongoing production report

Read actual run artifacts from the source checkout, not the isolated worktree:

```sh
REPORT_DIR=docs/model-intelligence
DAILY_DIR="$REPORT_DIR/daily"
mkdir -p "$DAILY_DIR"

rtk python tools/model-intelligence.py report \
  --run-root "$SOURCE_REPO/plans" \
  --run-root "$SOURCE_REPO/.workflow-kernel/runs" \
  --benchmark-root "$BENCH_ROOT" \
  --observed-at "$OBSERVED_AT" \
  --json-output "$DAILY_DIR/$RUN_DATE.json" \
  --markdown-output "$DAILY_DIR/$RUN_DATE.md"

cp "$DAILY_DIR/$RUN_DATE.json" "$REPORT_DIR/latest.json"
cp "$DAILY_DIR/$RUN_DATE.md" "$REPORT_DIR/latest.md"
jq '{production:{cost_summary_artifacts:.production.cost_summary_artifacts,
  metrics_artifacts:.production.metrics_artifacts,
  empty_cost_summaries:.production.empty_cost_summaries,
  malformed_artifacts:.production.malformed_artifacts,
  by_model:.production.by_model,
  quality:.production.quality},benchmarks:.benchmarks}' "$REPORT_DIR/latest.json"
```

Interpret honestly:

- Lead with per-role validated quality, distinct-case coverage, first-pass
  reliability, rework/time to valid, latency, context, and instrumentation.
  Provider spend and access are separate secondary views.
- Historical v1 and digest-incompatible v2 evidence cannot enter current
  comparisons. Benchmark prompt, parser/normalizer, scorer, binding, or harness
  faults have no model conclusion and cannot promote or demote a model.
- If a benchmark fault appears, preserve its attempt, stop benchmark calls,
  repair the benchmark locally, and pass offline fixtures before any later
  evidence collection. The daily pulse itself makes no paid benchmark call.
- `lanes: 0`, empty summaries, missing token/cost coverage, and unattributed
  models are measurement gaps—not zero cost or successful efficiency.
- Never add token counts to input bytes.
- Provider-billed cost and imputed subscription-equivalent cost remain labeled.
- Finding contribution, completion, fallback, retry, and first-pass validation
  are workflow quality signals; do not claim isolated model causality when the
  artifacts do not establish it.
- Compare the new latest report with the previous tracked version and state the
  actual deltas. Do not fill gaps with estimates outside the matrix contract.

## 4. Validate and commit

Run:

```sh
rtk ./tools/test-benchmark-evidence-contract.sh
rtk ./tools/test-openrouter-role-benchmark.sh
rtk python3 tests/test_model_intelligence.py -v
rtk ./tools/validate-provider-neutral-routing.sh
rtk ./tools/validate-routing-economics.sh
rtk ./tools/validate-dual-compat.sh
rtk ./tools/validate-composition.sh --all
rtk git diff --check
rtk git status --short
```

If validation fails, do not commit. Report the failing command, preserve the
worktree for inspection, and do not change policy to make a test pass.

If validation passes, stage only the paths this run intentionally changed and
commit with `chore(models): daily pulse $RUN_DATE`. Never use `git add -A`.

## 5. Findings returned to Scheduled

Always report:

- catalog status, timestamp, digest, and material changes;
- new candidate nominations without promotion;
- production evidence coverage and missing instrumentation;
- model/role cost, duration, token or byte, fallback, retry, validation, and
  finding-contribution changes actually supported by artifacts;
- strong/weak points in the current routing system;
- files changed, validation results, branch, and commit—or why no commit exists;
- exactly one recommended follow-up, or `none`.
