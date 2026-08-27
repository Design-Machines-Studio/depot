#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROUTER="$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh"
PROBE="$ROOT/plugins/model-router/skills/model-router/references/availability-probe.sh"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
FIXTURES="$ROOT/plugins/model-router/skills/model-router/tests/availability-fixtures.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/model-router-tests.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export MODEL_ROUTER_TEST_MODE=1

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

fixture() {
  jq --arg name "$1" '.[$name]' "$FIXTURES" > "$TMP/availability.json"
}

cat > "$TMP/transport-stub" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
model=""; output=""; provider_receipt=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --model) model="$2"; shift 2 ;;
    --output-file) output="$2"; shift 2 ;;
    --provider-receipt-file) provider_receipt="$2"; shift 2 ;;
    *) shift 2 ;;
  esac
done
if [ -n "${MODEL_ROUTER_STUB_CALL_LOG:-}" ]; then
  printf '%s\n' "$model" >> "$MODEL_ROUTER_STUB_CALL_LOG"
fi
if [ -n "${MODEL_ROUTER_AVAILABILITY_FILE:-}" ]; then
  outcome="$(jq -r --arg model "$model" '.candidateResults[$model].outcome // "success"' "$MODEL_ROUTER_AVAILABILITY_FILE")"
else
  outcome=success
fi
if [ -n "${MODEL_ROUTER_EXPECT_PUBLICATION_DIR:-}" ]; then
  set -- "$MODEL_ROUTER_EXPECT_PUBLICATION_DIR"/.model-router-output.*
  [ -e "$1" ] || exit 78
  set -- "$MODEL_ROUTER_EXPECT_PUBLICATION_DIR"/.model-router-receipt.*
  [ -e "$1" ] || exit 78
fi
case "$outcome" in
  success) printf 'bounded role output\n' > "$output" ;;
  quota) printf 'quota exhausted\n' >&2; exit 77 ;;
  content-refusal) printf 'model content refusal\n' >&2; exit 77 ;;
  mutate-fail)
    printf '%s\n' 'mutated by failed writer' > "$MODEL_ROUTER_STUB_MUTATE_PATH"
    printf '%s\n' 'transport unavailable' >&2
    exit 77
    ;;
  commit-success)
    printf '%s\n' 'committed by successful writer' > "$MODEL_ROUTER_STUB_MUTATE_PATH"
    git add -- "$MODEL_ROUTER_STUB_MUTATE_PATH"
    git -c user.name=test -c user.email=test@example.invalid commit -qm 'fixture writer commit'
    commit="$(git rev-parse HEAD)"
    printf 'bounded role output\n' > "$output"
    jq -n --arg commit "$commit" '{commit:$commit,filesChanged:"tracked.txt"}' > "$provider_receipt"
    ;;
  *) printf 'transport unavailable\n' >&2; exit 77 ;;
esac
[ -z "${MODEL_ROUTER_STUB_PROVIDER_RECEIPT:-}" ] || cp "$MODEL_ROUTER_STUB_PROVIDER_RECEIPT" "$provider_receipt"
if [ -n "${MODEL_ROUTER_REMOVE_PUBLICATION_DIR:-}" ]; then
  rm -f "$MODEL_ROUTER_REMOVE_PUBLICATION_DIR"/.model-router-output.* \
    "$MODEL_ROUTER_REMOVE_PUBLICATION_DIR"/.model-router-receipt.*
  rmdir "$MODEL_ROUTER_REMOVE_PUBLICATION_DIR"
fi
STUB
chmod +x "$TMP/transport-stub"
printf 'review the supplied evidence\n' > "$TMP/prompt"
printf 'complete repository evidence\n' > "$TMP/evidence"

# Production dispatch rejects every fixture hook unless test mode is explicit.
fixture healthy
for fixture_hook in MODEL_ROUTER_AVAILABILITY_FILE MODEL_ROUTER_TRANSPORT_STUB MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS; do
  case "$fixture_hook" in
    MODEL_ROUTER_AVAILABILITY_FILE) fixture_value="$TMP/availability.json" ;;
    MODEL_ROUTER_TRANSPORT_STUB) fixture_value="$TMP/transport-stub" ;;
    *) fixture_value=1 ;;
  esac
  set +e
  env -u MODEL_ROUTER_TEST_MODE "$fixture_hook=$fixture_value" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort low --capability structured-output \
      --prompt-file "$TMP/prompt" --output-file "$TMP/no-test-mode.out" \
      --receipt-file "$TMP/no-test-mode.receipt" >/dev/null 2>&1
  no_test_mode_rc=$?
  set -e
  assert test "$no_test_mode_rc" -eq 2
done

