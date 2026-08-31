#!/usr/bin/env bash
# browser-evidence-packet.sh -- create and validate an explicit exact-head UI packet.
#
# Artifacts are relative to the packet directory. The caller names every input
# and output path; this helper never searches for a latest run or timestamp.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
umask 077

ACTION="${1:-}"
[ "$#" -gt 0 ] && shift
REPOSITORY_ROOT=""
PROTOTYPE_ROOT=""
CAPTURE_FILE=""
PACKET_FILE=""
SELECTED_CASES_FILE=""
EVIDENCE_REF=""

usage() { printf '%s\n' 'browser-evidence-packet: invalid invocation' >&2; exit 2; }
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repository-root) [ "$#" -ge 2 ] || usage; REPOSITORY_ROOT="$2"; shift 2 ;;
    --prototype-root) [ "$#" -ge 2 ] || usage; PROTOTYPE_ROOT="$2"; shift 2 ;;
    --capture-file) [ "$#" -ge 2 ] || usage; CAPTURE_FILE="$2"; shift 2 ;;
    --packet-file) [ "$#" -ge 2 ] || usage; PACKET_FILE="$2"; shift 2 ;;
    --selected-cases-file) [ "$#" -ge 2 ] || usage; SELECTED_CASES_FILE="$2"; shift 2 ;;
    --evidence-ref) [ "$#" -ge 2 ] || usage; EVIDENCE_REF="$2"; shift 2 ;;
    *) usage ;;
  esac
done
case "$ACTION" in create|validate) ;; *) usage ;; esac
command -v jq >/dev/null 2>&1 || exit 76
[ -n "$REPOSITORY_ROOT" ] && [ -d "$REPOSITORY_ROOT" ] && [ ! -L "$REPOSITORY_ROOT" ] || usage
REPOSITORY_ROOT="$(cd "$REPOSITORY_ROOT" && pwd -P)"
[ -n "$PACKET_FILE" ] && [ -d "$(dirname "$PACKET_FILE")" ] || usage

repo_identity() {
  local root="$1" remote
  remote="$(git -C "$root" config --get remote.origin.url 2>/dev/null || true)"
  printf '%s' "$remote" | sed -E \
    -e 's#^git@github\.com:##' -e 's#^https://github\.com/##' -e 's#^ssh://git@github\.com/##' -e 's#\.git$##' -e 's#/$##'
}

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'
  fi
}

