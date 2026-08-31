#!/usr/bin/env bash
# ui-review-readiness.sh -- dm-review UI-lane prerequisite and cleanup helper.
#
# Current consumer: dm-review selected UI lanes. It prevents doomed model
# dispatch when the repository's rendered app or the host's local interactive
# browser is unavailable. It replaces per-reviewer localhost scanning and
# unowned start/stop guesses; it is not an orchestration layer or browser broker.
#
# Usage:
#   ui-review-readiness.sh prepare --repository-root ROOT --state-file FILE
#     [--target-url URL --target-source explicit|t3-preview]
#     [--visual-required true|false]
#   ui-review-readiness.sh confirm-browser --repository-root ROOT \
#     --state-file FILE --browser-evidence-file FILE
#   ui-review-readiness.sh settle --repository-root ROOT --state-file FILE \
#     --analysis-result-file FILE
#   ui-review-readiness.sh cleanup --repository-root ROOT --state-file FILE
set -uo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
umask 077

ACTION="${1:-}"
[ "$#" -gt 0 ] && shift
REPOSITORY_ROOT=""
STATE_FILE=""
BROWSER_EVIDENCE_FILE=""
ANALYSIS_RESULT_FILE=""
TARGET_URL_INPUT=""
TARGET_SOURCE_INPUT=""
VISUAL_REQUIRED=false

usage() {
  printf '%s\n' 'ui-review-readiness: invalid invocation' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repository-root) [ "$#" -ge 2 ] || usage; REPOSITORY_ROOT="$2"; shift 2 ;;
    --state-file) [ "$#" -ge 2 ] || usage; STATE_FILE="$2"; shift 2 ;;
    --browser-evidence-file) [ "$#" -ge 2 ] || usage; BROWSER_EVIDENCE_FILE="$2"; shift 2 ;;
    --analysis-result-file|--participant-result-file) [ "$#" -ge 2 ] || usage; ANALYSIS_RESULT_FILE="$2"; shift 2 ;;
    --target-url) [ "$#" -ge 2 ] || usage; TARGET_URL_INPUT="$2"; shift 2 ;;
    --target-source) [ "$#" -ge 2 ] || usage; TARGET_SOURCE_INPUT="$2"; shift 2 ;;
    --visual-required) [ "$#" -ge 2 ] || usage; VISUAL_REQUIRED="$2"; shift 2 ;;
    *) usage ;;
  esac
done

case "$ACTION" in prepare|confirm-browser|settle|cleanup) ;; *) usage ;; esac
command -v jq >/dev/null 2>&1 || { printf '%s\n' 'ui-review-readiness: unavailable (missing runtime dependency)' >&2; exit 76; }
[ -n "$REPOSITORY_ROOT" ] && [ -d "$REPOSITORY_ROOT" ] && [ ! -L "$REPOSITORY_ROOT" ] || usage
REPOSITORY_ROOT="$(cd "$REPOSITORY_ROOT" && pwd -P)" || usage
git -C "$REPOSITORY_ROOT" rev-parse --show-toplevel >/dev/null 2>&1 || usage
[ -n "$STATE_FILE" ] && [ -d "$(dirname "$STATE_FILE")" ] || usage
case "$VISUAL_REQUIRED" in true|false) ;; *) usage ;; esac
[ -z "$TARGET_URL_INPUT" ] || [ "$ACTION" = prepare ] || usage
[ -z "$TARGET_SOURCE_INPUT" ] || [ "$ACTION" = prepare ] || usage

emit_closed() {
  local reason="$1" next_action="$2"
  jq -cn --arg reason "$reason" --arg next_action "$next_action" \
    '{state:"closed",dispatchAllowed:false,reason:$reason,nextAction:$next_action,
      reviewDisposition:"REVIEW INCOMPLETE"}'
}

emit_rendered_gap() {
  local reason="$1" next_action="$2" required="$VISUAL_REQUIRED"
  if [ -f "$STATE_FILE" ] && [ ! -L "$STATE_FILE" ]; then
    required="$(jq -r '.visualRequired // false' "$STATE_FILE" 2>/dev/null)"
  fi
  if [ "$required" = true ]; then
    emit_closed "$reason" "$next_action"
    exit 76
  fi
  jq -cn --arg reason "$reason" \
    '{state:"not_available",dispatchAllowed:false,reason:$reason,
      coverageDisposition:"NOT RUN",reviewDisposition:"completed",createdResources:0,
      nextAction:"none; restore rendered readiness only when browser coverage is needed"}'
  exit 0
}

