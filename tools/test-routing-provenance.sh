#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROUTER="$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh"
ORIGIN="$ROOT/plugins/model-router/skills/model-router/references/implementation-origin.sh"
RECOMMEND="$ROOT/plugins/model-router/skills/model-router/references/operator-recommendation.sh"
TERMINAL="$ROOT/plugins/model-router/skills/model-router/references/render-terminal-report.sh"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/routing-provenance.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export MODEL_ROUTER_TEST_MODE=1

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

mkdir -p "$TMP/incoming" "$TMP/override" "$TMP/fake-kernel"
for cli_dir in incoming override; do
  cat > "$TMP/$cli_dir/codex" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$0" >> "$MODEL_ROUTER_CLI_LOG"
case "${1:-}:${2:-}" in
  login:status) printf '%s\n' 'Logged in using ChatGPT' ;;
  app-server:--stdio)
    initialized=0
    while IFS= read -r request; do
      case "$(printf '%s' "$request" | jq -r '.method // empty')" in
        initialize) printf '%s\n' '{"id":0,"result":{"serverInfo":{"name":"fixture"}}}' ;;
        initialized) initialized=1 ;;
        account/rateLimits/read)
          [ "$initialized" -eq 1 ] || exit 91
          printf '%s\n' '{"id":7,"result":{"rateLimits":{"primary":{"usedPercent":10,"windowDurationMins":300},"secondary":{"usedPercent":20,"windowDurationMins":10080}}}}'
          ;;
      esac
    done
    ;;
  *) exit 1 ;;
esac
STUB
  cat > "$TMP/$cli_dir/claude" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$0" >> "$MODEL_ROUTER_CLI_LOG"
printf '%s\n' '{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"max"}'
STUB
  chmod +x "$TMP/$cli_dir/codex" "$TMP/$cli_dir/claude"
done

FAKE_HOME="$TMP/home"
FAKE_BUNDLE="$FAKE_HOME/.codex/plugins/cache/depot/openrouter/1.20.0"
FAKE_REFS="$FAKE_BUNDLE/skills/openrouter-delegate/references"
mkdir -p "$FAKE_REFS"
cat > "$TMP/fake-kernel/workflow-kernel-launcher.sh" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' '{"selected_root":"~/.codex/plugins/cache/depot/openrouter/1.20.0","version":"1.20.0","cache_class":"codex","reason":"fixture"}'
STUB
for asset in openrouter-wrapper.sh delegation-boundary.sh; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$FAKE_REFS/$asset"
  chmod +x "$FAKE_REFS/$asset"
done
printf 'load_openrouter_api_key() { return 1; }\n' > "$FAKE_REFS/openrouter-credential.sh"
printf '%s\n' '{"schemaVersion":2}' > "$FAKE_REFS/delegation-security-policy.json"
chmod +x "$TMP/fake-kernel/workflow-kernel-launcher.sh"

# Native executables exist only on the incoming PATH. The recommendation
# resolves them before sanitization and the live probe invokes those exact files.
MODEL_ROUTER_CLI_LOG="$TMP/incoming.log" PATH="$TMP/incoming:/usr/bin:/bin" HOME="$FAKE_HOME" \
  "$RECOMMEND" --role builder-fast --capability read-repository \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" --format json > "$TMP/incoming.json"
assert grep -Fxq "$TMP/incoming/codex" "$TMP/incoming.log"
assert grep -Fxq "$TMP/incoming/claude" "$TMP/incoming.log"
assert jq -e '.recommendedStart.model == "gpt-5.6-luna" and .recommendedStart.harness == "Codex"' "$TMP/incoming.json"

# Explicit absolute overrides win over a different incoming PATH.
MODEL_ROUTER_CLI_LOG="$TMP/override.log" PATH="$TMP/incoming:/usr/bin:/bin" HOME="$FAKE_HOME" \
  MODEL_ROUTER_CODEX_CLI_PATH="$TMP/override/codex" \
  MODEL_ROUTER_CLAUDE_CLI_PATH="$TMP/override/claude" \
  "$RECOMMEND" --role builder-fast --capability read-repository \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" --format json > "$TMP/override.json"
