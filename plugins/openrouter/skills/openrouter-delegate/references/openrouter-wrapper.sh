#!/usr/bin/env bash
# openrouter-wrapper.sh -- generalized single-turn model runner for the World B
# OpenRouter rail. Stable exit codes (0/28/1/2) and direct text stdout let the
# generic review-agent runner map success, timeout, exhausted, and invocation
# outcomes without provider-specific response parsing. Arguments are positional:
# <model> <prompt|-> [timeout] [fallback].
#
# Usage:
#   ./openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
#     <prompt|->  literal prompt, or "-" to read prompt from stdin
#
# Env:
#   OPENROUTER_API_KEY   required
#   OPENROUTER_SYSTEM    optional system prompt (default: terse coding assistant)
#   OPENROUTER_BASE      optional, default https://openrouter.ai/api/v1
#   OPENROUTER_ZDR       1 -> no-train/no-retain providers (data_collection: deny)
#   OPENROUTER_PROVIDER_SORT
#                       price|throughput|latency|exacto; Kimi defaults to exacto
#   OPENROUTER_PROVIDER_ORDER
#                       optional comma-separated provider/endpoint slugs
#   OPENROUTER_ALLOW_FALLBACKS
#                       0|1 when provider order is set (default 1)
#   OPENROUTER_RECEIPT_FILE
#                       optional content-free JSON generation receipt path
#
# Exit codes:
#   0  success   28 timeout   1 exhausted/error   2 bad args
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"   # fixed PATH: prevent caller-controlled dependency hijack

MODEL="${1:-}"; PROMPT_ARG="${2:-}"; TIMEOUT="${3:-90}"; FALLBACK="${4:-}"
if [ -z "$MODEL" ] || [ -z "$PROMPT_ARG" ]; then
  echo "usage: $0 <model> <prompt|-> [timeout] [fallback]" >&2; exit 2
fi

