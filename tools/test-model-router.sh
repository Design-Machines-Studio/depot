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
  success)
    printf 'bounded role output\n' > "$output"
    case "$model" in
      fable) printf '%s\n' '{"model":"claude-fable-5"}' > "$provider_receipt" ;;
      opus) printf '%s\n' '{"model":"claude-opus-5"}' > "$provider_receipt" ;;
    esac
    ;;
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
  HOME="$FAKE_HOME" MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" --role "$role" --effort "$effort" \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/$name.out" --receipt-file "$TMP/$name.receipt" \
      --contract-digest "sha256:$(printf 'a%.0s' {1..64})" --contract-revision 1 \
      "$@" > "$TMP/$name.public"
}

# The dispatcher owns one invocation-local Kernel and OpenRouter binding. A
# fake coherent bundle proves the no-inherited-variable path and closed causes
# without contacting a paid provider.
FAKE_HOME="$TMP/fake-home"
FAKE_BUNDLE="$FAKE_HOME/.codex/plugins/cache/depot/openrouter/1.20.2"
FAKE_REFS="$FAKE_BUNDLE/skills/openrouter-delegate/references"
mkdir -p "$FAKE_REFS" "$TMP/fake-kernel"
cat > "$TMP/fake-kernel/workflow-kernel-launcher.sh" <<'STUB'
#!/usr/bin/env bash
if [ "${FAKE_KERNEL_OUTCOME:-ok}" = unavailable ]; then exit 4; fi
printf '%s\n' '{"selected_root":"~/.codex/plugins/cache/depot/openrouter/1.20.2","version":"1.20.2","cache_class":"codex","reason":"active-host"}'
STUB
cat > "$FAKE_REFS/delegation-boundary.sh" <<'STUB'
#!/usr/bin/env bash
dirname "${BASH_SOURCE[0]}" >> "$FAKE_BUNDLE_LOG"
changed=""; output_paths=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --changed-files) changed="$2"; shift 2 ;;
    --output-paths) output_paths="$2"; shift 2 ;;
    *) shift ;;
  esac
done
if [ -n "$output_paths" ]; then
  while IFS= read -r path; do printf '%s\0' "$path"; done < "$changed" > "$output_paths"
