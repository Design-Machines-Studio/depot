# Depot model intelligence

Depot model intelligence combines three evidence classes without pretending
they are interchangeable:

1. OpenRouter catalog facts: exact identity, availability, capabilities,
   context limits, provider limits, and pricing.
2. Controlled `depot-role-v1` results: deterministic quality score, duration,
   token/cost receipt fields, transport, and repeated-attempt reliability.
3. Production evidence: Workflow Kernel `metrics.json` and
   `run-cost-summary.json` artifacts from actual Pipeline and dm-review runs.

Public benchmarks and OpenRouter rankings nominate candidates. They do not
promote models. Native subscription runs retain their marginal-cost advantage,
while API-equivalent pricing makes their opportunity cost visible.

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

Aggregate local production artifacts and retained benchmark results:

```sh
./tools/model-intelligence.py report \
  --run-root /home/ned/ai/depot/plans \
  --run-root /home/ned/ai/depot/.workflow-kernel/runs \
  --benchmark-root /home/ned/benchmark-results/depot-role-v1 \
  --json-output docs/model-intelligence/latest.json \
  --markdown-output docs/model-intelligence/latest.md
```

The source checkout paths are explicit because Git-ignored run evidence is not
copied into an isolated scheduled-task worktree. Reports aggregate content-free
economic and quality signals; they do not publish private prompt/output content
or private receipt identity fields.

Run an exact OpenRouter model through the existing benchmark:

```sh
BENCH=./plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh
"$BENCH" --run \
  --case review-zero-deferral \
  --model deepseek/deepseek-v4-flash-0731 \
  --result-dir /home/ned/benchmark-results/depot-role-v1/manual/openrouter/deepseek-v4-flash/review-zero-deferral/run-1
```

Run one admitted native subscription model or policy alias through the same
prompt and scorer. The receipt retains the actual served identity when the CLI
reports it:

```sh
./tools/run-native-depot-role-benchmark.sh \
  --case review-zero-deferral \
  --transport codex-cli \
  --model gpt-5.6-sol \
  --effort medium \
  --result-dir /home/ned/benchmark-results/depot-role-v1/manual/codex-cli/gpt-5.6-sol/review-zero-deferral/run-1
```

Use `--transport claude-cli --model fable` for an admitted Claude subscription
candidate. Native results record subscription billing and any CLI-reported
tokens. Missing counters remain missing; billed cost is never invented.

## Interpretation and promotion gates

- Keep token counts and deterministic input bytes as separate units.
- Keep provider-billed cost and subscription API-equivalent cost separately
  labeled.
- Count failed and incomplete attempts; never select only successful runs.
- Require at least three successful attempts on every applicable local case.
- Compare per-axis results—quality, success, duration, tokens, cost, fallback,
  and production quality signals—not one opaque composite score.
- A new OpenRouter model may enter a role only as a later canary rung after the
  controlled gate. Moving it ahead of an incumbent additionally requires
  production evidence from that canary position.
- If an included-subscription native candidate remains within the accepted
  quality/reliability floor, prefer it unless an OpenRouter model demonstrates
  a material latency, context, capability, or capacity-preservation advantage.
- Routing edits occur only on an isolated automation branch, pass the complete
  validators, and never merge themselves.

## Focused verification

```sh
python3 tests/test_model_intelligence.py -v
./tools/test-openrouter-role-benchmark.sh
./tools/validate-provider-neutral-routing.sh
./tools/validate-routing-economics.sh
```

Run `./tools/validate-composition.sh --all` before committing a matrix, policy,
plugin-version, or generated-manifest change.
