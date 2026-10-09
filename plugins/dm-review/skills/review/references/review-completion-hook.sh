#!/usr/bin/env bash
# Bounded completion backstop for the current dm-review owner.
#
# Purpose: SessionStart supplies this native session's review-owner context.
# Stop gives one continuation when the bound root owner stops in an executing or
# checking phase at a change boundary it has not been continued for. It never
# runs review lanes, never creates or adopts an owner, and its continuation
# marker is never review coverage. The existing producer remains the only
# coverage authority and the workflow pre-PR gate stays mandatory.
# Dependencies: bash, git, jq and review-owner-context.sh from this bundle.
# Usage: review-completion-hook.sh session-start|stop < native-hook-input.json
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONTEXT_HELPER="$HERE/review-owner-context.sh"
REASON='Resume this exact owner, validate current producer coverage and perform only the missing supported review action; never approve the plan/UI/merge gate.'

# Non-blocking diagnostic. It never claims the hook is active.
diagnose() {
  if command -v jq >/dev/null 2>&1; then
    jq -cn --arg message "$1" '{systemMessage:$message}'
  else
    printf '%s\n' '{"systemMessage":"Review completion hook unavailable: jq is required."}'
  fi
  exit 0
}
quiet() { exit 0; }

[ "$#" -eq 1 ] || diagnose 'Review completion hook unavailable: expected one mode argument, session-start or stop.'
case "$1" in
  session-start) MODE=init; EVENT=SessionStart ;;
  stop) MODE=stop; EVENT=Stop ;;
  *) diagnose 'Review completion hook unavailable: unsupported mode; expected session-start or stop.' ;;
esac
for tool in jq git; do
  command -v "$tool" >/dev/null 2>&1 || diagnose "Review completion hook unavailable: $tool is required."
done
[ -f "$CONTEXT_HELPER" ] && [ -x "$CONTEXT_HELPER" ] ||
  diagnose 'Review completion hook unavailable: review-owner-context.sh is missing from this dm-review bundle.'

NATIVE="$(cat)"
jq -e --arg event "$EVENT" 'type=="object" and .hook_event_name==$event and
  (.session_id|type=="string" and length>0) and (.cwd|type=="string" and startswith("/")) and
  ($event=="SessionStart" or (.stop_hook_active|type=="boolean"))' <<< "$NATIVE" >/dev/null 2>&1 ||
  diagnose "Review completion hook unavailable: malformed or unsupported native $EVENT input."
# Workers never act for the parent session.
jq -e '.agent_id==null and .agent_type==null' <<< "$NATIVE" >/dev/null || quiet

# Only the root of a GitHub checkout can hold a session pointer. Other
# directories and unrelated repositories are silent.
REPO="$(cd "$(jq -r .cwd <<< "$NATIVE")" 2>/dev/null && pwd -P)" || quiet
[ "$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)" = "$REPO" ] || quiet
case "$(git -C "$REPO" remote get-url origin 2>/dev/null)" in
  git@github.com:*|https://github.com/*) ;;
  *) quiet ;;
esac

if [ "$MODE" = init ]; then
  # Initialize an unbound planning pointer or preserve a matching one on resume.
  if OUTPUT="$("$CONTEXT_HELPER" init --repository-root "$REPO" <<< "$NATIVE" 2>&1)"; then
    printf '%s\n' "$OUTPUT"
    exit 0
  fi
  diagnose "Review completion hook unavailable: ${OUTPUT#Not ready: }"
fi

# shellcheck source=review-owner-context.sh
source "$CONTEXT_HELPER"
SESSION="$(jq -r .session_id <<< "$NATIVE")"
REPOSITORY="$( (review_repository "$REPO") 2>/dev/null )" || quiet
# Same derivation as review-owner-context.sh; the fixture test pins it.
KEY="$(printf '%s\0%s\0%s' "$REPOSITORY" "$REPO" "$SESSION" | review_sha256)"
DIRECTORY="$(cd "${TMPDIR:-/tmp}" && pwd -P)/claude-hook-state/review-$KEY"
CONTEXT="$DIRECTORY/review-owner.json"

