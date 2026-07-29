#!/usr/bin/env bash
#
# validate-openrouter-cascade.sh -- Guard the OpenRouter model cascade contract.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -t 1 ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[0;33m'
  RESET='\033[0m'
else
  GREEN='' RED='' YELLOW='' RESET=''
fi

fail() {
  printf "  ${RED}FAIL${RESET}  %s\n" "$1"
  return 0
}

pass() {
  printf "  ${GREEN}OK${RESET}    %s\n" "$1"
}

cascade="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
wrapper="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
model_selection="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-selection.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"

any_failed=0

if [ ! -x "$cascade" ]; then
  fail "cascade-dispatch.sh is missing or not executable"
  any_failed=1
else
  probe_fixture="$(mktemp "${TMPDIR:-/tmp}/openrouter-probe.json.XXXXXX")"
  printf '%s\n' '{"codex":{"state":"ok","remaining_pct":100},"openrouter":{"state":"ok","remaining_pct":100}}' > "$probe_fixture"
  out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind logic --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" --exhausted-rail codex 2>/dev/null || true)"
  role="$(printf '%s' "$out" | jq -r '.role // empty' 2>/dev/null || true)"
  kind="$(printf '%s' "$out" | jq -r '.kind // empty' 2>/dev/null || true)"
  model="$(printf '%s' "$out" | jq -r '.model // empty' 2>/dev/null || true)"
  if [ "$role" = "openrouter_exec" ] && [ "$kind" = "openrouter_exec" ] && [ "$model" = "moonshotai/kimi-k3" ]; then
    pass "cascade skips explicitly exhausted Codex rail and descends to OpenRouter exec"
  else
    fail "cascade should descend to quality-first openrouter_exec moonshotai/kimi-k3 when --exhausted-rail codex is set"
    printf "  ${YELLOW}GOT${RESET}   %s\n" "${out:-<empty>}"
    any_failed=1
  fi

  ui_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind ui --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" 2>/dev/null || true)"
  ui_role="$(printf '%s' "$ui_out" | jq -r '.role // empty' 2>/dev/null || true)"
  ui_kind="$(printf '%s' "$ui_out" | jq -r '.kind // empty' 2>/dev/null || true)"
  if [ "$ui_role" = "premium_sub" ] && [ "$ui_kind" = "native" ]; then
    pass "UI coding selects Codex-native subscription execution"
  else
    fail "UI coding must resolve to Codex-native execution, never Claude"
    any_failed=1
  fi

  or_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind docs --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" --exhausted-rail openrouter 2>/dev/null || true)"
  or_role="$(printf '%s' "$or_out" | jq -r '.role // empty' 2>/dev/null || true)"
  if [ "$or_role" = "premium_sub" ] &&
     printf '%s' "$or_out" | jq -e '
       .requestedProvider == "openrouter" and
       .requestedModel == "moonshotai/kimi-k3" and
       .attemptedProvider == "codex" and
       .attemptedModel == "gpt-5.6-sol" and
       .actualImplementer == "codex" and
       .actualModel == "gpt-5.6-sol" and
       .fallback == true and
       .native_vendor_origin_invariant == "passed"
     ' >/dev/null 2>&1; then
    pass "OpenRouter-primary coding returns to Codex when OpenRouter is exhausted"
  else
    fail "OpenRouter-primary coding must return to Codex, never Claude"
    any_failed=1
  fi

  # bash 3.2 portability: the DEFAULT path (no --exhausted-rail, empty list) must
  # not trip the empty-array + set -u fatal. Exercise it under the system /bin/bash
  # (3.2 on macOS) explicitly -- env bash may be a modern build that hides the bug.
  if [ -x /bin/bash ]; then
    base_out="$(CASCADE_EXHAUSTED_RAILS= /bin/bash "$cascade" --kind logic --prompt test \
      --host codex --dry-run --probe-file "$probe_fixture" 2>/dev/null || true)"
    if printf '%s' "$base_out" | jq -e '.model' >/dev/null 2>&1; then
      pass "cascade-dispatch runs clean under system bash with no --exhausted-rail"
    else
      fail "cascade-dispatch breaks under system /bin/bash when --exhausted-rail is unset (bash 3.2 empty-array)"
      any_failed=1
    fi
  fi

  malformed_profile="$(mktemp "${TMPDIR:-/tmp}/openrouter-profile.json.XXXXXX")"
  jq '.hosts.codex.roles.openrouter_exec.kind = "unknown_rail"
      | .hosts.codex.roles.openrouter_exec.probe = "none"' \
    "$REPO_ROOT/plugins/pipeline/references/harness-profile.json" > "$malformed_profile"
  set +e
  malformed_out="$(CASCADE_EXHAUSTED_RAILS= PROFILE_FILE="$malformed_profile" "$cascade" \
    --class openrouter --prompt test --host codex --probe-file "$probe_fixture" 2>&1)"
  malformed_rc=$?
  set -e
  rm -f "$malformed_profile"
  if [ "$malformed_rc" -eq 2 ] &&
     printf '%s' "$malformed_out" | grep -Fq "unknown rail kind 'unknown_rail'"; then
    pass "unknown cascade rail kind fails closed"
  else
    fail "unknown cascade rail kind must fail closed with exit 2"
    any_failed=1
  fi

  origin_profile="$(mktemp "${TMPDIR:-/tmp}/openrouter-origin-profile.json.XXXXXX")"
  jq '.hosts.codex.roles.openrouter_exec.models = ["OpenAI/gpt-test"]' \
    "$REPO_ROOT/plugins/pipeline/references/harness-profile.json" > "$origin_profile"
  set +e
  origin_out="$(CASCADE_EXHAUSTED_RAILS= PROFILE_FILE="$origin_profile" "$cascade" \
    --class openrouter --prompt test --host codex --dry-run \
    --probe-file "$probe_fixture" 2>&1)"
  origin_rc=$?
  set -e
  rm -f "$origin_profile"
  if [ "$origin_rc" -eq 2 ] &&
     printf '%s' "$origin_out" | grep -Fq "native-vendor-origin invariant"; then
    pass "mixed-case OpenAI/Anthropic origins fail before OpenRouter dispatch"
  else
    fail "mixed-case native-vendor origins must be rejected on the cascade path"
    any_failed=1
  fi

  if grep -Eq 'mktemp .*XXXXXX\.' \
      "$cascade" "$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"; then
    fail "OpenRouter runners use BSD-incompatible mktemp suffix templates"
    any_failed=1
  else
    pass "OpenRouter runner temp templates end in XXXXXX for BSD portability"
  fi
  rm -f "$probe_fixture"
