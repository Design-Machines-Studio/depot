#!/usr/bin/env bash
# cascade-dispatch.sh -- World B usage-aware model-cascade decision engine.
# Harness-neutral (Claude Code / Codex / opencode / Pi). Generalizes the merged
# execution-orchestrator fallback into a Codex/OpenRouter coding ladder.
# usage-gauged ladder. Reads model-cascade.json (executor-intent classes ->
# role ladders) + routing-policy.json + harness-profile.json (role->rail per host) + usage-probe.sh
# (live headroom). Picks the best rung above the class quality_floor; on a cap
# error fires the Airlift Tier-1 checkpoint and descends.
#
# Usage:
#   cascade-dispatch.sh --class <codex|openrouter> --prompt <text|-> \
#       [--kind <ui|logic|integration|config>] [--phase <p>] [--host H] \
#       [--timeout N] [--dry-run] [--probe-file <json>] \
#       [--attempt-receipt-template <path-with-{attempt}>] \
#       [--exhausted-rail <codex|openrouter>]
#   (--kind is an alternative to --class; mapped via cascade.class_from_kind)
#
# Exit codes:
#   0   a wrapper/codex_companion/openrouter_exec rung executed -- output on stdout
#   64  chosen rung is NATIVE -- directive JSON on stdout; the HOST orchestrator
#       runs that model in-process (Claude subagent / Codex). The only host-specific action.
#   76  ladder exhausted -- no rung had headroom above the floor
#   77  disclosure declined -- use the trusted native fallback
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
CLASS=""; KIND=""; PROMPT=""; PHASE="execute"; HOST=""; TIMEOUT="3600"; DRYRUN=0; PROBE_FILE=""
ATTEMPT_RECEIPT_TEMPLATE=""
OPENROUTER_ATTEMPT_INDEX=0
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
    --attempt-receipt-template) ATTEMPT_RECEIPT_TEMPLATE="$2"; shift 2;;
    --exhausted-rail) EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
command -v jq >/dev/null 2>&1 || { echo "cascade-dispatch: jq required" >&2; exit 2; }
[ -z "$CLASS" ] && [ -n "$KIND" ] && CLASS="$(jq -r --arg k "$KIND" '.class_from_kind[$k] // empty' "$CASCADE")"
[ -z "$CLASS" ] || [ -z "$PROMPT" ] && { echo "usage: $0 --class <codex|openrouter>|--kind <k> --prompt <p|-> [opts]" >&2; exit 2; }
if [ -n "$ATTEMPT_RECEIPT_TEMPLATE" ]; then
  case "$ATTEMPT_RECEIPT_TEMPLATE" in
    *'{attempt}'*) ;;
    *) echo "cascade-dispatch: attempt receipt template requires {attempt}" >&2; exit 2;;
  esac
fi
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
  [ -z "$root" ] && return 127                       # Codex not installed -> unavailable
  node "${root}/scripts/codex-companion.mjs" task --write "$PROMPT" 2>&1
}
resolve_openrouter_bundle() {
  local active_host=""
  [ -n "${WORKFLOW_KERNEL:-}" ] && [ -x "$WORKFLOW_KERNEL" ] || return 1
  [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && active_host="claude"
  [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && active_host="codex"
  if [ -n "$active_host" ]; then
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.15.0 --active-host "$active_host" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.15.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  fi
}

# Resolve the complete OpenRouter bundle once for this cascade process. Child
# probes and executors receive the same version/cache/reason binding and must
# compare it with their own pre-transport revalidation.
unset OPENROUTER_BUNDLE_REF OPENROUTER_BUNDLE_VERSION \
  OPENROUTER_BUNDLE_CACHE_CLASS OPENROUTER_BUNDLE_REASON \
  OPENROUTER_BUNDLE_RESOLVED
OPENROUTER_BUNDLE_JSON=""
if [ "$DRYRUN" != "1" ] &&
   { [ -n "${OPENROUTER_API_KEY:-}" ] || [ -n "${OPENROUTER_API_KEY_FILE:-}" ]; }; then
  OPENROUTER_BUNDLE_JSON="$(resolve_openrouter_bundle 2>/dev/null)" || OPENROUTER_BUNDLE_JSON=""
fi
if [ -n "$OPENROUTER_BUNDLE_JSON" ]; then
  OPENROUTER_BUNDLE_REF="$(printf '%s' "$OPENROUTER_BUNDLE_JSON" | jq -r '.selected_root // empty')"
  OPENROUTER_BUNDLE_VERSION="$(printf '%s' "$OPENROUTER_BUNDLE_JSON" | jq -r '.version // empty')"
  OPENROUTER_BUNDLE_CACHE_CLASS="$(printf '%s' "$OPENROUTER_BUNDLE_JSON" | jq -r '.cache_class // empty')"
  OPENROUTER_BUNDLE_REASON="$(printf '%s' "$OPENROUTER_BUNDLE_JSON" | jq -r '.reason // empty')"
  OPENROUTER_BUNDLE_RESOLVED=1
  export OPENROUTER_BUNDLE_REF OPENROUTER_BUNDLE_VERSION \
    OPENROUTER_BUNDLE_CACHE_CLASS OPENROUTER_BUNDLE_REASON \
    OPENROUTER_BUNDLE_RESOLVED
fi

resolve_openrouter_root() {
  [ "${OPENROUTER_BUNDLE_RESOLVED:-0}" = "1" ] || return 1
  case "${OPENROUTER_BUNDLE_REF:-}" in
    "~/"*) printf '%s' "$HOME/${OPENROUTER_BUNDLE_REF#\~/}" ;;
    *) return 1 ;;
  esac
}

