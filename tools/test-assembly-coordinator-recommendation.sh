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
assert jq -e '.recommendedStart.model == "deepseek/deepseek-v4-flash-0731" and .recommendedStart.harness == "OpenRouter" and .recommendedStart.cost.label == "metered API"' "$TMP/review.json"

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
assert jq -e '.recommendedStart.model == "gpt-5.6-luna"' "$TMP/reordered.json"

jq '(.models[] | select(.slug == "deepseek/deepseek-v4-flash-0731")).input_usd_per_m=9.99 | (.models[] | select(.slug == "deepseek/deepseek-v4-flash-0731")).output_usd_per_m=8.88' "$MATRIX" > "$TMP/priced-matrix.json"
"$RECOMMEND" --role review-fast --capability read-repository \
  --capability structured-output --effort medium --matrix-file "$TMP/priced-matrix.json" \
  --availability-file "$TMP/healthy.json" --format json > "$TMP/priced.json"
assert jq -e '.recommendedStart.cost.apiPrice.inputUsdPerM == 9.99 and .recommendedStart.cost.apiPrice.outputUsdPerM == 8.88' "$TMP/priced.json"

jq '.codex={state:"unknown",authMode:"subscription",reason:"rate_limit_mapping_unknown",allowances:{a:{state:"limited"},b:{state:"ok"}}} | .openrouter.state="unavailable"' "$TMP/healthy.json" > "$TMP/unmapped.json"
"$RECOMMEND" --role builder-deep --capability read-repository \
  --capability write-repository --capability tool-use --capability long-context \
  --capability structured-output --effort high --matrix-file "$MATRIX" \
  --availability-file "$TMP/unmapped.json" --format json > "$TMP/attemptable.json"
assert jq -e '.recommendedStart.availability == "attemptable" and (.recommendedStart.why | contains("without attributing an allowance bucket"))' "$TMP/attemptable.json"

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
assert grep -Fq -- '- Matrix evidence: 2026-08-26' "$TMP/recommended.md"

printf 'assembly-coordinator-recommendation: %d assertions passed\n' "$pass"