fi
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
model="${1:-fixture/model}"
effort="${OPENROUTER_REASONING_EFFORT:-}"
runid="${OPENROUTER_RUN_ID:-}"
lane="${OPENROUTER_LANE_ID:-}"
write_valid_failure() {
  local kind="$1" reason="$2" http="$3" timeout_kind="${4:-}"
  jq -n --arg model "$model" --arg effort "$effort" --arg runid "$runid" \
    --arg lane "$lane" --arg kind "$kind" --arg reason "$reason" --arg http "$http" \
    --arg timeout_kind "$timeout_kind" '{schemaVersion:2,invocationId:("a" * 64),outcome:(if ($kind == "stream_timeout" or $kind == "curl_timeout") then "timeout" else "error" end),failureKind:$kind,failureReason:(if $reason == "" then null else $reason end),timeout:(if $timeout_kind == "" then null else {kind:$timeout_kind} end),httpStatus:(if $http == "" then null else ($http|tonumber) end),requestedModel:$model,modelCandidates:[$model],attemptedModel:null,attemptedModels:null,attemptProvenance:"not_reported_by_completion",fallbackUsed:null,responseModel:null,responseModelProvenance:"not_available",servingProvider:null,servingProviderProvenance:"not_reported_by_completion",usage:{prompt_tokens:8,completion_tokens:3,total_tokens:11,cost:0.0125},reasoningEffort:{requested:$effort,transmitted:$effort,status:"transmitted",evidence:"request-envelope",modelReasoningMeasurement:null},routing:{workload:"mechanical",sort:"throughput",providerFallbackAllowed:true,webSearch:false},authorization:{runId:(if $runid == "" then null else $runid end),laneId:(if $lane == "" then null else $lane end),requestEnvelopeSha256:("b" * 64)}}' > "$OPENROUTER_RECEIPT_FILE"
}
write_valid_success() {
  jq -n --arg model "$model" --arg effort "$effort" --arg runid "$runid" --arg lane "$lane" '{schemaVersion:2,invocationId:("a" * 64),outcome:"success",failureKind:null,failureReason:null,timeout:null,httpStatus:200,generationId:"fixture-generation",requestedModel:$model,modelCandidates:[$model],attemptedModel:$model,attemptedModels:[$model],attemptProvenance:"response_model",fallbackUsed:false,responseModel:$model,responseModelProvenance:"response",servingProvider:"fixture-provider",servingProviderProvenance:"response",usage:{prompt_tokens:1,completion_tokens:1,total_tokens:2,cost:0.000001,is_byok:false,prompt_tokens_details:{cached_tokens:0},cost_details:{upstream_inference_cost:0.000001},completion_tokens_details:{reasoning_tokens:0}},reasoningEffort:{requested:$effort,transmitted:$effort,status:"transmitted",evidence:"request-envelope",modelReasoningMeasurement:null},routing:{workload:"mechanical",sort:"throughput",providerFallbackAllowed:true,webSearch:false},authorization:{runId:(if $runid == "" then null else $runid end),laneId:(if $lane == "" then null else $lane end),requestEnvelopeSha256:("b" * 64)}}' > "$OPENROUTER_RECEIPT_FILE"
}
case "${FAKE_PROVIDER_OUTCOME:-success}" in
  success)
    write_valid_success
    if [ "${FAKE_WRITE_MODE:-0}" = 1 ]; then
      printf '%s\n' 'diff --git a/tracked.txt b/tracked.txt' '--- a/tracked.txt' '+++ b/tracked.txt' '@@ -1 +1 @@' '-initial' '+written'
    else
      printf '%s\n' 'bounded provider output'
    fi
    ;;
  success-no-effort)
    printf '%s\n' '{"outcome":"success","usage":{"prompt_tokens":1,"completion_tokens":1},"costUsd":0.000001}' > "$OPENROUTER_RECEIPT_FILE"
    printf '%s\n' 'unproven provider output'
    ;;
  model) write_valid_failure http_error unknown_http_error 404; exit 1 ;;
  permission) write_valid_failure http_error key_permission_denied 403; exit 1 ;;
  budget) write_valid_failure http_error organization_monthly_budget_exceeded 403; exit 1 ;;
  credits) write_valid_failure http_error insufficient_credits 402; exit 1 ;;
  rate|quota) write_valid_failure http_error rate_limited 429; exit 1 ;;
  unknown|server) write_valid_failure http_error unknown_http_error 500; exit 1 ;;
  transport) write_valid_failure transport_error "" 0; exit 1 ;;
  timeout) write_valid_failure stream_timeout "" "" idle; exit 28 ;;
  stream) write_valid_failure stream_error "" ""; exit 1 ;;
  inconsistent) write_valid_failure stream_timeout rate_limited "" idle; exit 1 ;;
  publication-failure) printf '%s\n' '### RUNNER FAILURE: could not write OpenRouter failure receipt' >&2; exit 1 ;;
  malformed) printf '%s\n' '{"schemaVersion":2,"outcome":"error","failureKind":"future_failure","diagnostic":"fixture-secret"}' > "$OPENROUTER_RECEIPT_FILE"; exit 1 ;;
  missing) exit 1 ;;
  first-fail)
    calls="${FAKE_PROVIDER_CALLS:-/tmp/model-router-fake-provider.calls}"
    count=0
    [ -f "$calls" ] && count="$(wc -l < "$calls" | tr -d ' ')"
    printf '%s\n' "$model" >> "$calls"
    if [ "$count" -eq 0 ]; then write_valid_failure http_error rate_limited 429; exit 1; fi
    write_valid_success
    printf '%s\n' 'diff --git a/tracked.txt b/tracked.txt' '--- a/tracked.txt' '+++ b/tracked.txt' '@@ -1 +1 @@' '-initial' '+written'
    ;;
  *) exit 90 ;;
esac
STUB
printf '%s\n' '{"schemaVersion":2,"disclosureControls":{"providerInputParity":true},"executionControls":{},"delegationModes":{},"reviewControls":{}}' > "$FAKE_REFS/delegation-security-policy.json"
chmod +x "$TMP/fake-kernel/workflow-kernel-launcher.sh" "$FAKE_REFS/delegation-boundary.sh" "$FAKE_REFS/openrouter-wrapper.sh"