valid_selected_target_url() {
  printf '%s' "$1" | jq -eR '
    test("^https?://[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*(:[0-9]{1,5})?([/?#][^[:space:]]*)?$")
  ' >/dev/null 2>&1
}

load_argv() {
  local source="$1" query="$2" arg
  UI_ARGV=()
  while IFS= read -r arg; do UI_ARGV+=("$arg"); done < <(jq -r "$query[]" "$source")
  [ "${#UI_ARGV[@]}" -gt 0 ] || return 1
}

validate_repo_executable() {
  local relative="$1" physical
  case "$relative" in ./*) ;; *) return 1 ;; esac
  case "$relative" in *'/../'*|../*|*/..|*'\'*|*$'\n'*|*$'\r'*) return 1 ;; esac
  [ -f "$REPOSITORY_ROOT/${relative#./}" ] && [ -x "$REPOSITORY_ROOT/${relative#./}" ] &&
    [ ! -L "$REPOSITORY_ROOT/${relative#./}" ] || return 1
  physical="$(cd "$(dirname "$REPOSITORY_ROOT/${relative#./}")" && pwd -P)/$(basename "$relative")"
  case "$physical" in "$REPOSITORY_ROOT"/*) ;; *) return 1 ;; esac
  git -C "$REPOSITORY_ROOT" ls-files --error-unmatch -- "${relative#./}" >/dev/null 2>&1
}

run_bounded_argv() {
  local limit="$1" output pid waited=0 rc
  shift
  output="$(mktemp "${TMPDIR:-/tmp}/dm-review-ui-command.XXXXXX")" || return 1
  (cd "$REPOSITORY_ROOT" && "$@" > "$output" 2>&1) &
  pid=$!
  while [ "$waited" -lt "$limit" ]; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null || true
    sleep 1
    kill -KILL "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    rm -f "$output"
    return 124
  fi
  wait "$pid" 2>/dev/null; rc=$?
  rm -f "$output"
  return "$rc"
}

validate_declaration() {
  local declaration="$1"
  [ -f "$declaration" ] && [ ! -L "$declaration" ] || return 1
  jq -e '
    type == "object" and
    (keys | sort) == (["readiness","schemaVersion","start","targetUrl"] | sort) and
    .schemaVersion == 1 and
    (.targetUrl | type) == "string" and
    (.targetUrl | test("^https?://(localhost|127\\.0\\.0\\.1|[a-z0-9.-]+\\.(test|site)|[a-z0-9.-]+\\.ddev\\.site)(:[0-9]{1,5})?(/[^[:space:]]*)?$")) and
    (.readiness | type) == "object" and
    (.readiness | keys | sort) == (["argv","attempts","timeoutSeconds"] | sort) and
    (.readiness.argv | type) == "array" and (.readiness.argv | length) > 0 and
    all(.readiness.argv[]; type == "string" and length > 0 and length <= 4096) and
    (.readiness.attempts | type) == "number" and (.readiness.attempts | floor) == .readiness.attempts and .readiness.attempts >= 1 and .readiness.attempts <= 30 and
    (.readiness.timeoutSeconds | type) == "number" and (.readiness.timeoutSeconds | floor) == .readiness.timeoutSeconds and .readiness.timeoutSeconds >= 1 and .readiness.timeoutSeconds <= 60 and
    ((.start == null) or (
      (.start | type) == "object" and
      (.start | keys | sort) == (["argv","cleanupArgv","resourceKind","timeoutSeconds"] | sort) and
      (.start.resourceKind == "process" or .start.resourceKind == "compose") and
      (.start.argv | type) == "array" and (.start.argv | length) > 0 and
      (.start.cleanupArgv | type) == "array" and (.start.cleanupArgv | length) > 0 and
      all(.start.argv[], .start.cleanupArgv[]; type == "string" and length > 0 and length <= 4096) and
      (.start.timeoutSeconds | type) == "number" and (.start.timeoutSeconds | floor) == .start.timeoutSeconds and .start.timeoutSeconds >= 1 and .start.timeoutSeconds <= 300
    ))
  ' "$declaration" >/dev/null 2>&1 &&
    git -C "$REPOSITORY_ROOT" ls-files --error-unmatch -- .dm/ui-review.json >/dev/null 2>&1
}

write_state() {
  local target_url="$1" stage="$2" dispatch_allowed="$3" created="$4" cleanup_pending="$5"
  local readiness_argv="$6" readiness_attempts="$7" readiness_timeout="$8"
  local cleanup_argv="$9" cleanup_timeout="${10}" target_source="${11:-declaration}" visual_required="${12:-false}" tmp
  tmp="$(mktemp "$(dirname "$STATE_FILE")/.ui-review-state.XXXXXX")" || return 1
  jq -cn --arg target_url "$target_url" --arg stage "$stage" \
    --argjson dispatch_allowed "$dispatch_allowed" --argjson created "$created" \
    --argjson cleanup_pending "$cleanup_pending" --argjson readiness_argv "$readiness_argv" \
    --argjson readiness_attempts "$readiness_attempts" --argjson readiness_timeout "$readiness_timeout" \
    --argjson cleanup_argv "$cleanup_argv" --argjson cleanup_timeout "$cleanup_timeout" \
    --arg target_source "$target_source" --argjson visual_required "$visual_required" \
    '{schemaVersion:1,targetUrl:$target_url,stage:$stage,dispatchAllowed:$dispatch_allowed,
      targetSource:$target_source,visualRequired:$visual_required,
      createdByReview:$created,cleanupPending:$cleanup_pending,
      readinessArgv:$readiness_argv,readinessAttempts:$readiness_attempts,
      readinessTimeoutSeconds:$readiness_timeout,cleanupArgv:$cleanup_argv,
      cleanupTimeoutSeconds:$cleanup_timeout}' > "$tmp" || { rm -f "$tmp"; return 1; }
  mv "$tmp" "$STATE_FILE"
}

validate_state() {
  [ -f "$STATE_FILE" ] && [ ! -L "$STATE_FILE" ] || return 1
  jq -e '
    type == "object" and
    (keys | sort) == (["cleanupArgv","cleanupPending","cleanupTimeoutSeconds","createdByReview","dispatchAllowed","readinessArgv","readinessAttempts","readinessTimeoutSeconds","schemaVersion","stage","targetSource","targetUrl","visualRequired"] | sort) and
    .schemaVersion == 1 and (.targetUrl | type) == "string" and
    (.targetSource == "explicit" or .targetSource == "t3-preview" or .targetSource == "declaration") and
    (.visualRequired | type) == "boolean" and
    (.stage == "app_ready" or .stage == "ready" or .stage == "closed" or .stage == "settled") and
    (.dispatchAllowed | type) == "boolean" and (.createdByReview | type) == "boolean" and
    (.cleanupPending | type) == "boolean" and
    (.readinessArgv | type) == "array" and
    (if .targetSource == "declaration" then (.readinessArgv | length) > 0 else (.readinessArgv | length) == 0 end) and
    all(.readinessArgv[]; type == "string" and length > 0 and length <= 4096) and
    (.readinessAttempts | type) == "number" and (.readinessAttempts | floor) == .readinessAttempts and .readinessAttempts >= 1 and .readinessAttempts <= 30 and
    (.readinessTimeoutSeconds | type) == "number" and (.readinessTimeoutSeconds | floor) == .readinessTimeoutSeconds and .readinessTimeoutSeconds >= 1 and .readinessTimeoutSeconds <= 60 and
    (.cleanupArgv | type) == "array" and all(.cleanupArgv[]; type == "string" and length > 0 and length <= 4096) and
    (.cleanupTimeoutSeconds | type) == "number" and (.cleanupTimeoutSeconds | floor) == .cleanupTimeoutSeconds and .cleanupTimeoutSeconds >= 0 and .cleanupTimeoutSeconds <= 300 and
    (if .createdByReview then (.cleanupArgv | length) > 0 and .cleanupTimeoutSeconds >= 1 else true end)
  ' "$STATE_FILE" >/dev/null 2>&1
}

update_state() {
  local stage="$1" dispatch_allowed="$2" cleanup_pending="${3:-}" tmp
  tmp="$(mktemp "$(dirname "$STATE_FILE")/.ui-review-state.XXXXXX")" || return 1
  if [ -n "$cleanup_pending" ]; then
    jq --arg stage "$stage" --argjson dispatch "$dispatch_allowed" --argjson pending "$cleanup_pending" \
      '.stage=$stage | .dispatchAllowed=$dispatch | .cleanupPending=$pending' "$STATE_FILE" > "$tmp" || { rm -f "$tmp"; return 1; }
  else
    jq --arg stage "$stage" --argjson dispatch "$dispatch_allowed" \
      '.stage=$stage | .dispatchAllowed=$dispatch' "$STATE_FILE" > "$tmp" || { rm -f "$tmp"; return 1; }
  fi
  mv "$tmp" "$STATE_FILE"
}

cleanup_owned() {
  local created pending timeout_seconds rc=0
  CLEANUP_REMOVED=0
  validate_state || return 1
  created="$(jq -r '.createdByReview // false' "$STATE_FILE" 2>/dev/null)"
  pending="$(jq -r '.cleanupPending // false' "$STATE_FILE" 2>/dev/null)"
  [ "$created" = true ] && [ "$pending" = true ] || return 0
  load_argv "$STATE_FILE" '.cleanupArgv' || return 1
  validate_repo_executable "${UI_ARGV[0]}" || return 1
  timeout_seconds="$(jq -r '.cleanupTimeoutSeconds' "$STATE_FILE")"
  run_bounded_argv "$timeout_seconds" "${UI_ARGV[@]}" || rc=$?
  [ "$rc" -eq 0 ] || return "$rc"
  update_state "$(jq -r '.stage' "$STATE_FILE")" "$(jq -r '.dispatchAllowed' "$STATE_FILE")" false || return 1
  CLEANUP_REMOVED=1
}

if [ "$ACTION" = cleanup ]; then
  if ! validate_state; then
    emit_closed resource_cleanup_failed 'inspect the exact UI review state and run only its recorded cleanup'
    exit 76
  fi
  if cleanup_owned; then
    created="$(jq -r '.createdByReview // false' "$STATE_FILE" 2>/dev/null)"
    update_state settled false false || exit 76
    jq -cn --argjson created "$created" --argjson removed "$CLEANUP_REMOVED" \
      '{state:(if $removed == 1 then "cleaned" else "already_clean" end),
        removedCount:$removed,preexistingUntouched:($created | not)}'
    exit 0
  fi
  emit_closed resource_cleanup_failed 'run the registered UI cleanup command and inspect only the recorded review resource'
  exit 76
fi

if [ "$ACTION" = settle ]; then
  validate_state &&
    jq -e '.stage == "ready" and .dispatchAllowed == true' "$STATE_FILE" >/dev/null 2>&1 || usage
  [ -f "$ANALYSIS_RESULT_FILE" ] && [ ! -L "$ANALYSIS_RESULT_FILE" ] || usage
  analysis_valid=false
  if jq -e '
    type == "object" and
    (keys | sort) == (["evidenceSource","lanes","transportStub"] | sort) and
    .evidenceSource == "live" and .transportStub == false and
    (.lanes |
      type == "array" and length > 0 and length <= 3 and
      length == (map(.lane) | unique | length) and all(.[];
        type == "object" and
        (keys | sort) == (["capabilities","disposition","lane","role"] | sort) and
        (.lane == "visual-browser-tester" or .lane == "ux-quality-reviewer" or .lane == "ui-standards-reviewer") and
        .role == "review-deep" and
        (.capabilities | type) == "array" and (.capabilities | index("browser") | not) and
        (.disposition == "completed" or .disposition == "unavailable")))
  ' "$ANALYSIS_RESULT_FILE" >/dev/null 2>&1; then analysis_valid=true; fi
  # Consume the ready state before cleanup so a repeated settle can never
  # complete against stale browser evidence. Explicit cleanup remains valid
  # if the registered cleanup command subsequently fails.
  update_state settled false || exit 76
  cleanup_rc=0
  cleanup_owned || cleanup_rc=$?
  if [ "$cleanup_rc" -ne 0 ]; then
    emit_closed resource_cleanup_failed 'run the registered UI cleanup command and inspect only the recorded review resource'
    exit 76
  fi
  if [ "$analysis_valid" != true ] || ! jq -e 'all(.lanes[]; .disposition == "completed")' "$ANALYSIS_RESULT_FILE" >/dev/null 2>&1; then
    emit_closed model_participant_unavailable 'restore the unavailable provider-neutral UI analysis participant and reuse the same browser packet'
    exit 76
  fi
  jq -cn '{state:"completed",dispatchAllowed:false,reason:"available",
    reviewDisposition:"completed",cleanup:"complete"}'
  exit 0
fi

DECLARATION="$REPOSITORY_ROOT/.dm/ui-review.json"
close_registered_state() {
  local reason="$1" next_action="$2" cleanup_rc=0
  trap - EXIT HUP INT TERM
  cleanup_owned || cleanup_rc=$?
  if [ "$cleanup_rc" -ne 0 ]; then
    emit_closed resource_cleanup_failed 'run the registered UI cleanup command and inspect only the recorded review resource'
    exit 76
  fi
  update_state closed false false || exit 76
  case "$reason" in
    visual_target_unavailable|dev_server_unavailable|browser_transport_unavailable)
      emit_rendered_gap "$reason" "$next_action"
      ;;
    *) emit_closed "$reason" "$next_action"; exit 76 ;;
  esac
}

cleanup_on_unexpected_exit() {
  local action_rc=$?
  trap - EXIT HUP INT TERM
  cleanup_owned >/dev/null 2>&1 || true
  update_state closed false false >/dev/null 2>&1 || true
  exit "$action_rc"
}

if [ "$ACTION" = prepare ]; then
  if [ -n "$TARGET_URL_INPUT" ]; then
    case "$TARGET_SOURCE_INPUT" in explicit|t3-preview) ;; *) usage ;; esac
    valid_selected_target_url "$TARGET_URL_INPUT" || usage
    [ ! -e "$STATE_FILE" ] || usage
    write_state "$TARGET_URL_INPUT" app_ready false false false '[]' 1 1 '[]' 0 \
      "$TARGET_SOURCE_INPUT" "$VISUAL_REQUIRED" || exit 76
    jq -cn --arg target_url "$TARGET_URL_INPUT" --arg source "$TARGET_SOURCE_INPUT" \
      '{state:"app_ready",dispatchAllowed:false,reason:"browser_evidence_required",
        targetUrl:$target_url,targetSource:$source,createdResources:0,
        nextAction:"navigate the invocation-selected target with the host local browser, then run confirm-browser"}'
    exit 0
  fi
  if ! validate_declaration "$DECLARATION"; then
    if [ -e "$DECLARATION" ]; then
      emit_rendered_gap dev_server_unavailable 'repair the optional tracked .dm/ui-review.json declaration or supply an explicit target'
    fi
    if [ "$VISUAL_REQUIRED" = true ]; then
      emit_rendered_gap visual_target_unavailable 'supply an explicit URL, attach an automation-capable T3 preview, or add the optional tracked declaration'
    fi
    jq -cn '{state:"not_available",dispatchAllowed:false,reason:"visual_target_unavailable",
      coverageDisposition:"NOT RUN",reviewDisposition:"completed",createdResources:0,
      nextAction:"none; configure a visual target only when rendered coverage is needed"}'
    exit 0
  fi
  TARGET_URL="$(jq -r '.targetUrl' "$DECLARATION")"
  load_argv "$DECLARATION" '.readiness.argv' || usage
  validate_repo_executable "${UI_ARGV[0]}" || {
    emit_rendered_gap dev_server_unavailable 'repair the tracked repository-owned readiness command and rerun'
  }
  READINESS_ARGV=("${UI_ARGV[@]}")
  READINESS_ARGV_JSON="$(jq -c '.readiness.argv' "$DECLARATION")"
  READINESS_TIMEOUT="$(jq -r '.readiness.timeoutSeconds' "$DECLARATION")"
  READINESS_ATTEMPTS="$(jq -r '.readiness.attempts' "$DECLARATION")"
  CREATED=false

  if [ -e "$STATE_FILE" ]; then
    validate_state &&
      jq -e --arg target "$TARGET_URL" '.stage == "app_ready" and .dispatchAllowed == false and .targetUrl == $target' "$STATE_FILE" >/dev/null 2>&1 || usage
    if ! run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then
      close_registered_state dev_server_unavailable 'inspect the registered application readiness command and rerun'
    fi
    CREATED="$(jq -r '.createdByReview' "$STATE_FILE")"
  elif run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then
    write_state "$TARGET_URL" app_ready false false false "$READINESS_ARGV_JSON" \
      "$READINESS_ATTEMPTS" "$READINESS_TIMEOUT" '[]' 0 declaration "$VISUAL_REQUIRED" || exit 76
  else
    if [ "$(jq -r '.start == null' "$DECLARATION")" = true ]; then
      emit_rendered_gap dev_server_unavailable 'run the repository-declared application consumer and rerun'
    fi
    if [ "$(jq -r '.start.resourceKind' "$DECLARATION")" = compose ]; then
      emit_rendered_gap dev_server_unavailable 'start the exact declared Compose consumer through the dm-review Docker creation contract, then rerun readiness'
    fi
    load_argv "$DECLARATION" '.start.cleanupArgv' || usage
    validate_repo_executable "${UI_ARGV[0]}" || {
      emit_rendered_gap dev_server_unavailable 'repair the tracked repository-owned cleanup command and rerun'
    }
    CLEANUP_ARGV_JSON="$(jq -c '.start.cleanupArgv' "$DECLARATION")"
    START_TIMEOUT="$(jq -r '.start.timeoutSeconds' "$DECLARATION")"
    load_argv "$DECLARATION" '.start.argv' || usage
    validate_repo_executable "${UI_ARGV[0]}" || {
      emit_rendered_gap dev_server_unavailable 'repair the tracked repository-owned start command and rerun'
    }
    CREATED=true
    write_state "$TARGET_URL" app_ready false true true "$READINESS_ARGV_JSON" \
      "$READINESS_ATTEMPTS" "$READINESS_TIMEOUT" "$CLEANUP_ARGV_JSON" "$START_TIMEOUT" declaration "$VISUAL_REQUIRED" || exit 76
    trap cleanup_on_unexpected_exit EXIT
    trap 'exit 130' HUP INT TERM
    if ! run_bounded_argv "$START_TIMEOUT" "${UI_ARGV[@]}"; then
      close_registered_state dev_server_unavailable 'run the repository-declared application consumer and rerun'
    fi
    ready=false
    attempt=0
    while [ "$attempt" -lt "$READINESS_ATTEMPTS" ]; do
      if run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then ready=true; break; fi
      attempt=$((attempt + 1))
      [ "$attempt" -ge "$READINESS_ATTEMPTS" ] || sleep 1
    done
    if [ "$ready" != true ]; then
      close_registered_state dev_server_unavailable 'inspect the declared application start/readiness commands and rerun'
    fi
    trap - EXIT HUP INT TERM
  fi
  jq -cn --arg target_url "$TARGET_URL" --argjson created "$CREATED" \
    '{state:"app_ready",dispatchAllowed:false,reason:"browser_evidence_required",
      targetUrl:$target_url,createdResources:(if $created then 1 else 0 end),
      nextAction:"navigate the declared target with the host local browser, then run confirm-browser"}'
  exit 0
fi

# confirm-browser consumes the exact readiness snapshot registered by prepare.
validate_state &&
  jq -e '.stage == "app_ready" and .dispatchAllowed == false' "$STATE_FILE" >/dev/null 2>&1 || usage
TARGET_URL="$(jq -r '.targetUrl' "$STATE_FILE")"
READINESS_TIMEOUT="$(jq -r '.readinessTimeoutSeconds' "$STATE_FILE")"
if [ "$(jq -r '.createdByReview and .cleanupPending' "$STATE_FILE")" = true ]; then
  trap cleanup_on_unexpected_exit EXIT
  trap 'exit 130' HUP INT TERM
fi
if [ "$(jq -r '.targetSource' "$STATE_FILE")" = declaration ]; then
  load_argv "$STATE_FILE" '.readinessArgv' || usage
  validate_repo_executable "${UI_ARGV[0]}" || close_registered_state dev_server_unavailable 'repair the registered readiness command and rerun'
  READINESS_ARGV=("${UI_ARGV[@]}")
  if ! run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then
    close_registered_state dev_server_unavailable 'inspect the registered application readiness command and rerun'
  fi
fi
if [ ! -f "$BROWSER_EVIDENCE_FILE" ] || [ -L "$BROWSER_EVIDENCE_FILE" ] ||
   ! jq -e --arg target_url "$TARGET_URL" '
     type == "object" and
     (keys | sort) == (["evidenceRef","localNavigation","schemaVersion","status","targetUrl","transportClass"] | sort) and
     .schemaVersion == 1 and .status == "ready" and
     .transportClass == "local-interactive" and .localNavigation == "confirmed" and
     .targetUrl == $target_url and
     (.evidenceRef | type) == "string" and (.evidenceRef | test("^[a-z0-9][a-z0-9._/-]{0,255}$"))
   ' "$BROWSER_EVIDENCE_FILE" >/dev/null 2>&1; then
  close_registered_state browser_transport_unavailable 'attach a local interactive browser, navigate the selected target, and rerun'
fi
update_state ready true || exit 76
trap - EXIT HUP INT TERM
CREATED="$(jq -r '.createdByReview' "$STATE_FILE")"
jq -cn --arg target_url "$TARGET_URL" --argjson created "$CREATED" \
  '{state:"ready",dispatchAllowed:true,reason:"available",targetUrl:$target_url,
    browserTransport:"local-interactive",browserEvidence:"bounded-host-evidence",
    createdResources:(if $created then 1 else 0 end),
    nextAction:"dispatch provider-neutral UI analysis without browser capability"}'