assert grep -Fxq "$TMP/override/codex" "$TMP/override.log"
assert grep -Fxq "$TMP/override/claude" "$TMP/override.log"
assert sh -c "! grep -Fq '$TMP/incoming/' '$TMP/override.log'"

# Missing native executables do not break remaining rails.
PATH="/usr/bin:/bin" HOME="$FAKE_HOME" "$RECOMMEND" --role builder-fast \
  --capability read-repository --capability structured-output --effort medium \
  --matrix-file "$MATRIX" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
  --format json > "$TMP/absent.json"
assert jq -e '.recommendedStart.harness == "OpenRouter" and .recommendedStart.availability == "unknown"' "$TMP/absent.json"

cat > "$TMP/availability.json" <<'JSON'
{
  "codex":{"state":"ok","authMode":"subscription","allowances":{"unattributed":{"state":"ok"}}},
  "claude":{"state":"ok","authMode":"subscription","plan":"max","rateLimitsObserved":false,"agentSdkRateLimitsObserved":false},
  "openrouter":{"state":"ok"},
  "candidateResults":{}
}
JSON
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
printf 'anonymous review output\n' > "$output"
[ -z "${MODEL_ROUTER_CALL_LOG:-}" ] || printf '%s\n' "$model" >> "$MODEL_ROUTER_CALL_LOG"
STUB
chmod +x "$TMP/transport-stub"
printf 'review the exact diff\n' > "$TMP/prompt"
printf 'complete repository evidence\n' > "$TMP/evidence"

run_role() {
  local name="$1" role="$2"; shift 2
  rm -f "$TMP/$name.out" "$TMP/$name.receipt" "$TMP/$name.public"
  HOME="$FAKE_HOME" MODEL_ROUTER_AVAILABILITY_FILE="${MODEL_ROUTER_TEST_AVAILABILITY:-$TMP/availability.json}" \
    MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport-stub" \
    "$ROUTER" --workflow-kernel "$TMP/fake-kernel/workflow-kernel-launcher.sh" \
      --role "$role" --effort high --capability read-repository \
      --capability structured-output --prompt-file "$TMP/prompt" \
      --repository-evidence-file "$TMP/evidence" --output-file "$TMP/$name.out" \
      --receipt-file "$TMP/$name.receipt" "$@" > "$TMP/$name.public"
}

# Recommendation and runtime dispatch use the same policy and availability
# semantics when independence does not alter the candidate set.
"$RECOMMEND" --role builder-fast --capability read-repository \
  --capability structured-output --effort high --matrix-file "$MATRIX" \
  --availability-file "$TMP/availability.json" --format json > "$TMP/parity-recommendation.json"
run_role parity builder-fast
assert test "$(jq -r '.recommendedStart.model' "$TMP/parity-recommendation.json")" = "$(jq -r '.served.model' "$TMP/parity.receipt")"
assert jq -e '.served.transport == "codex-cli" and .served.allowanceWindow == "mapping-unknown"' "$TMP/parity.receipt"

# When Codex is unavailable, OpenRouter is the automatic next eligible rail.
jq '.codex.state="unavailable" | .codex.authMode="unknown"' "$TMP/availability.json" > "$TMP/openrouter-fallback.json"
MODEL_ROUTER_TEST_AVAILABILITY="$TMP/openrouter-fallback.json" run_role openrouter-fallback builder-fast
assert jq -e '.served.transport == "openrouter" and .fallback == true' "$TMP/openrouter-fallback.receipt"

git init -q "$TMP/repo"
git -C "$TMP/repo" config user.name fixture
git -C "$TMP/repo" config user.email fixture@example.invalid
printf 'base\n' > "$TMP/repo/tracked.txt"
git -C "$TMP/repo" add tracked.txt
git -C "$TMP/repo" commit -qm base
BASE="$(git -C "$TMP/repo" rev-parse HEAD)"
printf 'change\n' >> "$TMP/repo/tracked.txt"
git -C "$TMP/repo" commit -qam change
HEAD_COMMIT="$(git -C "$TMP/repo" rev-parse HEAD)"

