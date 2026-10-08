#!/usr/bin/env bash
# Selected Assembly development source cleanup, never ref/Docker disposal.
# Usage: canonical-checkout.sh inspect|prepare|finish --repository-root ROOT
#   --repository OWNER/REPO --target-branch BRANCH --binding-file INSTALL.json
#   --delivered-head REVIEWED_SHA --current-context POINTER [--owner-context POINTER ...] [--keep-path REL ...]
#   [--inspection INSPECT.json] [--implementation-root ROOT]
#   [--preservation PRODUCER.json] [--residue-path ABS ...]
# Dependencies: Git, jq; Bash 3.2+. inspect emits JSON-quoted paths (including
# newlines); prepare requires that exact unchanged inspection before mutation.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/review-owner-context.sh"
MODE="${1:-}"; [ "$#" -gt 0 ] && shift
REPO= ID= BRANCH= BINDING= CURRENT= INSPECTION= IMPLEMENTATION= DELIVERED= PRESERVATION=
OWNERS=(); KEEP=(); RESIDUE=()
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || exit 2
  case "$1" in
    --repository-root) REPO="$2" ;; --repository) ID="$2" ;;
    --target-branch) BRANCH="$2" ;; --binding-file) BINDING="$2" ;;
    --current-context) CURRENT="$2" ;; --owner-context) OWNERS+=("$2") ;;
    --keep-path) KEEP+=("$2") ;; --residue-path) RESIDUE+=("$2") ;; --inspection) INSPECTION="$2" ;;
    --implementation-root) IMPLEMENTATION="$2" ;; --delivered-head) DELIVERED="$2" ;;
    --preservation) PRESERVATION="$2" ;; *) exit 2 ;;
  esac
  shift 2
done
case "$MODE" in inspect|prepare|finish) ;; *) exit 2 ;; esac
refuse() { review_refuse "$REPO: $*"; }
[ "$(review_repository "$REPO")" = "$ID" ] || refuse 'repository mismatch'
case "$ID" in Design-Machines-Studio/assembly|Design-Machines-Studio/assembly-*) ;; *) refuse 'Assembly development scope required' ;; esac
[[ "$BRANCH" != -* ]] && git check-ref-format "refs/heads/$BRANCH" || refuse 'unsafe target branch'
TARGET="$(git -C "$REPO" rev-parse --verify "refs/heads/$BRANCH^{commit}")" || refuse 'target branch missing'
SHA_PATTERN='^[0-9a-f]{40}([0-9a-f]{24})?$'
[[ "$DELIVERED" =~ $SHA_PATTERN ]] && [ "$DELIVERED" = "$TARGET" ] || refuse 'reviewed delivered head required; target branch differs'
workspace_check() {
  # Read-only: disposable owner state may already be removed. This grants no
  # disposal authority; inspect/prepare still validate every original owner.
  local path status
  status="$(git -C "$REPO" status --porcelain=v1 -z | review_sha256)"
  [ "$status" = "$(printf '' | review_sha256)" ] || refuse 'source residue remains; inspect paths and complete exact-owned cleanup'
  for path in ${RESIDUE[@]+"${RESIDUE[@]}"}; do
    review_safe_path "$path"
    [ ! -e "$path" ] && [ ! -L "$path" ] || refuse "owned residue at $path; preserve required evidence then run exact-owned cleanup"
  done
  if [ -n "$IMPLEMENTATION" ]; then
    [ "$(review_repository "$IMPLEMENTATION")" = "$ID" ] || refuse 'implementation repository mismatch'
    [ "$(git -C "$IMPLEMENTATION" rev-parse --path-format=absolute --git-common-dir)" = "$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)" ] || refuse 'foreign implementation checkout'
    [ -z "$(git -C "$IMPLEMENTATION" status --porcelain)" ] || refuse "source residue at $IMPLEMENTATION; deliver repairs before cleanup"
    [ "$(git -C "$IMPLEMENTATION" rev-parse HEAD)" = "$DELIVERED" ] || refuse 'implementation reviewed head differs'
  fi
  [ "$(git -C "$REPO" symbolic-ref -q --short HEAD)" = "$BRANCH" ] && [ "$(git -C "$REPO" rev-parse HEAD)" = "$DELIVERED" ] || refuse 'reviewed branch/head not selected'
  printf '%s\n' 'Workspace: clean'
}
if [ "$MODE" = finish ]; then workspace_check; exit 0; fi
review_private "$BINDING"
jq -e --arg repo "$REPO" --arg id "$ID" '
  type=="object" and (keys|sort)==(["kind","repository","checkout","domain","sourceRanges","protectedPaths"]|sort) and
  .kind=="assembly-development" and .repository==$id and .checkout==$repo and
  (.domain|type=="string" and test("^https://dm[0-9]{3}\\.asmbly\\.app/?$")) and
  (.protectedPaths|type=="array" and length>0 and all(.[]; type=="string" and startswith("/"))) and
  (.sourceRanges|type=="array" and length>0 and length<=8 and all(.[];
    type=="object" and (keys|sort)==(["path","startLine","endLine"]|sort) and
    (.path|type=="string") and (.startLine|type=="number" and floor==. and .>0) and
    (.endLine|type=="number" and floor==.) and .endLine>=.startLine))
