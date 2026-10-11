#!/usr/bin/env bash
# Current policy and real Claude argv construction; no network/model calls.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/plugins/model-router/skills/model-router/references"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/router-quality.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1
export MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json"
export MODEL_ROUTER_CLAUDE_CLI_PATH="$TMP/claude"
export MODEL_ROUTER_CODEX_CLI_PATH="$TMP/codex"
# Dispatcher resolves CLI paths before sanitizing PATH.
export PATH="$TMP:$PATH"
export QUALITY_ARGV="$TMP/argv.json" QUALITY_CALLS="$TMP/calls"
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }
healthy() {
  jq '.healthy' "$DIR/../tests/availability-fixtures.json" > "$TMP/availability.json"
}
cat > "$TMP/claude" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" | jq -Rs 'split("\n")[:-1]' > "$QUALITY_ARGV"
model=""; tools=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --tools) tools="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '%s\n' "$model" >> "$QUALITY_CALLS"
cat >/dev/null
if [ "$model" = claude-haiku-5-5 ]; then
  case "${QUALITY_CLAUDE_CODE:-}" in
    "") ;;
    *) jq -cn --arg code "$QUALITY_CLAUDE_CODE" '{is_error:true,error:{code:$code},result:"native failure"}'; exit 1 ;;
  esac
fi
case "${QUALITY_FAILURE:-}" in
  quota) printf 'quota exhausted\n' >&2; exit 1 ;;
  model) [ "$model" != fable ] || { printf 'model unavailable\n' >&2; exit 1; } ;;
esac
[ "$model" != fable ] || model=claude-fable-5
if [[ "$tools" == *Edit* ]]; then
  printf 'implemented\n' > tracked.txt
  git add tracked.txt
  git -c user.name=test -c user.email=test@example.invalid commit -qm 'bounded implementation'
fi
jq -cn --arg model "${QUALITY_SERVED_MODEL:-$model}" '{model:$model,result:"bounded result",usage:{input_tokens:10,cache_read_input_tokens:20,cache_creation_input_tokens:30,output_tokens:40,output_tokens_details:{thinking_tokens:5}},total_cost_usd:0.123}'
STUB
cat > "$TMP/codex" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}:${2:-}" = features:list ]; then printf 'fast_mode stable true\n'; exit 0; fi
if [ "${1:-}:${2:-}" = exec:--help ]; then printf -- '--strict-config\n'; exit 0; fi
printf '%s\n' "$@" | jq -Rs 'split("\n")[:-1]' > "$QUALITY_ARGV"
model=""; output=""; sandbox=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --sandbox) sandbox="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --output-last-message) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '%s\n' "$model" >> "$QUALITY_CALLS"
cat >/dev/null
if [ "${QUALITY_FAILURE:-}" = model ] && [ "$model" = gpt-6.1-sol ]; then printf 'model unavailable\n' >&2; exit 1; fi
if [ "$sandbox" = workspace-write ]; then
  printf 'implemented\n' > tracked.txt
  git add tracked.txt
  git -c user.name=test -c user.email=test@example.invalid commit -qm 'bounded implementation'
fi
printf 'bounded result\n' > "$output"
STUB
chmod +x "$TMP/claude" "$TMP/codex"
printf 'Perform the bounded task.\n' > "$TMP/prompt"
printf 'Supplied source and browser evidence.\n' > "$TMP/evidence"
mkdir "$TMP/repo"
git -C "$TMP/repo" init -q
printf 'original\n' > "$TMP/repo/tracked.txt"
git -C "$TMP/repo" add tracked.txt
git -C "$TMP/repo" -c user.name=test -c user.email=test@example.invalid commit -qm initial
run() {
  local name="$1" role="$2"; shift 2
  (cd "$TMP/repo"; "$DIR/role-dispatch.sh" --workflow-kernel "$KERNEL" \
    --role "$role" --effort "${QUALITY_EFFORT:-high}" --prompt-file "$TMP/prompt" \
    --output-file "$TMP/$name.out" --receipt-file "$TMP/$name.receipt" "$@") > "$TMP/$name.public"
}

healthy
for role in architect plan-critic review-deep; do
  run "$role" "$role" --capability read-repository --capability tool-use
  assert jq -e '.served.model == "gpt-6.1-sol" and .served.transport == "codex-cli" and .normalizedEffort == "high"' "$TMP/$role.receipt"
  assert jq -e 'index("read-only") != null and (index("--dangerously-bypass-approvals-and-sandbox") == null)' "$QUALITY_ARGV"