# Probe subscription authentication and separately reported noninteractive
# allowance windows using local CLI stubs. No model or paid API call occurs.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/codex" <<'STUB'
#!/usr/bin/env bash
case "${1:-}:${2:-}" in
  login:status) printf '%s\n' 'Logged in using ChatGPT' ;;
  app-server:--stdio)
    initialized=0
    while IFS= read -r request; do
      method="$(printf '%s' "$request" | jq -r '.method // empty')"
      [ -z "${MODEL_ROUTER_CODEX_RPC_LOG:-}" ] || printf '%s\n' "$method" >> "$MODEL_ROUTER_CODEX_RPC_LOG"
      case "$method" in
        initialize)
          [ "${MODEL_ROUTER_CODEX_FIXTURE:-legacy}" = init-no-response ] ||
            printf '%s\n' '{"id":0,"result":{"serverInfo":{"name":"fixture"}}}'
          ;;
        initialized) initialized=1 ;;
        account/rateLimits/read)
          [ "$initialized" -eq 1 ] || exit 91
          case "${MODEL_ROUTER_CODEX_FIXTURE:-legacy}" in
            rate-no-response) : ;;
            legacy)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"primary":{"usedPercent":20,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}}}}'
              ;;
            v147)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex","primary":null,"secondary":{"usedPercent":25,"windowDurationMins":10080}},"rateLimitsByLimitId":{"codex":{"limitId":"codex","limitName":null,"primary":null,"secondary":{"usedPercent":25,"windowDurationMins":10080}},"codex_named":{"limitId":"codex_named","limitName":"Named","primary":{"usedPercent":20,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}},"codex_other":{"limitId":"codex_other","limitName":"Other","primary":{"usedPercent":95,"windowDurationMins":300},"secondary":{"usedPercent":95,"windowDurationMins":10080}}}}}'
              ;;
            exhausted)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex","primary":null,"secondary":{"usedPercent":25,"windowDurationMins":10080}},"rateLimitsByLimitId":{"codex":{"limitId":"codex","primary":{"usedPercent":95,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}}}}}'
              ;;
            multiple-no-best)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex","primary":null,"secondary":{"usedPercent":25,"windowDurationMins":10080}},"rateLimitsByLimitId":{"codex":{"limitId":"codex","primary":{"usedPercent":95,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}},"codex_other":{"limitId":"codex_other","limitName":"Other","primary":{"usedPercent":1,"windowDurationMins":300},"secondary":{"usedPercent":1,"windowDurationMins":10080}}}}}'
              ;;
            all-exhausted)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex"},"rateLimitsByLimitId":{"codex":{"limitId":"codex","primary":{"usedPercent":95,"windowDurationMins":300},"secondary":{"usedPercent":95,"windowDurationMins":10080}},"codex_other":{"limitId":"codex_other","primary":{"usedPercent":96,"windowDurationMins":300},"secondary":{"usedPercent":97,"windowDurationMins":10080}}}}}'
              ;;
            unknown-mapping)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex","primary":null,"secondary":{"usedPercent":25,"windowDurationMins":10080}},"rateLimitsByLimitId":{"codex_other":{"limitId":"codex_other","limitName":"Other","primary":{"usedPercent":20,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}},"codex_extra":{"limitId":"codex_extra","limitName":"Extra","primary":{"usedPercent":20,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}}}}}'
              ;;
            malformed-map)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex"},"rateLimitsByLimitId":{"codex":{"limitId":"wrong","primary":{"usedPercent":20,"windowDurationMins":300},"secondary":{"usedPercent":25,"windowDurationMins":10080}}}}}'
              ;;
            unsupported)
              printf '%s\n' '{"id":7,"result":{"futureLimits":{}}}'
              ;;
            missing-window)
              printf '%s\n' '{"id":7,"result":{"rateLimits":{"limitId":"codex"},"rateLimitsByLimitId":{"codex":{"limitId":"codex","primary":null,"secondary":{"usedPercent":25,"windowDurationMins":10080}}}}}'
              ;;
          esac
          ;;
      esac
    done
    ;;
  exec:*)
    output=""
    while [ "$#" -gt 0 ]; do
      case "$1" in --output-last-message) output="$2"; shift 2 ;; *) shift ;; esac
    done
    printf 'api=%s,file=%s\n' "${OPENROUTER_API_KEY-unset}" "${OPENROUTER_API_KEY_FILE-unset}" > "$MODEL_ROUTER_NATIVE_ENV_CAPTURE"
    if [ -n "${MODEL_ROUTER_NATIVE_PROMPT_CAPTURE:-}" ]; then cat > "$MODEL_ROUTER_NATIVE_PROMPT_CAPTURE"; else cat >/dev/null; fi
    printf 'native codex output\n' > "$output"
    ;;
  *) exit 1 ;;
esac
STUB
cat > "$TMP/bin/claude" <<'STUB'
#!/usr/bin/env bash
if [ "${1:-}" = -p ]; then
  printf 'api=%s,file=%s\n' "${OPENROUTER_API_KEY-unset}" "${OPENROUTER_API_KEY_FILE-unset}" > "$MODEL_ROUTER_NATIVE_ENV_CAPTURE"
  if [ -n "${MODEL_ROUTER_NATIVE_PROMPT_CAPTURE:-}" ]; then cat > "$MODEL_ROUTER_NATIVE_PROMPT_CAPTURE"; else cat >/dev/null; fi
  printf '%s\n' '{"result":"native claude output"}'
  exit 0
fi
case "${FAKE_CLAUDE_AUTH:-subscription}" in
  subscription) printf '%s\n' '{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"max"}' ;;
  pro) printf '%s\n' '{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"pro"}' ;;
  future) printf '%s\n' '{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"future-tier"}' ;;
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
  MODEL_ROUTER_CODEX_FIXTURE=legacy MODEL_ROUTER_CODEX_RPC_LOG="$TMP/codex-rpc.log" \
  MODEL_ROUTER_CLAUDE_RATE_LIMITS_FILE="$TMP/claude-telemetry.json" \
  "$PROBE" > "$TMP/probe-subscription.json"
if [ "${MODEL_ROUTER_TEST_DEBUG:-0}" = 1 ]; then jq . "$TMP/probe-subscription.json"; fi
assert jq -e '.codex.authMode == "subscription" and .codex.state == "ok" and .claude.authMode == "subscription" and .claude.agentSdkRateLimitsObserved == true and .claude.allowances.agent_sdk.state == "ok"' "$TMP/probe-subscription.json"
assert test "$(sed -n '1p' "$TMP/codex-rpc.log")" = initialize
assert test "$(sed -n '2p' "$TMP/codex-rpc.log")" = initialized
assert test "$(sed -n '3p' "$TMP/codex-rpc.log")" = account/rateLimits/read

