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
  out="$("$cascade" --kind logic --prompt test --host codex --dry-run --exhausted-rail codex 2>/dev/null || true)"
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

  ui_out="$("$cascade" --kind ui --prompt test --host codex --dry-run 2>/dev/null || true)"
  ui_role="$(printf '%s' "$ui_out" | jq -r '.role // empty' 2>/dev/null || true)"
  ui_kind="$(printf '%s' "$ui_out" | jq -r '.kind // empty' 2>/dev/null || true)"
  if [ "$ui_role" = "premium_sub" ] && [ "$ui_kind" = "native" ]; then
    pass "UI coding selects Codex-native subscription execution"
  else
    fail "UI coding must resolve to Codex-native execution, never Claude"
    any_failed=1
  fi

  or_out="$("$cascade" --kind docs --prompt test --host codex --dry-run --exhausted-rail openrouter 2>/dev/null || true)"
  or_role="$(printf '%s' "$or_out" | jq -r '.role // empty' 2>/dev/null || true)"
  if [ "$or_role" = "premium_sub" ]; then
    pass "OpenRouter-primary coding returns to Codex when OpenRouter is exhausted"
  else
    fail "OpenRouter-primary coding must return to Codex, never Claude"
    any_failed=1
  fi

  # bash 3.2 portability: the DEFAULT path (no --exhausted-rail, empty list) must
  # not trip the empty-array + set -u fatal. Exercise it under the system /bin/bash
  # (3.2 on macOS) explicitly -- env bash may be a modern build that hides the bug.
  if [ -x /bin/bash ]; then
    base_out="$(/bin/bash "$cascade" --kind logic --prompt test --host codex --dry-run 2>/dev/null || true)"
    if printf '%s' "$base_out" | jq -e '.model' >/dev/null 2>&1; then
      pass "cascade-dispatch runs clean under system bash with no --exhausted-rail"
    else
      fail "cascade-dispatch breaks under system /bin/bash when --exhausted-rail is unset (bash 3.2 empty-array)"
      any_failed=1
    fi
  fi
fi

if grep -q 'zdr: true' "$wrapper" && grep -q 'data_collection: "deny"' "$wrapper"; then
  pass "OpenRouter ZDR mode requests both zdr:true and data_collection:deny"
else
  fail "OPENROUTER_ZDR=1 must send provider.zdr=true as well as data_collection=deny"
  any_failed=1
fi

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