dispatch_wrapper() {
  local model="$1" system task_tmp_root system_file prompt_file receipt_file root response rc
  root="$(resolve_openrouter_root)" || return 77
  system="${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}"
  task_tmp_root="${TMPDIR:-/tmp}"
  system_file="$(mktemp "$task_tmp_root/cascade-wrapper.system.XXXXXX")" || return 1
  prompt_file="$(mktemp "$task_tmp_root/cascade-wrapper.prompt.XXXXXX")" || {
    rm -f "$system_file"; return 1;
  }
  receipt_file="$(mktemp "$task_tmp_root/cascade-wrapper.result.XXXXXX")" || {
    rm -f "$system_file" "$prompt_file"; return 1;
  }
  printf '%s' "$system" > "$system_file"
  printf '%s' "$PROMPT" > "$prompt_file"
  "$root/skills/openrouter-delegate/references/delegation-boundary.sh" \
    --mode artifact-delegation \
    --policy "$root/skills/openrouter-delegate/references/delegation-security-policy.json" \
    --content-file "$system_file" --content-file "$prompt_file" >/dev/null || {
      rm -f "$system_file" "$prompt_file" "$receipt_file"; return 77;
    }
  response="$(env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$system_file" \
    OPENROUTER_WORKLOAD="mechanical" \
    OPENROUTER_RECEIPT_FILE="$receipt_file" \
    bash "$root/skills/openrouter-delegate/references/openrouter-wrapper.sh" \
      "$model" - "$TIMEOUT" < "$prompt_file")"; rc=$?
  [ "$rc" -eq 0 ] || {
    rm -f "$system_file" "$prompt_file" "$receipt_file"
    [ "$rc" -eq 2 ] && return 2
    return 1
  }
  jq -e '.schemaVersion == 2 and .outcome == "success" and
    (.authorization.requestEnvelopeSha256 | test("^[0-9a-f]{64}$"))' \
    "$receipt_file" >/dev/null 2>&1 || {
      rm -f "$system_file" "$prompt_file" "$receipt_file"; return 2;
    }
  printf '%s' "$response"
  rm -f "$system_file" "$prompt_file" "$receipt_file"
}
resolve_openrouter_exec() {
  [ -x "$DIR/openrouter-exec.sh" ] && printf '%s' "$DIR/openrouter-exec.sh"
}
dispatch_openrouter_exec() {
  local runner attempt_receipt=""
  runner="$(resolve_openrouter_exec)"
  [ -z "$runner" ] && return 1
  if [ -n "$ATTEMPT_RECEIPT_TEMPLATE" ]; then
    attempt_receipt="${ATTEMPT_RECEIPT_TEMPLATE//\{attempt\}/$2}"
    printf '%s' "$PROMPT" | "$runner" --model "$1" --timeout "$TIMEOUT" \
      --attempt-receipt "$attempt_receipt"
  else
    printf '%s' "$PROMPT" | "$runner" --model "$1" --timeout "$TIMEOUT"
  fi
}

