#!/usr/bin/env bash
# Session pointer only. Native SessionStart/Stop JSON is read from stdin.
# Sourceable identity helpers are also used by the publication gate.
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

review_refuse() { printf 'Not ready: %s\n' "$*" >&2; exit 3; }
review_stat() {
  # GNU and BSD stat use different format flags. All callers pass absolute paths.
  local gnu bsd value
  case "$1" in
    uid) gnu=%u; bsd=%u ;; mode) gnu=%a; bsd=%Lp ;;
    links) gnu=%h; bsd=%l ;; identity) gnu='[%d,%i]'; bsd='[%d,%i]' ;;
    *) return 2 ;;
  esac
  if value="$(stat -c "$gnu" -- "$2" 2>/dev/null)"; then
    printf '%s\n' "$value"
  else
    stat -f "$bsd" "$2"
  fi
}
review_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum
  else shasum -a 256
  fi | awk '{print $1}'
}
review_safe_path() {
  local path="$1" part cursor=/
  local -a parts
  [[ "$path" = /* && "$path" != *$'\n'* && "$path" != *$'\t'* ]] || review_refuse 'unsafe path'
  # Lexical canonicality also works for not-yet-created marker paths.
  case "$path" in *//*|*/./*|*/../*|*/.|*/..) review_refuse 'noncanonical path' ;; esac
  [ "$path" = / ] || [ "${path%/}" = "$path" ] || review_refuse 'noncanonical path'
  IFS=/ read -r -a parts <<< "$path"
  for part in "${parts[@]}"; do
    [ -n "$part" ] || continue
    cursor="${cursor%/}/$part"
    [ ! -L "$cursor" ] || review_refuse 'symlink path'
  done
}
review_private() {
  review_safe_path "$1"
  [ -e "$1" ] && [ "$(review_stat uid "$1")" = "$(id -u)" ] || review_refuse 'foreign or missing private context'
  local mode
  mode="$(review_stat mode "$1")"
  (( (8#$mode & 077) == 0 )) || review_refuse 'context is not private'
  if [ -f "$1" ]; then
    [ "$(review_stat links "$1")" = 1 ] || review_refuse 'linked private context'
  else
    [ -d "$1" ] || review_refuse 'invalid private context'
  fi
}
review_repository() {
  review_safe_path "$1"
  [ "$(git -C "$1" rev-parse --show-toplevel)" = "$1" ] || review_refuse 'repository root mismatch'
  local remote
  remote="$(git -C "$1" remote get-url origin)"
  remote="${remote%.git}"
  case "$remote" in
    git@github.com:*) remote="${remote#git@github.com:}" ;;
    https://github.com/*) remote="${remote#https://github.com/}" ;;
    *) review_refuse 'canonical repository unavailable' ;;
  esac
  [[ "$remote" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || review_refuse 'invalid repository identity'
  printf '%s\n' "$remote"
}
review_owner_validate() {
  # $1 is the closed owner object, $2 the canonical checkout.
  local owner="$1" repo="$2" root run workflow state metadata
  jq -e 'type=="object" and (keys|sort)==(["repository","workflow","run_id","run_root","state_dir"]|sort) and
    (.repository|type=="string") and (.workflow|IN("pipeline","dm-review","dm-review-loop")) and
    (.run_id|type=="string" and test("^[a-z0-9][a-z0-9._-]{0,127}$")) and
    all(.run_root,.state_dir; type=="string" and startswith("/"))' <<< "$owner" >/dev/null || review_refuse 'invalid current owner'
  [ "$(jq -r .repository <<< "$owner")" = "$(review_repository "$repo")" ] || review_refuse 'foreign repository owner'
  root="$(jq -r .run_root <<< "$owner")"; run="$(jq -r .run_id <<< "$owner")"
  workflow="$(jq -r .workflow <<< "$owner")"; state="$(jq -r .state_dir <<< "$owner")"
  review_private "$root"
  metadata="$root/.depot-owned-run.json"
  review_private "$metadata"
  [ "$state" = "$repo/.workflow-kernel/runs/$run" ] || review_refuse 'foreign owner state directory'
  review_safe_path "$state"
  [ -d "$state" ] || review_refuse 'missing owner state directory'
  jq -e --arg root "$root" --arg run "$run" --arg workflow "$workflow" \
    --argjson rootid "$(review_stat identity "$root")" \
    --argjson baseid "$(review_stat identity "$(dirname "$root")")" '
    (keys|sort)==(["version","workflow","run_id","root","root_identity","base_identity","resources"]|sort) and
    .version==1 and .root==$root and .run_id==$run and .workflow==$workflow and
    .root_identity==$rootid and .base_identity==$baseid and
    (.resources|type=="array" and all(.[];
      (keys|sort)==(["kind","relative_path","device","inode"]|sort) and
      (.kind|IN("temporary-directory","temporary-repository","cache","raw-output","diagnostic")) and
      (.relative_path|type=="string" and test("^[A-Za-z0-9_][A-Za-z0-9_./-]*$") and (split("/")|all(.[];. != ".." and . != "." and . != ""))) and
      (.device|type=="number") and (.inode|type=="number")))
  ' "$metadata" >/dev/null || review_refuse 'exact-owned metadata mismatch'
}
review_change_boundary() {
  # Bind committed and dirty content, including untracked files; no timestamps.
  local repo="$1" file
  {
    git -C "$repo" rev-parse HEAD
    git -C "$repo" diff --binary HEAD
    git -C "$repo" diff --cached --binary HEAD
    while IFS= read -r -d '' file; do
      printf '%s\0' "$file"
      review_stat mode "$repo/$file"
      if [ -L "$repo/$file" ]; then readlink "$repo/$file"; else review_sha256 < "$repo/$file"; fi
    done < <(git -C "$repo" ls-files --others --exclude-standard -z)
  } | review_sha256 | awk '{print "sha256:" $1}'
}

if [ "${BASH_SOURCE[0]}" != "$0" ]; then return 0; fi
MODE="${1:-}"; [ "$#" -gt 0 ] && shift
REPO= CONTEXT= WORKFLOW= RUN= RUN_ROOT= STATE= PHASE= BOUNDARY=
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || exit 2
  case "$1" in
    --repository-root) REPO="$2" ;; --context) CONTEXT="$2" ;;
    --workflow) WORKFLOW="$2" ;; --run-id) RUN="$2" ;;
    --run-root) RUN_ROOT="$2" ;; --state-dir) STATE="$2" ;;
    --phase) PHASE="$2" ;; --change-boundary) BOUNDARY="$2" ;;
    *) exit 2 ;;
  esac
  shift 2