# Codex 0.147 normalizes every structurally valid bucket. The incomplete
# backward-compatible default window is non-applicable, and multiple buckets
# stay unmapped unless policy has authoritative candidate metadata.
for codex_fixture in v147 exhausted multiple-no-best all-exhausted unknown-mapping malformed-map unsupported missing-window; do
  MODEL_ROUTER_CODEX_FIXTURE="$codex_fixture" MODEL_ROUTER_CODEX_RPC_TIMEOUT=2 \
    env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE PATH="$TMP/bin:$PATH" \
    FAKE_CLAUDE_AUTH=none "$PROBE" > "$TMP/probe-$codex_fixture.json"
done
if [ "${MODEL_ROUTER_TEST_DEBUG:-0}" = 1 ]; then
  jq . "$TMP"/probe-v147.json "$TMP"/probe-exhausted.json \
    "$TMP"/probe-unknown-mapping.json "$TMP"/probe-malformed-map.json
fi
assert jq -e '.codex.state == "unknown" and .codex.reason == "rate_limit_mapping_unknown" and .codex.allowances.codex.reason == "required_window_missing" and .codex.allowances.codex_named.state == "ok"' "$TMP/probe-v147.json"
assert jq -e '.codex.state == "limited" and .codex.reason == "rate_limit_exhausted"' "$TMP/probe-exhausted.json"
assert jq -e '.codex.state == "unknown" and .codex.reason == "rate_limit_mapping_unknown" and .codex.allowances.codex.state == "limited" and .codex.allowances.codex_other.state == "ok"' "$TMP/probe-multiple-no-best.json"
assert jq -e '.codex.state == "limited" and .codex.reason == "rate_limit_exhausted" and all(.codex.allowances[]; .state == "limited")' "$TMP/probe-all-exhausted.json"
assert jq -e '.codex.state == "unknown" and .codex.reason == "rate_limit_mapping_unknown" and (has("defaultAllowanceId") | not)' "$TMP/probe-unknown-mapping.json"
assert jq -e '.codex.state == "unknown" and .codex.reason == "rate_limit_response_malformed"' "$TMP/probe-malformed-map.json"
assert jq -e '.codex.state == "unknown" and .codex.reason == "rate_limit_shape_unsupported"' "$TMP/probe-unsupported.json"
assert jq -e '.codex.state == "unknown" and .codex.reason == "required_window_missing"' "$TMP/probe-missing-window.json"

for codex_fixture in init-no-response rate-no-response; do
  started_at="$(date +%s)"
  MODEL_ROUTER_CODEX_FIXTURE="$codex_fixture" MODEL_ROUTER_CODEX_RPC_TIMEOUT=2 \
    env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE PATH="$TMP/bin:$PATH" \
    FAKE_CLAUDE_AUTH=none "$PROBE" > "$TMP/probe-$codex_fixture.json"
  elapsed=$(( $(date +%s) - started_at ))
  assert test "$elapsed" -lt 8
  assert jq -e '.codex.state == "unknown" and .codex.reason == "rate_limit_probe_no_response"' "$TMP/probe-$codex_fixture.json"
done

# Probe output and downstream receipts expose only normalized state/reasons,
# never raw account payloads or exact quota balances.
jq -c '.codex' "$TMP/probe-v147.json" > "$TMP/probe-v147-codex.json"
assert sh -c "! grep -Eq 'usedPercent|remaining_pct|resetsAt|limitName' '$TMP/probe-v147-codex.json'"
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=subscription "$PROBE" > "$TMP/probe-no-telemetry.json"
assert jq -e '.claude.authMode == "subscription" and .claude.plan == "max" and .claude.state == "unknown" and .claude.rateLimitsObserved == false' "$TMP/probe-no-telemetry.json"
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=pro "$PROBE" > "$TMP/probe-pro.json"
assert jq -e '.claude.authMode == "subscription" and .claude.plan == "pro" and .claude.state == "unknown"' "$TMP/probe-pro.json"
env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
  PATH="$TMP/bin:$PATH" FAKE_CLAUDE_AUTH=future "$PROBE" > "$TMP/probe-future.json"
assert jq -e '.claude.authMode == "subscription" and .claude.plan == "unknown" and .claude.state == "unknown"' "$TMP/probe-future.json"
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
    "$ROUTER" --workflow-kernel "$KERNEL" --role "$role" --effort "$effort" \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/$name.out" --receipt-file "$TMP/$name.receipt" \
      --contract-digest "sha256:$(printf 'a%.0s' {1..64})" --contract-revision 1 \
      "$@" > "$TMP/$name.public"
}

# The dispatcher owns one invocation-local Kernel and OpenRouter binding. A
# fake coherent bundle proves the no-inherited-variable path and closed causes
# without contacting a paid provider.
FAKE_HOME="$TMP/fake-home"
FAKE_BUNDLE="$FAKE_HOME/.codex/plugins/cache/depot/openrouter/1.19.1"
FAKE_REFS="$FAKE_BUNDLE/skills/openrouter-delegate/references"
mkdir -p "$FAKE_REFS" "$TMP/fake-kernel"
cat > "$TMP/fake-kernel/workflow-kernel-launcher.sh" <<'STUB'
#!/usr/bin/env bash
if [ "${FAKE_KERNEL_OUTCOME:-ok}" = unavailable ]; then exit 4; fi
printf '%s\n' '{"selected_root":"~/.codex/plugins/cache/depot/openrouter/1.19.1","version":"1.19.1","cache_class":"codex","reason":"active-host"}'
STUB
cat > "$FAKE_REFS/delegation-boundary.sh" <<'STUB'
#!/usr/bin/env bash
dirname "${BASH_SOURCE[0]}" >> "$FAKE_BUNDLE_LOG"
[ "${FAKE_BOUNDARY_OUTCOME:-allow}" = allow ]
STUB
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-credential.sh" \
  "$FAKE_REFS/openrouter-credential.sh"