# Gate OpenRouter availability once before any external rung. Payload screening
# remains inside the exact dispatch function so it examines materialized bytes.
OPENROUTER_GATE_STATE="unchecked"
openrouter_allowed() {
  [ "$DRYRUN" = "1" ] && return 0
  [ "$OPENROUTER_GATE_STATE" = "safe" ] && return 0
  [ "$OPENROUTER_GATE_STATE" = "denied" ] && return 1
  if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -z "${OPENROUTER_API_KEY_FILE:-}" ]; then
    OPENROUTER_GATE_STATE="denied"
    return 1
  fi
  if ! resolve_openrouter_root >/dev/null; then
    OPENROUTER_GATE_STATE="denied"
    return 1
  fi
  OPENROUTER_GATE_STATE="safe"
  return 0
}

probe_json() {
  if [ -n "$PROBE_FILE" ]; then
    # A caller-selected file is a deterministic fixture, never live capacity.
    # Override even a forged `live` field so test data cannot acquire stronger
    # provenance by self-assertion.
    jq -c '. + {probe_source:"fixture"}' "$PROBE_FILE" 2>/dev/null || echo '{}'
  else
    [ -x "$PROBE" ] && "$PROBE" || echo '{}'
  fi
}
PROBES="$(probe_json)"
PROBE_SOURCE="$(printf '%s' "$PROBES" | jq -r '.probe_source // "unknown"' 2>/dev/null)"
case "$PROBE_SOURCE" in
  live) ;;
  fixture)
    echo "cascade-dispatch: probe_source=fixture; headroom is test evidence, not live capacity" >&2
    ;;
  *)
    PROBE_SOURCE="unknown"
    ;;
esac
FLOOR="$(jq -r --arg c "$CLASS" '.cascades[$c].quality_floor // 0' "$CASCADE")"
LADDER="$(jq -r --arg c "$CLASS" '.cascades[$c].ladder[]?' "$CASCADE")"
[ -z "$LADDER" ] && { echo "cascade-dispatch: unknown class '$CLASS'" >&2; exit 2; }
REQUESTED_ROLE="$(printf '%s\n' "$LADDER" | sed -n '1p')"
REQUESTED_MODEL="$(jq -r --arg h "$HOST" --arg r "$REQUESTED_ROLE" \
  '.hosts[$h].roles[$r].models[0] // empty' "$PROFILE")"
THRESH="$(jq -r '.policy.headroom_threshold_pct // 8' "$CASCADE")"

rail_is_exhausted() {
  # bash 3.2 safe: avoid read -a + "${arr[@]}" (empty array + set -u is fatal on 3.2).
  # Comma-wrap both sides so a substring match is an exact rail match.
  [ -z "$EXHAUSTED_RAILS" ] && return 1
  case ",$EXHAUSTED_RAILS," in *",$1,"*) return 0 ;; esac
  return 1
}

rail_has_headroom() {
  local rail="$1"
  [ "$rail" = "none" ] && return 1
  rail_is_exhausted "$rail" && return 1
  if [ "$rail" = "openrouter" ]; then
    printf '%s' "$PROBES" | jq -e --arg rail "$rail" '
      type == "object"
        and (.[$rail] | type == "object")
        and (.[$rail].state == "ok")
        and (.[$rail].balance_usd | type == "number")
        and (.[$rail].balance_usd >= 0)
    ' >/dev/null 2>&1
    return
  fi
  printf '%s' "$PROBES" | jq -e --arg rail "$rail" --arg threshold "$THRESH" '
    ($threshold | tonumber?) as $limit
    | type == "object"
      and ($limit != null)
      and (.[$rail] | type == "object")
      and (.[$rail].state == "ok")
      and (.[$rail].remaining_pct | type == "number")
      and (.[$rail].remaining_pct >= 0)
      and (.[$rail].remaining_pct <= 100)
      and (.[$rail].remaining_pct > $limit)
  ' >/dev/null 2>&1
}

