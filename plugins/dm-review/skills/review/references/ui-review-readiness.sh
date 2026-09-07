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
#     [--target-source repository-declaration --repository-evidence-file FILE]
#     --applicable-lanes-json JSON
#     [--visual-required true|false]
#     [--workflow-kernel FILE --expected-registry-run-id ID
#      --expected-registry-node-id ID]
#   ui-review-readiness.sh confirm-browser --repository-root ROOT \
#     --state-file FILE --browser-evidence-file FILE \
#     [--expected-resource-ownership pre-existing|review-created-compose]
#   ui-review-readiness.sh settle --repository-root ROOT --state-file FILE \
#     --analysis-result-file FILE \
#     [--expected-resource-ownership pre-existing|review-created-compose]
#   ui-review-readiness.sh cleanup --repository-root ROOT --state-file FILE \
#     [--expected-resource-ownership pre-existing|review-created-compose]
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
REPOSITORY_EVIDENCE_FILE=""
VISUAL_REQUIRED=false
APPLICABLE_LANES_JSON=""
WORKFLOW_KERNEL_INPUT=""
EXPECTED_REGISTRY_RUN_ID=""
EXPECTED_REGISTRY_NODE_ID=""
EXPECTED_RESOURCE_OWNERSHIP=""

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
    --repository-evidence-file) [ "$#" -ge 2 ] || usage; REPOSITORY_EVIDENCE_FILE="$2"; shift 2 ;;
    --visual-required) [ "$#" -ge 2 ] || usage; VISUAL_REQUIRED="$2"; shift 2 ;;
    --applicable-lanes-json) [ "$#" -ge 2 ] || usage; APPLICABLE_LANES_JSON="$2"; shift 2 ;;
    --workflow-kernel) [ "$#" -ge 2 ] || usage; WORKFLOW_KERNEL_INPUT="$2"; shift 2 ;;
    --expected-registry-run-id) [ "$#" -ge 2 ] || usage; EXPECTED_REGISTRY_RUN_ID="$2"; shift 2 ;;
    --expected-registry-node-id) [ "$#" -ge 2 ] || usage; EXPECTED_REGISTRY_NODE_ID="$2"; shift 2 ;;
    --expected-resource-ownership) [ "$#" -ge 2 ] || usage; EXPECTED_RESOURCE_OWNERSHIP="$2"; shift 2 ;;
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
[ -z "$REPOSITORY_EVIDENCE_FILE" ] || [ "$ACTION" = prepare ] || usage
[ -z "$EXPECTED_RESOURCE_OWNERSHIP" ] || [ "$ACTION" != prepare ] || usage
case "$EXPECTED_RESOURCE_OWNERSHIP" in ""|pre-existing|review-created-compose) ;; *) usage ;; esac
if [ -n "$WORKFLOW_KERNEL_INPUT$EXPECTED_REGISTRY_RUN_ID$EXPECTED_REGISTRY_NODE_ID" ]; then
  [ -n "$WORKFLOW_KERNEL_INPUT" ] && [ -n "$EXPECTED_REGISTRY_RUN_ID" ] &&
    [ -n "$EXPECTED_REGISTRY_NODE_ID" ] || usage
  case "$WORKFLOW_KERNEL_INPUT" in /*) ;; *) usage ;; esac
  [ -f "$WORKFLOW_KERNEL_INPUT" ] && [ -x "$WORKFLOW_KERNEL_INPUT" ] &&
    [ ! -L "$WORKFLOW_KERNEL_INPUT" ] || usage
  [ "$(cd "$(dirname "$WORKFLOW_KERNEL_INPUT")" && pwd -P)/$(basename "$WORKFLOW_KERNEL_INPUT")" = "$WORKFLOW_KERNEL_INPUT" ] || usage
  printf '%s' "$EXPECTED_REGISTRY_RUN_ID" | jq -eR 'test("^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")' >/dev/null 2>&1 || usage
  printf '%s' "$EXPECTED_REGISTRY_NODE_ID" | jq -eR 'test("^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")' >/dev/null 2>&1 || usage
fi
if [ "$ACTION" = prepare ]; then
  printf '%s' "$APPLICABLE_LANES_JSON" | jq -e '
    type == "array" and length > 0 and length <= 3 and length == (unique | length) and
    all(.[]; . == "visual-browser-tester" or . == "ux-quality-reviewer" or . == "ui-standards-reviewer")
  ' >/dev/null 2>&1 || usage
else
  [ -z "$APPLICABLE_LANES_JSON" ] || usage
fi

emit_closed() {
  local reason="$1" next_action="$2" compose=false
  if [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ]; then
    compose=true
  elif [ -z "$EXPECTED_RESOURCE_OWNERSHIP" ] && [ -f "$STATE_FILE" ] && [ ! -L "$STATE_FILE" ]; then
    compose="$(jq -r '.targetSource == "repository-declaration" and .repositoryEvidence.resourceOwnership == "review-created-compose"' "$STATE_FILE" 2>/dev/null)"
  fi
  case "$compose" in true|false) ;; *) compose=false ;; esac
  jq -cn --arg reason "$reason" --arg next_action "$next_action" --argjson compose "$compose" \
    '{state:"closed",dispatchAllowed:false,reason:$reason,nextAction:$next_action,
      reviewDisposition:"REVIEW INCOMPLETE"} +
      (if $compose then {cleanup:"registry_cleanup_required",registryCleanupPending:true} else {} end)'
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
  local compose=false
  if [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ]; then
    compose=true
  elif [ -z "$EXPECTED_RESOURCE_OWNERSHIP" ] && [ -f "$STATE_FILE" ] && [ ! -L "$STATE_FILE" ]; then
    compose="$(jq -r '.targetSource == "repository-declaration" and .repositoryEvidence.resourceOwnership == "review-created-compose"' "$STATE_FILE" 2>/dev/null)"
  fi
  case "$compose" in true|false) ;; *) compose=false ;; esac
  jq -cn --arg reason "$reason" --argjson compose "$compose" \
    '{state:"not_available",dispatchAllowed:false,reason:$reason,
      coverageDisposition:"NOT RUN",reviewDisposition:"completed",
      createdResources:(if $compose then 1 else 0 end),
      nextAction:"none; restore rendered readiness only when browser coverage is needed"} +
      (if $compose then {cleanup:"registry_cleanup_required",registryCleanupPending:true,
        nextAction:"run the exact Workflow Kernel Docker cleanup plan referenced by private readiness state"} else {} end)'
  exit 0
}

valid_selected_target_url() {
  printf '%s' "$1" | jq -eR '
    test("^https?://[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*(:[0-9]{1,5})?([/?#][^[:space:]]*)?$")
  ' >/dev/null 2>&1
}

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'
  fi
}

checkout_fingerprint() {
  local snapshot path digest
  snapshot="$(mktemp "${TMPDIR:-/tmp}/dm-review-ui-checkout.XXXXXX")" || return 1
  git -C "$REPOSITORY_ROOT" status --porcelain=v1 -z --untracked-files=all > "$snapshot" || {
    rm -f "$snapshot"; return 1;
  }
  git -C "$REPOSITORY_ROOT" diff --binary --no-ext-diff HEAD -- >> "$snapshot" || {
    rm -f "$snapshot"; return 1;
  }
  while IFS= read -r -d '' path; do
    printf '\0%s\0' "$path" >> "$snapshot"
    if [ -f "$REPOSITORY_ROOT/$path" ] && [ ! -L "$REPOSITORY_ROOT/$path" ]; then
      digest="$(git -C "$REPOSITORY_ROOT" hash-object --no-filters -- "$path")" || {
        rm -f "$snapshot"; return 1;
      }
      printf '%s\0' "$digest" >> "$snapshot"
    elif [ -L "$REPOSITORY_ROOT/$path" ]; then
      printf 'symlink:%s\0' "$(readlink "$REPOSITORY_ROOT/$path")" >> "$snapshot"
    else
      printf 'unsupported\0' >> "$snapshot"
    fi
  done < <(git -C "$REPOSITORY_ROOT" ls-files --others --exclude-standard -z)
  digest="$(hash_file "$snapshot")" || { rm -f "$snapshot"; return 1; }
  rm -f "$snapshot"
  printf '%s\n' "$digest"
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

validate_workflow_kernel_registry() {
  local registry_path="$1" registry_run_id="$2" registry_node_id="$3"
  local result state_dir registry_repository
  [ -n "$WORKFLOW_KERNEL_INPUT" ] &&
    [ "$registry_run_id" = "$EXPECTED_REGISTRY_RUN_ID" ] &&
    [ "$registry_node_id" = "$EXPECTED_REGISTRY_NODE_ID" ] || return 1
  state_dir="$(cd "$(dirname "$registry_path")" && pwd -P)" || return 1
  registry_repository="$(git -C "$state_dir" rev-parse --show-toplevel 2>/dev/null)" || return 1
  registry_repository="$(cd "$registry_repository" && pwd -P)" || return 1
  [ "$registry_repository" = "$REPOSITORY_ROOT" ] || return 1
  result="$(mktemp "${TMPDIR:-/tmp}/dm-review-registry-validation.XXXXXX")" || return 1
  if ! "$WORKFLOW_KERNEL_INPUT" validate-resource-registry \
      --state-dir "$state_dir" \
      --run-id "$EXPECTED_REGISTRY_RUN_ID" \
      --node-id "$EXPECTED_REGISTRY_NODE_ID" >"$result" 2>&1; then
    rm -f "$result"
    return 1
  fi
  jq -se '
    length == 1 and
    (.[0] | type == "object" and
      (keys | sort) == (["active_resource_count","kind","schema_version","valid"] | sort) and
      .schema_version == 1 and .kind == "resource-registry-validation" and
      .valid == true and
      (.active_resource_count | type == "number" and floor == . and . > 0))
  ' "$result" >/dev/null 2>&1
  local status=$?
  rm -f "$result"
  return "$status"
}

validate_compose_registry_state() {
  local registry_ref registry_run_id registry_node_id registry_root registry_path registry_physical
  if [ "$ACTION" = prepare ]; then
    [ "$(jq -r '.targetSource == "repository-declaration" and .repositoryEvidence.resourceOwnership == "review-created-compose"' "$STATE_FILE" 2>/dev/null)" = true ] || return 0
  else
    [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ] || return 0
  fi
  registry_ref="$(jq -r '.repositoryEvidence.resourceRegistryRef' "$STATE_FILE")"
  registry_run_id="$(jq -r '.repositoryEvidence.resourceRegistryRunId' "$STATE_FILE")"
  registry_node_id="$(jq -r '.repositoryEvidence.resourceRegistryNodeId' "$STATE_FILE")"
  registry_root="$(cd "$(dirname "$STATE_FILE")" && pwd -P)" || return 1
  if [ "$registry_ref" = review/resources.jsonl ]; then
    [ "$(basename "$registry_root")" = review ] || return 1
    registry_root="$(cd "$registry_root/.." && pwd -P)" || return 1
  fi
  registry_path="$registry_root/$registry_ref"
  [ -f "$registry_path" ] && [ ! -L "$registry_path" ] || return 1
  registry_physical="$(cd "$(dirname "$registry_path")" && pwd -P)/$(basename "$registry_path")" || return 1
  case "$registry_physical" in "$registry_root"/*) ;; *) return 1 ;; esac
  validate_workflow_kernel_registry "$registry_physical" "$registry_run_id" "$registry_node_id"
}

REPOSITORY_EVIDENCE_REASON=""
validate_repository_evidence() {
  local evidence="$1" current_commit current_state source_path line_end line_count source_physical
  local registry_ref registry_run_id registry_node_id registry_root registry_path registry_physical
  REPOSITORY_EVIDENCE_REASON="repository_evidence_invalid"
  [ -f "$evidence" ] && [ ! -L "$evidence" ] || return 1
  jq -e '
    def credential_text:
      test("(?i)(-----BEGIN ([A-Z0-9]+[[:space:]]+)*PRIVATE KEY( BLOCK)?-----|[\u0027\"]?(authorization|cookie|set-cookie|password|secret|client[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|private[_-]?key|token|bearer|user|proxy[_-]?user)[\u0027\"]?[[:space:]]*:|(bearer|basic)[[:space:]]+|(^|[[:space:]])--?(authorization|cookie|password|secret|client[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|private[_-]?key|token|bearer|user|proxy[_-]?user)[[:space:]]+|(^|[[:space:]])-u([[:space:]]+|=)|(^|[[:space:]])-u[^[:space:]=]+|(authorization|cookie|password|secret|client[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|private[_-]?key|token|bearer|user|proxy[_-]?user)[[:space:]]*=|https?://[^[:space:]/:@]+:[^[:space:]@]+@|[?&](authorization|cookie|password|secret|client[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|private[_-]?key|token|bearer|user|proxy[_-]?user)=)");
    def credential_value_flag:
      test("(?i)^(--?(authorization|cookie|password|secret|client[_-]?secret|api[_-]?key|x[_-]?api[_-]?key|access[_-]?token|private[_-]?key|token|bearer|user|proxy[_-]?user)|-u)$");
    type == "object" and
    (keys | sort) == (["application","attempts","checkoutRoot","checkoutState","cleanupArgv","cleanupTimeoutSeconds","repositoryCommit","resourceOwnership","resourceRegistryNodeId","resourceRegistryRef","resourceRegistryRunId","schemaVersion","sources","status","targetSource","targetUrl","targetUrlProvenance"] | sort) and
    .schemaVersion == 1 and .status == "ready" and
    .targetSource == "repository-declaration" and
    (.application | type == "string" and length > 0 and length <= 128) and
    (.checkoutRoot | type == "string" and length > 0 and length <= 4096) and
    (.repositoryCommit | type == "string" and test("^[0-9a-f]{40}$")) and
    (.checkoutState == "clean" or .checkoutState == "dirty") and
    (.sources | type == "array" and length > 0 and length <= 8 and all(.[];
      type == "object" and (keys | sort) == (["lineEnd","lineStart","path"] | sort) and
      (.path | type == "string" and test("^[A-Za-z0-9._/-]{1,255}$") and (contains("..") | not)) and
      (.lineStart | type == "number" and floor == . and . >= 1) and
      (.lineEnd | type == "number" and floor == . and . >= 1) and
      .lineEnd >= .lineStart and (.lineEnd - .lineStart) <= 80)) and
    (.attempts | type == "array" and length <= 6 and all(.[];
      type == "object" and (keys | sort) == (["argv","exitStatus","kind","outputTail"] | sort) and
      (.kind == "status" or .kind == "readiness" or .kind == "start" or .kind == "rebuild") and
      (.argv | type == "array" and length > 0 and length <= 32 and
        all(.[]; type == "string" and length > 0 and length <= 4096 and (credential_text | not)) and
        (. as $argv | all(range(0; (length - 1)); ($argv[.] | credential_value_flag | not)))) and
      (.exitStatus | type == "number" and floor == . and . >= 0 and . <= 255) and
      (.outputTail | type == "string" and length <= 8192 and
        (credential_text | not)))) and
    (([.attempts[].outputTail | length] | add // 0) <= 24576) and
    (.targetUrl | type == "string") and
    (.targetUrlProvenance == "declaration-text" or .targetUrlProvenance == "status-output" or .targetUrlProvenance == "start-output" or .targetUrlProvenance == "rebuild-output") and
    (.resourceOwnership == "pre-existing" or .resourceOwnership == "review-created-compose") and
    (.resourceRegistryRef | type == "string" and length <= 256) and
    (.resourceRegistryRunId | type == "string" and length <= 256) and
    (.resourceRegistryNodeId | type == "string" and length <= 256) and
    (.cleanupArgv | type == "array" and length <= 32 and all(.[]; type == "string" and length > 0 and length <= 4096)) and
    (.cleanupTimeoutSeconds | type == "number" and floor == . and . >= 0 and . <= 300) and
    (if .resourceOwnership == "pre-existing" then
      .resourceRegistryRef == "" and .resourceRegistryRunId == "" and
      .resourceRegistryNodeId == "" and .cleanupArgv == [] and .cleanupTimeoutSeconds == 0
     else
      (.resourceRegistryRef == "resources.jsonl" or .resourceRegistryRef == "review/resources.jsonl") and
      (.resourceRegistryRunId | test("^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")) and
      (.resourceRegistryNodeId | test("^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")) and
      .cleanupArgv == [] and .cleanupTimeoutSeconds == 0
     end)
  ' "$evidence" >/dev/null 2>&1 || return 1
  [ "$(jq -r '.checkoutRoot' "$evidence")" = "$REPOSITORY_ROOT" ] || {
    REPOSITORY_EVIDENCE_REASON="checkout_root_mismatch"; return 1;
  }
  current_commit="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)" || return 1
  [ "$(jq -r '.repositoryCommit' "$evidence")" = "$current_commit" ] || {
    REPOSITORY_EVIDENCE_REASON="repository_commit_mismatch"; return 1;
  }
  if ! git -C "$REPOSITORY_ROOT" submodule foreach --recursive --quiet '
    test -z "$(git status --porcelain=v1 --untracked-files=all)"
  ' >/dev/null 2>&1; then
    REPOSITORY_EVIDENCE_REASON="dirty_submodule_unsupported"; return 1
  fi
  current_state=clean
  [ -z "$(git -C "$REPOSITORY_ROOT" status --porcelain)" ] || current_state=dirty
  [ "$(jq -r '.checkoutState' "$evidence")" = "$current_state" ] || {
    REPOSITORY_EVIDENCE_REASON="checkout_state_mismatch"; return 1;
  }
  valid_selected_target_url "$(jq -r '.targetUrl' "$evidence")" || {
    REPOSITORY_EVIDENCE_REASON="target_url_invalid"; return 1;
  }
  while IFS=$'\t' read -r source_path line_end; do
    [ -f "$REPOSITORY_ROOT/$source_path" ] && [ ! -L "$REPOSITORY_ROOT/$source_path" ] &&
      git -C "$REPOSITORY_ROOT" ls-files --error-unmatch -- "$source_path" >/dev/null 2>&1 || {
        REPOSITORY_EVIDENCE_REASON="source_untracked_or_unavailable"; return 1;
      }
    source_physical="$(cd "$(dirname "$REPOSITORY_ROOT/$source_path")" && pwd -P)/$(basename "$source_path")" || return 1
    case "$source_physical" in "$REPOSITORY_ROOT"/*) ;; *)
      REPOSITORY_EVIDENCE_REASON="source_path_unsafe"; return 1 ;;
    esac
    line_count="$(awk 'END { print NR }' "$source_physical")" || return 1
    [ "$line_end" -le "$line_count" ] || {
      REPOSITORY_EVIDENCE_REASON="source_line_out_of_range"; return 1;
    }
  done < <(jq -r '.sources[] | [.path, .lineEnd] | @tsv' "$evidence")
  if [ "$(jq -r '.resourceOwnership' "$evidence")" = review-created-compose ]; then
    registry_ref="$(jq -r '.resourceRegistryRef' "$evidence")"
    registry_run_id="$(jq -r '.resourceRegistryRunId' "$evidence")"
    registry_node_id="$(jq -r '.resourceRegistryNodeId' "$evidence")"
    registry_root="$(cd "$(dirname "$STATE_FILE")" && pwd -P)" || return 1
    if [ "$registry_ref" = review/resources.jsonl ]; then
      [ "$(basename "$registry_root")" = review ] || {
        REPOSITORY_EVIDENCE_REASON="resource_registry_reference_invalid"; return 1;
      }
      registry_root="$(cd "$registry_root/.." && pwd -P)" || return 1
    fi
    registry_path="$registry_root/$registry_ref"
    [ -f "$registry_path" ] && [ ! -L "$registry_path" ] || {
      REPOSITORY_EVIDENCE_REASON="resource_registry_unavailable"; return 1;
    }
    registry_physical="$(cd "$(dirname "$registry_path")" && pwd -P)/$(basename "$registry_path")" || return 1
    case "$registry_physical" in "$registry_root"/*) ;; *)
      REPOSITORY_EVIDENCE_REASON="resource_registry_reference_invalid"; return 1 ;;
    esac
    validate_workflow_kernel_registry "$registry_physical" "$registry_run_id" "$registry_node_id" || {
      REPOSITORY_EVIDENCE_REASON="resource_registry_invalid"; return 1;
    }
  fi
  REPOSITORY_EVIDENCE_REASON=""
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
  local cleanup_argv="$9" cleanup_timeout="${10}" target_source="${11:-declaration}" visual_required="${12:-false}"
  local applicable_lanes="${13}" repository_evidence="${14:-null}" checkout_digest="${15:-null}" tmp
  tmp="$(mktemp "$(dirname "$STATE_FILE")/.ui-review-state.XXXXXX")" || return 1
  jq -cn --arg target_url "$target_url" --arg stage "$stage" \
    --argjson dispatch_allowed "$dispatch_allowed" --argjson created "$created" \
    --argjson cleanup_pending "$cleanup_pending" --argjson readiness_argv "$readiness_argv" \
    --argjson readiness_attempts "$readiness_attempts" --argjson readiness_timeout "$readiness_timeout" \
    --argjson cleanup_argv "$cleanup_argv" --argjson cleanup_timeout "$cleanup_timeout" \
    --arg target_source "$target_source" --argjson visual_required "$visual_required" \
    --argjson applicable_lanes "$applicable_lanes" --argjson repository_evidence "$repository_evidence" \
    --argjson checkout_digest "$checkout_digest" \
    '{schemaVersion:1,targetUrl:$target_url,stage:$stage,dispatchAllowed:$dispatch_allowed,
      targetSource:$target_source,visualRequired:$visual_required,applicableLanes:$applicable_lanes,
      createdByReview:$created,cleanupPending:$cleanup_pending,
      readinessArgv:$readiness_argv,readinessAttempts:$readiness_attempts,
      readinessTimeoutSeconds:$readiness_timeout,cleanupArgv:$cleanup_argv,
      cleanupTimeoutSeconds:$cleanup_timeout,repositoryEvidence:$repository_evidence,
      repositoryCheckoutFingerprint:$checkout_digest}' > "$tmp" || { rm -f "$tmp"; return 1; }
  mv "$tmp" "$STATE_FILE"
}

validate_state() {
  [ -f "$STATE_FILE" ] && [ ! -L "$STATE_FILE" ] || return 1
  jq -e --arg action "$ACTION" --arg expected_ownership "$EXPECTED_RESOURCE_OWNERSHIP" '
    type == "object" and
    (keys | sort) == (["applicableLanes","cleanupArgv","cleanupPending","cleanupTimeoutSeconds","createdByReview","dispatchAllowed","readinessArgv","readinessAttempts","readinessTimeoutSeconds","repositoryCheckoutFingerprint","repositoryEvidence","schemaVersion","stage","targetSource","targetUrl","visualRequired"] | sort) and
    .schemaVersion == 1 and (.targetUrl | type) == "string" and
    (.targetSource == "explicit" or .targetSource == "t3-preview" or
     .targetSource == "repository-declaration" or .targetSource == "declaration") and
    (.visualRequired | type) == "boolean" and
    (.applicableLanes | type == "array" and length > 0 and length <= 3 and length == (unique | length) and
      all(.[]; . == "visual-browser-tester" or . == "ux-quality-reviewer" or . == "ui-standards-reviewer")) and
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
    (if .createdByReview then (.cleanupArgv | length) > 0 and .cleanupTimeoutSeconds >= 1 else true end) and
    (if .targetSource == "repository-declaration" then
      (.repositoryEvidence | type == "object") and
      .repositoryEvidence.targetSource == "repository-declaration" and
      .repositoryEvidence.status == "ready" and
      .repositoryEvidence.targetUrl == .targetUrl and
      (.createdByReview == false and .cleanupPending == false) and
      (.repositoryEvidence.resourceOwnership == "pre-existing" or
       .repositoryEvidence.resourceOwnership == "review-created-compose") and
      .repositoryEvidence.cleanupArgv == .cleanupArgv and
      .repositoryEvidence.cleanupTimeoutSeconds == .cleanupTimeoutSeconds and
      (.repositoryCheckoutFingerprint | type == "string" and test("^[0-9a-f]{64}$"))
     else .repositoryEvidence == null and .repositoryCheckoutFingerprint == null end) and
    (if .targetSource == "repository-declaration" and $action != "prepare" then
       ($expected_ownership == "pre-existing" or $expected_ownership == "review-created-compose") and
       .repositoryEvidence.resourceOwnership == $expected_ownership
     else $expected_ownership == "" end)
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

compose_interrupted() {
  local exit_code="${1:-130}" next_action
  trap - EXIT HUP INT TERM
  next_action='repair the exact Workflow Kernel registry authority before continuing cleanup'
  if validate_state && validate_compose_registry_state; then
    next_action='run the exact Workflow Kernel Docker cleanup plan referenced by private readiness state'
  fi
  update_state closed false false >/dev/null 2>&1 || true
  emit_closed resource_cleanup_failed "$next_action"
  exit "$exit_code"
}

if [ "$ACTION" = cleanup ]; then
  if ! validate_state; then
    emit_closed resource_cleanup_failed 'inspect the exact UI review state and run only its recorded cleanup'
    exit 76
  fi
  if [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ]; then
    trap 'compose_interrupted 130' HUP INT TERM
    if ! validate_compose_registry_state; then
      emit_closed resource_cleanup_failed 'repair the exact Workflow Kernel registry authority before continuing cleanup'
      exit 76
    fi
    update_state settled false false || exit 76
    trap - HUP INT TERM
    jq -cn '{state:"registry_cleanup_required",removedCount:0,
      preexistingUntouched:false,registryCleanupPending:true,
      nextAction:"run the exact Workflow Kernel Docker cleanup plan referenced by private readiness state"}'
    exit 0
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
  if [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ]; then
    trap 'compose_interrupted 130' HUP INT TERM
  fi
  if ! validate_compose_registry_state; then
    update_state settled false false || exit 76
    emit_closed resource_cleanup_failed 'repair the exact Workflow Kernel registry authority before continuing cleanup'
    exit 76
  fi
  [ -f "$ANALYSIS_RESULT_FILE" ] && [ ! -L "$ANALYSIS_RESULT_FILE" ] || usage
  analysis_valid=false
  planned_lanes="$(jq -c '.applicableLanes | sort' "$STATE_FILE")"
  if jq -e --argjson planned "$planned_lanes" '
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
      and ([.lanes[].lane] | sort) == $planned
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
  if [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ]; then
    trap - HUP INT TERM
    jq -cn '{state:"completed",dispatchAllowed:false,reason:"available",
      reviewDisposition:"completed",cleanup:"registry_cleanup_required",
      registryCleanupPending:true,
      nextAction:"run the exact Workflow Kernel Docker cleanup plan referenced by private readiness state"}'
    exit 0
  fi
  jq -cn '{state:"completed",dispatchAllowed:false,reason:"available",
    reviewDisposition:"completed",cleanup:"complete"}'
  exit 0
fi

DECLARATION="$REPOSITORY_ROOT/.dm/ui-review.json"
close_registered_state() {
  local reason="$1" next_action="$2" cleanup_rc=0
  trap - EXIT HUP INT TERM
  if { [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ] ||
       { [ -z "$EXPECTED_RESOURCE_OWNERSHIP" ] &&
         [ "$(jq -r '.targetSource == "repository-declaration" and .repositoryEvidence.resourceOwnership == "review-created-compose"' "$STATE_FILE" 2>/dev/null)" = true ]; }; } &&
     ! validate_compose_registry_state; then
    update_state closed false false || exit 76
    emit_closed resource_cleanup_failed 'repair the exact Workflow Kernel registry authority before continuing cleanup'
    exit 76
  fi
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
  if [ "$TARGET_SOURCE_INPUT" = repository-declaration ]; then
    [ -z "$TARGET_URL_INPUT" ] && [ -n "$REPOSITORY_EVIDENCE_FILE" ] || usage
    if ! validate_repository_evidence "$REPOSITORY_EVIDENCE_FILE"; then
      emit_rendered_gap dev_server_unavailable "repair the repository target evidence prerequisite: $REPOSITORY_EVIDENCE_REASON"
    fi
    [ ! -e "$STATE_FILE" ] || usage
    TARGET_URL="$(jq -r '.targetUrl' "$REPOSITORY_EVIDENCE_FILE")"
    REPOSITORY_EVIDENCE_JSON="$(jq -c . "$REPOSITORY_EVIDENCE_FILE")"
    CHECKOUT_FINGERPRINT="$(checkout_fingerprint)" || exit 76
    CHECKOUT_FINGERPRINT_JSON="$(printf '%s' "$CHECKOUT_FINGERPRINT" | jq -R .)" || exit 76
    CLEANUP_ARGV_JSON="$(jq -c '.cleanupArgv' "$REPOSITORY_EVIDENCE_FILE")"
    CLEANUP_TIMEOUT="$(jq -r '.cleanupTimeoutSeconds' "$REPOSITORY_EVIDENCE_FILE")"
    CREATED=false
    CLEANUP_PENDING=false
    REGISTERED_CREATED=false
    if [ "$(jq -r '.resourceOwnership' "$REPOSITORY_EVIDENCE_FILE")" = review-created-compose ]; then
      REGISTERED_CREATED=true
    fi
    write_state "$TARGET_URL" app_ready false "$CREATED" "$CLEANUP_PENDING" '[]' 1 1 \
      "$CLEANUP_ARGV_JSON" "$CLEANUP_TIMEOUT" repository-declaration "$VISUAL_REQUIRED" \
      "$APPLICABLE_LANES_JSON" "$REPOSITORY_EVIDENCE_JSON" "$CHECKOUT_FINGERPRINT_JSON" || exit 76
    jq -cn --argjson created "$REGISTERED_CREATED" \
      --arg application "$(jq -r '.application' "$REPOSITORY_EVIDENCE_FILE")" \
      --arg repository_commit "$(jq -r '.repositoryCommit' "$REPOSITORY_EVIDENCE_FILE")" \
      --arg checkout_state "$(jq -r '.checkoutState' "$REPOSITORY_EVIDENCE_FILE")" \
      --arg provenance "$(jq -r '.targetUrlProvenance' "$REPOSITORY_EVIDENCE_FILE")" \
      --arg ownership "$(jq -r '.resourceOwnership' "$REPOSITORY_EVIDENCE_FILE")" \
      --argjson sources "$(jq -c '.sources' "$REPOSITORY_EVIDENCE_FILE")" \
      --argjson attempts "$(jq -c '[.attempts[] | {kind,exitStatus}]' "$REPOSITORY_EVIDENCE_FILE")" \
      '{state:"app_ready",dispatchAllowed:false,reason:"browser_evidence_required",
        targetRef:"private-readiness-state",targetSource:"repository-declaration",
        repositoryEvidence:{application:$application,repositoryCommit:$repository_commit,
          checkoutState:$checkout_state,sources:$sources,attempts:$attempts,
          targetUrlProvenance:$provenance,resourceOwnership:$ownership,
          privateOutputTails:"readiness-state-only"},
        createdResources:(if $created then 1 else 0 end),
        nextAction:"navigate the repository-declared target with the host local browser, then run confirm-browser"}'
    exit 0
  fi
  [ -z "$REPOSITORY_EVIDENCE_FILE" ] || usage
  if [ -n "$TARGET_URL_INPUT" ]; then
    case "$TARGET_SOURCE_INPUT" in explicit|t3-preview) ;; *) usage ;; esac
    valid_selected_target_url "$TARGET_URL_INPUT" || usage
    [ ! -e "$STATE_FILE" ] || usage
    write_state "$TARGET_URL_INPUT" app_ready false false false '[]' 1 1 '[]' 0 \
      "$TARGET_SOURCE_INPUT" "$VISUAL_REQUIRED" "$APPLICABLE_LANES_JSON" null || exit 76
    jq -cn --arg target_url "$TARGET_URL_INPUT" --arg source "$TARGET_SOURCE_INPUT" \
      '{state:"app_ready",dispatchAllowed:false,reason:"browser_evidence_required",
        targetUrl:$target_url,targetSource:$source,createdResources:0,
        nextAction:"navigate the selected target with the host local browser, then run confirm-browser"}'
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
      jq -e --arg target "$TARGET_URL" --argjson lanes "$APPLICABLE_LANES_JSON" \
        '.stage == "app_ready" and .dispatchAllowed == false and .targetUrl == $target and .applicableLanes == $lanes' \
        "$STATE_FILE" >/dev/null 2>&1 || usage
    if ! run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then
      close_registered_state dev_server_unavailable 'inspect the registered application readiness command and rerun'
    fi
    CREATED="$(jq -r '.createdByReview' "$STATE_FILE")"
  elif run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then
    write_state "$TARGET_URL" app_ready false false false "$READINESS_ARGV_JSON" \
      "$READINESS_ATTEMPTS" "$READINESS_TIMEOUT" '[]' 0 declaration "$VISUAL_REQUIRED" "$APPLICABLE_LANES_JSON" null || exit 76
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
      "$READINESS_ATTEMPTS" "$READINESS_TIMEOUT" "$CLEANUP_ARGV_JSON" "$START_TIMEOUT" declaration "$VISUAL_REQUIRED" "$APPLICABLE_LANES_JSON" null || exit 76
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
elif [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ]; then
  trap 'compose_interrupted 130' HUP INT TERM
fi
if [ "$(jq -r '.targetSource' "$STATE_FILE")" = declaration ]; then
  load_argv "$STATE_FILE" '.readinessArgv' || usage
  validate_repo_executable "${UI_ARGV[0]}" || close_registered_state dev_server_unavailable 'repair the registered readiness command and rerun'
  READINESS_ARGV=("${UI_ARGV[@]}")
  if ! run_bounded_argv "$READINESS_TIMEOUT" "${READINESS_ARGV[@]}"; then
    close_registered_state dev_server_unavailable 'inspect the registered application readiness command and rerun'
  fi
fi
if [ "$(jq -r '.targetSource' "$STATE_FILE")" = repository-declaration ]; then
  [ "$(jq -r '.repositoryEvidence.checkoutRoot' "$STATE_FILE")" = "$REPOSITORY_ROOT" ] ||
    close_registered_state dev_server_unavailable 'restore the repository-declared checkout identity and rerun discovery'
  [ "$(jq -r '.repositoryEvidence.repositoryCommit' "$STATE_FILE")" = "$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)" ] ||
    close_registered_state dev_server_unavailable 'rerun repository target discovery for the current source commit'
  CURRENT_STATE=clean
  [ -z "$(git -C "$REPOSITORY_ROOT" status --porcelain)" ] || CURRENT_STATE=dirty
  [ "$(jq -r '.repositoryEvidence.checkoutState' "$STATE_FILE")" = "$CURRENT_STATE" ] ||
    close_registered_state dev_server_unavailable 'rerun repository target discovery for the current checkout state'
  [ "$(jq -r '.repositoryCheckoutFingerprint' "$STATE_FILE")" = "$(checkout_fingerprint)" ] ||
    close_registered_state dev_server_unavailable 'rerun repository target discovery after checkout content changed'
  validate_compose_registry_state ||
    close_registered_state resource_cleanup_failed 'repair the exact Workflow Kernel registry authority before browser confirmation'
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
if [ "$(jq -r '.targetSource' "$STATE_FILE")" = repository-declaration ]; then
  CREATED=false
  [ "$EXPECTED_RESOURCE_OWNERSHIP" = review-created-compose ] && CREATED=true
else
  CREATED="$(jq -r '.createdByReview' "$STATE_FILE")"
fi
EVIDENCE_REF="$(jq -r '.evidenceRef' "$BROWSER_EVIDENCE_FILE")"
if [ "$(jq -r '.targetSource' "$STATE_FILE")" = repository-declaration ]; then
  jq -cn --arg evidence_ref "$EVIDENCE_REF" --argjson created "$CREATED" \
    '{state:"ready",dispatchAllowed:true,reason:"available",targetRef:"private-readiness-state",
      browserTransport:"local-interactive",browserEvidence:"bounded-host-evidence",evidenceRef:$evidence_ref,
      createdResources:(if $created then 1 else 0 end),
      nextAction:(if $created then
        "dispatch provider-neutral UI analysis without browser capability, then run the exact Workflow Kernel Docker cleanup plan referenced by private readiness state"
       else "dispatch provider-neutral UI analysis without browser capability" end)} +
      (if $created then {cleanup:"registry_cleanup_required",registryCleanupPending:true} else {} end)'
else
  jq -cn --arg target_url "$TARGET_URL" --arg evidence_ref "$EVIDENCE_REF" --argjson created "$CREATED" \
    '{state:"ready",dispatchAllowed:true,reason:"available",targetUrl:$target_url,
      browserTransport:"local-interactive",browserEvidence:"bounded-host-evidence",evidenceRef:$evidence_ref,
      createdResources:(if $created then 1 else 0 end),
      nextAction:"dispatch provider-neutral UI analysis without browser capability"}'
fi
