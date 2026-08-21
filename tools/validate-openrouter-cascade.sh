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

routine_review_routes_valid() {
  local source="$1"
  jq -e '
    .agentType as $a
    | $a["pattern-recognition-specialist"].provider == "openrouter"
      and $a["pattern-recognition-specialist"].model == "deepseek/deepseek-v4-pro-0813"
      and $a["pattern-recognition-specialist"].fallbackModel == "qwen/qwen3.8-max"
      and $a["pattern-recognition-specialist"].fallbackProvider == "codex"
      and $a["code-simplicity-reviewer"].provider == "openrouter"
      and $a["code-simplicity-reviewer"].model == "qwen/qwen3.8-max"
      and $a["code-simplicity-reviewer"].fallbackModel == "deepseek/deepseek-v4-pro-0813"
      and $a["code-simplicity-reviewer"].fallbackProvider == "codex"
      and $a["doc-sync-reviewer"].provider == "openrouter"
      and $a["doc-sync-reviewer"].model == "deepseek/deepseek-v4-flash-0731"
      and $a["doc-sync-reviewer"].fallbackModel == "openai/gpt-5.6-luna"
      and $a["doc-sync-reviewer"].fallbackProvider == "codex"
      and $a["test-coverage-reviewer"].provider == "openrouter"
      and $a["test-coverage-reviewer"].model == "deepseek/deepseek-v4-flash-0731"
      and $a["test-coverage-reviewer"].fallbackModel == "openai/gpt-5.6-luna"
      and $a["test-coverage-reviewer"].fallbackProvider == "codex"
  ' "$source" >/dev/null 2>&1
}

expect_routine_review_route_reject() {
  local label="$1"
  local filter="$2"
  local mutated

  if ! mutated="$(jq -c "$filter" "$routing_policy")"; then
    fail "routine review mutation fixture builds: $label"
    any_failed=1
  elif printf '%s\n' "$mutated" | routine_review_routes_valid -; then
    fail "routine review routes reject mutation: $label"
    any_failed=1
  else
    pass "routine review routes reject mutation: $label"
  fi
}

cascade="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
wrapper="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
boundary="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh"
security_policy="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
model_selection="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-selection.md"
matrix_refresh_receipt="$REPO_ROOT/docs/openrouter-model-matrix-refreshes/2026-08-21.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"

any_failed=0

if [ ! -x "$cascade" ]; then
  fail "cascade-dispatch.sh is missing or not executable"
  any_failed=1
else
  probe_fixture="$(mktemp "${TMPDIR:-/tmp}/openrouter-probe.json.XXXXXX")"
  printf '%s\n' '{"probe_source":"live","codex":{"state":"ok","remaining_pct":100},"openrouter":{"state":"ok","balance_usd":0.01}}' > "$probe_fixture"
  out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind logic --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" --exhausted-rail codex 2>/dev/null || true)"
  role="$(printf '%s' "$out" | jq -r '.role // empty' 2>/dev/null || true)"
  kind="$(printf '%s' "$out" | jq -r '.kind // empty' 2>/dev/null || true)"
  model="$(printf '%s' "$out" | jq -r '.model // empty' 2>/dev/null || true)"
  fixture_source="$(printf '%s' "$out" | jq -r '.probe_source // empty' 2>/dev/null || true)"
  if [ "$role" = "openrouter_exec" ] && [ "$kind" = "openrouter_exec" ] &&
     [ "$model" = "deepseek/deepseek-v4-flash-0731" ] && [ "$fixture_source" = "fixture" ]; then
    pass "cascade skips explicitly exhausted Codex rail and descends to OpenRouter exec"
  else
    fail "cascade should descend to economical OpenRouter and must label caller probe files as fixture, never live"
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

  inherited_home="$(mktemp -d "${TMPDIR:-/tmp}/openrouter-inherited-binding.XXXXXX")"
  inherited_marker="$inherited_home/forged-loader-ran"
  inherited_root="$inherited_home/.codex/plugins/cache/depot/openrouter/9.9.9"
  mkdir -p "$inherited_root/skills/openrouter-delegate/references"
  cat > "$inherited_root/skills/openrouter-delegate/references/openrouter-credential.sh" <<EOF
touch "$inherited_marker"
load_openrouter_api_key() { return 1; }
EOF
  inherited_key="$inherited_home/key"
  printf 'test\n' > "$inherited_key"
  chmod 600 "$inherited_key"
  set +e
  HOME="$inherited_home" WORKFLOW_KERNEL=/bin/false OPENROUTER_API_KEY_FILE="$inherited_key" \
    OPENROUTER_BUNDLE_REF='~/.codex/plugins/cache/depot/openrouter/9.9.9' \
    OPENROUTER_BUNDLE_VERSION=9.9.9 OPENROUTER_BUNDLE_CACHE_CLASS=codex \
    OPENROUTER_BUNDLE_REASON=forged OPENROUTER_BUNDLE_RESOLVED=1 \
    "$cascade" --kind config --prompt test --host codex >/dev/null 2>&1
  inherited_rc=$?
  set -e
  if [ "$inherited_rc" -eq 76 ] && [ ! -e "$inherited_marker" ]; then
    pass "failed bundle resolution ignores inherited OpenRouter bindings"
  else
    fail "failed bundle resolution must clear inherited OpenRouter bindings"
    any_failed=1
  fi
  rm -rf "$inherited_home"

  # Headroom is positive evidence, not an absence-of-error default. Every
  # unknown, missing, malformed, or at-threshold Codex reading must skip the
  # Codex rung while a separately healthy OpenRouter fixture remains eligible.
  while IFS='|' read -r label codex_probe; do
    printf '%s\n' "{\"codex\":$codex_probe,\"openrouter\":{\"state\":\"ok\",\"balance_usd\":0.01}}" > "$probe_fixture"
    conservative_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind logic --prompt test --host codex \
      --dry-run --probe-file "$probe_fixture" 2>/dev/null || true)"
    conservative_role="$(printf '%s' "$conservative_out" | jq -r '.role // empty' 2>/dev/null || true)"
    if [ "$conservative_role" = "openrouter_exec" ]; then
      pass "$label Codex headroom is unavailable"
    else
      fail "$label Codex headroom must fail closed to the healthy OpenRouter rung"
      any_failed=1
    fi
  done <<'EOF'