new_write_repo() {
  local name="$1" repo
  repo="$TMP/$name"
  mkdir "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.name test
  git -C "$repo" config user.email test@example.invalid
  printf '%s\n' initial > "$repo/tracked.txt"
  git -C "$repo" add tracked.txt
  git -C "$repo" -c user.name=test -c user.email=test@example.invalid commit -qm initial
  printf '%s\n' "$repo"
}

run_real_write_case() {
  local name="$1" outcome="$2" repo rc
  repo="$(new_write_repo "real-write-$name")"
  fixture codex-exhausted
  set +e
  (
    cd "$repo"
    HOME="$FAKE_HOME" OPENROUTER_API_KEY=test FAKE_BUNDLE_LOG="$TMP/real-write-bundle.log" \
      FAKE_WRITE_MODE=1 FAKE_PROVIDER_OUTCOME="$outcome" FAKE_PROVIDER_CALLS="$TMP/$name.calls" \
      MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
      MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 OPENROUTER_EXEC_ALLOWED_PATHS=tracked.txt \
      "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
        --role builder-fast --effort medium --capability read-repository \
        --capability write-repository --capability structured-output \
        --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
        --output-file "$TMP/$name.out" --receipt-file "$TMP/$name.receipt" \
        --contract-digest "sha256:$(printf 'd%.0s' {1..64})" --contract-revision 4 \
        > "$TMP/$name.public"
  )
  rc=$?
  set -e
  printf '%s\n' "$rc" > "$TMP/$name.rc"
  printf '%s\n' "$repo"
}

real_success_repo="$(run_real_write_case real-success success)"
assert test "$(cat "$TMP/real-success.rc")" -eq 0
assert test "$(cat "$real_success_repo/tracked.txt")" = written
assert jq -e '.served.transport == "openrouter" and .served.commit != null and ([.attempts[] | select(.transport == "openrouter")][0].providerReceiptStatus == "valid-provider-success")' "$TMP/real-success.receipt"
assert test "$(find "$real_success_repo" -maxdepth 1 -name '.model-router-attempts.*' -print)" = ""

for real_failure_case in permission quota timeout stream server missing malformed inconsistent; do
  run_real_write_case "real-$real_failure_case" "$real_failure_case" >/dev/null
  assert test "$(cat "$TMP/real-$real_failure_case.rc")" -eq 76
  assert test "$(cat "$TMP/real-write-real-$real_failure_case/tracked.txt")" = initial
  assert test ! -e "$TMP/real-$real_failure_case.out"
  assert jq -e '.served == null and ([.attempts[] | select(.transport == "openrouter")][0].processExitStatus != null)' \
    "$TMP/real-$real_failure_case.receipt"
done
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_credential_unavailable" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.failureReason == "key_permission_denied" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.httpStatus == 403 and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.usage.cost == 0.0125)' "$TMP/real-permission.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "rate_limited" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.failureReason == "rate_limited" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.httpStatus == 429)' "$TMP/real-quota.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_transport_failed" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.failureKind == "stream_timeout" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.timeoutKind == "idle")' "$TMP/real-timeout.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].processExitStatus == 28)' "$TMP/real-timeout.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_transport_failed" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.failureKind == "stream_error")' "$TMP/real-stream.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.httpStatus == null)' "$TMP/real-stream.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "unknown_provider_failure" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.httpStatus == 500)' "$TMP/real-server.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_receipt_missing" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence == null)' "$TMP/real-missing.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_receipt_malformed" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence == null)' "$TMP/real-malformed.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_receipt_malformed" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence == null)' "$TMP/real-inconsistent.receipt"
assert sh -c "! grep -Eq 'fixture-secret|diagnostic|fake-home|OPENROUTER_API_KEY' '$TMP/real-malformed.receipt' '$TMP/real-missing.receipt'"

run_real_write_case real-publication-failure publication-failure >/dev/null
assert test "$(cat "$TMP/real-publication-failure.rc")" -eq 76
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_receipt_publication_failed" and [.attempts[] | select(.transport == "openrouter")][0].providerReceiptStatus == "publication-failed")' "$TMP/real-publication-failure.receipt"