cat > "$FAKE_REFS/openrouter-wrapper.sh" <<'STUB'
#!/usr/bin/env bash
set -u
refs="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf '%s\n' "$refs" >> "$FAKE_BUNDLE_LOG"
. "$refs/openrouter-credential.sh"
OPENROUTER_API_KEY=test
export OPENROUTER_API_KEY
load_openrouter_api_key
cat >/dev/null
case "${FAKE_PROVIDER_OUTCOME:-success}" in
  success)
    printf '%s\n' '{"outcome":"success","usage":{"prompt_tokens":1,"completion_tokens":1},"costUsd":0.000001}' > "$OPENROUTER_RECEIPT_FILE"
    printf '%s\n' 'bounded provider output'
    ;;
  model)
    printf '%s\n' '{"outcome":"error","failureKind":"http_error","failureReason":"unknown_http_error","httpStatus":404}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  permission)
    printf '%s\n' '{"outcome":"error","failureKind":"http_error","failureReason":"key_permission_denied","httpStatus":403}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  budget)
    printf '%s\n' '{"outcome":"error","failureKind":"http_error","failureReason":"organization_monthly_budget_exceeded","httpStatus":403}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  credits)
    printf '%s\n' '{"outcome":"error","failureKind":"http_error","failureReason":"insufficient_credits","httpStatus":402}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  rate)
    printf '%s\n' '{"outcome":"error","failureKind":"http_error","failureReason":"rate_limited","httpStatus":429}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  unknown)
    printf '%s\n' '{"outcome":"error","failureKind":"http_error","failureReason":"unknown_http_error","httpStatus":500}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  transport)
    printf '%s\n' '{"outcome":"error","failureKind":"transport_error","failureReason":null}' > "$OPENROUTER_RECEIPT_FILE"
    exit 1
    ;;
  *) exit 90 ;;
esac
STUB
printf '%s\n' '{"schemaVersion":2,"disclosureControls":{"providerInputParity":true},"executionControls":{},"delegationModes":{},"reviewControls":{}}' > "$FAKE_REFS/delegation-security-policy.json"
chmod +x "$TMP/fake-kernel/workflow-kernel-launcher.sh" "$FAKE_REFS/delegation-boundary.sh" "$FAKE_REFS/openrouter-wrapper.sh"

# A strict key-file load leaves OPENROUTER_API_KEY_FILE set. The successfully
# loaded key is nevertheless available to the probe and must not be reported as
# a missing credential.
printf '%s\n' test > "$TMP/key-file"
chmod 600 "$TMP/key-file"
curl() { printf '%s\n' '{"data":{"total_credits":10,"total_usage":1}}'; }
export -f curl
key_file_probe="$(env PATH=/usr/bin:/bin HOME="$FAKE_HOME" \
  OPENROUTER_API_KEY_FILE="$TMP/key-file" OPENROUTER_BUNDLE_RESOLVED=1 \
  OPENROUTER_BUNDLE_REF='~/.codex/plugins/cache/depot/openrouter/1.19.1' \
  "$PROBE")"
unset -f curl
assert test "$(printf '%s' "$key_file_probe" | jq -r '.openrouter.state')" = ok
assert test "$(printf '%s' "$key_file_probe" | jq -r '.openrouter.reason')" = available

# The probe binds the same credential loader as the wrapper. A raw key wins
# without reading a lower-precedence invalid file, and neither fixture value is
# emitted in normalized availability evidence.
curl() { printf '%s\n' '{"data":{"total_credits":10,"total_usage":1}}'; }
export -f curl
both_probe="$(env PATH=/usr/bin:/bin HOME="$FAKE_HOME" \
  OPENROUTER_API_KEY=test OPENROUTER_API_KEY_FILE="$TMP/does-not-exist" \
  OPENROUTER_BUNDLE_RESOLVED=1 \
  OPENROUTER_BUNDLE_REF='~/.codex/plugins/cache/depot/openrouter/1.19.1' \
  "$PROBE")"
unset -f curl
assert test "$(printf '%s' "$both_probe" | jq -r '.openrouter.state')" = ok
assert sh -c "! printf '%s' '$both_probe' | grep -Eq 'OPENROUTER_API_KEY|does-not-exist|Bearer test'"

# role-dispatch resolves native CLIs before fixing PATH. The child availability
# probe must receive those exact paths or the healthy unattributed allowance is
# misreported as mapping-unknown and the real Codex attempt is skipped.
curl() { printf '%s\n' '{"data":{"total_credits":10,"total_usage":1}}'; }
export -f curl
rm -f "$TMP/live-path.calls"
env PATH="$TMP/bin:$PATH" HOME="$FAKE_HOME" OPENROUTER_API_KEY=test \
  FAKE_CLAUDE_AUTH=none FAKE_BUNDLE_LOG="$TMP/fake-bundle.log" \
  MODEL_ROUTER_CODEX_FIXTURE=v147 MODEL_ROUTER_CODEX_RPC_TIMEOUT=2 \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  MODEL_ROUTER_STUB_CALL_LOG="$TMP/live-path.calls" \
  "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
    --role builder-deep --effort high --capability structured-output \
    --prompt-file "$TMP/prompt" --output-file "$TMP/live-path.out" \
    --receipt-file "$TMP/live-path.receipt" >/dev/null
unset -f curl
assert jq -e '.probeSource == "live" and .served.transport == "codex-cli" and .served.allowanceWindow == "mapping-unknown" and (.attempts | length) == 1' \
  "$TMP/live-path.receipt"
assert test "$(wc -l < "$TMP/live-path.calls" | tr -d ' ')" -eq 1

fixture codex-exhausted
rm -f "$TMP/fake-bundle.log"
env -u WORKFLOW_KERNEL HOME="$FAKE_HOME" FAKE_BUNDLE_LOG="$TMP/fake-bundle.log" \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 \
  "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
    --role review-deep --effort high --capability read-repository \
    --capability long-context --capability structured-output \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/self-contained.out" --receipt-file "$TMP/self-contained.receipt" >/dev/null
