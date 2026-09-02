#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECOMMEND="$ROOT/plugins/model-router/skills/model-router/references/operator-recommendation.sh"
POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
COORDINATOR="$ROOT/plugins/project-manager/skills/assembly-coordinator/SKILL.md"
OPINIONS="$ROOT/plugins/project-manager/skills/assembly-coordinator/references/planning-opinions.md"
REVIEW_PROMPT="$ROOT/plugins/dm-review/skills/review/references/reviewer-prompt-template.md"
TERMINAL="$ROOT/plugins/model-router/skills/model-router/references/render-terminal-report.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/coordinator-recommendation.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export MODEL_ROUTER_TEST_MODE=1

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

cat > "$TMP/healthy.json" <<'JSON'
{"codex":{"state":"ok","authMode":"subscription"},"claude":{"state":"ok","authMode":"subscription","plan":"max","fable":"available"},"openrouter":{"state":"ok"}}
JSON

"$RECOMMEND" --role builder-deep --capability read-repository \
  --capability write-repository --capability tool-use --capability long-context \
  --capability structured-output --effort high --matrix-file "$MATRIX" \
  --availability-file "$TMP/healthy.json" --format json > "$TMP/builder.json"
assert jq -e '.recommendedStart.model == "gpt-5.6-sol" and .recommendedStart.harness == "Codex" and .recommendedStart.effort == "high"' "$TMP/builder.json"
assert jq -e '.recommendedStart.fallback.model == "gpt-5.6-terra" and (.recommendedStart.fallback | keys | length) == 3' "$TMP/builder.json"
assert jq -e '.recommendedStart.cost.label == "included subscription" and .recommendedStart.cost.apiEquivalent.inputUsdPerM == 5 and .recommendedStart.cost.apiPrice == null' "$TMP/builder.json"

"$RECOMMEND" --role review-fast --capability read-repository \
  --capability structured-output --effort medium --matrix-file "$MATRIX" \
  --availability-file "$TMP/healthy.json" --format json > "$TMP/review.json"
assert jq -e '.recommendedStart.model == "gpt-5.6-luna" and .recommendedStart.harness == "Codex" and .recommendedStart.cost.label == "included subscription"' "$TMP/review.json"

jq '.openrouter.state="unavailable"' "$TMP/healthy.json" > "$TMP/no-openrouter.json"
"$RECOMMEND" --role review-fast --capability read-repository \
  --capability structured-output --effort medium --matrix-file "$MATRIX" \
  --availability-file "$TMP/no-openrouter.json" --format json > "$TMP/review-native.json"
assert jq -e '.recommendedStart.model == "gpt-5.6-luna" and .recommendedStart.harness == "Codex"' "$TMP/review-native.json"

jq '.roles["review-fast"] += [
  {model:"qwen/qwen3.8-max",provider:"openrouter",transport:"openrouter",family:"qwen",billing:"api",capabilities:["read-repository","long-context","structured-output"]},
  {model:"deepseek/deepseek-v4-pro-0813",provider:"openrouter",transport:"openrouter",family:"deepseek",billing:"api",capabilities:["read-repository","long-context","structured-output"]}
]' "$POLICY" > "$TMP/capability-policy.json"
"$RECOMMEND" --policy-file "$TMP/capability-policy.json" --role review-fast \
  --capability read-repository --capability long-context \
  --capability structured-output --effort medium --matrix-file "$MATRIX" \
  --availability-file "$TMP/healthy.json" --format json > "$TMP/review-long-context.json"
assert jq -e '.recommendedStart.model == "qwen/qwen3.8-max" and .recommendedStart.fallback.model == "deepseek/deepseek-v4-pro-0813"' "$TMP/review-long-context.json"

jq '.roles["review-fast"] |= reverse' "$POLICY" > "$TMP/reordered-policy.json"
"$RECOMMEND" --policy-file "$TMP/reordered-policy.json" --role review-fast \
  --capability read-repository --capability structured-output --effort medium \
  --matrix-file "$MATRIX" --availability-file "$TMP/healthy.json" --format json \
  > "$TMP/reordered.json"
assert jq -e '.recommendedStart.model == "z-ai/glm-5.3-flash" and .recommendedStart.harness == "OpenRouter"' "$TMP/reordered.json"

jq '(.models[] | select(.slug == "deepseek/deepseek-v4-flash-0731")).input_usd_per_m=9.99 | (.models[] | select(.slug == "deepseek/deepseek-v4-flash-0731")).output_usd_per_m=8.88' "$MATRIX" > "$TMP/priced-matrix.json"
jq '.codex.state="unavailable"' "$TMP/healthy.json" > "$TMP/no-codex.json"
"$RECOMMEND" --role review-fast --capability read-repository \
  --capability structured-output --effort medium --matrix-file "$TMP/priced-matrix.json" \
  --availability-file "$TMP/no-codex.json" --format json > "$TMP/priced.json"
assert jq -e '.recommendedStart.cost.apiPrice.inputUsdPerM == 9.99 and .recommendedStart.cost.apiPrice.outputUsdPerM == 8.88' "$TMP/priced.json"

jq '.codex={state:"unknown",authMode:"subscription",reason:"rate_limit_mapping_unknown",allowances:{a:{state:"limited"},b:{state:"ok"}}} | .openrouter.state="unavailable"' "$TMP/healthy.json" > "$TMP/unmapped.json"
"$RECOMMEND" --role builder-deep --capability read-repository \
  --capability write-repository --capability tool-use --capability long-context \
  --capability structured-output --effort high --matrix-file "$MATRIX" \
  --availability-file "$TMP/unmapped.json" --format json > "$TMP/attemptable.json"