local_repo="$(new_write_repo real-local-rejection)"
fixture codex-exhausted
set +e
(
  cd "$local_repo"
  env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE HOME="$FAKE_HOME" FAKE_BUNDLE_LOG="$TMP/local-rejection-bundle.log" \
    FAKE_WRITE_MODE=1 FAKE_PROVIDER_OUTCOME=success MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
    MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 OPENROUTER_EXEC_ALLOWED_PATHS=tracked.txt \
    "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" --role builder-fast \
      --effort medium --capability read-repository --capability write-repository \
      --capability structured-output --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/local-rejection.out" --receipt-file "$TMP/local-rejection.receipt" \
      --contract-digest "sha256:$(printf 'e%.0s' {1..64})" --contract-revision 5 >/dev/null
)
local_rejection_rc=$?
set -e
assert test "$local_rejection_rc" -eq 76
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_adapter_rejected" and [.attempts[] | select(.transport == "openrouter")][0].providerReceiptStatus == "adapter-local-rejection")' "$TMP/local-rejection.receipt"

first_fail_repo="$(run_real_write_case real-first-fail first-fail)"
assert test "$(cat "$TMP/real-first-fail.rc")" -eq 0
assert jq -e '.fallback == true and .fallbackReason == "rate_limited" and ([.attempts[] | select(.transport == "openrouter")] | length) == 2 and ([.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.failureReason == "rate_limited") and .served.transport == "openrouter"' "$TMP/real-first-fail.receipt"
assert test "$(cat "$first_fail_repo/tracked.txt")" = written

run_real_write_case stale-first missing >/dev/null
run_real_write_case stale-second server >/dev/null
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "provider_receipt_missing")' "$TMP/stale-first.receipt"
assert jq -e '([.attempts[] | select(.transport == "openrouter")][0].reason == "unknown_provider_failure" and [.attempts[] | select(.transport == "openrouter")][0].providerFailureEvidence.httpStatus == 500)' "$TMP/stale-second.receipt"

# A strict key-file load leaves OPENROUTER_API_KEY_FILE set. The successfully
# loaded key is nevertheless available to the probe and must not be reported as
# a missing credential.
printf '%s\n' test > "$TMP/key-file"
chmod 600 "$TMP/key-file"
curl() { printf '%s\n' '{"data":{"total_credits":10,"total_usage":1}}'; }
export -f curl
key_file_probe="$(env PATH=/usr/bin:/bin HOME="$FAKE_HOME" \
  OPENROUTER_API_KEY_FILE="$TMP/key-file" OPENROUTER_BUNDLE_RESOLVED=1 \
  OPENROUTER_BUNDLE_REF='~/.codex/plugins/cache/depot/openrouter/1.20.2' \
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
  OPENROUTER_BUNDLE_REF='~/.codex/plugins/cache/depot/openrouter/1.20.2' \
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

# A provider completion without request-envelope effort evidence cannot become
# a clean pass. The fixed candidate ladder terminates without a blind retry.
fixture codex-exhausted
set +e
HOME="$FAKE_HOME" FAKE_BUNDLE_LOG="$TMP/fake-bundle.log" \
  FAKE_PROVIDER_OUTCOME=success-no-effort \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS=1 \
  "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
    --role review-deep --effort high --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/no-effort.out" --receipt-file "$TMP/no-effort.receipt" >/dev/null
no_effort_rc=$?
set -e
assert test "$no_effort_rc" -eq 76
assert test ! -e "$TMP/no-effort.out"
assert jq -e '
  ([.attempts[] | select(.transport == "openrouter")] | length) == 2 and
  ([.attempts[] | select(.transport == "openrouter")] |
    all(.[]; .outcome == "failed" and .reason == "provider_effort_evidence_unavailable" and .transmittedEffort == null))
' "$TMP/no-effort.receipt"

# Fast work resolves externally while the public surface stays anonymous.
fixture healthy
run_role fast builder-fast low --capability read-repository --capability write-repository --capability structured-output
assert jq -e '.role == "builder-fast" and (.participantId | test("^participant-[a-f0-9]{8}$")) and .disposition == "completed"' "$TMP/fast.public"
assert sh -c "! grep -Eq 'deepseek|openrouter|gpt-[0-9]|fable|kimi|qwen|grok' '$TMP/fast.public'"

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
assert jq -e '.served.transport == "openrouter" and ([.attempts[] | select(.transport == "codex-cli" and .reason == "rate_limit_exhausted")] | length) == 3' \
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
HOME="$FAKE_HOME" MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$TMP/mapped-router/role-dispatch.sh" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" --role builder-deep --effort high \
    --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/mapped.out" --receipt-file "$TMP/mapped.receipt" >/dev/null
