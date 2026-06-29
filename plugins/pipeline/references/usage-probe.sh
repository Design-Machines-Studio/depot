#!/usr/bin/env bash
# usage-probe.sh — gauge remaining headroom per rail for the model cascade.
# Emits JSON the orchestrator reads to pick the highest available rung.
#
#   { "codex":  {"state":"ok|limited|unknown","resets_at":"<iso|null>","remaining_pct":<int|null>},
#     "claude": {"state":"ok|limited|unknown","resets_at":"<iso|null>","remaining_pct":<int|null>},
#     "openrouter": {"state":"ok|low|unknown","balance_usd":<num|null>} }
#
# SKETCH: the three probes shell out to ccusage / codex / OpenRouter. The exact
# stdout shapes of `ccusage` and `codex` shift between versions, so the parsers
# below are marked TODO — verify the field names against YOUR installed versions
# once and pin them. The contract (the JSON above) is what the cascade depends on.
set -uo pipefail

iso_or_null() { [ -n "${1:-}" ] && printf '"%s"' "$1" || printf 'null'; }

# --- Claude Max via ccusage (Airlift's Tier-3 signal) -------------------------
# `ccusage` reports rolling 5h + weekly windows. TODO: confirm JSON flag/fields.
claude_json() {
  local out="" pct="" reset="" state="unknown"
  if command -v ccusage >/dev/null 2>&1; then
    out="$(ccusage --json 2>/dev/null)" || out=""
    if [ -n "$out" ]; then
      pct="$(printf '%s' "$out"  | jq -r '.weekly.remaining_pct // .remaining_pct // empty' 2>/dev/null)"
      reset="$(printf '%s' "$out"| jq -r '.weekly.resets_at // .resets_at // empty' 2>/dev/null)"
      if [ -n "$pct" ]; then [ "$pct" -le 8 ] 2>/dev/null && state="limited" || state="ok"; fi
    fi
  fi
  printf '{"state":"%s","resets_at":%s,"remaining_pct":%s}' \
    "$state" "$(iso_or_null "$reset")" "${pct:-null}"
}

# --- Codex sub via `codex` status --------------------------------------------
# Reactive truth is UsageLimitReachedError.resets_at at call time; this is the
# proactive probe. TODO: confirm `codex status --json` (or parse `/status`).
codex_json() {
  local out="" pct="" reset="" state="unknown"
  if command -v codex >/dev/null 2>&1; then
    out="$(codex status --json 2>/dev/null)" || out=""
    if [ -n "$out" ]; then
      pct="$(printf '%s' "$out"  | jq -r '.weekly.remaining_pct // .rate_limit.remaining_pct // empty' 2>/dev/null)"
      reset="$(printf '%s' "$out"| jq -r '.weekly.resets_at // .rate_limit.resets_at // empty' 2>/dev/null)"
      if [ -n "$pct" ]; then [ "$pct" -le 8 ] 2>/dev/null && state="limited" || state="ok"; fi
    fi
  fi
  printf '{"state":"%s","resets_at":%s,"remaining_pct":%s}' \
    "$state" "$(iso_or_null "$reset")" "${pct:-null}"
}

# --- OpenRouter: no cap, just balance ----------------------------------------
openrouter_json() {
  local bal="" state="unknown"
  if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    bal="$(curl -sS --max-time 10 https://openrouter.ai/api/v1/credits \
      -H "Authorization: Bearer $OPENROUTER_API_KEY" 2>/dev/null \
      | jq -r '(.data.total_credits - .data.total_usage) // empty' 2>/dev/null)"
    # Validate numeric before use: untrusted API output must never reach awk's
    # program text (code injection) nor the unquoted JSON below (malformed output).
    # Non-numeric -> unknown (fail-open: prefer dispatch + reactive cap detection).
    case "$bal" in ''|*[!0-9.+-]*) bal="" ;; esac
    [ -n "$bal" ] && { awk -v b="$bal" 'BEGIN{exit !(b < 5)}' && state="low" || state="ok"; }
  fi
  printf '{"state":"%s","balance_usd":%s}' "$state" "${bal:-null}"
}

printf '{"codex":%s,"claude":%s,"openrouter":%s}\n' \
  "$(codex_json)" "$(claude_json)" "$(openrouter_json)"