done
case "$MODE" in init|bind|phase|clear) ;; *) exit 2 ;; esac
NATIVE="$(cat)"
jq -e '(.hook_event_name|IN("SessionStart","Stop")) and
  (.session_id|type=="string" and length>0 and length<=256 and (test("[\u0000-\u001f\u007f]")|not)) and
  (.cwd|type=="string") and (.agent_id==null) and (.agent_type==null)' <<< "$NATIVE" >/dev/null || review_refuse 'native root session context unavailable'
SESSION="$(jq -r .session_id <<< "$NATIVE")"
[ "$(cd "$(jq -r .cwd <<< "$NATIVE")" && pwd -P)" = "$REPO" ] || review_refuse 'native repository mismatch'
REPOSITORY="$(review_repository "$REPO")"
KEY="$(printf '%s\0%s\0%s' "$REPOSITORY" "$REPO" "$SESSION" | review_sha256)"
# macOS native TMPDIR (and /tmp) can have a system symlink above it. Resolve
# that existing directory first; marker/run paths still reject symlink components.
BASE="$(cd "${TMPDIR:-/tmp}" && pwd -P)/claude-hook-state"
DIRECTORY="$BASE/review-$KEY"
EXPECTED="$DIRECTORY/review-owner.json"
umask 077
if [ "$MODE" = init ]; then
  [ "$(jq -r .hook_event_name <<< "$NATIVE")" = SessionStart ] || review_refuse 'init requires SessionStart'
  review_safe_path "$BASE"
  [ -d "$BASE" ] || mkdir -- "$BASE"
  # Existing reminder markers may share this account-owned directory.
  [ "$(review_stat uid "$BASE")" = "$(id -u)" ] || review_refuse 'foreign hook-state directory'
  [ -d "$DIRECTORY" ] || mkdir -- "$DIRECTORY"
else
  [ "$CONTEXT" = "$EXPECTED" ] || review_refuse 'hook activation unavailable: exact SessionStart context required'