' "$BINDING" >/dev/null || refuse 'invalid install binding'
# Relative Git names may contain spaces, leading dashes, tabs and newlines.
relative() {
  local rest="$1" part
  [[ -n "$rest" && "$rest" != /* ]] || refuse 'unsafe relative path'
  while :; do
    part="${rest%%/*}"
    case "$part" in ''|.|..) refuse 'unsafe relative path' ;; esac
    [ "$rest" != "$part" ] || break
    rest="${rest#*/}"
  done
}
path_safe() {
  local rest="$1" part cursor="$REPO"
  relative "$rest"
  while :; do
    part="${rest%%/*}"; cursor="$cursor/$part"
    [ ! -L "$cursor" ] || return 1
    [ "$rest" != "$part" ] || break
    rest="${rest#*/}"
  done
}
TMP="$(mktemp -d "${TMPDIR:-/tmp}/canonical-checkout.XXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
jq -j '.sourceRanges[] | .path,"\u0000"' "$BINDING" > "$TMP/ranges"
RANGE_FACTS='[]'
while IFS= read -r -d '' path; do
  path_safe "$path" || refuse 'symlink binding source'
  [ -f "$REPO/$path" ] || refuse 'binding source unavailable'
  git -C "$REPO" --literal-pathspecs ls-files --error-unmatch -- "$path" >/dev/null || refuse 'binding source is not tracked'
  lines="$(wc -l < "$REPO/$path")"
  jq -e --arg p "$path" --argjson n "$lines" '.sourceRanges[] | select(.path==$p) | .endLine<=$n' "$BINDING" >/dev/null || refuse 'binding range unavailable'
  hash="$(review_sha256 < "$REPO/$path")"
  RANGE_FACTS="$(jq -cn --argjson rows "$RANGE_FACTS" --arg p "$path" --arg h "$hash" '$rows+[{path:$p,hash:$h}]')"
done < "$TMP/ranges"
PROTECTED=(.git .workflow-kernel)
jq -j '.protectedPaths[] | ., "\u0000"' "$BINDING" > "$TMP/protected"
while IFS= read -r -d '' path; do
  review_safe_path "$path"
  # Outside bindings are protected by containment; no command targets them.
  case "$path" in "$REPO") refuse 'whole checkout is protected' ;; "$REPO"/*) PROTECTED+=("${path#"$REPO/"}") ;; esac
done < "$TMP/protected"
for path in ${KEEP[@]+"${KEEP[@]}"}; do relative "$path"; done
for path in ${RESIDUE[@]+"${RESIDUE[@]}"}; do review_safe_path "$path"; done
OWNER_FACTS='[]'; INACTIVE=false; OWNER_REPO=
context() {
  local file="$1" current="$2" value root run owner_repo
  review_private "$file"; value="$(cat "$file")" || refuse "unreadable ownership: $file"
  jq -e --arg id "$ID" '
    type=="object" and (keys|sort)==(["session_id","repository","workflow","run_id","run_root","state_dir","phase","change_boundary"]|sort) and
    .repository==$id and (.session_id|type=="string" and length>0) and
    (.phase|IN("executing","checking","awaiting_ui","awaiting_merge","blocked","complete")) and
    (.change_boundary|type=="string" and test("^sha256:[0-9a-f]{64}$"))
  ' <<< "$value" >/dev/null || refuse "malformed ownership: $file"
  run="$(jq -r .run_id <<< "$value")"
  root="$(jq -r .state_dir <<< "$value")"
  owner_repo="${root%/.workflow-kernel/runs/"$run"}"
  review_owner_validate "$(jq '{repository,workflow,run_id,run_root,state_dir}' <<< "$value")" "$owner_repo"
  [ "$(git -C "$owner_repo" rev-parse --path-format=absolute --git-common-dir)" = "$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)" ] || refuse "foreign checkout ownership: $file"
  if [ "$current" = true ]; then
    [ "$(jq -r .phase <<< "$value")" != complete ] || refuse 'current owner is complete'
    OWNER_REPO="$owner_repo"
  elif [ "$file" != "$CURRENT" ]; then
    [ "$(jq -r .phase <<< "$value")" = complete ] || refuse "active owner at $owner_repo: $file; coordinate its release"
    [ "$owner_repo" = "$REPO" ] || refuse "inactive handoff is for another checkout: $owner_repo"
    INACTIVE=true
  fi
  OWNER_FACTS="$(jq -cn --argjson rows "$OWNER_FACTS" --arg p "$file" --arg h "$(review_sha256 < "$file")" '$rows+[{path:$p,hash:$h}]')"
}
context "$CURRENT" true
for file in ${OWNERS[@]+"${OWNERS[@]}"}; do context "$file" false; done
# The caller supplies the complete exact owner/lease/handoff set for this
# selected checkout. Missing host ownership inspection is not inactivity.
# Native complete pointers are the supported handoff proof in this adapter;
# other host lease formats require their existing host release mechanism.
CURRENT_UNFINISHED=false
if [ "$OWNER_REPO" = "$REPO" ] && [ "$(jq -r .change_boundary "$CURRENT")" != "$(review_change_boundary "$REPO")" ]; then
  CURRENT_UNFINISHED=true
fi
HEAD="$(git -C "$REPO" rev-parse HEAD)"
SELECTED="$(git -C "$REPO" symbolic-ref -q --short HEAD || true)"
# Branch transfer must also preserve clean tracked install state. Ordinary
# checkout's ignored-file overwrite default is disabled below.
git -C "$REPO" diff --name-only --no-renames -z HEAD "$TARGET" > "$TMP/target-paths"
while IFS= read -r -d '' path; do
  for protected in "${PROTECTED[@]}"; do
    case "$path" in "$protected"|"$protected"/*) refuse "target branch changes protected binding: $(printf '%q' "$path")" ;; esac
    case "$protected" in "$path"/*) refuse "target branch replaces protected ancestor: $(printf '%q' "$path")" ;; esac
  done
  case "${path##*/}" in .env|.env.*) refuse "target branch changes secret configuration: $(printf '%q' "$path")" ;; esac