done

run design design-consultant --capability read-repository --repository-evidence-file "$TMP/evidence"
assert jq -e '.served.model == "claude-opus-5-5"' "$TMP/design.receipt"
assert jq -e '.[index("--tools")+1] == ""' "$QUALITY_ARGV"

# A requested independent critic excludes both Claude candidates and uses Sol.
receipt_id="$(jq -r '.receiptId' "$TMP/design.receipt")"
mkdir "$TMP/registry"
# Synthetic live-shaped receipt, confined to this disposable test registry.
jq '.probeSource="live" | .transportStub=false' "$TMP/design.receipt" > "$TMP/registry/design.receipt"
run independent plan-critic --capability read-repository --capability independent-family \
  --independence-receipt-dir "$TMP/registry" --independence-receipt-id "$receipt_id"
assert jq -e '.served.model == "gpt-6.1-sol" and .familyIndependence.excludedFamilies == ["anthropic"]' "$TMP/independent.receipt"

before="$(git -C "$TMP/repo" rev-parse HEAD)"
run implementation builder-deep --capability read-repository --capability write-repository --capability tool-use \
  --contract-digest "sha256:$(printf '%064d' 0)" --contract-revision 1
assert jq -e '.served.model == "gpt-6.1-sol" and .transmittedEffort == "high"' "$TMP/implementation.receipt"
assert jq -e 'index("workspace-write") != null' "$QUALITY_ARGV"
assert test "$(git -C "$TMP/repo" rev-parse HEAD)" != "$before"
assert test -z "$(git -C "$TMP/repo" status --porcelain)"

# Unavailable/exhausted Claude falls back to Sol, never Luna for deep work.
healthy
jq '.claude.state="unavailable" | .claude.authMode="none"' "$TMP/availability.json" > "$TMP/next"
mv "$TMP/next" "$TMP/availability.json"
run native-fallback builder-deep --capability read-repository --capability tool-use
assert jq -e '.served.model == "gpt-6.1-sol"' "$TMP/native-fallback.receipt"

run design-fallback design-consultant --capability read-repository --repository-evidence-file "$TMP/evidence"
assert jq -e '.served.model == "gpt-6.1-sol"' "$TMP/design-fallback.receipt"
healthy
jq '.claude.fable="unavailable"' "$TMP/availability.json" > "$TMP/next"
mv "$TMP/next" "$TMP/availability.json"
for role in architect plan-critic review-deep; do
  run "unavailable-$role" "$role" --capability read-repository
  assert jq -e '.served.model == "gpt-6.1-sol" and .attempts[0].outcome == "served"' "$TMP/unavailable-$role.receipt"
done
# Strong judgment starts on Sol and escalates to Astra for a concrete fault.
assert jq -e 'all(.roles | to_entries[] | select(.key | IN("architect","plan-critic","review-deep","builder-deep"));
  .value[0].model == "gpt-6.1-sol" and .value[1].model == "gpt-6-astra")' "$DIR/role-policy.json"
healthy
QUALITY_FAILURE=model run model-fallback architect --capability read-repository
assert jq -e '.served.model == "gpt-6-astra" and .fallback == true' "$TMP/model-fallback.receipt"
: > "$QUALITY_CALLS"
QUALITY_FAILURE=quota run quota-fallback design-consultant --capability read-repository --repository-evidence-file "$TMP/evidence"
assert jq -e '.served.model == "gpt-6.1-sol" and .attempts[0].reason == "quota-exhausted"' "$TMP/quota-fallback.receipt"
assert test "$(cat "$QUALITY_CALLS")" = "$(printf 'claude-opus-5-5\ngpt-6.1-sol')"
QUALITY_SERVED_MODEL=claude-sonnet-5-5 run substituted design-consultant --capability read-repository --repository-evidence-file "$TMP/evidence"
assert jq -e '.served.model == "gpt-6.1-sol" and ([.attempts[] | select(.reason == "provider_model_substitution")] | length) == 1' "$TMP/substituted.receipt"
run fast builder-fast --capability read-repository
assert jq -e '.served.model == "gpt-6-luna" and .served.serviceMode.transmitted == "fast" and .served.serviceMode.confirmed == null' "$TMP/fast.receipt"
assert jq -e 'index("service_tier=\"fast\"") != null and index("--strict-config") != null' "$QUALITY_ARGV"
healthy
for role in architect plan-critic review-deep builder-deep design-consultant; do
  "$DIR/operator-recommendation.sh" --role "$role" --effort high --capability read-repository \
    --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" \
    --availability-file "$TMP/availability.json" --format json > "$TMP/recommend-$role.json"
  case "$role" in
    design-consultant) primary=claude-opus-5-5; fallback=gpt-6.1-sol ;;
    *) primary=gpt-6.1-sol; fallback=gpt-6-astra ;;
  esac
  assert jq -e --arg primary "$primary" --arg fallback "$fallback" \
    '.recommendedStart.model == $primary and .recommendedStart.fallback.model == $fallback' "$TMP/recommend-$role.json"
