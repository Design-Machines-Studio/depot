#!/usr/bin/env bash
# cascade-dispatch.sh — World B usage-aware model-cascade decision engine.
# Harness-neutral (Claude Code / Codex / opencode / Pi). Generalizes the merged
# execution-orchestrator 3d fallback ("Codex unavailable -> Claude") into a full
# usage-gauged ladder. Reads model-cascade.json (executor-intent classes →
# role ladders) + routing-policy.json + harness-profile.json (role→rail per host) + usage-probe.sh
# (live headroom). Picks the best rung above the class quality_floor; on a cap
# error fires the Airlift Tier-1 checkpoint and descends.
#
# Usage:
#   cascade-dispatch.sh --class <codex|claude> --prompt <text|-> \
#       [--kind <ui|logic|integration|config>] [--phase <p>] [--host H] \
#       [--timeout N] [--dry-run] [--probe-file <json>] \
#       [--exhausted-rail <codex|claude|openrouter>]
#   (--kind is an alternative to --class; mapped via cascade.class_from_kind)
#
# Exit codes:
#   0   a wrapper/codex_companion/openrouter_exec rung executed -- output on stdout
#   64  chosen rung is NATIVE — directive JSON on stdout; the HOST orchestrator
#       runs that model in-process (Claude subagent / Codex). The only host-specific action.
#   75  ladder exhausted — no rung had headroom above the floor
#   2   bad args
#
# Deps: bash, jq. Optional: airlift engine (guarded; no-op if absent), node + Codex plugin.
set -uo pipefail

# Fixed PATH reset -- prevent caller-controlled hijack of jq/node/ls/awk/grep/bash while
# this dispatcher shells out during autonomous execution. Depot shell-script convention.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASCADE="${CASCADE_FILE:-$DIR/model-cascade.json}"
PROFILE="${PROFILE_FILE:-$DIR/harness-profile.json}"
PROBE="${PROBE_CMD:-$DIR/usage-probe.sh}"
# openrouter-wrapper is owned by the openrouter leaf plugin — resolved at call time (resolve_wrapper)

CLASS=""; KIND=""; PROMPT=""; PHASE="execute"; HOST=""; TIMEOUT="120"; DRYRUN=0; PROBE_FILE=""
EXHAUSTED_RAILS="${CASCADE_EXHAUSTED_RAILS:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --class) CLASS="$2"; shift 2;;
    --kind) KIND="$2"; shift 2;;
    --prompt) PROMPT="$2"; shift 2;;
    --phase) PHASE="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --dry-run) DRYRUN=1; shift;;
    --probe-file) PROBE_FILE="$2"; shift 2;;
    --exhausted-rail) EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
command -v jq >/dev/null 2>&1 || { echo "cascade-dispatch: jq required" >&2; exit 2; }
[ -z "$CLASS" ] && [ -n "$KIND" ] && CLASS="$(jq -r --arg k "$KIND" '.class_from_kind[$k] // empty' "$CASCADE")"
[ -z "$CLASS" ] || [ -z "$PROMPT" ] && { echo "usage: $0 --class <codex|claude>|--kind <k> --prompt <p|-> [opts]" >&2; exit 2; }
[ "$PROMPT" = "-" ] && PROMPT="$(cat)"

# --- host detection ----------------------------------------------------------
if [ -z "$HOST" ]; then
  HOST="$(jq -r '.active_host' "$PROFILE" 2>/dev/null)"
  { [ "$HOST" = "auto" ] || [ -z "$HOST" ]; } && HOST="${CASCADE_HOST:-}"
  if [ -z "$HOST" ]; then
    if   [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ]; then HOST="claude-code"
    elif [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ]; then HOST="codex"
    else HOST="generic"; fi
  fi
fi

# --- Airlift Tier-1 checkpoint (guarded resolve; no model budget; no-op if absent)
checkpoint() {
  local engine=""
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    engine="$(ls -t "$cache"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)"
    [ -n "$engine" ] && break
  done
  if [ -n "$engine" ] && [ -x "$engine" ]; then bash "$engine" write --phase "$PHASE" >/dev/null 2>&1 || true; fi
}