fi

if grep -q 'zdr: true' "$wrapper" && grep -q 'data_collection: "deny"' "$wrapper"; then
  pass "OpenRouter ZDR mode requests both zdr:true and data_collection:deny"
else
  fail "OPENROUTER_ZDR=1 must send provider.zdr=true as well as data_collection=deny"
  any_failed=1
fi

fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/openrouter-origin.XXXXXX")"
server_pid=""
cleanup() {
  [ -z "$server_pid" ] || kill "$server_pid" >/dev/null 2>&1 || true
  rm -rf "$fixture_root"
}
trap cleanup EXIT
network_marker="$fixture_root/network.marker"
fail_primary="$fixture_root/fail-primary"
missing_model="$fixture_root/missing-model"
missing_provider="$fixture_root/missing-provider"
malformed_model="$fixture_root/malformed-model"
substituted_model="$fixture_root/substituted-model"
port_file="$fixture_root/port"
request_file="$fixture_root/request.json"
cat > "$fixture_root/http-sentinel.py" <<'PY'
import http.server
import json
import pathlib
import sys

marker = pathlib.Path(sys.argv[1])
fail_primary = pathlib.Path(sys.argv[2])
port_file = pathlib.Path(sys.argv[3])
request_file = pathlib.Path(sys.argv[4])
missing_model = pathlib.Path(sys.argv[5])
missing_provider = pathlib.Path(sys.argv[6])
malformed_model = pathlib.Path(sys.argv[7])
substituted_model = pathlib.Path(sys.argv[8])

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        document = json.loads(self.rfile.read(length))
        model = document.get("model", "")
        request_file.write_text(json.dumps(document), encoding="utf-8")
        with marker.open("a", encoding="utf-8") as output:
            output.write(model + "\n")
        if fail_primary.exists() and model == "z-ai/glm-5.2":
            status = 429
            response = {"error": {"message": "capacity"}}
        else:
            status = 200
            response = {
                "id": "gen-fixture",
                "created": 1785210000,
                "model": model + "-canonical",
                "provider": "FixtureProvider",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
                "choices": [{"message": {"content": "controlled"}}],
            }
            if missing_model.exists():
                response.pop("model")
            if missing_provider.exists():
                response.pop("provider")
            if malformed_model.exists():
                response["model"] = "unqualified-model"
            if substituted_model.exists():
                response["model"] = "z-ai/glm-5.2"
        payload = json.dumps(response).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass

server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
port_file.write_text(str(server.server_port), encoding="utf-8")
server.serve_forever()
PY
python3 "$fixture_root/http-sentinel.py" \
  "$network_marker" "$fail_primary" "$port_file" "$request_file" \
  "$missing_model" "$missing_provider" "$malformed_model" "$substituted_model" &