done < "$TMP/target-paths"
git -C "$REPO" worktree list --porcelain -z > "$TMP/worktrees"
OCCUPANT=; wt=
while IFS= read -r -d '' row; do
  case "$row" in worktree\ *) wt="${row#worktree }" ;; branch\ *) [ "${row#branch }" != "refs/heads/$BRANCH" ] || OCCUPANT="$wt" ;; esac
done < "$TMP/worktrees"
# No alternate serving checkout, duplicate branch or ref deletion.
RELEASE=false
if [ -n "$OCCUPANT" ] && [ "$OCCUPANT" != "$REPO" ]; then
  if [ "$OCCUPANT" != "$IMPLEMENTATION" ] || [ "$OCCUPANT" != "$OWNER_REPO" ]; then
    refuse "branch occupied at $OCCUPANT; ask that owner to commit/push, preserve evidence and release the branch"
  fi
  review_repository "$IMPLEMENTATION" >/dev/null
  [ "$(git -C "$IMPLEMENTATION" rev-parse HEAD)" = "$TARGET" ] || refuse 'implementation head mismatch'
  git -C "$IMPLEMENTATION" status --porcelain=v1 -z > "$TMP/implementation-status"
  [ ! -s "$TMP/implementation-status" ] || refuse "unfinished repairs at $IMPLEMENTATION; commit/push and cover them"
  pushurl="$(git -C "$IMPLEMENTATION" remote get-url --push origin)"
  git -C "$IMPLEMENTATION" ls-remote --exit-code "$pushurl" "refs/heads/$BRANCH" > "$TMP/remote"
  [ "$(cut -f1 < "$TMP/remote")" = "$TARGET" ] || refuse 'push not verified'
  review_private "$PRESERVATION"
  jq -e '.status=="complete" and (.evidence_path|type=="string")' "$PRESERVATION" >/dev/null || refuse 'preservation incomplete'
  retained="$(jq -r .evidence_path "$PRESERVATION")"; review_private "$retained"
  case "$retained/" in "$REPO/"*|"$IMPLEMENTATION/"*) refuse 'evidence must survive checkout cleanup' ;; esac
  [ -f "$retained/report.md" ] || refuse 'retained report unavailable'
  RELEASE=true