assert jq -e '.served.transport == "openrouter" and .served.tokens.prompt_tokens == 1' "$TMP/self-contained.receipt"
assert test "$(sort -u "$TMP/fake-bundle.log" | wc -l | tr -d ' ')" -eq 1

set +e
HOME="$FAKE_HOME" MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$TMP/missing/workflow-kernel-launcher.sh" \
    --role review-deep --effort high --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/missing-kernel.out" --receipt-file "$TMP/missing-kernel.receipt" >/dev/null
missing_kernel_rc=$?
HOME="$FAKE_HOME" FAKE_KERNEL_OUTCOME=unavailable \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
    --role review-deep --effort high --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/missing-bundle.out" --receipt-file "$TMP/missing-bundle.receipt" >/dev/null
missing_bundle_rc=$?
set -e
assert test "$missing_kernel_rc" -eq 76
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "workflow_kernel_unavailable")' "$TMP/missing-kernel.receipt"
assert test "$missing_bundle_rc" -eq 76
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "provider_bundle_unavailable")' "$TMP/missing-bundle.receipt"

for provider_case in credential availability; do
  if [ "$provider_case" = credential ]; then provider_reason=provider_credential_unavailable
  else provider_reason=provider_availability_unknown
  fi
  jq --arg reason "$provider_reason" '.openrouter={state:"unknown",reason:$reason}' \
    "$TMP/availability.json" > "$TMP/provider-$provider_case.json"
  set +e
  HOME="$FAKE_HOME" MODEL_ROUTER_AVAILABILITY_FILE="$TMP/provider-$provider_case.json" \
    "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
      --role review-deep --effort high --capability read-repository --capability long-context \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/provider-$provider_case.out" --receipt-file "$TMP/provider-$provider_case.receipt" >/dev/null
  provider_case_rc=$?
  set -e
  assert test "$provider_case_rc" -eq 76
  assert jq -e --arg reason "$provider_reason" \
    '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == $reason)' \
    "$TMP/provider-$provider_case.receipt"
done

for failure_case in boundary permission budget credits rate transport model unknown; do
  rm -f "$TMP/failure-$failure_case.out" "$TMP/failure-$failure_case.receipt"
  set +e
  HOME="$FAKE_HOME" FAKE_BUNDLE_LOG="$TMP/fake-bundle.log" \
    FAKE_BOUNDARY_OUTCOME="$([ "$failure_case" = boundary ] && printf decline || printf allow)" \
    FAKE_PROVIDER_OUTCOME="$failure_case" MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
    MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 \
    "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
      --role review-deep --effort high --capability read-repository --capability long-context \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/failure-$failure_case.out" --receipt-file "$TMP/failure-$failure_case.receipt" >/dev/null
  failure_case_rc=$?
  set -e
  assert test "$failure_case_rc" -eq 76
done
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "provider_boundary_declined")' "$TMP/failure-boundary.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "provider_credential_unavailable")' "$TMP/failure-permission.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "organization_monthly_budget_exceeded")' "$TMP/failure-budget.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "insufficient_credits")' "$TMP/failure-credits.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "rate_limited")' "$TMP/failure-rate.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "provider_transport_failed")' "$TMP/failure-transport.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "provider_model_unavailable")' "$TMP/failure-model.receipt"
assert jq -e '[.attempts[] | select(.transport == "openrouter")] | all(.[]; .reason == "unknown_provider_failure")' "$TMP/failure-unknown.receipt"
assert sh -c "! grep -Eq 'fake-home|OPENROUTER_API_KEY|transport_error|model_not_found' '$TMP/failure-transport.receipt' '$TMP/failure-model.receipt'"

# Fast work resolves externally while the public surface stays anonymous.
fixture healthy
run_role fast builder-fast low --capability read-repository --capability write-repository --capability structured-output
assert jq -e '.role == "builder-fast" and (.participantId | test("^participant-[a-f0-9]{8}$")) and .disposition == "completed"' "$TMP/fast.public"
assert sh -c "! grep -Eq 'deepseek|openrouter|gpt-5|fable|kimi|qwen|grok' '$TMP/fast.public'"

# Deep work prefers healthy native subscription capacity.
run_role deep builder-deep high --capability read-repository --capability tool-use
assert jq -e '.served.transport == "codex-cli" and .served.billingMode == "included-subscription"' "$TMP/deep.receipt"

# A multi-bucket 0.147 response without an authoritative model mapping does
# not guess ownership. Any healthy bucket makes the requested candidate
# attemptable, and the invocation itself settles candidate availability.
jq -s '.[0] as $base | .[1].codex as $codex | $base | .codex = $codex' "$TMP/availability.json" "$TMP/probe-v147.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
rm -f "$TMP/mapping-unknown.calls"
MODEL_ROUTER_STUB_CALL_LOG="$TMP/mapping-unknown.calls" \
  run_role mapping-unknown builder-deep high --capability read-repository --capability long-context
assert jq -e '.served.transport == "codex-cli" and .served.allowanceWindow == "mapping-unknown" and (.attempts | length) == 1' "$TMP/mapping-unknown.receipt"
assert test "$(wc -l < "$TMP/mapping-unknown.calls" | tr -d ' ')" -eq 1

for attemptable_fixture in multiple-no-best unknown-mapping; do
  fixture healthy
  jq -s '.[0] as $base | .[1].codex as $codex | $base | .codex = $codex' \
    "$TMP/availability.json" "$TMP/probe-$attemptable_fixture.json" > "$TMP/availability.next"
  mv "$TMP/availability.next" "$TMP/availability.json"
  run_role "attemptable-$attemptable_fixture" builder-deep high \
    --capability read-repository --capability long-context
  assert jq -e '.served.transport == "codex-cli" and .served.allowanceWindow == "mapping-unknown" and (.attempts | length) == 1' \
    "$TMP/attemptable-$attemptable_fixture.receipt"