server_pid=$!
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  [ -s "$port_file" ] && break
  sleep 0.1
done
[ -s "$port_file" ] || {
  fail "controlled loopback network sentinel did not start"
  exit 1
}
sentinel_base="http://127.0.0.1:$(cat "$port_file")"

if grep -q 'OPENROUTER_CURL_CMD\|"\$CURL_CMD"' "$wrapper"; then
  fail "wrapper must not accept a caller-selected curl command"
  any_failed=1
else
  pass "wrapper retains fixed-path curl execution"
fi

forbidden_case() {
  local label="$1" primary="$2" fallback="$3" rc
  rm -f "$network_marker" "$fail_primary"
  set +e
  OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
    "$wrapper" "$primary" test 10 "$fallback" >/dev/null 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 2 ] && [ ! -e "$network_marker" ]; then
    pass "$label stops before network contact"
  else
    fail "$label must reject before network contact"
    any_failed=1
  fi
}

forbidden_case primary-openai openai/gpt-test ""
forbidden_case fallback-openai z-ai/glm-5.2 openai/gpt-test
forbidden_case primary-anthropic anthropic/claude-test ""
forbidden_case fallback-anthropic z-ai/glm-5.2 anthropic/claude-test

rm -f "$network_marker" "$fail_primary"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   "$wrapper" z-ai/glm-5.2 test 10 >/dev/null 2>&1 &&
   grep -Fxq z-ai/glm-5.2 "$network_marker"; then
  pass "allowed GLM reaches the controlled network sentinel"
else
  fail "allowed GLM must prove the sentinel is reachable"
  any_failed=1
fi

receipt_file="$fixture_root/kimi-receipt.json"
rm -f "$network_marker" "$request_file" "$receipt_file"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_RECEIPT_FILE="$receipt_file" \
   "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1 &&
   jq -e '.provider.sort == "exacto" and (.provider | has("order") | not)' \
     "$request_file" >/dev/null &&
   jq -e '
     .generationId == "gen-fixture"
     and .requestedModel == "moonshotai/kimi-k3"
     and .attemptedModel == "moonshotai/kimi-k3"
     and .attemptedModels == ["moonshotai/kimi-k3"]
     and .fallbackUsed == false
     and .responseModel == "moonshotai/kimi-k3-canonical"
     and .responseModelProvenance == "response"
     and .servingProvider == "FixtureProvider"
     and .servingProviderProvenance == "response"
     and .usage.total_tokens == 15
   ' "$receipt_file" >/dev/null; then
  pass "Kimi defaults to live quality-first Exacto routing and emits a content-free receipt"
else
  fail "Kimi must use Exacto by default and preserve generation/provider/usage evidence"
  any_failed=1
fi

missing_model_receipt="$fixture_root/missing-model-receipt.json"
rm -f "$network_marker" "$missing_model_receipt"
touch "$missing_model"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_RECEIPT_FILE="$missing_model_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
missing_model_rc=$?
set -e
rm -f "$missing_model"
if [ "$missing_model_rc" -eq 1 ] && [ ! -e "$missing_model_receipt" ]; then
  pass "a successful HTTP response without model provenance fails closed"
else
  fail "missing response.model must not become a successful or inferred receipt"
  any_failed=1
fi

missing_provider_receipt="$fixture_root/missing-provider-receipt.json"
rm -f "$network_marker" "$missing_provider_receipt"
touch "$missing_provider"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_RECEIPT_FILE="$missing_provider_receipt" \
   "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1 &&
   jq -e '
     .servingProvider == null
     and .servingProviderProvenance == "not_reported_by_completion"
     and .responseModel == "moonshotai/kimi-k3-canonical"
   ' "$missing_provider_receipt" >/dev/null; then
  pass "an omitted provider is recorded as not reported, not inferred"
else
  fail "missing provider identity must remain explicit provenance uncertainty"
  any_failed=1
fi
rm -f "$missing_provider"

malformed_model_receipt="$fixture_root/malformed-model-receipt.json"
rm -f "$network_marker" "$malformed_model_receipt"
touch "$malformed_model"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_RECEIPT_FILE="$malformed_model_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
malformed_model_rc=$?
set -e
rm -f "$malformed_model"
if [ "$malformed_model_rc" -eq 1 ] && [ ! -e "$malformed_model_receipt" ]; then
  pass "an unqualified response model fails provenance validation"
else
  fail "response model must retain canonical provider/model origin"
  any_failed=1
fi

substituted_model_receipt="$fixture_root/substituted-model-receipt.json"
rm -f "$network_marker" "$substituted_model_receipt"
touch "$substituted_model"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_RECEIPT_FILE="$substituted_model_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
substituted_model_rc=$?
set -e
rm -f "$substituted_model"
if [ "$substituted_model_rc" -eq 1 ] && [ ! -e "$substituted_model_receipt" ]; then
  pass "an unrelated served model fails attempted-family validation"
