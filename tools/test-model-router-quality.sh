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
jq -cn --arg model "${QUALITY_SERVED_MODEL:-$model}" '{model:$model,result:"bounded result"}'
STUB
cat > "$TMP/codex" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
model=""; output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --output-last-message) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '%s\n' "$model" >> "$QUALITY_CALLS"
cat >/dev/null
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
    --role "$role" --effort high --prompt-file "$TMP/prompt" \
    --output-file "$TMP/$name.out" --receipt-file "$TMP/$name.receipt" "$@") > "$TMP/$name.public"
}

healthy
for role in architect plan-critic review-deep; do
  run "$role" "$role" --capability read-repository --capability tool-use
  assert jq -e '.served.model == "fable" and .served.servedIdentity == "claude-fable-5" and .normalizedEffort == "high"' "$TMP/$role.receipt"
  assert jq -e '.[index("--tools")+1] == "Read,Glob,Grep" and (index("--dangerously-skip-permissions") == null)' "$QUALITY_ARGV"
done
# A requested independent critic excludes both Claude candidates and uses Sol.
receipt_id="$(jq -r '.receiptId' "$TMP/architect.receipt")"
mkdir "$TMP/registry"
# Synthetic live-shaped receipt, confined to this disposable test registry.
jq '.probeSource="live" | .transportStub=false' "$TMP/architect.receipt" > "$TMP/registry/architect.receipt"
run independent plan-critic --capability read-repository --capability independent-family \
  --independence-receipt-dir "$TMP/registry" --independence-receipt-id "$receipt_id"
assert jq -e '.served.model == "gpt-6-astra" and .familyIndependence.excludedFamilies == ["anthropic"]' "$TMP/independent.receipt"

run design design-consultant --capability read-repository --repository-evidence-file "$TMP/evidence"
assert jq -e '.served.model == "claude-opus-5-5"' "$TMP/design.receipt"
assert jq -e '.[index("--tools")+1] == ""' "$QUALITY_ARGV"

before="$(git -C "$TMP/repo" rev-parse HEAD)"
run implementation builder-deep --capability read-repository --capability write-repository --capability tool-use \
  --contract-digest "sha256:$(printf '%064d' 0)" --contract-revision 1
assert jq -e '.served.model == "claude-opus-5-5" and .transmittedEffort == "high"' "$TMP/implementation.receipt"
assert jq -e '.[index("--tools")+1] == "Read,Glob,Grep,Edit,Write,Bash" and .[index("--allowedTools")+1] == "Read,Glob,Grep,Edit,Write,Bash"' "$QUALITY_ARGV"
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
  assert jq -e '.served.model == "gpt-6-astra" and .attempts[0].outcome == "skipped"' "$TMP/unavailable-$role.receipt"
done
# Each configured pair remains adjacent in every role that uses its primary.
assert jq -e 'all(.roles[]; . as $rows | all(range(0; length); . as $i |
  if $rows[$i].model == "fable" then $rows[$i+1].model == "gpt-6-astra"
  elif $rows[$i].model == "claude-opus-5-5" then $rows[$i+1].model == "gpt-6.1-sol"
  else true end))' "$DIR/role-policy.json"

healthy
QUALITY_FAILURE=model run model-fallback architect --capability read-repository
assert jq -e '.served.model == "gpt-6-astra" and .fallback == true' "$TMP/model-fallback.receipt"
: > "$QUALITY_CALLS"
QUALITY_FAILURE=quota run quota-fallback architect --capability read-repository
assert jq -e '.served.model == "gpt-6-astra" and (.attempts[0].reason == "rate_limit_exhausted" or .attempts[0].reason == "quota-exhausted")' "$TMP/quota-fallback.receipt"
assert test "$(cat "$QUALITY_CALLS")" = "$(printf 'fable\ngpt-6-astra')"

# Exact design identity stays mandatory; other Claude lanes also reject substitution.
QUALITY_SERVED_MODEL=claude-sonnet-5-5 run substituted architect --capability read-repository
assert jq -e '.served.model == "gpt-6-astra" and ([.attempts[] | select(.reason == "provider_model_substitution")] | length) == 1' "$TMP/substituted.receipt"
run fast builder-fast --capability read-repository
assert jq -e '.served.model == "gpt-6-luna"' "$TMP/fast.receipt"
assert jq -e 'all(.roles[][] | select(.model == "fable"); (.capabilities | index("write-repository") | not))' "$DIR/role-policy.json"
healthy
for role in architect plan-critic review-deep builder-deep design-consultant; do
  "$DIR/operator-recommendation.sh" --role "$role" --effort high --capability read-repository \
    --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" \
    --availability-file "$TMP/availability.json" --format json > "$TMP/recommend-$role.json"
  case "$role" in
    builder-deep|design-consultant) primary=claude-opus-5-5; fallback=gpt-6.1-sol ;;
    *) primary=fable; fallback=gpt-6-astra ;;
  esac
  assert jq -e --arg primary "$primary" --arg fallback "$fallback" \
    '.recommendedStart.model == $primary and .recommendedStart.fallback.model == $fallback' "$TMP/recommend-$role.json"
done
jq '.claude.fable="unavailable"' "$TMP/availability.json" > "$TMP/next"
mv "$TMP/next" "$TMP/availability.json"
"$DIR/operator-recommendation.sh" --role architect --effort high --capability read-repository \
  --matrix-file "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json" \
  --availability-file "$TMP/availability.json" --format json > "$TMP/recommend-unavailable.json"
assert jq -e '.recommendedStart.model == "gpt-6-astra"' "$TMP/recommend-unavailable.json"
printf 'model-router-quality: %d assertions passed\n' "$pass"
