#!/usr/bin/env bash
# openrouter-wrapper.sh — generalized model runner for World B (Rail 2).
# Drop-in sibling of deepseek-wrapper.sh: same arg shape + exit codes so
# deepseek-agent-runner can call it with a one-line path change.
#
# Usage:
#   ./openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
#     <prompt|->  literal prompt, or "-" to read prompt from stdin
#
# Env:
#   OPENROUTER_API_KEY   required
#   OPENROUTER_SYSTEM    optional system prompt (default: terse coding assistant)
#   OPENROUTER_BASE      optional, default https://openrouter.ai/api/v1
#
# Exit codes (match deepseek-wrapper.sh):
#   0  success   28 timeout   1 exhausted/error   2 bad args
set -uo pipefail

MODEL="${1:-}"; PROMPT_ARG="${2:-}"; TIMEOUT="${3:-90}"; FALLBACK="${4:-}"
[ -z "$MODEL" ] || [ -z "$PROMPT_ARG" ] && { echo "usage: $0 <model> <prompt|-> [timeout] [fallback]" >&2; exit 2; }
[ -z "${OPENROUTER_API_KEY:-}" ] && { echo "### RUNNER FAILURE: OPENROUTER_API_KEY unset" >&2; exit 1; }

BASE="${OPENROUTER_BASE:-https://openrouter.ai/api/v1}"
SYSTEM="${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}"

if [ "$PROMPT_ARG" = "-" ]; then PROMPT="$(cat)"; else PROMPT="$PROMPT_ARG"; fi

# Prefer gtimeout (coreutils on macOS) then timeout; degrade gracefully.
TO=""; command -v gtimeout >/dev/null 2>&1 && TO="gtimeout ${TIMEOUT}s"
[ -z "$TO" ] && command -v timeout >/dev/null 2>&1 && TO="timeout ${TIMEOUT}s"

# Provider preferences (per-request — portable, beats relying on dashboard defaults):
#   OPENROUTER_REQUIRE_PARAMS=1 (default) → skip providers that don't support the
#       requested params (e.g. tool calling) so agentic calls don't silently degrade.
#   OPENROUTER_ZDR=1 → only providers that do NOT train on / retain data (privacy).
#   OPENROUTER_PROVIDER_SORT=throughput|latency|price → bias provider choice.
build_provider() {
  jq -n \
    --argjson req "$([ "${OPENROUTER_REQUIRE_PARAMS:-1}" = "1" ] && echo true || echo false)" \
    --arg zdr "${OPENROUTER_ZDR:-0}" \
    --arg sort "${OPENROUTER_PROVIDER_SORT:-}" '
    {require_parameters: $req}
    + (if $zdr == "1" then {data_collection: "deny"} else {} end)
    + (if $sort != "" then {sort: $sort} else {} end)'
}

call() {
  local model="$1" body resp http
  body="$(jq -n --arg m "$model" --arg s "$SYSTEM" --arg p "$PROMPT" --argjson prov "$(build_provider)" \
    '{model:$m, provider:$prov, messages:[{role:"system",content:$s},{role:"user",content:$p}]}')"
  resp="$($TO curl -sS -w '\n%{http_code}' "$BASE/chat/completions" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -H "Content-Type: application/json" \
    -H "HTTP-Referer: https://designmachines.dev" \
    -H "X-Title: world-b-runner" \
    --max-time "$TIMEOUT" -d "$body")"
  local rc=$?
  [ $rc -eq 124 ] && { echo "### RUNNER TIMEOUT ($model, ${TIMEOUT}s)" >&2; return 28; }
  http="$(printf '%s' "$resp" | tail -n1)"
  body="$(printf '%s' "$resp" | sed '$d')"
  if [ "$http" = "429" ] || [ "$http" = "503" ]; then return 75; fi   # retry/fallback
  if [ "$http" != "200" ]; then
    echo "### RUNNER FAILURE ($model, HTTP $http): $(printf '%s' "$body" | jq -r '.error.message // empty' 2>/dev/null)" >&2
    return 1
  fi
  printf '%s' "$body" | jq -r '.choices[0].message.content // empty'
}

out="$(call "$MODEL")"; rc=$?
if [ $rc -eq 75 ] && [ -n "$FALLBACK" ]; then
  echo "### note: $MODEL rate-limited, falling back to $FALLBACK" >&2
  out="$(call "$FALLBACK")"; rc=$?
fi
[ $rc -eq 75 ] && rc=1
[ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
exit $rc