# --- Codex via codex-companion (matches execution-orchestrator.md 3d) ---------
resolve_codex_root() {
  local root=""
  for cache in "$HOME/.claude/plugins/cache/openai-codex/codex" "$HOME/.codex/plugins/cache/openai-codex/codex"; do
    root="$(ls -td "$cache"/*/ 2>/dev/null | head -1)"
    [ -n "$root" ] && break
  done
  printf '%s' "$root"
}
dispatch_codex() {
  local root; root="$(resolve_codex_root)"
  [ -z "$root" ] && return 127                       # Codex not installed → unavailable
  node "${root}/scripts/codex-companion.mjs" task --write "$PROMPT" 2>&1
}
# openrouter-wrapper lives in the openrouter leaf plugin (dual-cache resolve, like CODEX_ROOT/airlift).
resolve_wrapper() {
  [ -n "${WRAPPER_CMD:-}" ] && { printf '%s' "$WRAPPER_CMD"; return; }
  local w=""
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    w="$(ls -t "$cache"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1)"
    [ -n "$w" ] && break
  done
  [ -z "$w" ] && [ -x "$DIR/openrouter-wrapper.sh" ] && w="$DIR/openrouter-wrapper.sh"   # dev fallback
  printf '%s' "$w"
}
dispatch_wrapper() { local w; w="$(resolve_wrapper)"; [ -z "$w" ] && return 1; "$w" "$1" "$PROMPT" "$TIMEOUT" "${2:-}"; }
resolve_openrouter_exec() {
  [ -n "${OPENROUTER_EXEC_CMD:-}" ] && { printf '%s' "$OPENROUTER_EXEC_CMD"; return; }
  local runner=""
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    runner="$(ls -t "$cache"/pipeline/*/references/openrouter-exec.sh 2>/dev/null | head -1)"
    [ -n "$runner" ] && break
  done
  [ -z "$runner" ] && [ -x "$DIR/openrouter-exec.sh" ] && runner="$DIR/openrouter-exec.sh"
  printf '%s' "$runner"
}
dispatch_openrouter_exec() {
  local runner; runner="$(resolve_openrouter_exec)"
  [ -z "$runner" ] && return 1
  printf '%s' "$PROMPT" | "$runner" --model "$1" --timeout "$TIMEOUT" 2>&1
}

probe_json() { [ -n "$PROBE_FILE" ] && cat "$PROBE_FILE" || { [ -x "$PROBE" ] && "$PROBE" || echo '{}'; }; }
PROBES="$(probe_json)"
FLOOR="$(jq -r --arg c "$CLASS" '.cascades[$c].quality_floor // 0' "$CASCADE")"
LADDER="$(jq -r --arg c "$CLASS" '.cascades[$c].ladder[]?' "$CASCADE")"
[ -z "$LADDER" ] && { echo "cascade-dispatch: unknown class '$CLASS'" >&2; exit 2; }
THRESH="$(jq -r '.policy.headroom_threshold_pct // 8' "$CASCADE")"

rail_is_exhausted() {
  # bash 3.2 safe: avoid read -a + "${arr[@]}" (empty array + set -u is fatal on 3.2).
  # Comma-wrap both sides so a substring match is an exact rail match.
  [ -z "$EXHAUSTED_RAILS" ] && return 1
  case ",$EXHAUSTED_RAILS," in *",$1,"*) return 0 ;; esac
  return 1
}

rail_has_headroom() {
  local rail="$1" state pct
  [ "$rail" = "none" ] && return 0
  rail_is_exhausted "$rail" && return 1
  state="$(printf '%s' "$PROBES" | jq -r --arg r "$rail" '.[$r].state // "unknown"')"
  case "$state" in limited|low) return 1;; esac
  pct="$(printf '%s' "$PROBES" | jq -r --arg r "$rail" '.[$r].remaining_pct // empty')"
  [ -n "$pct" ] && [ "$pct" -lt "$THRESH" ] 2>/dev/null && return 1
  return 0
}

# --- walk the ladder ---------------------------------------------------------
for role in $LADDER; do
  kind="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].kind // "none"' "$PROFILE")"
  [ "$kind" = "none" ] && continue
  prail="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].probe // "none"' "$PROFILE")"
  rail_has_headroom "$prail" || continue
  models="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].models[]?' "$PROFILE")"
  for model in $models; do
    q="$(jq -r --arg m "$model" '.quality_rank[$m] // 0' "$CASCADE")"
    [ "$q" -lt "$FLOOR" ] 2>/dev/null && continue
    if [ "$DRYRUN" = "1" ]; then
      jq -n --arg c "$CLASS" --arg h "$HOST" --arg role "$role" --arg k "$kind" \
            --arg m "$model" --arg q "$q" --arg pr "$prail" \
            '{class:$c,host:$h,role:$role,kind:$k,model:$m,quality:($q|tonumber),probe_rail:$pr}'
      exit 0
    fi
    # Traversal intent per rung kind: codex_companion is single-attempt per role
    # -> `break` to the next ROLE on any failure; native emits a directive and
    # `exit 64`s on the first qualifying model (the orchestrator owns the in-process
    # model descent, e.g. opus->sonnet); wrapper roles iterate their model list
    # -> `continue` to the next MODEL on a per-model error.
    case "$kind" in
      native)
        jq -n --arg m "$model" --arg role "$role" --arg pr "$prail" \
              '{dispatch:"native",model:$m,role:$role,probe_rail:$pr}'; exit 64;;
      codex_companion)
        out="$(dispatch_codex)"; rc=$?
        [ $rc -eq 127 ] && break                       # Codex absent → next role
        if printf '%s' "$out" | grep -qiE 'usage limit|rate.?limit|quota'; then
          checkpoint; break                            # CAP → handoff, next role
        fi
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        break;;                                        # other codex failure → next role (Claude)
      wrapper)
        fb="$(printf '%s' "$models" | awk -v m="$model" 'f{print;exit} $0==m{f=1}')"
        out="$(dispatch_wrapper "$model" "$fb")"; rc=$?
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        continue;;                                     # wrapper error → next model
      openrouter_exec)
        out="$(dispatch_openrouter_exec "$model")"; rc=$?
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        continue;;
    esac
  done
done

echo "cascade-dispatch: ladder exhausted for class '$CLASS' on host '$HOST' (floor $FLOOR)" >&2
exit 75