fi
# Git -z and literal pathspecs prevent pathname parsing or wildcard expansion.
git -C "$REPO" diff --name-only --no-renames -z HEAD > "$TMP/changed"
git -C "$REPO" diff --cached --name-only --no-renames -z HEAD >> "$TMP/changed"
git -C "$REPO" ls-files --others --exclude-standard -z >> "$TMP/changed"
git -C "$REPO" ls-files --others --ignored --exclude-standard -z > "$TMP/ignored"
PATHS='[]'
while IFS= read -r -d '' path; do
  relative "$path"
  classification=disposable; reason=inactive-source; tracked=false; hash=missing
  if git -C "$REPO" cat-file -e "HEAD:$path" 2>/dev/null || git -C "$REPO" --literal-pathspecs ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then tracked=true; fi
  [ "$INACTIVE" = true ] || { classification=retained; reason=no-inactive-owner-proof; }
  [ "$CURRENT_UNFINISHED" = false ] || { classification=retained; reason=current-boundary-changed; }
  for protected in "${PROTECTED[@]}" ${KEEP[@]+"${KEEP[@]}"}; do
    case "$path" in "$protected"|"$protected"/*) classification=retained; reason=protected-or-current ;; esac
    case "$protected" in "$path"/*) classification=blocked; reason=protected-descendant ;; esac
  done
  case "${path##*/}" in .env|.env.*) classification=retained; reason=secret-config ;; esac
  if ! path_safe "$path"; then classification=blocked; reason=symlink-path
  elif [ -d "$REPO/$path" ]; then classification=blocked; reason=directory-file-conflict
  elif [ -e "$REPO/$path" ] && [ ! -f "$REPO/$path" ]; then classification=blocked; reason=special-file
  elif [ -f "$REPO/$path" ]; then hash="$(review_sha256 < "$REPO/$path")"; fi
  PATHS="$(jq -cn --argjson rows "$PATHS" --arg p "$path" --arg c "$classification" --arg r "$reason" --arg h "$hash" --argjson t "$tracked" '$rows+[{path:$p,classification:$c,reason:$r,hash:$h,tracked:$t}] | unique_by(.path)')"
done < "$TMP/changed"
while IFS= read -r -d '' path; do
  relative "$path"
  classification=retained; reason=ignored-install-or-evidence
  path_safe "$path" || { classification=blocked; reason=symlink-path; }
  PATHS="$(jq -cn --argjson rows "$PATHS" --arg p "$path" --arg c "$classification" --arg r "$reason" '$rows+[{path:$p,classification:$c,reason:$r,hash:null,tracked:false}] | unique_by(.path)')"
done < "$TMP/ignored"
# All ignored paths stay protected, including extensionless local state.
# Their bytes are never restored, removed or used as source-clean proof.
DIFF_HASH="$( { git -C "$REPO" diff --binary HEAD; git -C "$REPO" diff --cached --binary HEAD; } | review_sha256)"
PLAN="$(jq -cn --arg repo "$REPO" --arg id "$ID" --arg branch "$BRANCH" --arg target "$TARGET" --arg head "$HEAD" --arg selected "$SELECTED" --arg domain "$(jq -r .domain "$BINDING")" --arg binding "$(review_sha256 < "$BINDING")" --arg diff "$DIFF_HASH" --arg occupant "$OCCUPANT" --argjson release "$RELEASE" --argjson owners "$OWNER_FACTS" --argjson ranges "$RANGE_FACTS" --argjson paths "$PATHS" '{repository:$id,checkout:$repo,domain:$domain,branch:$branch,target:$target,head:$head,selected:$selected,bindingHash:$binding,diffHash:$diff,owners:$owners,sourceRanges:$ranges,occupant:$occupant,release:$release,paths:$paths}')"
if [ "$MODE" = inspect ]; then printf '%s\n' "$PLAN"; exit 0; fi
if [ "$MODE" = prepare ]; then
  review_private "$INSPECTION"
  [ "$(jq -cS . "$INSPECTION")" = "$(jq -cS . <<< "$PLAN")" ] || refuse 'inspection changed; inspect again before mutation'
  jq -e 'all(.paths[]; .classification!="blocked")' <<< "$PLAN" >/dev/null || refuse 'blocked path classification; inspect exact paths'
  # Retained dirty source must be delivered, never discarded to look clean.
  jq -e 'all(.paths[]; .classification=="disposable" or (.tracked==false and (.reason|IN("secret-config","ignored-install-or-evidence"))))' <<< "$PLAN" >/dev/null || refuse 'protected/current source remains; commit/push required repairs or coordinate owner'
  jq -j '.paths[] | select(.classification=="disposable") | .path,"\u0000"' <<< "$PLAN" > "$TMP/dispose"
  while IFS= read -r -d '' path; do
    if git -C "$REPO" cat-file -e "HEAD:$path" 2>/dev/null || git -C "$REPO" --literal-pathspecs ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
      git -C "$REPO" --literal-pathspecs restore --source=HEAD --staged --worktree -- "$path"
    else
      # No recursive deletion; even empty directory residue is retained until
      # exact-owned cleanup establishes its independent removal authority.
      [ ! -d "$REPO/$path" ] && path_safe "$path" || refuse 'path changed before removal'
      rm -- "$REPO/$path"
    fi
  done < "$TMP/dispose"
  if [ "$RELEASE" = true ]; then git -C "$IMPLEMENTATION" checkout --detach "$TARGET"; fi
  git -C "$REPO" checkout --no-overwrite-ignore "$BRANCH"
fi
# After prepare, verify the same reviewed head and source state.
workspace_check