assert jq -e '.served.transport == "codex-cli" and .served.allowanceWindow == "codex_named" and (.attempts | length) == 1' "$TMP/mapped.receipt"

jq '(.roles["builder-deep"][] | select(.transport == "codex-cli")).rateLimitId = "does_not_exist"' \
  "$TMP/mapped-router/role-policy.json" > "$TMP/mapped-router/role-policy.next"
mv "$TMP/mapped-router/role-policy.next" "$TMP/mapped-router/role-policy.json"
HOME="$FAKE_HOME" MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
  "$TMP/mapped-router/role-dispatch.sh" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" --role builder-deep --effort high \
    --capability read-repository --capability long-context \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/missing-map.out" --receipt-file "$TMP/missing-map.receipt" >/dev/null
assert jq -e '.served.transport == "openrouter" and ([.attempts[] | select(.transport == "codex-cli" and .reason == "rate_limit_mapping_unknown")] | length) == 3' "$TMP/missing-map.receipt"

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
jq '.candidateResults["gpt-6-astra"].outcome="quota"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role quota-fallback builder-deep high --capability read-repository --capability long-context
assert jq -e '.served.transport == "openrouter" and .attempts[0].reason == "rate_limit_exhausted" and ([.attempts[].model] | index("gpt-5.6-terra") == null and index("gpt-5.6-sol") == null)' "$TMP/quota-fallback.receipt"

# Failure reasons are attempt-local; an earlier quota cannot relabel a later transport failure.
fixture healthy
jq '.candidateResults["gpt-6-astra"].outcome="quota"
  | .candidateResults["deepseek/deepseek-v4-pro-0813"].outcome="transport"
  | .candidateResults["x-ai/grok-4.6"].outcome="success"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role local-failure builder-deep high --capability read-repository --capability long-context
assert jq -e '.served.model == "x-ai/grok-4.6" and .fallbackReason == "transport-unavailable"' "$TMP/local-failure.receipt"

# Driver requests preserve their own effort; bounded workers do not inherit it.
fixture healthy
for effort in low medium high max; do
  run_role "astra-$effort" architect "$effort" --capability read-repository --capability structured-output
  assert jq -e --arg effort "$effort" '.served.model == "gpt-6-astra" and .requested.effort == $effort and .normalizedEffort == $effort' "$TMP/astra-$effort.receipt"
done
for effort in high max; do
  run_role "luna-$effort" builder-fast "$effort" --capability read-repository --capability structured-output
  assert jq -e --arg effort "$effort" '.served.model == "gpt-5.6-luna" and .requested.effort == $effort and .normalizedEffort == $effort' "$TMP/luna-$effort.receipt"
done
# Model-specific transport failure can use the optional native baseline; a
# quota response above must instead skip the entire exhausted subscription rail.
jq '.candidateResults["gpt-6-astra"].outcome="transport"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role sol-baseline architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .normalizedEffort == "high" and .fallback == true' "$TMP/sol-baseline.receipt"

# Two eligible operators receive identical subscription-first behavior from one policy.
fixture healthy
run_role architect-a architect low --capability read-repository --capability structured-output
assert jq -e '.served.model == "gpt-6-astra" and .served.billingMode == "included-subscription"' "$TMP/architect-a.receipt"
fixture second-eligible-operator
run_role architect-b architect medium --capability read-repository --capability structured-output
assert jq -e '.served.model == "gpt-6-astra" and .served.billingMode == "included-subscription"' "$TMP/architect-b.receipt"

# Claude allowance states remain distinct when the subscription-first Codex
# candidate is unavailable.
fixture fable-exhausted
jq '.codex.state="limited" | .codex.fiveHourRemainingPct=0 | .codex.weeklyRemainingPct=0' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role fable-fallback architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "qwen/qwen3.8-max" and .served.transport == "openrouter" and .fallback == true' "$TMP/fable-fallback.receipt"
# An eligible Claude subscription follows the unavailable native Codex rail.
jq '.codex.state="exhausted"
  | .codex.windows.five_hour.remaining_pct=0
  | .codex.windows.weekly.remaining_pct=0
  | .claude.state="ok"
  | .claude.fiveHourRemainingPct=80
  | .claude.weeklyRemainingPct=70' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role opus-fallback architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.transport == "claude-cli" and .fallback == true' "$TMP/opus-fallback.receipt"