create_origin() {
  local name="$1" class="$2"; shift 2
  "$ORIGIN" create --repository "$TMP/repo" --base "$BASE" --head "$HEAD_COMMIT" \
    --origin-class "$class" --declaration-source operator --output "$TMP/$name.origin.json" "$@" >/dev/null
}
run_origin_role() {
  local name="$1"
  shift
  (cd "$TMP/repo" && run_role "$name" security-review --capability long-context \
    --capability independent-family --origin-file "$TMP/$name.origin.json" "$@")
}

create_origin openai codex-host-authored
run_origin_role openai
assert jq -e '.familyIndependence.excludedFamilies == ["openai"] and .served.family != "openai" and .served.transport == "openrouter"' "$TMP/openai.receipt"

create_origin claude claude-host-authored
run_origin_role claude
assert jq -e '.familyIndependence.excludedFamilies == ["anthropic"] and .served.family != "anthropic"' "$TMP/claude.receipt"

create_origin human human-authored
run_origin_role human
assert jq -e '.familyIndependence.humanAuthored == true and .familyIndependence.excludedFamilies == [] and .served.model == "gpt-5.6-terra"' "$TMP/human.receipt"

create_origin mixed mixed-known --contributor-origin codex-host-authored --contributor-origin claude-host-authored
run_origin_role mixed
assert jq -e '.familyIndependence.excludedFamilies == ["anthropic","openai"] and .served.transport == "openrouter"' "$TMP/mixed.receipt"

create_origin unknown unknown
assert jq -e '.originClass == "unknown" and .contributingFamilies == []' "$TMP/unknown.origin.json"
assert grep -Fq 'unknown provenance is one transparent nonblocking limitation' "$ROOT/plugins/dm-review/skills/review/references/implementation-origin.md"
assert grep -Fq 'unknown provenance keeps the required independent lanes incomplete' "$ROOT/plugins/dm-review/skills/review/references/implementation-origin.md"
assert test "$(grep -c 'Was this exact diff authored in Codex' "$ROOT/plugins/dm-review/skills/review/references/implementation-origin.md")" -eq 1

# HEAD and diff changes invalidate the declaration, including a repair after a
# formerly human-authored exact diff.
printf 'repair\n' >> "$TMP/repo/tracked.txt"
git -C "$TMP/repo" commit -qam repair
set +e
"$ORIGIN" verify --repository "$TMP/repo" --file "$TMP/human.origin.json" >/dev/null 2>&1
stale_rc=$?
set -e
assert test "$stale_rc" -eq 3

# Public reviewer and synthesis inputs remain anonymous; the terminal report is
# the single identity/cost projection and retains every required measurement field.
assert sh -c "! grep -Eq 'gpt-5\\.|deepseek/|qwen/|x-ai/|moonshotai/|openrouter|anthropic|openai' '$ROOT/plugins/dm-review/skills/review/references/reviewer-prompt-template.md' '$ROOT/plugins/dm-review/agents/workflow/review-consolidator.md'"
mkdir -p "$TMP/private" "$TMP/report"
cp "$TMP/openai.receipt" "$TMP/private/openai.json"
printf '%s\n' '{"schemaVersion":1,"receiptFiles":["openai.json"]}' > "$TMP/private/terminal-receipt-index.json"
chmod 700 "$TMP/private"
"$TERMINAL" --receipt-index "$TMP/private/terminal-receipt-index.json" --status complete \
  --json-output "$TMP/report/model-cost-report.json" --markdown-output "$TMP/report/model-cost-report.md"
assert jq -e '.calls[0].attempts[0] | .model and .provider and .transport and (.duration.status|type=="string") and (.tokens.status|type=="string") and (.billedCost.status|type=="string") and (.result|type=="string")' "$TMP/report/model-cost-report.json"

# Pipeline variants and the loop all preserve internally generated provenance.
assert grep -Fq 'lean implementation still dispatches' "$ROOT/plugins/pipeline/commands/pipeline.md"
assert grep -Fq 'every successful live implementation and repair receipt ID' "$ROOT/plugins/pipeline/references/codex-native-execution-adapter.md"
assert grep -Fq 'one cumulative implementation provenance set' "$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
assert grep -Fq "Preserve the initial review's complete implementation receipt IDs" "$ROOT/plugins/dm-review/commands/dm-review-loop.md"

printf 'routing-provenance: %d assertions passed\n' "$pass"