validate_artifact_path() {
  local packet_dir="$1" ref="$2" artifact="$packet_dir/$ref" artifact_dir
  [ -f "$artifact" ] && [ ! -L "$artifact" ] || return 1
  artifact_dir="$(cd "$(dirname "$artifact")" && pwd -P)" || return 1
  case "$artifact_dir" in "$packet_dir"|"$packet_dir"/*) ;; *) return 1 ;; esac
  [ "$(wc -c < "$artifact")" -le 10485760 ]
}

validate_root_identity() {
  local root="$1" identity
  git -C "$root" rev-parse --show-toplevel >/dev/null 2>&1 || return 1
  identity="$(repo_identity "$root")"
  printf '%s' "$identity" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
}

validate_root_identity "$REPOSITORY_ROOT" || usage
REPOSITORY_IDENTITY="$(repo_identity "$REPOSITORY_ROOT")"
REPOSITORY_COMMIT="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)"
REPOSITORY_STATE=clean
[ -z "$(git -C "$REPOSITORY_ROOT" status --porcelain)" ] || REPOSITORY_STATE=dirty

PROTOTYPE_REPOSITORY=null
PROTOTYPE_COMMIT=null
if [ -n "$PROTOTYPE_ROOT" ]; then
  [ -d "$PROTOTYPE_ROOT" ] && [ ! -L "$PROTOTYPE_ROOT" ] || usage
  PROTOTYPE_ROOT="$(cd "$PROTOTYPE_ROOT" && pwd -P)"
  validate_root_identity "$PROTOTYPE_ROOT" || usage
  PROTOTYPE_REPOSITORY="$(repo_identity "$PROTOTYPE_ROOT")"
  PROTOTYPE_COMMIT="$(git -C "$PROTOTYPE_ROOT" rev-parse HEAD)"
fi

safe_packet_shape='type == "object" and
  (keys | sort) == (["artifacts","completionStatus","consoleAccessibilitySummary","domClassCopyActionObservations","layoutComputedStyleObservations","prototypeCommit","prototypeRepository","repositoryCommit","repositoryIdentity","repositoryState","schemaVersion","selectedCaseIds"] | sort) and
  .schemaVersion == 1 and .completionStatus == "completed" and
  (.repositoryIdentity | test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")) and
  (.repositoryCommit | test("^[0-9a-f]{40}$")) and (.repositoryState == "clean" or .repositoryState == "dirty") and
  ((.prototypeRepository == null and .prototypeCommit == null) or
   ((.prototypeRepository | test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")) and (.prototypeCommit | test("^[0-9a-f]{40}$")))) and
  (.selectedCaseIds | type == "array" and length > 0 and length <= 64 and length == (unique | length) and
    all(.[]; type == "string" and test("^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$"))) and
  (.artifacts | type == "array" and length > 0 and length <= 64 and length == (map(.ref) | unique | length) and all(.[];
    type == "object" and (keys | sort) == (["ref","sha256"] | sort) and
    (.ref | test("^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}\\.(png|jpe?g|webp|json)$") and (contains("..") | not)) and
    (.sha256 | test("^[0-9a-f]{64}$")))) and
  ([.domClassCopyActionObservations,.layoutComputedStyleObservations] | all(.[];
    type == "array" and length <= 40 and all(.[]; type == "string" and length > 0 and length <= 512 and
      (test("https?://|(?i)(authorization|bearer|cookie|password|secret|access[_-]?token|browser storage|localStorage|sessionStorage)") | not)))) and
  (.consoleAccessibilitySummary | type == "string" and length > 0 and length <= 2048 and
    (test("https?://|(?i)(authorization|bearer|cookie|password|secret|access[_-]?token|browser storage|localStorage|sessionStorage)") | not))'

emit_rejected() {
  jq -cn --arg reason "$1" '{status:"rejected",reason:$reason}'
  exit 76
}

if [ "$ACTION" = create ]; then
  [ -f "$CAPTURE_FILE" ] && [ ! -L "$CAPTURE_FILE" ] || usage
  jq -e '
    type == "object" and
    (keys | sort) == (["artifactRefs","completionStatus","consoleAccessibilitySummary","domClassCopyActionObservations","layoutComputedStyleObservations","localNavigationConfirmed","schemaVersion","selectedCaseIds"] | sort) and
    .schemaVersion == 1 and .completionStatus == "completed" and .localNavigationConfirmed == true and
    (.selectedCaseIds | type == "array" and length > 0 and length <= 64 and length == (unique | length) and all(.[]; type == "string" and test("^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$"))) and
    (.artifactRefs | type == "array" and length > 0 and length <= 64 and length == (unique | length) and all(.[]; type == "string" and test("^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}\\.(png|jpe?g|webp|json)$") and (contains("..") | not))) and
    ([.domClassCopyActionObservations,.layoutComputedStyleObservations] | all(.[]; type == "array" and length <= 40 and all(.[]; type == "string" and length > 0 and length <= 512))) and
    (.consoleAccessibilitySummary | type == "string" and length > 0 and length <= 2048)
  ' "$CAPTURE_FILE" >/dev/null 2>&1 || usage
  packet_dir="$(cd "$(dirname "$PACKET_FILE")" && pwd -P)"
  [ ! -L "$PACKET_FILE" ] || emit_rejected packet_path_symlink
  artifacts='[]'
  while IFS= read -r ref; do
    artifact="$packet_dir/$ref"
    validate_artifact_path "$packet_dir" "$ref" || emit_rejected artifact_missing_or_unbounded
    digest="$(hash_file "$artifact")"
    artifacts="$(printf '%s' "$artifacts" | jq -c --arg ref "$ref" --arg digest "$digest" '. + [{ref:$ref,sha256:$digest}]')"
  done < <(jq -r '.artifactRefs[]' "$CAPTURE_FILE")
  tmp="$(mktemp "$packet_dir/.browser-evidence-packet.XXXXXX")"
  jq -cn --arg repository_identity "$REPOSITORY_IDENTITY" --arg repository_commit "$REPOSITORY_COMMIT" \
    --arg repository_state "$REPOSITORY_STATE" --argjson prototype_repository "$(if [ "$PROTOTYPE_REPOSITORY" = null ]; then printf null; else printf '%s' "$PROTOTYPE_REPOSITORY" | jq -R .; fi)" \
    --argjson prototype_commit "$(if [ "$PROTOTYPE_COMMIT" = null ]; then printf null; else printf '%s' "$PROTOTYPE_COMMIT" | jq -R .; fi)" \
    --argjson selected_case_ids "$(jq -c '.selectedCaseIds | sort' "$CAPTURE_FILE")" --argjson artifacts "$artifacts" \
    --argjson dom "$(jq -c '.domClassCopyActionObservations' "$CAPTURE_FILE")" \
    --argjson layout "$(jq -c '.layoutComputedStyleObservations' "$CAPTURE_FILE")" \
    --arg summary "$(jq -r '.consoleAccessibilitySummary' "$CAPTURE_FILE")" \
    '{schemaVersion:1,repositoryIdentity:$repository_identity,repositoryCommit:$repository_commit,
      repositoryState:$repository_state,prototypeRepository:$prototype_repository,prototypeCommit:$prototype_commit,
      selectedCaseIds:$selected_case_ids,artifacts:$artifacts,domClassCopyActionObservations:$dom,
      layoutComputedStyleObservations:$layout,consoleAccessibilitySummary:$summary,completionStatus:"completed"}' > "$tmp"
  jq -e "$safe_packet_shape" "$tmp" >/dev/null 2>&1 || { rm -f "$tmp"; usage; }
  mv "$tmp" "$PACKET_FILE"
  jq -cn --arg packet "$PACKET_FILE" '{status:"created",packetFile:$packet}'
  exit 0
fi

[ -f "$PACKET_FILE" ] && [ ! -L "$PACKET_FILE" ] || emit_rejected packet_missing
[ -f "$SELECTED_CASES_FILE" ] && [ ! -L "$SELECTED_CASES_FILE" ] || usage
printf '%s' "$EVIDENCE_REF" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$' || usage
jq -e 'type == "array" and length > 0 and length <= 64 and length == (unique | length) and all(.[]; type == "string")' "$SELECTED_CASES_FILE" >/dev/null 2>&1 || usage
jq -e "$safe_packet_shape" "$PACKET_FILE" >/dev/null 2>&1 || emit_rejected packet_schema

[ "$(jq -r '.repositoryIdentity' "$PACKET_FILE")" = "$REPOSITORY_IDENTITY" ] || emit_rejected repository_identity_mismatch
[ "$(jq -r '.repositoryCommit' "$PACKET_FILE")" = "$REPOSITORY_COMMIT" ] || emit_rejected repository_commit_mismatch
[ "$(jq -r '.repositoryState' "$PACKET_FILE")" = "$REPOSITORY_STATE" ] || emit_rejected repository_state_mismatch
[ "$REPOSITORY_STATE" = clean ] || emit_rejected repository_dirty_not_reusable
[ "$(jq -r '.prototypeRepository // "null"' "$PACKET_FILE")" = "$PROTOTYPE_REPOSITORY" ] || emit_rejected prototype_identity_mismatch
[ "$(jq -r '.prototypeCommit // "null"' "$PACKET_FILE")" = "$PROTOTYPE_COMMIT" ] || emit_rejected prototype_commit_mismatch
packet_cases="$(jq -c '.selectedCaseIds | sort' "$PACKET_FILE")"
selected_cases="$(jq -c 'sort' "$SELECTED_CASES_FILE")"
[ "$packet_cases" = "$selected_cases" ] || emit_rejected selected_case_set_mismatch

packet_dir="$(cd "$(dirname "$PACKET_FILE")" && pwd -P)"
while IFS=$'\t' read -r ref expected; do
  artifact="$packet_dir/$ref"
  validate_artifact_path "$packet_dir" "$ref" || emit_rejected artifact_missing_or_unbounded
  [ "$(hash_file "$artifact")" = "$expected" ] || emit_rejected artifact_hash_mismatch
done < <(jq -r '.artifacts[] | [.ref,.sha256] | @tsv' "$PACKET_FILE")

jq -cn --arg evidence_ref "$EVIDENCE_REF" --argjson selected_case_ids "$selected_cases" \
  '{status:"accepted",evidenceRef:$evidence_ref,selectedCaseIds:$selected_case_ids}'