assert jq -e '.recommendedStart.availability == "attemptable" and (.recommendedStart.why | contains("without attributing an allowance bucket"))' "$TMP/attemptable.json"

# Live recommendations resolve native CLIs before sanitizing PATH, honor
# explicit absolute overrides, and keep the OpenRouter rail when neither native
# executable is present. These fixtures intentionally test CLI discovery only;
# they carry no implementation-origin or reviewer-eligibility inputs.
mkdir -p "$TMP/native/incoming" "$TMP/native/override" "$TMP/native/fake-kernel"
for cli_dir in incoming override; do
  cat > "$TMP/native/$cli_dir/codex" <<'STUB'
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
  cat > "$TMP/native/$cli_dir/claude" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$0" >> "$MODEL_ROUTER_CLI_LOG"
printf '%s\n' '{"loggedIn":true,"authMethod":"claude.ai","subscriptionType":"max"}'
STUB
  chmod +x "$TMP/native/$cli_dir/codex" "$TMP/native/$cli_dir/claude"
done

FAKE_HOME="$TMP/native/home"
FAKE_BUNDLE="$FAKE_HOME/.codex/plugins/cache/depot/openrouter/1.20.0"
FAKE_REFS="$FAKE_BUNDLE/skills/openrouter-delegate/references"
mkdir -p "$FAKE_REFS"
cat > "$TMP/native/fake-kernel/workflow-kernel-launcher.sh" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' '{"selected_root":"~/.codex/plugins/cache/depot/openrouter/1.20.0","version":"1.20.0","cache_class":"codex","reason":"fixture"}'
STUB
for asset in openrouter-wrapper.sh delegation-boundary.sh; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$FAKE_REFS/$asset"
  chmod +x "$FAKE_REFS/$asset"
done
printf 'load_openrouter_api_key() { return 1; }\n' > "$FAKE_REFS/openrouter-credential.sh"
printf '%s\n' '{"schemaVersion":2}' > "$FAKE_REFS/delegation-security-policy.json"
chmod +x "$TMP/native/fake-kernel/workflow-kernel-launcher.sh"

MODEL_ROUTER_CLI_LOG="$TMP/native/incoming.log" \
  PATH="$TMP/native/incoming:/usr/bin:/bin" HOME="$FAKE_HOME" \
  "$RECOMMEND" --role builder-fast --capability read-repository \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --workflow-kernel "$TMP/native/fake-kernel/workflow-kernel-launcher.sh" \
    --format json > "$TMP/native/incoming.json"
assert grep -Fxq "$TMP/native/incoming/codex" "$TMP/native/incoming.log"
assert grep -Fxq "$TMP/native/incoming/claude" "$TMP/native/incoming.log"
assert jq -e '.recommendedStart.model == "gpt-5.6-luna" and .recommendedStart.harness == "Codex"' "$TMP/native/incoming.json"

MODEL_ROUTER_CLI_LOG="$TMP/native/override.log" \
  PATH="$TMP/native/incoming:/usr/bin:/bin" HOME="$FAKE_HOME" \
  MODEL_ROUTER_CODEX_CLI_PATH="$TMP/native/override/codex" \
  MODEL_ROUTER_CLAUDE_CLI_PATH="$TMP/native/override/claude" \
  "$RECOMMEND" --role builder-fast --capability read-repository \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --workflow-kernel "$TMP/native/fake-kernel/workflow-kernel-launcher.sh" \
    --format json > "$TMP/native/override.json"
assert grep -Fxq "$TMP/native/override/codex" "$TMP/native/override.log"
assert grep -Fxq "$TMP/native/override/claude" "$TMP/native/override.log"
assert sh -c "! grep -Fq '$TMP/native/incoming/' '$TMP/native/override.log'"

PATH="/usr/bin:/bin" HOME="$FAKE_HOME" \
  "$RECOMMEND" --role builder-fast --capability read-repository \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --workflow-kernel "$TMP/native/fake-kernel/workflow-kernel-launcher.sh" \
    --format json > "$TMP/native/absent.json"
assert jq -e '.recommendedStart.harness == "OpenRouter" and .recommendedStart.availability == "unknown"' "$TMP/native/absent.json"

assert grep -Fq 'Routine status-only coordination emits no empty block.' "$COORDINATOR"
assert grep -Fq 'The block is for the human operator and primary executor only.' "$COORDINATOR"
assert sh -c "! grep -Eq 'gpt-5\\.|deepseek/|qwen/|x-ai/|moonshotai/|Recommended start' '$OPINIONS' '$REVIEW_PROMPT'"
assert grep -Fq 'tokenProvenance' "$TERMINAL"
assert grep -Fq 'billedCostUsd' "$TERMINAL"

"$RECOMMEND" --role review-fast --capability read-repository \
  --capability structured-output --effort medium --matrix-file "$MATRIX" \
  --availability-file "$TMP/healthy.json" --format markdown > "$TMP/recommended.md"
assert test "$(grep -c '^Recommended start$' "$TMP/recommended.md")" -eq 1
assert test "$(grep -c '^- Fallback:' "$TMP/recommended.md")" -eq 1
assert grep -Fq -- '- Matrix evidence: 2026-08-27' "$TMP/recommended.md"

printf 'assembly-coordinator-recommendation: %d assertions passed\n' "$pass"