done

fixture healthy
jq -s '.[0] as $base | .[1].codex as $codex | $base | .codex = $codex' \
  "$TMP/availability.json" "$TMP/probe-all-exhausted.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role all-buckets-exhausted builder-deep high \
  --capability read-repository --capability long-context
assert jq -e '.served.transport == "openrouter" and ([.attempts[] | select(.transport == "codex-cli" and .reason == "rate_limit_exhausted")] | length) == 2' \
  "$TMP/all-buckets-exhausted.receipt"

# When authoritative policy metadata does name the applicable 0.147 bucket,
# the same response becomes eligible without comparing it with other buckets.
fixture healthy
jq -s '.[0] as $base | .[1].codex as $codex | $base | .codex = $codex' \
  "$TMP/availability.json" "$TMP/probe-v147.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
cp -R "$(dirname "$ROUTER")" "$TMP/mapped-router"
jq '(.roles["builder-deep"][] | select(.transport == "codex-cli")).rateLimitId = "codex_named"' \
  "$TMP/mapped-router/role-policy.json" > "$TMP/mapped-router/role-policy.next"
mv "$TMP/mapped-router/role-policy.next" "$TMP/mapped-router/role-policy.json"
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$TMP/mapped-router/role-dispatch.sh" --workflow-kernel "$KERNEL" --role builder-deep --effort high \
    --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/mapped.out" --receipt-file "$TMP/mapped.receipt" >/dev/null
assert jq -e '.served.transport == "codex-cli" and .served.allowanceWindow == "codex_named" and (.attempts | length) == 1' "$TMP/mapped.receipt"

jq '(.roles["builder-deep"][] | select(.transport == "codex-cli")).rateLimitId = "does_not_exist"' \
  "$TMP/mapped-router/role-policy.json" > "$TMP/mapped-router/role-policy.next"
mv "$TMP/mapped-router/role-policy.next" "$TMP/mapped-router/role-policy.json"
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$TMP/mapped-router/role-dispatch.sh" --workflow-kernel "$KERNEL" --role builder-deep --effort high \
    --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/missing-map.out" --receipt-file "$TMP/missing-map.receipt" >/dev/null
assert jq -e '.served.transport == "openrouter" and ([.attempts[] | select(.transport == "codex-cli" and .reason == "rate_limit_mapping_unknown")] | length) == 2' "$TMP/missing-map.receipt"

# Safe availability reasons survive candidate attempts and the operator receipt
# without carrying raw response/account/quota data.
cp "$TMP/probe-exhausted.json" "$TMP/availability.json"
set +e
run_role exhausted-reason builder-deep high --capability tool-use
exhausted_reason_rc=$?
set -e
assert test "$exhausted_reason_rc" -eq 76
assert jq -e '.fallbackReason == "rate_limit_exhausted" and all(.attempts[]; .reason == "rate_limit_exhausted")' "$TMP/exhausted-reason.receipt"
assert sh -c "! grep -Eq 'usedPercent|remaining_pct|resetsAt|limitName|account' '$TMP/exhausted-reason.receipt'"

# Browser means local interactive navigation. With no runtime-proven transport,
# the request closes explicitly and never turns on OpenRouter web search.
fixture healthy
set +e
run_role browser-closed research-fast high --capability browser --capability structured-output
browser_closed_rc=$?
set -e
assert test "$browser_closed_rc" -eq 76
assert jq -e '.fallbackReason == "browser_transport_unavailable" and (.attempts | length) == 0' "$TMP/browser-closed.receipt"

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
assert jq -e '.served.transport == "openrouter" and .attempts[0].reason == "rate_limit_exhausted" and ([.attempts[].model] | index("gpt-5.6-terra") == null)' "$TMP/quota-fallback.receipt"

# Failure reasons are attempt-local; an earlier quota cannot relabel a later transport failure.
fixture healthy
jq '.candidateResults["gpt-5.6-sol"].outcome="quota"
  | .candidateResults["deepseek/deepseek-v4-pro-0813"].outcome="transport"
  | .candidateResults["x-ai/grok-4.6"].outcome="success"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role local-failure builder-deep high --capability read-repository --capability long-context
assert jq -e '.served.model == "x-ai/grok-4.6" and .fallbackReason == "transport-unavailable"' "$TMP/local-failure.receipt"

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
fixture claude-pro
run_role pro-bounded architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "subscription-headroom-unknown"' "$TMP/pro-bounded.receipt"
fixture claude-unrecognized-subscription
run_role future-bounded architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "fable" and .served.billingMode == "subscription-headroom-unknown"' "$TMP/future-bounded.receipt"
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

# Independent roles retain native subscription tails when OpenRouter is unavailable.
jq '.openrouter.state="unknown"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role native-independent plan-critic high --capability read-repository --capability independent-family --human-authored
assert jq -e '.served.model == "opus" and .served.transport == "claude-cli"' "$TMP/native-independent.receipt"
run_role native-security security-review high --capability read-repository --capability independent-family --human-authored
assert jq -e '.served.model == "opus" and .served.transport == "claude-cli"' "$TMP/native-security.receipt"

