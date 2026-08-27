#!/usr/bin/env bash
# Validate role ordering, effort economics, availability, and private receipts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
WRAPPER="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
failures=0

check() {
  local label="$1"; shift
  if "$@"; then printf '  OK    %s\n' "$label"
  else printf '  FAIL  %s\n' "$label"; failures=1; fi
}

check 'router schema and threshold are closed' jq -e '
  .schemaVersion == 1 and .availability.headroomThresholdPct == 8 and
  .effort.vocabulary == ["low","medium","high","max"]' "$POLICY"

check 'builder-fast starts with the bounded fast candidate' jq -e '
  .roles["builder-fast"][0].model == "deepseek/deepseek-v4-flash-0731" and
  .roles["builder-fast"][0].transport == "openrouter"' "$POLICY"

check 'builder-deep starts on native subscription capacity' jq -e '
  .roles["builder-deep"][0].model == "gpt-5.6-sol" and
  .roles["builder-deep"][0].billing == "included-subscription"' "$POLICY"

check 'architect begins with eligible native Fable then native Sol' jq -e '
  .roles.architect[0].model == "fable" and
  .roles.architect[1].model == "gpt-5.6-sol"' "$POLICY"

check 'security head is isolated from ordinary roles' jq -e '
  .roles["security-review"][0].model == "moonshotai/kimi-k3" and
  ([.roles | to_entries[] | select(.key != "security-review") | .value[].model | select(test("kimi";"i"))] | length == 0)' "$POLICY"

check 'external max effort normalization is recorded policy' jq -e '
  .effort.transports.openrouter.max == "high" and
  .effort.transports["codex-cli"].max == "max" and
  .effort.transports["claude-cli"].max == "max"' "$POLICY"

check 'tracked policy carries no operator identity or billing preference' sh -c \
  "! grep -Eiq 'travis|jeremy|email|allowPaidClaudeCredits' '$POLICY'"

check 'OpenRouter matrix retains usage and price evidence' jq -e '
  .snapshot_date == "2026-08-27" and
  all(.models[]; (.slug|type)=="string" and (.input_usd_per_m|type)=="number" and (.output_usd_per_m|type)=="number")' "$MATRIX"

check 'OpenRouter wrapper retains content-free receipt fields' sh -c \
  "grep -Fq 'requestedModel' '$WRAPPER' && grep -Fq 'responseModel' '$WRAPPER' && grep -Fq 'servingProvider' '$WRAPPER' && grep -Fq 'usage' '$WRAPPER'"

check 'Pipeline postmortem reports roles and keeps exact identity private' sh -c \
  "grep -Fq 'roleSplit:' '$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md' && grep -Fq 'private model-router receipts' '$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md'"

check 'provider-neutral drift and leak validator passes' "$ROOT/tools/validate-provider-neutral-routing.sh"
check 'resolver economics fixtures pass' "$ROOT/tools/test-model-router.sh"
check 'Depot role benchmark fixtures pass' "$ROOT/tools/test-openrouter-role-benchmark.sh"

if [ "$failures" -ne 0 ]; then
  printf 'routing economics validation failed\n' >&2
  exit 1
fi
printf 'routing economics validation passed\n'