for candidate in "$MODEL" "$FALLBACK"; do
  [ -z "$candidate" ] && continue
  candidate_origin="$(printf '%s' "$candidate" | tr '[:upper:]' '[:lower:]')"
  case "$candidate_origin" in
    openai/*|anthropic/*)
      echo "### RUNNER FAILURE: native-vendor-origin invariant rejected OpenRouter model '$candidate'" >&2
      exit 2
      ;;
  esac
done
[ -z "${OPENROUTER_API_KEY:-}" ] && { echo "### RUNNER FAILURE: OPENROUTER_API_KEY unset" >&2; exit 1; }

BASE="${OPENROUTER_BASE:-https://openrouter.ai/api/v1}"
SYSTEM="${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}"
PROVIDER_ORDER="${OPENROUTER_PROVIDER_ORDER:-}"
PROVIDER_SORT="${OPENROUTER_PROVIDER_SORT:-}"
ALLOW_FALLBACKS="${OPENROUTER_ALLOW_FALLBACKS:-1}"

case "$ALLOW_FALLBACKS" in
  0|1) ;;
  *) echo "### RUNNER FAILURE: OPENROUTER_ALLOW_FALLBACKS must be 0 or 1" >&2; exit 2 ;;
esac
case "$PROVIDER_SORT" in
  ""|price|throughput|latency|exacto) ;;
  *) echo "### RUNNER FAILURE: invalid OPENROUTER_PROVIDER_SORT" >&2; exit 2 ;;
esac
if [ -n "$PROVIDER_ORDER" ]; then
  case "$PROVIDER_ORDER" in
    *".."*|,*|*,|*,,*|*[!A-Za-z0-9._,/-]*)
      echo "### RUNNER FAILURE: invalid OPENROUTER_PROVIDER_ORDER" >&2
      exit 2
      ;;
  esac
elif [ -z "$PROVIDER_SORT" ]; then
  case "$MODEL" in
    moonshotai/kimi-k3|moonshotai/kimi-k3-*|moonshotai/kimi-k3:*)
      # OpenRouter's Exacto strategy continuously reorders providers using live
      # quality signals. Explicit OPENROUTER_PROVIDER_ORDER remains available
      # for reproducible evals and incident replay.
      PROVIDER_SORT="exacto"
      ;;
  esac
fi

if [ "$PROMPT_ARG" = "-" ]; then PROMPT="$(cat)"; else PROMPT="$PROMPT_ARG"; fi

# Prefer gtimeout (coreutils on macOS) then timeout; degrade gracefully.
TO=""; command -v gtimeout >/dev/null 2>&1 && TO="gtimeout ${TIMEOUT}s"
[ -z "$TO" ] && command -v timeout >/dev/null 2>&1 && TO="timeout ${TIMEOUT}s"

# Provider preferences (per-request -- portable, beats relying on dashboard defaults):
#   OPENROUTER_REQUIRE_PARAMS=1 (default) -> skip providers that don't support the
#       requested params (e.g. tool calling) so agentic calls don't silently degrade.
#   OPENROUTER_ZDR=1 -> only providers that do NOT train on / retain data (privacy).
#   OPENROUTER_PROVIDER_SORT=throughput|latency|price|exacto -> bias provider choice.
#   OPENROUTER_PROVIDER_ORDER=slug,slug -> deterministic preference order.
build_provider() {
  jq -n \
    --argjson req "$([ "${OPENROUTER_REQUIRE_PARAMS:-1}" = "1" ] && echo true || echo false)" \
    --arg zdr "${OPENROUTER_ZDR:-0}" \
    --arg sort "$PROVIDER_SORT" \
    --arg order "$PROVIDER_ORDER" \
    --argjson allow "$([ "$ALLOW_FALLBACKS" = "1" ] && echo true || echo false)" '
    {require_parameters: $req}
    + (if $zdr == "1" then {data_collection: "deny", zdr: true} else {} end)
    + (if $order != ""
       then {order: ($order | split(",")), allow_fallbacks: $allow}
       elif $sort != ""
       then {sort: $sort}
       else {}
       end)'
}

PROVIDER="$(build_provider)"   # provider prefs depend only on env -- compute once, reuse across primary + fallback

write_receipt() {
  local response_body="$1" requested_model="$2" receipt_tmp
  [ -z "${OPENROUTER_RECEIPT_FILE:-}" ] && return 0
  receipt_tmp="${OPENROUTER_RECEIPT_FILE}.tmp.$$"
  (
    umask 077
    printf '%s' "$response_body" | jq \
      --arg requested "$requested_model" '
      {
        schemaVersion: 1,
        generationId: (.id // null),
        created: (.created // null),
        requestedModel: $requested,
        responseModel: (.model // $requested),
        servingProvider: (.provider // null),
        usage: (.usage // null)
      }' > "$receipt_tmp"
  ) || {
    rm -f "$receipt_tmp"
    echo "### RUNNER FAILURE: could not write OpenRouter receipt" >&2
    return 1
  }
  mv "$receipt_tmp" "$OPENROUTER_RECEIPT_FILE"
}

call() {
  local model="$1" body resp http rc
  body="$(jq -n --arg m "$model" --arg s "$SYSTEM" --arg p "$PROMPT" --argjson prov "$PROVIDER" \
    '{model:$m, provider:$prov, messages:[{role:"system",content:$s},{role:"user",content:$p}]}')"
  resp="$($TO curl -sS -w '\n%{http_code}' "$BASE/chat/completions" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -H "Content-Type: application/json" \
    -H "HTTP-Referer: https://designmachines.dev" \
    -H "X-Title: world-b-runner" \
    --max-time "$TIMEOUT" -d "$body")"
  rc=$?   # capture the curl/timeout pipeline status (separate line: a `local rc=$?` would mask it with local's own 0)
  { [ $rc -eq 124 ] || [ $rc -eq 28 ]; } && { echo "### RUNNER TIMEOUT ($model, ${TIMEOUT}s)" >&2; return 28; }
  http="$(printf '%s' "$resp" | tail -n1)"
  body="$(printf '%s' "$resp" | sed '$d')"
  if [ "$http" = "429" ] || [ "$http" = "503" ]; then return 75; fi   # retry/fallback
  if [ "$http" != "200" ]; then
    echo "### RUNNER FAILURE ($model, HTTP $http): $(printf '%s' "$body" | jq -r '.error.message // empty' 2>/dev/null)" >&2
    return 1
  fi
  write_receipt "$body" "$model" || return 1
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