else
  fail "served model provenance must match the attempted model family"
  any_failed=1
fi

rm -f "$network_marker" "$request_file"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_PROVIDER_ORDER=baseten/fp8,moonshotai/mxfp4 \
   OPENROUTER_ALLOW_FALLBACKS=0 \
   "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1 &&
   jq -e '
     .provider.order == ["baseten/fp8", "moonshotai/mxfp4"]
     and .provider.allow_fallbacks == false
     and (.provider | has("sort") | not)
   ' "$request_file" >/dev/null; then
  pass "explicit endpoint order overrides dynamic sorting for reproducible Kimi calls"
else
  fail "explicit Kimi endpoint order must be preserved without an ambiguous sort"
  any_failed=1
fi

rm -f "$network_marker"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_PROVIDER_SORT=unknown \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
invalid_sort_rc=$?
set -e
if [ "$invalid_sort_rc" -eq 2 ] && [ ! -e "$network_marker" ]; then
  pass "invalid provider sort fails before network contact"
else
  fail "invalid provider sort must fail closed before network contact"
  any_failed=1
fi

fallback_receipt="$fixture_root/fallback-receipt.json"
rm -f "$network_marker" "$fallback_receipt"
touch "$fail_primary"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_RECEIPT_FILE="$fallback_receipt" \
   OPENROUTER_PROVIDER_ORDER=fixture/primary,fixture/fallback \
   OPENROUTER_FALLBACK_PROVIDER_ORDER=fixture/fallback-a,fixture/fallback-b \
   OPENROUTER_ALLOW_FALLBACKS=0 \
   "$wrapper" z-ai/glm-5.2 test 10 deepseek/deepseek-v4-pro \
   >/dev/null 2>&1 &&
   [ "$(sed -n '1p' "$network_marker")" = "z-ai/glm-5.2" ] &&
   [ "$(sed -n '2p' "$network_marker")" = "deepseek/deepseek-v4-pro" ] &&
   jq -e '
     .requestedModel == "z-ai/glm-5.2"
     and .attemptedModel == "deepseek/deepseek-v4-pro"
     and .attemptedModels == ["z-ai/glm-5.2", "deepseek/deepseek-v4-pro"]
     and .fallbackUsed == true
     and .responseModel == "deepseek/deepseek-v4-pro-canonical"
   ' "$fallback_receipt" >/dev/null &&
   jq -e '
     .provider.order == ["fixture/fallback-a", "fixture/fallback-b"]
     and .provider.allow_fallbacks == false
   ' "$request_file" >/dev/null; then
  pass "fallback preserves explicit endpoint order and reports the actual served model"
else
  fail "fallback sentinel sequence, provider order, or provenance receipt is invalid"
  any_failed=1
fi
rm -f "$fail_primary"

kimi_fallback_receipt="$fixture_root/kimi-fallback-receipt.json"
rm -f "$network_marker" "$request_file" "$kimi_fallback_receipt"
touch "$fail_primary"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_RECEIPT_FILE="$kimi_fallback_receipt" \
   "$wrapper" z-ai/glm-5.2 test 10 moonshotai/kimi-k3 \
   >/dev/null 2>&1 &&
   jq -e '.provider.sort == "exacto" and (.provider | has("order") | not)' \
     "$request_file" >/dev/null &&
   jq -e '
     .attemptedModels == ["z-ai/glm-5.2", "moonshotai/kimi-k3"]
     and .fallbackUsed == true
   ' "$kimi_fallback_receipt" >/dev/null; then
  pass "GLM-to-Kimi fallback recomputes Kimi's Exacto provider default"
else
  fail "fallback provider preferences must be derived from the attempted model"
  any_failed=1
fi
rm -f "$fail_primary"

fallback_block="$(awk '/## Rate-Limit Fallback Chain/{flag=1; next} /## Privacy/{flag=0} flag' "$model_selection")"
if printf '%s' "$fallback_block" | grep -q 'minimax/minimax-m3'; then
  pass "OpenRouter fallback docs include MiniMax-M3"
else
  fail "model-selection.md fallback chain is missing minimax/minimax-m3"
  any_failed=1
fi

if grep -q -- '--exhausted-rail' "$orchestrator"; then
  pass "pipeline orchestrator passes observed exhausted rail into cascade"
else
  fail "execution-orchestrator.md must pass --exhausted-rail after cap/unavailable events"
  any_failed=1
fi

if [ "$any_failed" -ne 0 ]; then
  exit 1
fi

printf "  ${GREEN}OK${RESET}    OpenRouter cascade contract valid\n"