done
jq '.claude.fable="unavailable"' "$TMP/availability.json" > "$TMP/next"
mv "$TMP/next" "$TMP/availability.json"
"$DIR/operator-recommendation.sh" --role architect --effort high --capability read-repository \
  --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" \
  --availability-file "$TMP/availability.json" --format json > "$TMP/recommend-unavailable.json"
assert jq -e '.recommendedStart.model == "gpt-6.1-sol"' "$TMP/recommend-unavailable.json"
# Narrow Haiku research uses the exact native identity and read tools only.
healthy
run narrow-research research-fast --capability read-repository --capability tool-use --capability structured-output
assert jq -e '.served.model == "claude-haiku-5-5" and .served.servedIdentity == "claude-haiku-5-5" and .served.billingMode == "included-subscription" and .served.billedCostUsd == null and .served.tokens.cache_read_input_tokens == 20' "$TMP/narrow-research.receipt"
assert jq -e '.[index("--tools")+1] == "Read,Glob,Grep" and .[index("--allowedTools")+1] == "Read,Glob,Grep" and index("service_tier=\"fast\"") == null and .[index("--effort")+1] == "high"' "$QUALITY_ARGV"
"$DIR/operator-recommendation.sh" --role research-fast --effort high --capability read-repository --capability tool-use \
  --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" --availability-file "$TMP/availability.json" --format json > "$TMP/haiku-recommend.json"
assert jq -e '.recommendedStart.model == "claude-haiku-5-5" and .recommendedStart.availability == "available" and .recommendedStart.fallback.model == "gpt-6-luna"' "$TMP/haiku-recommend.json"
# Large-context, writing and browser capabilities are not inferred from a host.
run large-research research-fast --capability read-repository --capability long-context
assert jq -e '.served.model == "gpt-6-luna"' "$TMP/large-research.receipt"
run fast-review review-fast --capability read-repository
assert jq -e '.served.model == "gpt-6-luna" and .served.serviceMode.transmitted == "fast"' "$TMP/fast-review.receipt"
# Unknown quota is attemptable; explicit normalized effort reaches Claude unchanged.
healthy
jq '.claude.state="unknown" | .claude.rateLimitsObserved=false' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
for effort in low medium high max; do
  QUALITY_EFFORT="$effort" run "haiku-effort-$effort" research-fast --capability read-repository
  assert jq -e --arg effort "$effort" '.served.availability == "attemptable" and .served.billingMode == "subscription-headroom-unknown" and .transmittedEffort == $effort' "$TMP/haiku-effort-$effort.receipt"
  assert jq -e --arg effort "$effort" '.[index("--effort")+1] == $effort' "$QUALITY_ARGV"
done
healthy
# Confirmed native Claude failure closes one rail/model and survives run reuse.
for code in quota_exceeded model_not_found authentication_failed; do
  QUALITY_CLAUDE_CODE="$code" run "haiku-$code" research-fast --capability read-repository --capability tool-use
  assert jq -e '.served.model == "gpt-6-luna" and .attempts[0].failureConfirmed == true and .attempts[0].processExitStatus == 1' "$TMP/haiku-$code.receipt"
done
# Generic failure text is never a confirmed account diagnosis.
QUALITY_CLAUDE_CODE=unknown run haiku-unknown research-fast --capability read-repository
assert jq -e '.attempts[0].failureConfirmed == false' "$TMP/haiku-unknown.receipt"
jq '.probeSource="live" | .transportStub=false' "$TMP/haiku-quota_exceeded.receipt" > "$TMP/claude-quota.json"
printf '%s\n' '{"schemaVersion":1,"receiptFiles":["claude-quota.json"]}' > "$TMP/terminal-receipt-index.json"
: > "$QUALITY_CALLS"
run reused-claude research-fast --capability read-repository --run-receipt-index "$TMP/terminal-receipt-index.json"
assert jq -e '.served.model == "gpt-6-luna" and .attempts[0].reusedFailure == true' "$TMP/reused-claude.receipt"
assert test "$(cat "$QUALITY_CALLS")" = gpt-6-luna
"$DIR/operator-recommendation.sh" --role research-fast --effort medium --capability read-repository \
  --run-receipt-index "$TMP/terminal-receipt-index.json" --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" --availability-file "$TMP/availability.json" --format json > "$TMP/reused-recommend.json"
