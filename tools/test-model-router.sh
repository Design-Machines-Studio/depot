#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROUTER="$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh"
PROBE="$ROOT/plugins/model-router/skills/model-router/references/availability-probe.sh"
FIXTURES="$ROOT/plugins/model-router/skills/model-router/tests/availability-fixtures.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/model-router-tests.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

fixture() {
  jq --arg name "$1" '.[$name]' "$FIXTURES" > "$TMP/availability.json"
}

cat > "$TMP/transport-stub" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
model=""; output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --output-file) output="$2"; shift 2 ;;
    *) shift 2 ;;
  esac
done
outcome="$(jq -r --arg model "$model" '.candidateResults[$model].outcome // "success"' "$MODEL_ROUTER_AVAILABILITY_FILE")"
case "$outcome" in
  success) printf 'bounded role output\n' > "$output" ;;
  quota) printf 'quota exhausted\n' >&2; exit 77 ;;
  disclosure-declined) printf 'disclosure declined\n' >&2; exit 77 ;;
  *) printf 'transport unavailable\n' >&2; exit 77 ;;
esac
STUB
chmod +x "$TMP/transport-stub"
printf 'review the supplied evidence\n' > "$TMP/prompt"

# Probe subscription authentication and separately reported noninteractive
# allowance windows using local CLI stubs. No model or paid API call occurs.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/codex" <<'STUB'
#!/usr/bin/env bash
case "${1:-}:${2:-}" in
  login:status) printf '%s\n' 'Logged in using ChatGPT' ;;
  app-server:--stdio)
    printf '%s\n' '{"id":7,"result":{"rateLimits":{"primary":{"usedPercent":20,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}}}}'
    ;;
  *) exit 1 ;;
esac
STUB
cat > "$TMP/bin/claude" <<'STUB'
#!/usr/bin/env bash
case "${FAKE_CLAUDE_AUTH:-subscription}" in
  subscription) printf '%s\n' '{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"max"}' ;;
  api) printf '%s\n' '{"loggedIn":true,"authMethod":"apiKey"}' ;;
  *) printf '%s\n' '{"loggedIn":false,"authMethod":"none"}' ;;
esac
STUB
chmod +x "$TMP/bin/codex" "$TMP/bin/claude"
cat > "$TMP/claude-telemetry.json" <<'JSON'
{"plan":"max","fable":"available","rate_limits":{"five_hour":{"used_percentage":95},"seven_day":{"used_percentage":95},"agent_sdk":{"five_hour":{"used_percentage":20},"seven_day":{"used_percentage":30}}}}
JSON
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=subscription \
  MODEL_ROUTER_CLAUDE_RATE_LIMITS_FILE="$TMP/claude-telemetry.json" \
  "$PROBE" > "$TMP/probe-subscription.json"
if [ "${MODEL_ROUTER_TEST_DEBUG:-0}" = 1 ]; then jq . "$TMP/probe-subscription.json"; fi
assert jq -e '.codex.authMode == "subscription" and .codex.state == "ok" and .claude.authMode == "subscription" and .claude.agentSdkRateLimitsObserved == true and .claude.allowances.agent_sdk.state == "ok"' "$TMP/probe-subscription.json"
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=subscription "$PROBE" > "$TMP/probe-no-telemetry.json"
assert jq -e '.claude.authMode == "subscription" and .claude.plan == "max" and .claude.state == "unknown" and .claude.rateLimitsObserved == false' "$TMP/probe-no-telemetry.json"
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=api "$PROBE" > "$TMP/probe-api.json"
assert jq -e '.claude.authMode == "api" and .claude.authMode != "subscription"' "$TMP/probe-api.json"
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=none "$PROBE" > "$TMP/probe-unauth.json"
assert jq -e '.claude.state == "unavailable" and .claude.authMode != "subscription"' "$TMP/probe-unauth.json"

run_role() {
  local name="$1" role="$2" effort="$3"; shift 3
  rm -f "$TMP/$name.out" "$TMP/$name.receipt" "$TMP/$name.public"
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    "$ROUTER" --role "$role" --effort "$effort" \
      --prompt-file "$TMP/prompt" --output-file "$TMP/$name.out" \
      --receipt-file "$TMP/$name.receipt" "$@" > "$TMP/$name.public"
}

# Fast work resolves externally while the public surface stays anonymous.
fixture healthy
run_role fast builder-fast low --capability read-repository --capability write-repository --capability structured-output
assert jq -e '.role == "builder-fast" and (.participantId | test("^participant-[a-f0-9]{8}$")) and .disposition == "completed"' "$TMP/fast.public"
assert sh -c "! grep -Eq 'deepseek|openrouter|gpt-5|fable|kimi|qwen|grok' '$TMP/fast.public'"

# Deep work prefers healthy native subscription capacity.
run_role deep builder-deep high --capability read-repository --capability tool-use
assert jq -e '.served.transport == "codex-cli" and .served.billingMode == "included-subscription"' "$TMP/deep.receipt"