# Opaque receipts exclude every implementing family.
fixture healthy
run_role implementer builder-deep high --capability read-repository
implementer_id="$(jq -r '.receiptId' "$TMP/implementer.receipt")"
mkdir "$TMP/implementation-registry"
jq '.probeSource="live" | .transportStub=false' "$TMP/implementer.receipt" > "$TMP/implementation-registry/implementer.receipt"
run_role independent plan-critic high --capability read-repository --capability independent-family --independence-receipt-dir "$TMP/implementation-registry" --independence-receipt-id "$implementer_id"
assert jq -e '.familyIndependence.required == true and .familyIndependence.passed == true and (.served.family != "openai")' "$TMP/independent.receipt"
assert jq -e '.participantId | test("^planner-[a-f0-9]{8}$")' "$TMP/independent.public"
assert sh -c "! grep -Eq 'openai|qwen|deepseek|grok|anthropic|moonshot|openrouter|gpt-5|fable|kimi' '$TMP/independent.public'"

# Fixture/stub receipts cannot be laundered into family-independence evidence.
mkdir "$TMP/simulated-registry"
cp "$TMP/implementer.receipt" "$TMP/simulated-registry/implementer.receipt"
set +e
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role plan-critic --effort high --capability read-repository \
    --capability independent-family --independence-receipt-dir "$TMP/simulated-registry" \
    --independence-receipt-id "$implementer_id" --prompt-file "$TMP/prompt" \
    --repository-evidence-file "$TMP/evidence" --output-file "$TMP/simulated.out" \
    --receipt-file "$TMP/simulated.receipt" >/dev/null 2>&1
simulated_rc=$?
set -e
assert test "$simulated_rc" -eq 2

# Prompt-only repository readers are ineligible without complete evidence.
fixture healthy
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium --capability read-repository \
    --prompt-file "$TMP/prompt" --output-file "$TMP/evidence-gate.out" \
    --receipt-file "$TMP/evidence-gate.receipt" >/dev/null
assert jq -e '.served.transport == "codex-cli"' "$TMP/evidence-gate.receipt"

# A prompt cannot masquerade as complete repository evidence, including via a hardlink.
set +e
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium --capability read-repository \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/prompt" \
    --output-file "$TMP/same-evidence.out" --receipt-file "$TMP/same-evidence.receipt" >/dev/null 2>&1
same_evidence_rc=$?
set -e
assert test "$same_evidence_rc" -eq 2
ln "$TMP/prompt" "$TMP/evidence-hardlink"
set +e
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium --capability read-repository \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence-hardlink" \
    --output-file "$TMP/hardlink-evidence.out" --receipt-file "$TMP/hardlink-evidence.receipt" >/dev/null 2>&1
hardlink_evidence_rc=$?
set -e
assert test "$hardlink_evidence_rc" -eq 2

# Human-authored diffs are explicitly independent without fabricating a model receipt.
run_role human-independent security-review high --capability read-repository --capability independent-family --human-authored
assert jq -e '.familyIndependence.required == true and .familyIndependence.humanAuthored == true and .familyIndependence.passed == true' "$TMP/human-independent.receipt"
set +e
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium --capability structured-output \
    --human-authored --prompt-file "$TMP/prompt" --output-file "$TMP/invalid-human.out" \
    --receipt-file "$TMP/invalid-human.receipt" >/dev/null 2>&1
invalid_human_rc=$?
set -e
assert test "$invalid_human_rc" -eq 2

# Write-adapter usage cost survives normalization into the router receipt.
fixture healthy
printf '%s\n' '{"usage":{"prompt_tokens":8,"completion_tokens":3,"cost":0.0125}}' > "$TMP/provider-receipt.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/provider-receipt.json" run_role write-cost builder-fast medium \
  --capability read-repository --capability write-repository --capability structured-output
assert jq -e '.served.billedCostUsd == 0.0125 and .served.costProvenance == "provider-receipt"' "$TMP/write-cost.receipt"

# Real native transport branches receive no OpenRouter credential material.
fixture healthy
rm -f "$TMP/native-env"
env PATH="$TMP/bin:$PATH" OPENROUTER_API_KEY=secret-marker \
  OPENROUTER_API_KEY_FILE="$TMP/key-file" MODEL_ROUTER_NATIVE_ENV_CAPTURE="$TMP/native-env" \
  MODEL_ROUTER_NATIVE_PROMPT_CAPTURE="$TMP/native-prompt" \
  MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role builder-deep --effort high --capability read-repository --capability write-repository \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/native-codex.out" --receipt-file "$TMP/native-codex.receipt" \
    --contract-digest "sha256:$(printf 'a%.0s' {1..64})" --contract-revision 1 >/dev/null
assert grep -Fxq 'api=unset,file=unset' "$TMP/native-env"

# A failed write that mutates repository state terminates the ladder.
mkdir "$TMP/write-repo"
git -C "$TMP/write-repo" init -q
printf '%s\n' 'initial' > "$TMP/write-repo/tracked.txt"
git -C "$TMP/write-repo" add tracked.txt
git -C "$TMP/write-repo" -c user.name=test -c user.email=test@example.invalid commit -qm initial
fixture healthy
jq '.candidateResults["gpt-5.6-sol"].outcome="mutate-fail"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
set +e
(
  cd "$TMP/write-repo"
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    MODEL_ROUTER_STUB_MUTATE_PATH="$TMP/write-repo/tracked.txt" \
    MODEL_ROUTER_STUB_CALL_LOG="$TMP/write-calls" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role builder-deep --effort high --capability write-repository \
      --capability structured-output --prompt-file "$TMP/prompt" \
      --output-file "$TMP/mutating-write.out" --receipt-file "$TMP/mutating-write.receipt" \
      --contract-digest "sha256:$(printf 'b%.0s' {1..64})" --contract-revision 2 >/dev/null
)
mutating_write_rc=$?
set -e
assert test "$mutating_write_rc" -eq 76
assert test "$(wc -l < "$TMP/write-calls")" -eq 1
assert jq -e '.fallbackReason == "repository-mutated-on-failed-attempt" and (.attempts | length) == 1' "$TMP/mutating-write.receipt"
assert jq -e '.contract_digest == ("sha256:" + ("a" * 64)) and .revision == 1' "$TMP/native-codex.receipt"
assert grep -Fq 'contract_digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$TMP/native-prompt"
assert grep -Fq 'contract_revision: 1' "$TMP/native-prompt"
rm -f "$TMP/native-env"
env PATH="$TMP/bin:$PATH" OPENROUTER_API_KEY=secret-marker \
  OPENROUTER_API_KEY_FILE="$TMP/key-file" MODEL_ROUTER_NATIVE_ENV_CAPTURE="$TMP/native-env" \
  MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role architect --effort high --capability read-repository \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/native-claude.out" --receipt-file "$TMP/native-claude.receipt" >/dev/null