fixture fable-initial-telemetry-absent
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role fable-bounded architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.billingMode == "subscription-headroom-unknown"' "$TMP/fable-bounded.receipt"
fixture claude-pro
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role pro-bounded architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.billingMode == "subscription-headroom-unknown"' "$TMP/pro-bounded.receipt"
fixture claude-unrecognized-subscription
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role future-bounded architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.billingMode == "subscription-headroom-unknown"' "$TMP/future-bounded.receipt"
fixture fable-agent-sdk-capacity
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role fable-sdk architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.billingMode == "included-subscription" and .served.allowanceWindow == "agent-sdk"' "$TMP/fable-sdk.receipt"

# Credits, unauthenticated, and API-key states never masquerade as included use.
fixture credits-disabled
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role credits-off architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "qwen/qwen3.8-max" and .served.transport == "openrouter"' "$TMP/credits-off.receipt"
fixture credits-enabled
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role credits-on architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "opus" and .served.billingMode == "paid-credits"' "$TMP/credits-on.receipt"
fixture claude-api-key
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role api-key architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "qwen/qwen3.8-max" and .served.transport == "openrouter"' "$TMP/api-key.receipt"
fixture claude-unauthenticated
jq '.codex.state="unavailable"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role unauth architect high --capability read-repository --capability structured-output
assert jq -e '.served.model == "qwen/qwen3.8-max" and .served.transport == "openrouter"' "$TMP/unauth.receipt"

# Security head identity stays private.
fixture healthy
run_role security security-review high --capability read-repository --capability structured-output
assert jq -e '.served.model == "gpt-5.6-terra" and .served.transport == "codex-cli"' "$TMP/security.receipt"
assert sh -c "! grep -Eq 'kimi|moonshot|openrouter|deepseek|gpt-[0-9]|fable|qwen|grok' '$TMP/security.public'"

# Human-authored work excludes no family, so subscription-first remains the
# head even when OpenRouter is unavailable.
jq '.openrouter.state="unknown"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role native-independent plan-critic high --capability read-repository --capability independent-family --human-authored
assert jq -e '.served.model == "gpt-5.6-terra" and .served.transport == "codex-cli"' "$TMP/native-independent.receipt"
run_role native-security security-review high --capability read-repository --capability independent-family --human-authored
assert jq -e '.served.model == "gpt-5.6-terra" and .served.transport == "codex-cli"' "$TMP/native-security.receipt"

# Ordinary security and critic reviews need no historical origin receipts.
fixture healthy
run_role security-without-origin security-review high --capability read-repository --capability long-context --capability structured-output
assert jq -e '.served != null and .familyIndependence.required == false and .requested.humanAuthored == false and .requested.independenceReceiptIds == []' "$TMP/security-without-origin.receipt"
assert jq -e '.disposition == "completed" and (.capabilities | index("independent-family") == null)' "$TMP/security-without-origin.public"
run_role critic-without-origin plan-critic high --capability read-repository --capability long-context --capability structured-output
assert jq -e '.served != null and .familyIndependence.required == false and .requested.humanAuthored == false and .requested.independenceReceiptIds == []' "$TMP/critic-without-origin.receipt"
assert jq -e '.disposition == "completed" and (.capabilities | index("independent-family") == null)' "$TMP/critic-without-origin.public"