# Exhausted Codex descends without an approval prompt.
fixture codex-exhausted
run_role deep-fallback builder-deep high --capability read-repository --capability long-context
assert jq -e '.served.transport == "openrouter" and .fallback == true' "$TMP/deep-fallback.receipt"

# A current quota response exhausts the native rail for this run; it is not
# retried under a second model alias.
fixture healthy
jq '.candidateResults["gpt-5.6-sol"].outcome="quota"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role quota-fallback builder-deep high --capability read-repository --capability long-context
assert jq -e '.served.transport == "openrouter" and ([.attempts[].model] | index("gpt-5.6-terra") == null)' "$TMP/quota-fallback.receipt"

# Two eligible operators receive identical Fable behavior from one policy.
fixture healthy
run_role architect-a architect max --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "included-subscription"' "$TMP/architect-a.receipt"
fixture second-eligible-operator
run_role architect-b architect max --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "included-subscription"' "$TMP/architect-b.receipt"

# Exhausted and initially unobservable Fable are distinct.
fixture fable-exhausted
run_role fable-fallback architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .fallback == true' "$TMP/fable-fallback.receipt"
# Fable-specific exhaustion does not suppress a distinct Claude model after
# the intervening native Codex rail is unavailable.
jq '.codex.state="exhausted"
  | .codex.windows.five_hour.remaining_pct=0
  | .codex.windows.weekly.remaining_pct=0
  | .claude.fiveHourRemainingPct=80
  | .claude.weeklyRemainingPct=70' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role opus-fallback architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.transport == "claude-cli" and .fallback == true' "$TMP/opus-fallback.receipt"
fixture fable-initial-telemetry-absent
run_role fable-bounded architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "subscription-headroom-unknown"' "$TMP/fable-bounded.receipt"
fixture fable-agent-sdk-capacity
run_role fable-sdk architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "included-subscription" and .served.allowanceWindow == "agent-sdk"' "$TMP/fable-sdk.receipt"

# Credits, unauthenticated, and API-key states never masquerade as included use.
fixture credits-disabled
run_role credits-off architect high --capability read-repository --capability structured-output
assert jq -e '.served.model != "fable"' "$TMP/credits-off.receipt"
fixture credits-enabled
run_role credits-on architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "paid-credits"' "$TMP/credits-on.receipt"
fixture claude-api-key
run_role api-key architect high --capability read-repository --capability structured-output
assert jq -e '.served.model != "fable" and .served.transport == "codex-cli"' "$TMP/api-key.receipt"
fixture claude-unauthenticated
run_role unauth architect high --capability read-repository --capability structured-output
assert jq -e '.served.model != "fable"' "$TMP/unauth.receipt"

# Security head identity stays private.
fixture healthy
run_role security security-review high --capability read-repository --capability structured-output
assert jq -e '.served.model == "moonshotai/kimi-k3"' "$TMP/security.receipt"
assert sh -c "! grep -Eq 'kimi|moonshot|openrouter|deepseek|gpt-5|fable|qwen|grok' '$TMP/security.public'"

# Opaque receipts exclude every implementing family.
run_role implementer builder-deep high --capability read-repository
implementer_id="$(jq -r '.receiptId' "$TMP/implementer.receipt")"
run_role independent plan-critic high --capability read-repository --capability independent-family --independence-receipt-id "$implementer_id"
assert jq -e '.familyIndependence.required == true and .familyIndependence.passed == true and (.served.family != "openai")' "$TMP/independent.receipt"
assert jq -e '.participantId | test("^planner-[a-f0-9]{8}$")' "$TMP/independent.public"
assert sh -c "! grep -Eq 'openai|qwen|deepseek|grok|anthropic|moonshot|openrouter|gpt-5|fable|kimi' '$TMP/independent.public'"

# Disclosure decline follows the role ladder with no prompt.
fixture healthy
jq '.candidateResults["qwen/qwen3.8-max"].outcome="disclosure-declined"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role disclosure plan-critic high --capability read-repository --capability structured-output
assert jq -e '.fallback == true and .fallbackReason == "disclosure-declined" and .served.model == "deepseek/deepseek-v4-pro-0813"' "$TMP/disclosure.receipt"

# Receipts are exact/content-free; public and peer surfaces remain identity-free.
assert jq -e '.requested.role and .requested.candidate.model and .effectiveEffort and .participantId and .attempts and .served.model and .served.provider and .served.transport and .served.billingMode and (.served.durationSeconds|type=="number") and (.served.tokenProvenance=="unavailable") and (.served.costProvenance=="unavailable") and .matrixSnapshot and (.fallbackReason|type=="string")' "$TMP/disclosure.receipt"
assert sh -c "! grep -Eq 'prompt|bounded role output' '$TMP/disclosure.receipt'"

printf 'model-router: %d assertions passed\n' "$pass"