# --- walk the ladder ---------------------------------------------------------
for role in $LADDER; do
  kind="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].kind // "none"' "$PROFILE")"
  [ "$kind" = "none" ] && continue
  case "$kind" in
    native|codex_companion|wrapper|openrouter_exec) ;;
    *) echo "cascade-dispatch: unknown rail kind '$kind'" >&2; exit 2;;
  esac
  prail="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].probe // "none"' "$PROFILE")"
  rail_has_headroom "$prail" || continue
  if [ "$prail" = "openrouter" ] && ! openrouter_allowed; then
    EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
    continue
  fi
  models="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].models[]?' "$PROFILE")"
  for model in $models; do
    model_origin="$(printf '%s' "$model" | tr '[:upper:]' '[:lower:]')"
    case "$kind:$model_origin" in
      wrapper:anthropic/*|openrouter_exec:anthropic/*)
        echo "cascade-dispatch: native-vendor-origin invariant rejected OpenRouter model '$model'" >&2
        exit 2
        ;;
    esac
    q="$(jq -r --arg m "$model" '.quality_rank[$m] // 0' "$CASCADE")"
    [ "$q" -lt "$FLOOR" ] 2>/dev/null && continue
    if [ "$DRYRUN" = "1" ]; then
      fallback=false
      fallback_reason="none"
      if [ "$CLASS" != "$prail" ]; then
        fallback=true
        fallback_reason="${CLASS}-unavailable-or-below-floor"
      fi
      jq -n --arg c "$CLASS" --arg h "$HOST" --arg role "$role" --arg k "$kind" \
            --arg m "$model" --arg q "$q" --arg pr "$prail" \
            --arg requested_model "$REQUESTED_MODEL" \
            --arg probe_source "$PROBE_SOURCE" \
            --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
            '{class:$c,host:$h,role:$role,kind:$k,model:$m,quality:($q|tonumber),probe_rail:$pr,
              probe_source:$probe_source,
              requestedProvider:$c,requestedModel:$requested_model,
              attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
              fallback:$fallback,fallbackReason:$fallback_reason,native_vendor_origin_invariant:"passed"}'
      exit 0
    fi
    # Traversal intent per rung kind: codex_companion is single-attempt per role
    # -> `break` to the next ROLE on any failure; native emits a directive and
    # `exit 64`s on the first qualifying model (the orchestrator owns the in-process
    # model descent, e.g. opus->sonnet); wrapper roles iterate their model list
    # -> `continue` to the next MODEL on a per-model error.
    case "$kind" in
      native)
        fallback=false
        fallback_reason="none"
        if [ "$CLASS" != "$prail" ]; then
          fallback=true
          fallback_reason="${CLASS}-unavailable-or-below-floor"
        fi
        jq -n --arg m "$model" --arg role "$role" --arg pr "$prail" \
              --arg requested_provider "$CLASS" --arg requested_model "$REQUESTED_MODEL" \
              --arg probe_source "$PROBE_SOURCE" \
              --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
              '{dispatch:"native",model:$m,role:$role,probe_rail:$pr,
                probe_source:$probe_source,
                requestedProvider:$requested_provider,requestedModel:$requested_model,
                attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
                fallback:$fallback,fallbackReason:$fallback_reason,nativeVendorOriginInvariant:"passed"}'
        exit 64;;
      codex_companion)
        out="$(dispatch_codex)"; rc=$?
        [ $rc -eq 127 ] && break                       # Codex absent -> next role
        if printf '%s' "$out" | grep -qiE 'usage limit|rate.?limit|quota'; then
          checkpoint; break                            # CAP -> handoff, next role
        fi
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        break;;                                        # other Codex failure -> next OpenRouter role
      wrapper)
        dispatch_wrapper "$model"; rc=$?
        [ $rc -eq 0 ] && exit 0
        if [ $rc -eq 77 ]; then
          OPENROUTER_GATE_STATE="denied"
          EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
          break
        fi
        [ $rc -eq 2 ] && exit 2
        continue;;                                     # wrapper error -> next model
      openrouter_exec)
        OPENROUTER_ATTEMPT_INDEX=$((OPENROUTER_ATTEMPT_INDEX + 1))
        out="$(dispatch_openrouter_exec "$model" "$OPENROUTER_ATTEMPT_INDEX")"; rc=$?
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        if [ $rc -eq 77 ]; then
          OPENROUTER_GATE_STATE="denied"
          EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
          break                                    # skip every later OpenRouter role
        fi
        [ $rc -eq 2 ] && exit 2
        continue;;
      *)
        echo "cascade-dispatch: unknown rail kind '$kind'" >&2
        exit 2;;
    esac
  done
done

echo "cascade-dispatch: ladder exhausted for class '$CLASS' on host '$HOST' (floor $FLOOR)" >&2
exit 76