# Opaque receipts exclude every implementing family.
fixture healthy
run_role implementer builder-deep high --capability read-repository
implementer_id="$(jq -r '.receiptId' "$TMP/implementer.receipt")"
mkdir "$TMP/implementation-registry"
jq '.probeSource="live" | .transportStub=false' "$TMP/implementer.receipt" > "$TMP/implementation-registry/implementer.receipt"
run_role independent plan-critic high --capability read-repository --capability independent-family --independence-receipt-dir "$TMP/implementation-registry" --independence-receipt-id "$implementer_id"
assert jq -e '.familyIndependence.required == true and .familyIndependence.passed == true and (.served.family != "openai")' "$TMP/independent.receipt"
assert jq -e '.participantId | test("^planner-[a-f0-9]{8}$")' "$TMP/independent.public"
assert sh -c "! grep -Eq 'openai|qwen|deepseek|grok|anthropic|moonshot|openrouter|gpt-[0-9]|fable|kimi' '$TMP/independent.public'"

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
jq '.candidateResults["gpt-6-astra"].outcome="mutate-fail"' "$TMP/availability.json" > "$TMP/availability.next"
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
jq '.candidateResults["gpt-6-astra"].outcome="commit-success"' "$TMP/availability.json" > "$TMP/availability.next"
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
jq '.candidateResults["gpt-5.6-terra"].outcome="content-refusal"' "$TMP/availability.json" > "$TMP/availability.next"
mv "$TMP/availability.next" "$TMP/availability.json"
run_role refusal plan-critic high --capability read-repository --capability structured-output
assert jq -e '.fallback == true and .fallbackReason == "content-refusal" and .served.model == "deepseek/deepseek-v4-pro-0813"' "$TMP/refusal.receipt"

# Standalone review coordination starts economically on Sol, while a bounded
# design consultation uses native Fable once and falls back when exhausted.
fixture healthy
run_role review-coordinator review-coordinator medium --capability read-repository --capability long-context --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .served.transport == "codex-cli" and .normalizedEffort == "medium"' "$TMP/review-coordinator.receipt"
printf '%s\n' '{}' > "$TMP/fable-missing-identity.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/fable-missing-identity.json" \
  run_role fable-design design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .fallback == true and ([.attempts[] | select(.model == "fable" and .servedIdentity == "unknown" and .reason == "provider_model_identity_unavailable")] | length) == 1' "$TMP/fable-design.receipt"
printf '%s\n' '{"model":"claude-fable-5"}' > "$TMP/fable-identity.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/fable-identity.json" \
  run_role fable-identity design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "fable" and .served.servedIdentity == "claude-fable-5"' "$TMP/fable-identity.receipt"
printf '%s\n' '{"response":{"model":"claude-fable-5"},"model":"fable"}' > "$TMP/fable-response-identity.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/fable-response-identity.json" \
  run_role fable-response-identity design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "fable" and .served.servedIdentity == "claude-fable-5"' "$TMP/fable-response-identity.receipt"
printf '%s\n' '{"modelUsage":{"claude-fable-5":{"outputTokens":12},"claude-haiku-4-5":{"outputTokens":3}}}' > "$TMP/fable-usage-identity.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/fable-usage-identity.json" \
  run_role fable-usage-identity design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "fable" and .served.servedIdentity == "claude-fable-5"' "$TMP/fable-usage-identity.receipt"
printf '%s\n' '{"modelUsage":{"claude-fable-5":{"outputTokens":12},"claude-opus-5":{"outputTokens":12}}}' > "$TMP/fable-ambiguous-identity.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/fable-ambiguous-identity.json" \
  run_role fable-ambiguous-identity design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .fallback == true and ([.attempts[] | select(.model == "fable" and .reason == "provider_model_identity_unavailable")] | length) == 1' "$TMP/fable-ambiguous-identity.receipt"
printf '%s\n' '{"model":"claude-opus-5"}' > "$TMP/fable-substitution.json"
MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/fable-substitution.json" \
  run_role fable-substitution design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .fallback == true and ([.attempts[] | select(.model == "fable" and .servedIdentity == "claude-opus-5" and .reason == "provider_model_substitution")] | length) == 1' "$TMP/fable-substitution.receipt"
fixture fable-exhausted
run_role fable-design-fallback design-consultant medium --capability long-context --capability structured-output
assert jq -e '.served.model == "gpt-5.6-sol" and .fallback == true and ([.attempts[] | select(.model == "fable" and .outcome == "skipped")] | length) == 1' "$TMP/fable-design-fallback.receipt"

mkdir -p "$TMP/profile-dispatch/.dm"
git -C "$TMP/profile-dispatch" init -q
printf '%s\n' '{"disabledCandidates":["opus"]}' > "$TMP/profile-dispatch/.dm/model-router.local.json"
fixture healthy
jq '.codex.state="unavailable" | .claude.state="ok" | .claude.authMode="subscription" | .openrouter.state="ok"' \
  "$TMP/availability.json" > "$TMP/profile-dispatch-availability.json"