assert grep -Fxq 'api=unset,file=unset' "$TMP/native-env"

# Publication failure cannot produce a completed public disposition or partial artifact.
mkdir "$TMP/reservation"
MODEL_ROUTER_EXPECT_PUBLICATION_DIR="$TMP/reservation" \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium --capability structured-output \
    --prompt-file "$TMP/prompt" --output-file "$TMP/reservation/out" \
    --receipt-file "$TMP/reservation/receipt" >/dev/null
assert test -s "$TMP/reservation/out"
assert test -s "$TMP/reservation/receipt"

mkdir "$TMP/publication"
set +e
MODEL_ROUTER_REMOVE_PUBLICATION_DIR="$TMP/publication" \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium --capability structured-output \
    --prompt-file "$TMP/prompt" --output-file "$TMP/publication/out" \
    --receipt-file "$TMP/publication/receipt" > "$TMP/publication-public"
publication_rc=$?
set -e
assert test "$publication_rc" -eq 76
assert sh -c "! grep -q '\"disposition\":\"completed\"' '$TMP/publication-public'"
assert jq -e '.disposition == "completed-publication-failed" and (.privateReceipt | length > 0)' "$TMP/publication-public"
read_publication_receipt="$(jq -r '.privateReceipt' "$TMP/publication-public")"
assert jq -e '.publication.output == "pending"' "$read_publication_receipt"
rm -f "$read_publication_receipt"

# A committed write keeps exact mutation provenance if output publication fails.
mkdir "$TMP/publication-write-repo"
git -C "$TMP/publication-write-repo" init -q
printf '%s\n' 'initial' > "$TMP/publication-write-repo/tracked.txt"
git -C "$TMP/publication-write-repo" add tracked.txt
git -C "$TMP/publication-write-repo" -c user.name=test -c user.email=test@example.invalid commit -qm initial
write_initial_head="$(git -C "$TMP/publication-write-repo" rev-parse HEAD)"
fixture healthy
jq '.candidateResults["gpt-5.6-sol"].outcome="commit-success"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
mkdir "$TMP/publication-write"
set +e
(
  cd "$TMP/publication-write-repo"
  MODEL_ROUTER_REMOVE_PUBLICATION_DIR="$TMP/publication-write" \
    MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    MODEL_ROUTER_STUB_MUTATE_PATH="$TMP/publication-write-repo/tracked.txt" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role builder-deep --effort high --capability write-repository \
      --capability structured-output --prompt-file "$TMP/prompt" \
      --output-file "$TMP/publication-write/out" \
      --receipt-file "$TMP/publication-write/receipt" \
      --contract-digest "sha256:$(printf 'c%.0s' {1..64})" \
      --contract-revision 3 > "$TMP/publication-write-public"
)
publication_write_rc=$?
set -e
assert test "$publication_write_rc" -eq 76
write_final_head="$(git -C "$TMP/publication-write-repo" rev-parse HEAD)"
assert test "$write_final_head" != "$write_initial_head"
assert jq -e --arg commit "$write_final_head" '.disposition == "completed-publication-failed" and .commit == $commit' "$TMP/publication-write-public"
write_publication_receipt="$(jq -r '.privateReceipt' "$TMP/publication-write-public")"
assert jq -e --arg commit "$write_final_head" '.served.commit == $commit and .publication.output == "pending"' "$write_publication_receipt"
rm -f "$write_publication_receipt"

# Model content refusal follows the role ladder with no prompt.
fixture healthy
jq '.candidateResults["qwen/qwen3.8-max"].outcome="content-refusal"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role refusal plan-critic high --capability read-repository --capability structured-output
assert jq -e '.fallback == true and .fallbackReason == "content-refusal" and .served.model == "deepseek/deepseek-v4-pro-0813"' "$TMP/refusal.receipt"

# Empty capability lists remain safe under nounset (including Bash 3.2).
fixture healthy
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort low --prompt-file "$TMP/prompt" \
    --output-file "$TMP/no-capabilities.out" --receipt-file "$TMP/no-capabilities.receipt" >/dev/null
assert jq -e '.requested.capabilities == []' "$TMP/no-capabilities.receipt"

# Receipts are exact/content-free; public and peer surfaces remain identity-free.
assert jq -e '.requested.role and .requested.candidate.model and .effectiveEffort and .participantId and .attempts and .served.model and .served.provider and .served.transport and .served.billingMode and (.served.durationSeconds|type=="number") and (.served.tokenProvenance=="unavailable") and (.served.costProvenance=="unavailable") and .matrixSnapshot and (.fallbackReason|type=="string")' "$TMP/refusal.receipt"
assert sh -c "! grep -Eq 'prompt|bounded role output' '$TMP/refusal.receipt'"
if grep -Fq 'Authorization: Bearer $OPENROUTER_API_KEY' "$PROBE"; then
  printf 'FAIL: OpenRouter credential appears in curl argv\n' >&2
  exit 1
fi
pass=$((pass + 1))
assert grep -Fq -- '-H "@$header_file"' "$PROBE"
assert grep -Fq 'unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE' "$PROBE"

printf 'model-router: %d assertions passed\n' "$pass"