# Missing context: nothing is bound. The owner reports activation unavailable
# when it cannot bind, and the pre-PR producer gate still runs.
[ -e "$CONTEXT" ] || [ -L "$CONTEXT" ] || quiet
# Foreign, linked or non-private records are never adopted.
( review_private "$DIRECTORY" && review_private "$CONTEXT" ) >/dev/null 2>&1 || quiet
RECORD="$(cat "$CONTEXT")"
jq -e --arg session "$SESSION" --arg repository "$REPOSITORY" \
  '.session_id==$session and .repository==$repository' <<< "$RECORD" >/dev/null 2>&1 || quiet
jq -e '(keys|sort)==(["session_id","repository","workflow","run_id","run_root","state_dir","phase","change_boundary"]|sort) and
  (.phase|IN("planning","awaiting_plan_approval","executing","checking","awaiting_ui","awaiting_merge","blocked","complete"))' \
  <<< "$RECORD" >/dev/null || diagnose 'Not ready: conflicting review-owner context; it was not adopted.'

# Planning, approval, designer/merge waits, blocked and complete are silent.
case "$(jq -r .phase <<< "$RECORD")" in executing|checking) ;; *) quiet ;; esac
jq -e 'all(.workflow,.run_id,.run_root,.state_dir; type=="string") and
  (.change_boundary|type=="string" and test("^sha256:[0-9a-f]{64}$"))' <<< "$RECORD" >/dev/null ||
  diagnose 'Not ready: conflicting review-owner context; it was not adopted.'
OWNER="$(jq -c '{repository,workflow,run_id,run_root,state_dir}' <<< "$RECORD")"
if ! ERROR="$( (review_owner_validate "$OWNER" "$REPO") 2>&1 )"; then
  diagnose "Not ready: bound review owner cannot be validated (${ERROR#Not ready: }); it was not adopted."
fi
# Bind the dedupe key to current owned source, committed or dirty.
BOUNDARY="$( (review_change_boundary "$REPO") 2>/dev/null )" ||
  diagnose 'Not ready: the current change boundary is unavailable.'
RUN_KEY="$(printf '%s\0%s' "$(jq -r .run_id <<< "$RECORD")" "$(jq -r .run_root <<< "$RECORD")" | review_sha256)"
MARKER="$DIRECTORY/continued-$RUN_KEY-${BOUNDARY#sha256:}"

if [ "$(jq -r .stop_hook_active <<< "$NATIVE")" = true ]; then
  # Another hook's continuation never stacks a second one from this hook.
  compgen -G "$DIRECTORY/continued-$RUN_KEY-*" >/dev/null || quiet
  # The one continuation ended while the owner is still unchecked.
  if ERROR="$("$CONTEXT_HELPER" phase --repository-root "$REPO" --context "$CONTEXT" \
      --phase blocked --change-boundary "$BOUNDARY" <<< "$NATIVE" 2>&1 >/dev/null)"; then
    diagnose 'Not ready: the bounded review continuation ended without a passing readiness check. The owner phase is recorded as blocked; resume the owner after resolving the blocker. The pre-PR producer gate still applies.'
  fi
  diagnose "Not ready: the bounded review continuation ended without a passing readiness check, and the blocked phase could not be recorded (${ERROR#Not ready: }). The pre-PR producer gate still applies."
fi

# One continuation per session, repository, run and change boundary.
[ ! -e "$MARKER" ] || quiet
( review_safe_path "$MARKER" ) >/dev/null 2>&1 && ( umask 077; : > "$MARKER" ) 2>/dev/null ||
  diagnose 'Not ready: the continuation marker could not be recorded, so no continuation was requested.'
jq -cn --arg reason "$REASON" '{decision:"block",reason:$reason}'