unknown|{"state":"unknown","remaining_pct":100}
missing state|{"remaining_pct":100}
missing percentage|{"state":"ok"}
malformed percentage|{"state":"ok","remaining_pct":"100"}
at-threshold|{"state":"ok","remaining_pct":8}
EOF

  printf '%s\n' '{"openrouter":{"state":"ok","balance_usd":0.01}}' > "$probe_fixture"
  missing_rail_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind logic --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" 2>/dev/null || true)"
  missing_rail_role="$(printf '%s' "$missing_rail_out" | jq -r '.role // empty' 2>/dev/null || true)"
  if [ "$missing_rail_role" = "openrouter_exec" ]; then
    pass "missing Codex probe record is unavailable"
  else
    fail "missing Codex probe record must fail closed to the healthy OpenRouter rung"
    any_failed=1
  fi

  printf '%s\n' '{not-json' > "$probe_fixture"
  set +e
  malformed_probe_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind logic --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" 2>&1)"
  malformed_probe_rc=$?
  set -e
  if [ "$malformed_probe_rc" -eq 76 ] &&
     printf '%s' "$malformed_probe_out" | grep -Fq "ladder exhausted"; then
    pass "malformed probe document makes every rail unavailable"
  else
    fail "malformed probe document must fail closed with exhausted-ladder exit 76"
    any_failed=1
  fi

  while IFS='|' read -r label openrouter_probe; do
    printf '%s\n' "{\"codex\":{\"state\":\"ok\",\"remaining_pct\":100},\"openrouter\":$openrouter_probe}" > "$probe_fixture"
    conservative_or_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind docs --prompt test --host codex \
      --dry-run --probe-file "$probe_fixture" 2>/dev/null || true)"
    conservative_or_role="$(printf '%s' "$conservative_or_out" | jq -r '.role // empty' 2>/dev/null || true)"
    if [ "$conservative_or_role" = "premium_sub" ]; then
      pass "$label OpenRouter balance is unavailable"
    else
      fail "$label OpenRouter balance must fail closed to the healthy Codex rung"
      any_failed=1
    fi
  done <<'EOF'
unknown|{"state":"unknown","balance_usd":100}
missing balance|{"state":"ok"}
malformed balance|{"state":"ok","balance_usd":"100"}
negative balance|{"state":"ok","balance_usd":-1}
EOF

  printf '%s\n' '{"codex":{"state":"ok","remaining_pct":100},"openrouter":{"state":"ok","balance_usd":0.01}}' > "$probe_fixture"

  or_out="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind docs --prompt test --host codex \
    --dry-run --probe-file "$probe_fixture" --exhausted-rail openrouter 2>/dev/null || true)"
  or_role="$(printf '%s' "$or_out" | jq -r '.role // empty' 2>/dev/null || true)"
  if [ "$or_role" = "premium_sub" ] &&
     printf '%s' "$or_out" | jq -e '
       .requestedProvider == "openrouter" and
       .requestedModel == "deepseek/deepseek-v4-flash-0731" and
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
  jq '.hosts.codex.roles.openrouter_exec.models = ["Anthropic/claude-test"]' \
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
    pass "mixed-case Anthropic origins fail before OpenRouter dispatch"
  else
    fail "mixed-case Anthropic origins must be rejected on the cascade path"
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
  if [ -n "$server_pid" ]; then
    kill "$server_pid" >/dev/null 2>&1 || true
    wait "$server_pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$fixture_root"
}
trap cleanup EXIT
trusted_system="$fixture_root/trusted.system"
trusted_prompt="$fixture_root/trusted.prompt"
printf '%s' 'You are a bounded test assistant.' > "$trusted_system"
printf '%s' 'Review this public fixture.' > "$trusted_prompt"
if "$boundary" --mode artifact-delegation --policy "$security_policy" \
   --content-file "$trusted_system" --content-file "$trusted_prompt" >/dev/null; then
  pass "automatic boundary accepts harmless private outbound files"
else
  fail "automatic boundary must accept harmless private outbound files"
  any_failed=1
fi

printf '%s' 'OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890' > "$trusted_prompt"
set +e
"$boundary" --mode artifact-delegation --policy "$security_policy" \
  --content-file "$trusted_system" --content-file "$trusted_prompt" \
  >/dev/null 2>&1
trusted_secret_rc=$?
set -e
if [ "$trusted_secret_rc" -eq 3 ]; then
  pass "automatic boundary declines credential-class content"
else
  fail "automatic boundary must retain the canonical disclosure scanner"
  any_failed=1
fi

network_marker="$fixture_root/network.marker"
fail_primary="$fixture_root/fail-primary"
missing_model="$fixture_root/missing-model"
missing_provider="$fixture_root/missing-provider"
malformed_model="$fixture_root/malformed-model"
substituted_model="$fixture_root/substituted-model"
stall_stream="$fixture_root/stall-stream"
delay_first_byte="$fixture_root/delay-first-byte"
stream_error="$fixture_root/stream-error"
port_file="$fixture_root/port"
request_file="$fixture_root/request.json"
cat > "$fixture_root/http-sentinel.py" <<'PY'
import http.server
import json
import pathlib
import sys
import time

