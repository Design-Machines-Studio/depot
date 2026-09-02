#!/usr/bin/env bash
# Validate role ordering, effort economics, availability, and private receipts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
WRAPPER="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
WEEKLY="$ROOT/docs/scheduled-model-intelligence/weekly-prompt.md"
LATEST="$ROOT/docs/model-intelligence/latest.json"
PAID_COST_CHECK="$ROOT/tools/validate-paid-benchmark-costs.sh"
BINDING_CHECK="$ROOT/tools/update-depot-role-benchmark-bindings.sh"
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
  .roles["builder-fast"][0].model == "gpt-5.6-luna" and
  .roles["builder-fast"][0].transport == "codex-cli"' "$POLICY"

check 'builder-deep starts on native subscription capacity' jq -e '
  .roles["builder-deep"][0].model == "gpt-5.6-sol" and
  .roles["builder-deep"][0].billing == "included-subscription"' "$POLICY"

check 'architect begins with native Sol subscription capacity' jq -e '
  .roles.architect[0].model == "gpt-5.6-sol" and
  .roles.architect[0].transport == "codex-cli"' "$POLICY"

check 'declared native aliases bind to exact approved served identities' jq -e '
  ([.roles[][] | select(has("servedIdentities"))] | length) > 0 and
  all(.roles[][]; if has("servedIdentities") then
    .transport == "claude-cli" and (.servedIdentities | type) == "array" and
    (.servedIdentities | length) == 1 and
    all(.servedIdentities[]; test("^claude-(fable|opus)-[0-9]+$"))
  else true end)' "$POLICY"

check 'security head is isolated from ordinary roles' jq -e '
  .roles["security-review"][0].model == "gpt-5.6-terra" and
  .roles["security-review"][1].model == "moonshotai/kimi-k3" and
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

check 'weekly benchmark procedure stops faults, partial spend, and identity leakage' sh -c \
  "grep -Fq 'recorded as nomination-only and not as runnable targets' '$WEEKLY' && \
   grep -Fq 'stop all native and OpenRouter benchmark' '$WEEKLY' && \
   grep -Fq './tools/validate-paid-benchmark-costs.sh \"\$WEEK_ROOT/openrouter\"' '$WEEKLY' && \
   grep -Fq 'paid-calls.stopped' '$WEEKLY' && \
   grep -Fq '> \"\$PAID_STOP\"' '$WEEKLY' && \
   ! grep -Eq '^[[:space:]]*break([[:space:]]|$)' '$WEEKLY' && \
   grep -Fq 'coordinator—not the editor' '$WEEKLY'"

check 'paid receipt gate rejects partial cost coverage' sh -c '
  fixture="$(mktemp -d)" || exit 1
  trap '\''rm -rf -- "$fixture"'\'' EXIT
  mkdir -p "$fixture/openrouter/model/case/run-1"
  printf '\''{"usage":{"cost":0.25}}\n'\'' > "$fixture/openrouter/model/case/run-1/receipt.json"
  "$1" "$fixture/openrouter" || exit 1
  mkdir -p "$fixture/openrouter/model/case/run-2"
  printf '\''{"usage":{}}\n'\'' > "$fixture/openrouter/model/case/run-2/receipt.json"
  ! "$1" "$fixture/openrouter" 2>/dev/null
' sh "$PAID_COST_CHECK"

check 'paid receipt gate rejects every incomplete cost boundary' sh -c '
  fixture="$(mktemp -d)" || exit 1
  trap '\''rm -rf -- "$fixture"'\'' EXIT
  check="$1"
  mkdir -p "$fixture/empty"
  ! "$check" "$fixture/empty" 2>/dev/null || exit 1
  for kind in malformed string null negative; do
    root="$fixture/$kind/model/case/run-1"
    mkdir -p "$root"
    case "$kind" in
      malformed) printf '\''not-json\n'\'' > "$root/receipt.json" ;;
      string) printf '\''{"usage":{"cost":"0.25"}}\n'\'' > "$root/receipt.json" ;;
      null) printf '\''{"usage":{"cost":null}}\n'\'' > "$root/receipt.json" ;;
      negative) printf '\''{"usage":{"cost":-0.01}}\n'\'' > "$root/receipt.json" ;;
    esac
    ! "$check" "$fixture/$kind" 2>/dev/null || exit 1
  done
  mkdir -p "$fixture/symlink/model/case/run-1"
  printf '\''{"usage":{"cost":0.25}}\n'\'' > "$fixture/valid.json"
  ln -s "$fixture/valid.json" "$fixture/symlink/model/case/run-1/receipt.json"
  ! "$check" "$fixture/symlink" 2>/dev/null
' sh "$PAID_COST_CHECK"

check 'repository-owned evaluator bindings are current' "$BINDING_CHECK" --check

check 'live model-intelligence report uses v2 no-conclusion semantics' sh -c \
  "jq -e '.schema_version == 2 and (.quality_efficiency.roles | length) == 9 and .benchmarks.routing_conclusion == \"no routing change justified\"' '$LATEST' >/dev/null && \
   ! grep -Fq 'parsed_successes' '$LATEST' && ! grep -Fq 'depot-role-v1' '$LATEST'"

check 'provider-neutral drift and leak validator passes' "$ROOT/tools/validate-provider-neutral-routing.sh"
check 'resolver economics fixtures pass' "$ROOT/tools/test-model-router.sh"
check 'benchmark evidence contract fixtures pass' "$ROOT/tools/test-benchmark-evidence-contract.sh"
check 'Depot role benchmark fixtures pass' "$ROOT/tools/test-openrouter-role-benchmark.sh"
check 'model intelligence and native benchmark tests pass' python3 "$ROOT/tests/test_model_intelligence.py" -v

if [ "$failures" -ne 0 ]; then
  printf 'routing economics validation failed\n' >&2
  exit 1
fi
printf 'routing economics validation passed\n'