fi
review_private "$DIRECTORY"
if [ -e "$EXPECTED" ] || [ -L "$EXPECTED" ]; then
  review_private "$EXPECTED"
  CURRENT="$(cat "$EXPECTED")"
  jq -e --arg session "$SESSION" --arg repository "$REPOSITORY" '
    (keys|sort)==(["session_id","repository","workflow","run_id","run_root","state_dir","phase","change_boundary"]|sort) and
    .session_id==$session and .repository==$repository and
    (.phase|IN("planning","awaiting_plan_approval","executing","checking","awaiting_ui","awaiting_merge","blocked","complete")) and
    (.change_boundary==null or (.change_boundary|type=="string" and test("^sha256:[0-9a-f]{64}$"))) and
    ((.workflow==null and .run_id==null and .run_root==null and .state_dir==null and (.phase|IN("planning","awaiting_plan_approval"))) or
     (.workflow!=null and .run_id!=null and .run_root!=null and .state_dir!=null))
  ' <<< "$CURRENT" >/dev/null || review_refuse 'conflicting session context'
  if [ "$(jq -r .run_id <<< "$CURRENT")" != null ] && [ "$(jq -r .phase <<< "$CURRENT")" != complete ]; then
    review_owner_validate "$(jq '{repository,workflow,run_id,run_root,state_dir}' <<< "$CURRENT")" "$REPO"
  fi
elif [ "$MODE" = init ]; then
  CURRENT="$(jq -cn --arg session "$SESSION" --arg repository "$REPOSITORY" '{session_id:$session,repository:$repository,workflow:null,run_id:null,run_root:null,state_dir:null,phase:"planning",change_boundary:null}')"
else review_refuse 'hook activation unavailable: missing SessionStart context'; fi

case "$MODE" in
  init) ;;
  bind)
    jq -e '.run_id==null or .phase=="complete"' <<< "$CURRENT" >/dev/null || review_refuse 'active owner cannot be rebound'
    OWNER="$(jq -cn --arg repository "$REPOSITORY" --arg workflow "$WORKFLOW" --arg run "$RUN" --arg root "$RUN_ROOT" --arg state "$STATE" '{repository:$repository,workflow:$workflow,run_id:$run,run_root:$root,state_dir:$state}')"
    review_owner_validate "$OWNER" "$REPO"
    [ "$BOUNDARY" = "$(review_change_boundary "$REPO")" ] || review_refuse 'change boundary mismatch'
    CURRENT="$(jq --argjson owner "$OWNER" --arg boundary "$BOUNDARY" '. + $owner | .phase="executing" | .change_boundary=$boundary' <<< "$CURRENT")" ;;
  phase)
    FROM="$(jq -r .phase <<< "$CURRENT")"
    case "$FROM:$PHASE" in
      planning:awaiting_plan_approval|executing:checking|checking:executing|checking:awaiting_ui|checking:awaiting_merge|awaiting_ui:executing|awaiting_ui:checking|awaiting_ui:awaiting_merge|awaiting_merge:checking|awaiting_merge:complete|checking:complete|executing:blocked|checking:blocked|awaiting_ui:blocked|awaiting_merge:blocked|blocked:executing|blocked:checking) ;;
      *) review_refuse 'invalid phase transition' ;;
    esac
    if [ "$(jq -r .run_id <<< "$CURRENT")" != null ]; then
      [ "$BOUNDARY" = "$(review_change_boundary "$REPO")" ] || review_refuse 'change boundary mismatch'
      CURRENT="$(jq --arg boundary "$BOUNDARY" '.change_boundary=$boundary' <<< "$CURRENT")"
    fi
    CURRENT="$(jq --arg phase "$PHASE" '.phase=$phase' <<< "$CURRENT")" ;;
  clear)
    jq -e '.phase=="complete" and .run_id!=null' <<< "$CURRENT" >/dev/null || review_refuse 'only completed owner may clear'
    [ "$RUN" = "$(jq -r .run_id <<< "$CURRENT")" ] && [ "$RUN_ROOT" = "$(jq -r .run_root <<< "$CURRENT")" ] || review_refuse 'clear owner mismatch'
    rm -- "$EXPECTED"
    exit 0 ;;
esac
TEMP="$(mktemp "$DIRECTORY/.review-owner.XXXXXX")"
trap 'rm -f -- "$TEMP"' EXIT
printf '%s\n' "$CURRENT" > "$TEMP"
mv -- "$TEMP" "$EXPECTED"
if [ "$MODE" = init ]; then
  jq -cn --arg context "$EXPECTED" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:("Review owner context: " + $context + ". Root owner binds only after plan/prompt approval; this pointer is not review coverage.")}}'
else printf '%s\n' "$EXPECTED"; fi