marker = pathlib.Path(sys.argv[1])
fail_primary = pathlib.Path(sys.argv[2])
port_file = pathlib.Path(sys.argv[3])
request_file = pathlib.Path(sys.argv[4])
missing_model = pathlib.Path(sys.argv[5])
missing_provider = pathlib.Path(sys.argv[6])
malformed_model = pathlib.Path(sys.argv[7])
substituted_model = pathlib.Path(sys.argv[8])
stall_stream = pathlib.Path(sys.argv[9])
delay_first_byte = pathlib.Path(sys.argv[10])
stream_error = pathlib.Path(sys.argv[11])

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        document = json.loads(self.rfile.read(length))
        candidates = document.get("models") or [document.get("model", "")]
        model = candidates[0]
        selected_model = model
        if fail_primary.exists() and len(candidates) > 1:
            selected_model = candidates[1]
        request_file.write_text(json.dumps(document), encoding="utf-8")
        with marker.open("a", encoding="utf-8") as output:
            output.write(",".join(candidates) + "\n")
        if fail_primary.exists() and len(candidates) == 1:
            status = 429
            response = {"error": {"message": "capacity"}}
        else:
            status = 200
            response = {
                "id": "gen-fixture",
                "created": 1785210000,
                "model": selected_model + "-canonical",
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
        if status != 200:
            payload = json.dumps(response).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if delay_first_byte.exists():
            time.sleep(2)
        first = {
            key: response[key]
            for key in ("id", "created", "model", "provider")
            if key in response
        }
        first["choices"] = [{"delta": {"content": "con"}}]
        second = {"choices": [{"delta": {"content": "trolled"}}]}
        final = {
            "usage": response["usage"],
            "choices": [{"delta": {}, "finish_reason": "stop"}],
        }
        if stream_error.exists():
            second = {"error": {"code": 502, "message": "fixture stream failure"}}
        chunks = [first, second, final]
        try:
            for index, chunk in enumerate(chunks):
                payload = f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                self.wfile.write(payload)
                self.wfile.flush()
                if index == 0 and stall_stream.exists():
                    time.sleep(3)
            if not stream_error.exists():
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass

server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
port_file.write_text(str(server.server_port), encoding="utf-8")
server.serve_forever()
PY
python3 "$fixture_root/http-sentinel.py" \
  "$network_marker" "$fail_primary" "$port_file" "$request_file" \
  "$missing_model" "$missing_provider" "$malformed_model" "$substituted_model" \
  "$stall_stream" "$delay_first_byte" "$stream_error" &
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

if grep -q -- '-H "Authorization: Bearer \$OPENROUTER_API_KEY"' "$wrapper" ||
   ! grep -q -- '-H "@\$authorization_header_file"' "$wrapper" ||
   ! grep -q 'unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE' "$wrapper"; then
  fail "wrapper must keep the bearer value out of curl argv and environment"
  any_failed=1
else
  pass "wrapper keeps the bearer value out of curl argv and environment"
fi

rm -f "$network_marker"
set +e
OPENROUTER_API_KEY=sk-or-v1-production-looking-key \
  OPENROUTER_BASE="$sentinel_base" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
production_key_loopback_rc=$?
set -e
if [ "$production_key_loopback_rc" -eq 2 ] && [ ! -e "$network_marker" ]; then
  pass "production-looking API key cannot use a loopback base override"
else
  fail "production-looking API key must be rejected before loopback network contact"
  any_failed=1
fi

rm -f "$network_marker"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="http://0.0.0.0:$(cat "$port_file")" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
non_loopback_rc=$?
set -e
if [ "$non_loopback_rc" -eq 2 ] && [ ! -e "$network_marker" ]; then
  pass "fixture API key cannot override the base to a non-allowlisted host"
else
  fail "non-allowlisted base override must be rejected before network contact"
  any_failed=1
fi

system_bytes_file="$fixture_root/system-bytes.prompt"
user_bytes_file="$fixture_root/user-bytes.prompt"
printf 'first system line\nsecond system line\n\n' > "$system_bytes_file"
printf 'first user line\nsecond user line\n\n' > "$user_bytes_file"
rm -f "$network_marker" "$request_file"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_SYSTEM_FILE="$system_bytes_file" \
   "$wrapper" moonshotai/kimi-k3 - 10 < "$user_bytes_file" >/dev/null 2>&1 &&
   jq -e '.messages[0].content == "first system line\nsecond system line\n\n"
     and .messages[1].content == "first user line\nsecond user line\n\n"' \
     "$request_file" >/dev/null; then
  pass "file-based system and stdin user prompts preserve trailing newline bytes"
else
  fail "wrapper must preserve complete system and user prompt bytes"
  any_failed=1
fi

rm -f "$network_marker"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_SYSTEM=inline OPENROUTER_SYSTEM_FILE="$system_bytes_file" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
conflicting_system_rc=$?
set -e
if [ "$conflicting_system_rc" -eq 2 ] && [ ! -e "$network_marker" ]; then
  pass "conflicting system prompt interfaces stop before network contact"
else
  fail "OPENROUTER_SYSTEM and OPENROUTER_SYSTEM_FILE must be mutually exclusive"
  any_failed=1
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

forbidden_case primary-anthropic anthropic/claude-test ""
forbidden_case fallback-anthropic z-ai/glm-5.2 anthropic/claude-test

for openai_slug in openai/gpt-test openai/gpt-5.6-luna openai/gpt-5.6-terra; do
  rm -f "$network_marker" "$fail_primary"
  if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
     "$wrapper" "$openai_slug" test 10 >/dev/null 2>&1 &&
     grep -Fxq "$openai_slug" "$network_marker"; then
    pass "allowed OpenAI API slug $openai_slug reaches the controlled network sentinel"
  else
    fail "allowed OpenAI API slug $openai_slug must prove the sentinel is reachable"
    any_failed=1
  fi
done

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
   jq -e '
     .stream == true
     and .stream_options.include_usage == true
     and .provider.sort == "exacto"
     and .provider.allow_fallbacks == true
     and (.provider | has("order") | not)
   ' \
     "$request_file" >/dev/null &&
   jq -e '
     .schemaVersion == 2
     and .outcome == "success"
     and .generationId == "gen-fixture"
     and .requestedModel == "moonshotai/kimi-k3"
     and .modelCandidates == ["moonshotai/kimi-k3"]
     and .attemptedModel == "moonshotai/kimi-k3"
     and .attemptedModels == ["moonshotai/kimi-k3"]
     and .fallbackUsed == false
     and .responseModel == "moonshotai/kimi-k3-canonical"
     and .responseModelProvenance == "response"
     and .servingProvider == "FixtureProvider"
     and .servingProviderProvenance == "response"
     and .usage.total_tokens == 15
     and .routing.workload == "quality"
     and .routing.sort == "exacto"
   ' "$receipt_file" >/dev/null; then
  pass "Kimi quality work streams with Exacto routing and emits a content-free receipt"
else
  fail "Kimi quality work must stream with native routing and preserve generation/provider/usage evidence"
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
if [ "$missing_model_rc" -eq 1 ] &&
   jq -e '
     .outcome == "error"
     and .failureKind == "missing_generation_provenance"
     and .responseModel == null
     and .servingProvider == null
     and .usage == null
     and (has("prompt") | not)
   ' "$missing_model_receipt" >/dev/null; then
  pass "a stream without model provenance fails closed with a content-free receipt"
else
  fail "missing response.model must produce a non-inferred failure receipt"
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
if [ "$malformed_model_rc" -eq 1 ] &&
   jq -e '
     .outcome == "error"
     and .failureKind == "malformed_model_provenance"
     and .attemptedModels == null
   ' "$malformed_model_receipt" >/dev/null; then
  pass "an unqualified response model fails with explicit provenance uncertainty"
else
  fail "malformed response provenance must produce a content-free failure receipt"
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
if [ "$substituted_model_rc" -eq 1 ] &&
   jq -e '
     .outcome == "error"
     and .failureKind == "unexpected_model_provenance"
     and .attemptedModels == null
   ' "$substituted_model_receipt" >/dev/null; then
  pass "an unrelated served model fails attempted-family validation with a receipt"
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
   [ "$(sed -n '1p' "$network_marker")" = "z-ai/glm-5.2,deepseek/deepseek-v4-pro" ] &&
   [ "$(wc -l < "$network_marker" | tr -d '[:space:]')" = "1" ] &&
   jq -e '
     .models == ["z-ai/glm-5.2", "deepseek/deepseek-v4-pro"]
     and .stream == true
   ' "$request_file" >/dev/null &&
   jq -e '
     .requestedModel == "z-ai/glm-5.2"
     and .modelCandidates == ["z-ai/glm-5.2", "deepseek/deepseek-v4-pro"]
     and .attemptedModel == "deepseek/deepseek-v4-pro"
     and .attemptedModels == ["z-ai/glm-5.2", "deepseek/deepseek-v4-pro"]
     and .fallbackUsed == true
     and .responseModel == "deepseek/deepseek-v4-pro-canonical"
   ' "$fallback_receipt" >/dev/null &&
   jq -e '
     .provider.order == [
       "fixture/primary",
       "fixture/fallback",
       "fixture/fallback-a",
       "fixture/fallback-b"
     ]
     and .provider.allow_fallbacks == false
   ' "$request_file" >/dev/null; then
  pass "one native request preserves endpoint order and reports the served fallback model"
else
  fail "native model fallback, provider order, or provenance receipt is invalid"
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
     .modelCandidates == ["z-ai/glm-5.2", "moonshotai/kimi-k3"]
     and .attemptedModels == ["z-ai/glm-5.2", "moonshotai/kimi-k3"]
     and .fallbackUsed == true
   ' "$kimi_fallback_receipt" >/dev/null; then
  pass "a quality fallback list containing Kimi retains Exacto routing"
else
  fail "quality-native fallback routing must retain Kimi's Exacto preference"
  any_failed=1
fi
rm -f "$fail_primary"

direct_receipt="$fixture_root/direct-receipt.json"
rm -f "$network_marker" "$request_file" "$direct_receipt"
if OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
   OPENROUTER_WORKLOAD=direct \
   OPENROUTER_RECEIPT_FILE="$direct_receipt" \
   "$wrapper" moonshotai/kimi-k3 test 10 z-ai/glm-5.2 \
   >/dev/null 2>&1 &&
   jq -e '
     .models == ["moonshotai/kimi-k3", "z-ai/glm-5.2"]
     and .provider.sort == "throughput"
     and .provider.allow_fallbacks == true
   ' "$request_file" >/dev/null &&
   jq -e '
     .routing.workload == "direct"
     and .routing.sort == "throughput"
     and (.authorization | has("mode") | not)
   ' "$direct_receipt" >/dev/null; then
  pass "direct Kimi work prefers throughput and records request evidence"
else
  fail "direct workload routing must preserve fallbacks and request evidence"
  any_failed=1
fi

invalid_workload_receipt="$fixture_root/invalid-workload-receipt.json"
rm -f "$network_marker" "$invalid_workload_receipt"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_WORKLOAD=unknown \
  OPENROUTER_RECEIPT_FILE="$invalid_workload_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
invalid_workload_rc=$?
set -e
if [ "$invalid_workload_rc" -eq 2 ] && [ ! -e "$network_marker" ]; then
  pass "invalid workload routing fails before network contact"
else
  fail "invalid OPENROUTER_WORKLOAD must fail closed before network contact"
  any_failed=1
fi

first_byte_receipt="$fixture_root/first-byte-timeout-receipt.json"
rm -f "$network_marker" "$first_byte_receipt"
touch "$delay_first_byte"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_FIRST_BYTE_TIMEOUT=1 OPENROUTER_IDLE_TIMEOUT=5 \
  OPENROUTER_RECEIPT_FILE="$first_byte_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 5 >/dev/null 2>&1
first_byte_rc=$?
set -e
rm -f "$delay_first_byte"
if [ "$first_byte_rc" -eq 28 ] &&
   jq -e '
     .outcome == "timeout"
     and .failureKind == "stream_timeout"
     and .timeout.kind == "first_byte"
     and .responseModel == null
     and .usage == null
     and (has("prompt") | not)
   ' "$first_byte_receipt" >/dev/null; then
  pass "first-byte timeout is distinct and content-free"
else
  fail "first-byte timeout must emit exit 28 and a classified failure receipt"
  any_failed=1
fi

idle_receipt="$fixture_root/idle-timeout-receipt.json"
rm -f "$network_marker" "$idle_receipt"
touch "$stall_stream"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_FIRST_BYTE_TIMEOUT=5 OPENROUTER_IDLE_TIMEOUT=1 \
  OPENROUTER_RECEIPT_FILE="$idle_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 5 >/dev/null 2>&1
idle_rc=$?
set -e
rm -f "$stall_stream"
if [ "$idle_rc" -eq 28 ] &&
   jq -e '
     .outcome == "timeout"
     and .timeout.kind == "idle"
     and .attemptedModels == null
   ' "$idle_receipt" >/dev/null; then
  pass "stream-idle timeout is distinct from first-byte and overall budgets"
else
  fail "stream-idle timeout must emit a classified failure receipt"
  any_failed=1
fi

overall_receipt="$fixture_root/overall-timeout-receipt.json"
rm -f "$network_marker" "$overall_receipt"
touch "$stall_stream"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_FIRST_BYTE_TIMEOUT=5 OPENROUTER_IDLE_TIMEOUT=5 \
  OPENROUTER_RECEIPT_FILE="$overall_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 1 >/dev/null 2>&1
overall_rc=$?
set -e
rm -f "$stall_stream"
if [ "$overall_rc" -eq 28 ] &&
   jq -e '
     .outcome == "timeout"
     and .timeout.kind == "overall"
   ' "$overall_receipt" >/dev/null; then
  pass "overall completion budget remains bounded after streaming begins"
else
  fail "overall timeout must remain independently enforceable"
  any_failed=1
fi

stream_error_receipt="$fixture_root/stream-error-receipt.json"
rm -f "$network_marker" "$stream_error_receipt"
touch "$stream_error"
set +e
OPENROUTER_API_KEY=test OPENROUTER_BASE="$sentinel_base" \
  OPENROUTER_RECEIPT_FILE="$stream_error_receipt" \
  "$wrapper" moonshotai/kimi-k3 test 10 >/dev/null 2>&1
stream_error_rc=$?
set -e
rm -f "$stream_error"
if [ "$stream_error_rc" -eq 1 ] &&
   jq -e '
     .outcome == "error"
     and .failureKind == "stream_error"
     and .usage == null
   ' "$stream_error_receipt" >/dev/null; then
  pass "mid-stream provider errors discard partial output and emit a failure receipt"
else
  fail "stream errors must never return partial completion content as success"
  any_failed=1
fi

fallback_block="$(awk '/## Pipeline execution cascade/{flag=1; next} /## Direct wrapper fallback behavior/{flag=0} flag' "$model_selection")"
documented_openrouter_exec="$(printf '%s\n' "$fallback_block" | awk -F'|' '
  $2 ~ /^[[:space:]]*`openrouter_exec`[[:space:]]*$/ {
    value=$3
    sub(/^[[:space:]]*/, "", value)
    sub(/[[:space:]]*$/, "", value)
    if (!found) print value
    found=1
  }
')"
expected_openrouter_exec='DeepSeek V4 Flash 0731 -> Grok 4.6'
if [ "$documented_openrouter_exec" = "$expected_openrouter_exec" ] &&
   grep -Fq 'DeepSeek V4 Flash 0731 is the bounded Pipeline' \
     "$REPO_ROOT/docs/cascade-migration.md" &&
   grep -Fq 'openrouter_exec deepseek/deepseek-v4-flash-0731' \
     "$REPO_ROOT/docs/cascade-migration.md" &&
   jq -e '
     ["deepseek/deepseek-v4-flash-0731", "x-ai/grok-4.6"] as $expected
     | [(.hosts[].roles.openrouter_exec.models == $expected)] | all
   ' "$REPO_ROOT/plugins/pipeline/references/harness-profile.json" >/dev/null; then
  pass "documented OpenRouter exec chain exactly matches every host profile"
else
  fail "documented OpenRouter exec chain must exactly match every host profile"
  any_failed=1
fi

if jq -e '
  ["deepseek/deepseek-v4-flash-0731", "qwen/qwen3.8-max"] as $expected
  | [(.hosts[].roles.cheap_api.models == $expected)] | all
' "$REPO_ROOT/plugins/pipeline/references/harness-profile.json" >/dev/null; then
  pass "cheap OpenRouter fallback uses exact DeepSeek then Qwen order"
else
  fail "cheap OpenRouter fallback must use exact DeepSeek then Qwen order"
  any_failed=1
fi

model_matrix="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
model_cascade="$REPO_ROOT/plugins/pipeline/references/model-cascade.json"
routing_policy="$REPO_ROOT/plugins/pipeline/references/routing-policy.json"

check_matrix_readable() {
  if [ ! -f "$model_matrix" ]; then
    fail "model-matrix.json is missing -- it is the canonical OpenRouter model data source"
    any_failed=1
    return 1
  fi
  if ! jq -e '.models | type == "array" and length > 0' "$model_matrix" >/dev/null 2>&1; then
    fail "model-matrix.json must parse as JSON with a non-empty .models array"
    any_failed=1
    return 1
  fi
  return 0
}

check_refresh_provenance_domains() {
  local routing_anchor native_anchor
  if ! jq -e '
    .refresh_protocol.routing as $routing
    | .refresh_protocol.native_api_equivalent_cost as $native
    | ($routing.owned_snapshot_paths == [
        "snapshot_date", "models[*].snapshot_date"
      ])
    and ($routing.preserved_snapshot_paths == [
        "native_api_equivalent_cost.snapshot_date",
        "native_api_equivalent_cost.models[*].snapshot_date"
      ])
    and ($native.owned_snapshot_paths == [
        "native_api_equivalent_cost.snapshot_date",
        "native_api_equivalent_cost.models[*].snapshot_date"
      ])
    and ($native.preserved_snapshot_paths == [
        "snapshot_date", "models[*].snapshot_date"
      ])
    and (($routing.owned_snapshot_paths - $routing.preserved_snapshot_paths) | length == 2)
    and (($native.owned_snapshot_paths - $native.preserved_snapshot_paths) | length == 2)
  ' "$model_matrix" >/dev/null 2>&1; then
    fail "model-matrix.json refresh protocol must keep routing and native-cost snapshot provenance independent"
    any_failed=1
    return
  fi

  routing_anchor="$(jq -r '.refresh_protocol.routing.documented_in // empty' "$model_matrix")"
  native_anchor="$(jq -r '.refresh_protocol.native_api_equivalent_cost.documented_in // empty' "$model_matrix")"
  if [ "$routing_anchor" != "model-selection.md -- Refreshing the routing matrix" ] \
     || [ "$native_anchor" != "model-selection.md -- Refreshing native API-equivalent cost evidence" ]; then
    fail "model-matrix.json refresh protocol must point to both current model-selection headings"
    any_failed=1
    return
  fi
  pass "model-matrix.json keeps routing and native-cost refresh provenance independent"
}

# Drift check 1: every OpenRouter-slugged quality_rank in model-cascade.json must
# exist in the matrix with the identical rank. Bare names (gpt-5.6-sol, opus,
# sonnet, ...) are native Codex/Claude identities, not OpenRouter models, and are
# out of the matrix's scope by design.
check_quality_rank_drift() {
  local drift
  # A drift fence must never report green because it could not evaluate. Guard
  # the input shape first, then let jq's exit status fail loudly rather than
  # swallowing it -- an empty result from a crashed filter is indistinguishable
  # from "no drift" and would silently enforce nothing.
  if ! jq -e '.quality_rank | type == "object"' "$model_cascade" >/dev/null 2>&1; then
    fail "model-cascade.json must parse as JSON with a .quality_rank object before drift can be checked"
    any_failed=1
    return
  fi
  if ! drift="$(jq -r --slurpfile matrix "$model_matrix" '
    ($matrix[0].models | map({key: .slug, value: .quality_rank}) | from_entries) as $m
    | .quality_rank
    | to_entries
    | map(select(.key | contains("/")))
    | map(
        . as $e
        | if ($m | has($e.key) | not) then
            "\($e.key): present in model-cascade.json quality_rank but missing from model-matrix.json"
          elif $m[$e.key] != $e.value then
            "\($e.key): model-cascade.json rank \($e.value) disagrees with model-matrix.json rank \($m[$e.key])"
          else
            empty
          end
      )
    | .[]
  ' "$model_cascade" 2>/dev/null)"; then
    fail "could not evaluate model-cascade.json quality_rank drift against model-matrix.json"
    any_failed=1
    return
  fi
  # Reverse leg. The forward pass above walks cascade -> matrix and only sees
  # slugged keys, so a matrix entry whose cascade twin is stored under the bare
  # native name (openai/gpt-5.6-terra in the matrix, gpt-5.6-terra in the
  # cascade) is fenced by nothing. Pair them on the basename after the slash and
  # require equal ranks when both exist.
  local twin_drift
  if ! twin_drift="$(jq -r --slurpfile matrix "$model_matrix" '
    .quality_rank as $c
    | $matrix[0].models
    | map(select(.slug | contains("/")))
    | map(
        . as $e
        | ($e.slug | split("/") | last) as $bare
        | if ($c | has($bare)) and $c[$bare] != $e.quality_rank then
            "\($e.slug): model-matrix.json rank \($e.quality_rank) disagrees with the native twin \($bare) rank \($c[$bare]) in model-cascade.json"
          else
            empty
          end
      )
    | .[]
  ' "$model_cascade" 2>/dev/null)"; then
    fail "could not evaluate model-matrix.json ranks against their native cascade twins"
    any_failed=1
    return
  fi
  if [ -n "$twin_drift" ]; then
    fail "model-matrix.json ranks disagree with their native twins in model-cascade.json"
    printf '%s\n' "$twin_drift" | while IFS= read -r line; do
      [ -n "$line" ] && printf "  ${YELLOW}DRIFT${RESET} %s\n" "$line"
    done
    any_failed=1
    return
  fi
  if [ -z "$drift" ]; then
    pass "model-cascade.json quality_rank matches model-matrix.json for every OpenRouter slug"
  else
    fail "model-cascade.json quality_rank has drifted from model-matrix.json"
    printf '%s\n' "$drift" | while IFS= read -r line; do
      [ -n "$line" ] && printf "  ${YELLOW}DRIFT${RESET} %s\n" "$line"
    done
    any_failed=1
  fi
}

# Drift check 2: every model slug routing-policy.json names for an agentType
# (primary or fallback) must exist in the matrix. agentType is deliberately
# the only fenced location: today it holds every vendor/model slug in the
# file. A slug added later to a phase override or chunkKind block would NOT
# be fenced here -- widen this filter if that happens.
check_routing_policy_slugs() {
  local missing
  # Same fail-loud discipline as the drift check above.
  if ! jq -e '.agentType | type == "object"' "$routing_policy" >/dev/null 2>&1; then
    fail "routing-policy.json must parse as JSON with an .agentType object before slugs can be checked"
    any_failed=1
    return
  fi
  if ! missing="$(jq -r --slurpfile matrix "$model_matrix" '
    ($matrix[0].models | map(.slug)) as $slugs
    | [.agentType | to_entries[] | .value | (.model, .fallbackModel)]
    | map(select(. != null))
    | unique
    | map(select(. as $s | ($slugs | index($s)) == null))
    | .[]
  ' "$routing_policy" 2>/dev/null)"; then
    fail "could not evaluate routing-policy.json model slugs against model-matrix.json"
    any_failed=1
    return
  fi
  if [ -z "$missing" ]; then
    pass "every routing-policy.json agentType model and fallback exists in model-matrix.json"
  else
    fail "routing-policy.json names model slugs that are absent from model-matrix.json"
    printf '%s\n' "$missing" | while IFS= read -r line; do
      [ -n "$line" ] && printf "  ${YELLOW}MISSING${RESET} %s\n" "$line"
    done
    any_failed=1
  fi
}

check_active_routing_semantics() {
  local harness="$REPO_ROOT/plugins/pipeline/references/harness-profile.json"
  local required='["deepseek/deepseek-v4-flash-0731","deepseek/deepseek-v4-pro-0813","qwen/qwen3.8-max","qwen/qwen3.8-2.4t-a95b","qwen/qwen3.8-27b","qwen/qwen3.7-flash","x-ai/grok-4.6","google/gemini-3.7-flash","meta/muse-spark-1.2","z-ai/glm-5.2","z-ai/glm-5.3","moonshotai/kimi-k3","openai/gpt-5.6-luna","openai/gpt-5.6-terra"]'

  if jq -e --argjson required "$required" '
    ([.models[].slug] | sort) == ($required | sort)
    and ([.models[].slug | select(test("^[^/]+/[^/]+$") | not)] | length == 0)
    and ([.models[].slug | select(test("(^|[-_/])latest($|[-_/])"; "i"))] | length == 0)
    and ([.models[] | (.canonical_slug | type == "string" and test("^[^/]+/[^/]+$") and (test("(^|[-_/])latest($|[-_/])"; "i") | not))] | all)
    and ([.models[] | (.supported_parameters | type == "array") and (.reasoning | type == "object" or .reasoning == null) and (.top_provider_is_moderated | type == "boolean")] | all)
    and ([.models[] | select(.slug == "deepseek/deepseek-v4-pro-0813") | .canonical_slug == "deepseek/deepseek-v4-pro-20260813" and .input_usd_per_m == 1.188 and .output_usd_per_m == 3.564 and .cache_read_usd_per_m == 0.0396 and .top_provider_max_completion_tokens == null and .pricing_overrides == null] | all)
    and ([.models[] | select(.slug == "openai/gpt-5.6-luna") | .input_usd_per_m == 0.2 and .output_usd_per_m == 1.2 and .cache_read_usd_per_m == 0.02 and .cache_write_usd_per_m == 0.25] | all)
    and ([.models[] | select(.slug == "openai/gpt-5.6-terra") | .input_usd_per_m == 2 and .output_usd_per_m == 12 and .cache_read_usd_per_m == 0.2 and .cache_write_usd_per_m == 2.5] | all)
    and ([.models[] | select(.slug == "z-ai/glm-5.3") | .canonical_slug == "z-ai/glm-5.3-20260816" and .recommendation_status == "catalogued-not-routed" and .reasoning == {"mandatory":true,"default_enabled":true,"supported_efforts":["max","high","low"],"default_effort":"max"} and .default_parameters == {"temperature":1,"top_p":0.95} and .top_provider_max_completion_tokens == 131072 and .top_provider_is_moderated == false and .cache_write_usd_per_m == null and .pricing_overrides == null] | all)
    and ([.models[].per_request_limits] | all(. == null))
  ' "$model_matrix" >/dev/null; then
    pass "matrix contains the exact versioned catalog candidates, identities, limits, pricing, parameters, and explicit missing values"
  else
    fail "matrix must contain the refreshed versioned candidates, catalog fields, and explicit missing values"
    any_failed=1
  fi

  if jq -e '[.models[] | select(.slug == "qwen/qwen3.8-2.4t-a95b") | .input_modalities] == [["text"]]' "$model_matrix" >/dev/null &&
     grep -Fq '| `qwen/qwen3.8-2.4t-a95b` | `qwen/qwen3.8-2.4t-a95b-20260812` | $2 / $6 / $0.25 / $unavailable | 1048576 / 1000000 / 262144 | false |' "$matrix_refresh_receipt"; then
    pass "Qwen 3.8 2.4T matrix modalities match the catalog refresh receipt"
  else
    fail "Qwen 3.8 2.4T matrix modalities must match the catalog refresh receipt"
    any_failed=1
  fi

  if jq -e --slurpfile matrix "$model_matrix" '
    ($matrix[0].models | map(select(.catalog_status == "available") | .slug)) as $available
    | ([.agentType[] | .model?, .fallbackModel?, .codexImplementerModel?, .codexImplementerFallbackModel?]
       | map(select(. != null)) | unique) as $active
    | all($active[]; (. as $slug | ($available | index($slug)) != null)
        and test("^[^/]+/[^/]+$")
        and (test("(^|[-_/])latest($|[-_/])"; "i") | not))
  ' "$routing_policy" >/dev/null &&
     jq -e --slurpfile matrix "$model_matrix" '
       ($matrix[0].models | map(select(.catalog_status == "available") | .slug)) as $available
       | [.hosts[].roles[] | select(.kind == "wrapper" or .kind == "openrouter_exec") | .models[]] as $active
       | all($active[]; (. as $slug | ($available | index($slug)) != null)
           and test("^[^/]+/[^/]+$")
           and (test("(^|[-_/])latest($|[-_/])"; "i") | not))
     ' "$harness" >/dev/null; then
    pass "active candidates are available exact matrix entries"
  else
    fail "unavailable, missing, malformed, or moving-alias candidates must not enter active routing"
    any_failed=1
  fi

  if routine_review_routes_valid "$routing_policy" &&
     jq -e '
    .agentType as $a
    | $a["openrouter-bulk-analyst"].model == "qwen/qwen3.8-max"
      and $a["second-perspective"].model == "qwen/qwen3.8-max"
      and $a["second-perspective"].fallbackModel == "x-ai/grok-4.6"
      and $a["second-perspective"].fallbackProvider == "implementer-aware-independent-family"
      and $a["second-perspective"].reviewerFamilyConstraint == "must-differ-from-every-implementer-family"
      and $a["security-auditor-openrouter"].model == "moonshotai/kimi-k3"
      and $a["security-auditor-openrouter"].fallbackModel == "x-ai/grok-4.6"
      and $a["security-auditor-codex-signoff"].reviewerFamilyConstraint == "must-differ-from-every-implementer-family"
      and ([ $a | to_entries[] | select(.key | test("security") | not)
             | .value | .model?, .fallbackModel? ]
           | map(select(. == "moonshotai/kimi-k3")) | length == 0)
      and ([ $a[] | .model?, .fallbackModel?, .codexImplementerModel?, .codexImplementerFallbackModel? ]
           | map(select(. == "z-ai/glm-5.2")) | length == 0)
  ' "$routing_policy" >/dev/null &&
     jq -e '
       ([.hosts[].roles[] | select(.kind == "wrapper" or .kind == "openrouter_exec") | .models[]]
        | map(select(. == "z-ai/glm-5.2" or . == "z-ai/glm-5.3" or . == "moonshotai/kimi-k3")) | length == 0)
       and ([.hosts[].roles | has("bulk_api")] | any | not)
       and (([.hosts[].roles | {openrouter_exec:.openrouter_exec.models, frontier_api:.frontier_api.models, cheap_api:.cheap_api.models}] | unique) | length == 1)
     ' "$harness" >/dev/null; then
    pass "dm-review roles and reachable host ladders enforce DeepSeek/Qwen reachability and Kimi/GLM isolation"
  else
    fail "active routing violates role reachability, Kimi/GLM isolation, or host parity"
    any_failed=1
  fi
  expect_routine_review_route_reject "simplicity fallback model" '.agentType["code-simplicity-reviewer"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "simplicity fallback provider" '.agentType["code-simplicity-reviewer"].fallbackProvider = "claude"'
  expect_routine_review_route_reject "pattern provider" '.agentType["pattern-recognition-specialist"].provider = "claude"'
  expect_routine_review_route_reject "pattern fallback model" '.agentType["pattern-recognition-specialist"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "pattern fallback provider" '.agentType["pattern-recognition-specialist"].fallbackProvider = "claude"'
  expect_routine_review_route_reject "documentation fallback model" '.agentType["doc-sync-reviewer"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "documentation fallback provider" '.agentType["doc-sync-reviewer"].fallbackProvider = "claude"'
  expect_routine_review_route_reject "test fallback model" '.agentType["test-coverage-reviewer"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "test fallback provider" '.agentType["test-coverage-reviewer"].fallbackProvider = "claude"'
}

# Drift check 3: the matrix snapshot_date (top level and every entry) must match
# the snapshot date stated in the model-selection.md prose.
check_matrix_snapshot_date() {
  local prose_date matrix_date entry_drift
  prose_date="$(grep -Eo 'checked-in planning snapshot from [0-9]{4}-[0-9]{2}-[0-9]{2}' "$model_selection" \
    | head -1 | grep -Eo '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)"
  matrix_date="$(jq -r '.snapshot_date // empty' "$model_matrix" 2>/dev/null || true)"
  if [ -z "$prose_date" ]; then
    fail "model-selection.md must state a 'checked-in planning snapshot from YYYY-MM-DD' date"
    any_failed=1
    return
  fi
  if [ -z "$matrix_date" ] || [ "$matrix_date" != "$prose_date" ]; then
    fail "model-matrix.json snapshot_date '${matrix_date:-<none>}' must match model-selection.md prose date '$prose_date'"
    any_failed=1
    return
  fi
  entry_drift="$(jq -r --arg d "$prose_date" '
    .models
    | map(select(.snapshot_date != $d) | "\(.slug): entry snapshot_date \(.snapshot_date // "<none>")")
    | .[]
  ' "$model_matrix" 2>/dev/null || true)"
  if [ -n "$entry_drift" ]; then
    fail "every model-matrix.json entry snapshot_date must match the shared snapshot date '$prose_date'"
    printf '%s\n' "$entry_drift" | while IFS= read -r line; do
      [ -n "$line" ] && printf "  ${YELLOW}DRIFT${RESET} %s\n" "$line"
    done
    any_failed=1
    return
  fi
  pass "model-matrix.json snapshot_date matches the model-selection.md prose snapshot date"
}

if check_matrix_readable; then
  check_refresh_provenance_domains
  check_quality_rank_drift
  check_routing_policy_slugs
  check_active_routing_semantics
  check_matrix_snapshot_date
fi

cascade_descent_ref="$REPO_ROOT/plugins/pipeline/references/execution-cascade-descent.md"
if grep -q -- '--exhausted-rail' "$cascade_descent_ref" &&
   grep -q 'execution-cascade-descent.md' "$orchestrator"; then
  pass "pipeline orchestrator passes observed exhausted rail into cascade"
else
  fail "execution-cascade-descent.md must pass --exhausted-rail after cap/unavailable events"
  any_failed=1
fi

if [ "$any_failed" -ne 0 ]; then
  exit 1
fi

printf "  ${GREEN}OK${RESET}    OpenRouter cascade contract valid\n"