(
  cd "$TMP/profile-dispatch"
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/profile-dispatch-availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role architect --effort medium \
      --capability read-repository --capability long-context --capability structured-output \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/profile-dispatch.out" --receipt-file "$TMP/profile-dispatch.receipt" >/dev/null
)
assert jq -e '.served.model == "qwen/qwen3.8-max" and .served.transport == "openrouter" and ([.attempts[].model] | index("opus") == null)' "$TMP/profile-dispatch.receipt"

printf '%s\n' '{"allowPaidClaudeCredits":"yes","disabledCandidates":["opus"]}' > "$TMP/profile-dispatch/.dm/model-router.local.json"
printf '%s\n' '{"model":"claude-opus-5"}' > "$TMP/opus-identity.json"
(
  cd "$TMP/profile-dispatch"
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/profile-dispatch-availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    MODEL_ROUTER_STUB_PROVIDER_RECEIPT="$TMP/opus-identity.json" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role architect --effort medium \
      --capability read-repository --capability long-context --capability structured-output \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/invalid-profile-dispatch.out" --receipt-file "$TMP/invalid-profile-dispatch.receipt" >/dev/null
)
assert jq -e '.served.model == "opus" and .served.servedIdentity == "claude-opus-5"' "$TMP/invalid-profile-dispatch.receipt"

jq '.claude.plan="credits-only" | del(.claude.paidCreditsEnabled)' \
  "$TMP/profile-dispatch-availability.json" > "$TMP/profile-credits-availability.json"
printf '%s\n' '{"allowPaidClaudeCredits":false}' > "$TMP/profile-dispatch/.dm/model-router.local.json"
(
  cd "$TMP/profile-dispatch"
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/profile-credits-availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role architect --effort medium \
      --capability read-repository --capability long-context --capability structured-output \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/credits-disabled-dispatch.out" --receipt-file "$TMP/credits-disabled-dispatch.receipt" >/dev/null
)
assert jq -e '.served.model == "qwen/qwen3.8-max" and ([.attempts[] | select(.model == "opus" and .outcome == "skipped")] | length) == 1' "$TMP/credits-disabled-dispatch.receipt"

printf '%s\n' '{"allowPaidClaudeCredits":true}' > "$TMP/profile-dispatch/.dm/model-router.local.json"
(
  cd "$TMP/profile-dispatch"
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/profile-credits-availability.json" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    "$ROUTER" --workflow-kernel "$KERNEL" --role architect --effort medium \
      --capability read-repository --capability long-context --capability structured-output \
      --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
      --output-file "$TMP/credits-enabled-dispatch.out" --receipt-file "$TMP/credits-enabled-dispatch.receipt" >/dev/null
)
assert jq -e '.served.model == "opus" and .served.billingMode == "paid-credits"' "$TMP/credits-enabled-dispatch.receipt"

# Empty capability lists remain safe under nounset (including Bash 3.2).
fixture healthy
MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability.json" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort low --prompt-file "$TMP/prompt" \
    --output-file "$TMP/no-capabilities.out" --receipt-file "$TMP/no-capabilities.receipt" >/dev/null
assert jq -e '.requested.capabilities == []' "$TMP/no-capabilities.receipt"

# Receipts are exact/content-free; public and peer surfaces remain identity-free.
assert jq -e '.requested.role and .requested.candidate.model and .normalizedEffort and .effectiveEffort == null and .transmittedEffort == null and .effortTransmission.status == "fixture-only" and .participantId and .attempts and .served.model and .served.provider and .served.transport and .served.billingMode and (.served.durationSeconds|type=="number") and (.served.tokenProvenance=="unavailable") and (.served.costProvenance=="unavailable") and .matrixSnapshot and (.fallbackReason|type=="string")' "$TMP/refusal.receipt"
assert sh -c "! grep -Eq 'prompt|bounded role output' '$TMP/refusal.receipt'"
if grep -Fq 'Authorization: Bearer $OPENROUTER_API_KEY' "$PROBE"; then
  printf 'FAIL: OpenRouter credential appears in curl argv\n' >&2
  exit 1
fi
pass=$((pass + 1))
assert grep -Fq -- '-H "@$header_file"' "$PROBE"
assert grep -Fq 'unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE' "$PROBE"

printf 'model-router: %d assertions passed\n' "$pass"
