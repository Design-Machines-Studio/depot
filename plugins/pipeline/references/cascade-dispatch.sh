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
#       [--exhausted-rail <codex|openrouter>]
#   (--kind is an alternative to --class; mapped via cascade.class_from_kind)
#
# Exit codes:
#   0   a wrapper/codex_companion/openrouter_exec rung executed -- output on stdout
#   64  chosen rung is NATIVE -- directive JSON on stdout; the HOST orchestrator
#       runs that model in-process (Claude subagent / Codex). The only host-specific action.
#   75  ladder exhausted -- no rung had headroom above the floor
#   77  disclosure declined -- use the trusted native fallback
#   78  exact payload user approval required -- surface digest and retry unchanged
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
# OpenRouter assets are selected once from one coherent installed bundle.
OPENROUTER_BUNDLE_STATE="unchecked"
OPENROUTER_BUNDLE_ROOT=""
OPENROUTER_BUNDLE_VERSION=""
OPENROUTER_BUNDLE_CLASS=""
OPENROUTER_BUNDLE_REASON=""

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
[ -z "$CLASS" ] || [ -z "$PROMPT" ] && { echo "usage: $0 --class <codex|openrouter>|--kind <k> --prompt <p|-> [opts]" >&2; exit 2; }
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
  [ "$OPENROUTER_BUNDLE_STATE" = "ready" ] && return 0
  [ "$OPENROUTER_BUNDLE_STATE" = "denied" ] && return 1
  local kernel="${WORKFLOW_KERNEL:-}" active="" result="" selected=""
  [ -n "$kernel" ] || kernel="$DIR/../../workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
  [ -x "$kernel" ] || { OPENROUTER_BUNDLE_STATE="denied"; return 1; }
  case "$HOST" in
    claude-code) active="claude" ;;
    codex) active="codex" ;;
  esac
  if [ -n "$active" ]; then
    result="$("$kernel" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.7.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
      --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
      --active-host "$active" 2>/dev/null)" || {
        OPENROUTER_BUNDLE_STATE="denied"; return 1;
      }
  else
    result="$("$kernel" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.7.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
      --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
      2>/dev/null)" || {
        OPENROUTER_BUNDLE_STATE="denied"; return 1;
      }
  fi
  selected="$(printf '%s' "$result" | jq -r '.selected_root // empty')"
  case "$selected" in
    "~/"*) OPENROUTER_BUNDLE_ROOT="$HOME/${selected#\~/}" ;;
    *) OPENROUTER_BUNDLE_STATE="denied"; return 1 ;;
  esac
  OPENROUTER_BUNDLE_VERSION="$(printf '%s' "$result" | jq -r '.version // empty')"
  OPENROUTER_BUNDLE_CLASS="$(printf '%s' "$result" | jq -r '.cache_class // empty')"
  OPENROUTER_BUNDLE_REASON="$(printf '%s' "$result" | jq -r '.reason // empty')"
  [ -x "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh" ] &&
    [ -x "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh" ] &&
    [ -x "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/payload-authorization.sh" ] &&
    [ -r "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json" ] || {
      OPENROUTER_BUNDLE_STATE="denied"; return 1;
    }
  OPENROUTER_BUNDLE_STATE="ready"
  return 0
}
dispatch_wrapper() {
  local model="$1" system task_tmp_root system_file prompt_file manifest_file
  local policy boundary authorization payload_sha256 rc
  resolve_openrouter_bundle || return 1
  system="${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}"
  task_tmp_root="${TMPDIR:-/tmp}"
  system_file="$(mktemp "$task_tmp_root/cascade-wrapper.system.XXXXXX")" || return 1
  prompt_file="$(mktemp "$task_tmp_root/cascade-wrapper.prompt.XXXXXX")" || {
    rm -f "$system_file"; return 1;
  }
  manifest_file="$(mktemp "$task_tmp_root/cascade-wrapper.authorization.XXXXXX")" || {
    rm -f "$system_file" "$prompt_file"; return 1;
  }
  policy="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
  boundary="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
  authorization="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/payload-authorization.sh"
  printf '%s' "$system" > "$system_file"
  printf '%s' "$PROMPT" > "$prompt_file"
  if ! "$boundary" --mode artifact-delegation --policy "$policy" \
      --content-file "$system_file" --content-file "$prompt_file"; then
    rm -f "$system_file" "$prompt_file" "$manifest_file"
    return 77
  fi
  payload_sha256="$("$authorization" snapshot --output "$manifest_file" \
    --content-file "$system_file" --content-file "$prompt_file")" || {
    rm -f "$system_file" "$prompt_file" "$manifest_file"; return 1;
  }
  if [ -z "${OPENROUTER_PAYLOAD_APPROVAL_SHA256:-}" ]; then
    printf '{"status":"approval_required","payloadSha256":"%s","authority":"user"}\n' "$payload_sha256"
    rm -f "$system_file" "$prompt_file" "$manifest_file"
    return 78
  fi
  if ! "$authorization" verify --manifest "$manifest_file" \
      --approved-sha256 "$OPENROUTER_PAYLOAD_APPROVAL_SHA256" \
      --content-file "$system_file" --content-file "$prompt_file" 2>/dev/null; then
    printf '{"status":"approval_required","payloadSha256":"%s","authority":"user","reason":"payload-or-approval-changed"}\n' "$payload_sha256"
    rm -f "$system_file" "$prompt_file" "$manifest_file"
    return 78
  fi
  OPENROUTER_SYSTEM="$(cat "$system_file")" \
    "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh" \
    "$model" - "$TIMEOUT" "" < "$prompt_file"
  rc=$?
  rm -f "$system_file" "$prompt_file" "$manifest_file"
  return "$rc"
}
resolve_openrouter_exec() {
  [ -x "$DIR/openrouter-exec.sh" ] && printf '%s' "$DIR/openrouter-exec.sh"
}
dispatch_openrouter_exec() {
  local runner; runner="$(resolve_openrouter_exec)"
  [ -z "$runner" ] && return 1
  printf '%s' "$PROMPT" | "$runner" --model "$1" --timeout "$TIMEOUT" 2>&1
}