assert jq -e '.recommendedStart.model == "gpt-6-luna"' "$TMP/reused-recommend.json"
# Inactive, exhausted and credits-only candidates agree in both projections.
cp "$DIR/role-policy.json" "$TMP/inactive-policy.json"
jq '.roles["research-fast"][0].enabled=false' "$TMP/inactive-policy.json" > "$TMP/inactive-next.json"
"$DIR/operator-recommendation.sh" --role research-fast --effort medium --capability read-repository \
  --policy-file "$TMP/inactive-next.json" --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" --availability-file "$TMP/availability.json" --format json > "$TMP/inactive.json"
assert jq -e '.recommendedStart.model == "gpt-6-luna"' "$TMP/inactive.json"
cp -R "$DIR" "$TMP/inactive-router"
cp "$TMP/inactive-next.json" "$TMP/inactive-router/role-policy.json"
original_dir="$DIR"; DIR="$TMP/inactive-router"
run inactive-dispatch research-fast --capability read-repository
DIR="$original_dir"
assert jq -e '.served.model == "gpt-6-luna" and .fallback == false' "$TMP/inactive-dispatch.receipt"
# A partial snapshot remains unknown, except for a confirmed exhausted window.
healthy
jq '.claude.state="unknown" | del(.claude.weeklyRemainingPct)' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
run partial-research research-fast --capability read-repository
assert jq -e '.served.model == "claude-haiku-5-5" and .served.availability == "attemptable"' "$TMP/partial-research.receipt"
jq '.claude.fiveHourRemainingPct=0' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
run partial-exhausted research-fast --capability read-repository
assert jq -e '.served.model == "gpt-6-luna" and .attempts[0].reason == "rate_limit_exhausted"' "$TMP/partial-exhausted.receipt"
# Reserved positive Claude headroom must never become confirmed exhaustion.
healthy
jq '.claude.state="limited" | .claude.fiveHourRemainingPct=5' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
run reserved-claude research-fast --capability read-repository
assert jq -e '.served.model == "gpt-6-luna" and .attempts[0].reason == "reserve_threshold_reached" and .attempts[0].failureConfirmed != true' "$TMP/reserved-claude.receipt"
# An observed zero outranks a reserved sibling, including aggregate limited state.
for state in unknown limited; do
  healthy
  jq --arg state "$state" '.claude.state=$state | .claude.fiveHourRemainingPct=5 | .claude.weeklyRemainingPct=0' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
  run "mixed-quota-$state" research-fast --capability read-repository
  assert jq -e '.served.model == "gpt-6-luna" and .attempts[0].reason == "rate_limit_exhausted"' "$TMP/mixed-quota-$state.receipt"
done
for state in exhausted limited unavailable; do
  healthy
  jq --arg state "$state" '.claude.state=$state' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
  run "haiku-$state" research-fast --capability read-repository
  assert jq -e '.served.model == "gpt-6-luna" and .attempts[0].outcome == "skipped"' "$TMP/haiku-$state.receipt"
  "$DIR/operator-recommendation.sh" --role research-fast --effort medium --capability read-repository \
    --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" --availability-file "$TMP/availability.json" --format json > "$TMP/recommend-$state.json"
  assert jq -e '.recommendedStart.model == "gpt-6-luna"' "$TMP/recommend-$state.json"
done
healthy
jq '.claude.plan="credits-only" | .claude.paidCreditsEnabled=true' "$TMP/availability.json" > "$TMP/next"; mv "$TMP/next" "$TMP/availability.json"
run haiku-no-paid research-fast --capability read-repository
assert jq -e '.served.model == "gpt-6-luna"' "$TMP/haiku-no-paid.receipt"
"$DIR/operator-recommendation.sh" --role research-fast --effort medium --capability read-repository \
  --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" --availability-file "$TMP/availability.json" --format json > "$TMP/no-paid.json"
assert jq -e '.recommendedStart.model == "gpt-6-luna"' "$TMP/no-paid.json"

printf 'model-router-quality: %d assertions passed\n' "$pass"