# Gate the prompt once before any OpenRouter execution or wrapper role. A
# missing/unverifiable boundary makes the entire OpenRouter rail unavailable;
# trusted Codex roles may still run.
OPENROUTER_GATE_STATE="unchecked"
openrouter_allowed() {
  [ "$DRYRUN" = "1" ] && return 0
  [ "$OPENROUTER_GATE_STATE" = "safe" ] && return 0
  [ "$OPENROUTER_GATE_STATE" = "denied" ] && return 1
  [ -n "${OPENROUTER_EXEC_ALLOWED_PATHS:-}" ] || {
    OPENROUTER_GATE_STATE="denied"
    return 1
  }
  local policy="" helper="" task_tmp_root prompt_file allowed_file rc
  resolve_openrouter_bundle || {
    OPENROUTER_GATE_STATE="denied"
    return 1
  }
  policy="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
  helper="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
  [ -f "$policy" ] && [ -x "$helper" ] || {
    OPENROUTER_GATE_STATE="denied"
    return 1
  }
  task_tmp_root="${TMPDIR:-/tmp}"
  prompt_file="$(mktemp "$task_tmp_root/cascade-boundary.prompt.XXXXXX")" || return 1
  allowed_file="$(mktemp "$task_tmp_root/cascade-boundary.allowed.XXXXXX")" || {
    rm -f "$prompt_file"
    return 1
  }
  printf '%s' "$PROMPT" > "$prompt_file"
  printf '%s\n' "$OPENROUTER_EXEC_ALLOWED_PATHS" > "$allowed_file"
  if "$helper" --policy "$policy" --changed-files "$allowed_file" --content-file "$prompt_file"; then
    rc=0
  else
    rc=$?
  fi
  rm -f "$prompt_file" "$allowed_file"
  if [ "$rc" -eq 0 ]; then
    OPENROUTER_GATE_STATE="safe"
    return 0
  fi
  OPENROUTER_GATE_STATE="denied"
  return 1
}

probe_json() { [ -n "$PROBE_FILE" ] && cat "$PROBE_FILE" || { [ -x "$PROBE" ] && "$PROBE" || echo '{}'; }; }
PROBES="$(probe_json)"
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
  if [ "$prail" = "openrouter" ] && ! openrouter_allowed; then
    EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
    continue
  fi
  models="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].models[]?' "$PROFILE")"
  for model in $models; do
    model_origin="$(printf '%s' "$model" | tr '[:upper:]' '[:lower:]')"
    case "$kind:$model_origin" in
      wrapper:openai/*|wrapper:anthropic/*|openrouter_exec:openai/*|openrouter_exec:anthropic/*)
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
            --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
            '{class:$c,host:$h,role:$role,kind:$k,model:$m,quality:($q|tonumber),probe_rail:$pr,
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
              --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
              '{dispatch:"native",model:$m,role:$role,probe_rail:$pr,
                requestedProvider:$requested_provider,requestedModel:$requested_model,
                attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
                fallback:$fallback,fallbackReason:$fallback_reason,nativeVendorOriginInvariant:"passed"}'; exit 64;;
      codex_companion)
        out="$(dispatch_codex)"; rc=$?
        [ $rc -eq 127 ] && break                       # Codex absent -> next role
        if printf '%s' "$out" | grep -qiE 'usage limit|rate.?limit|quota'; then
          checkpoint; break                            # CAP -> handoff, next role
        fi
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        break;;                                        # other Codex failure -> next OpenRouter role
      wrapper)
        out="$(dispatch_wrapper "$model")"; rc=$?
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        [ $rc -eq 78 ] && { printf '%s\n' "$out"; exit 78; }
        if [ $rc -eq 77 ]; then
          OPENROUTER_GATE_STATE="denied"
          EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
          break
        fi
        continue;;                                     # wrapper error -> next model
      openrouter_exec)
        out="$(dispatch_openrouter_exec "$model")"; rc=$?
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        [ $rc -eq 78 ] && { printf '%s\n' "$out"; exit 78; }
        if [ $rc -eq 77 ]; then
          OPENROUTER_GATE_STATE="denied"
          EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
          break                                    # skip every later OpenRouter role
        fi
        continue;;
      *)
        echo "cascade-dispatch: unknown rail kind '$kind'" >&2
        exit 2;;
    esac
  done
done

echo "cascade-dispatch: ladder exhausted for class '$CLASS' on host '$HOST' (floor $FLOOR)" >&2
exit 75
