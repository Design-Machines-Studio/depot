#!/usr/bin/env bash
# implementation-origin.sh -- private exact-diff implementation origin record.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
umask 077

MODE="${1:-}"
[ "$#" -gt 0 ] && shift || true
REPOSITORY=""
BASE=""
HEAD_REF=""
ORIGIN_CLASS=""
DECLARATION_SOURCE=""
OUTPUT=""
ORIGIN_FILE=""
RECEIPT_DIR=""
RECEIPT_IDS=()
CONTRIBUTOR_ORIGINS=()
RECEIPT_COUNT=0
CONTRIBUTOR_COUNT=0

usage() {
  printf '%s\n' 'usage: implementation-origin create --repository PATH --base REF --head REF --origin-class CLASS --declaration-source SOURCE --output FILE [--receipt-dir DIR --receipt-id ID ...] [--contributor-origin codex-host-authored|claude-host-authored ...]' >&2
  printf '%s\n' '       implementation-origin verify --repository PATH --file FILE [--receipt-dir DIR]' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repository) [ "$#" -ge 2 ] || usage; REPOSITORY="$2"; shift 2 ;;
    --base) [ "$#" -ge 2 ] || usage; BASE="$2"; shift 2 ;;
    --head) [ "$#" -ge 2 ] || usage; HEAD_REF="$2"; shift 2 ;;
    --origin-class) [ "$#" -ge 2 ] || usage; ORIGIN_CLASS="$2"; shift 2 ;;
    --declaration-source) [ "$#" -ge 2 ] || usage; DECLARATION_SOURCE="$2"; shift 2 ;;
    --output) [ "$#" -ge 2 ] || usage; OUTPUT="$2"; shift 2 ;;
    --file) [ "$#" -ge 2 ] || usage; ORIGIN_FILE="$2"; shift 2 ;;
    --receipt-dir) [ "$#" -ge 2 ] || usage; RECEIPT_DIR="$2"; shift 2 ;;
    --receipt-id) [ "$#" -ge 2 ] || usage; RECEIPT_IDS+=("$2"); RECEIPT_COUNT=$((RECEIPT_COUNT + 1)); shift 2 ;;
    --contributor-origin) [ "$#" -ge 2 ] || usage; CONTRIBUTOR_ORIGINS+=("$2"); CONTRIBUTOR_COUNT=$((CONTRIBUTOR_COUNT + 1)); shift 2 ;;
    *) usage ;;
  esac
done

command -v git >/dev/null 2>&1 && command -v jq >/dev/null 2>&1 || usage

sha256_stream() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | awk '{print $1}'
  else shasum -a 256 | awk '{print $1}'
  fi
}

repository_root() {
  local root
  root="$(git -C "$REPOSITORY" rev-parse --show-toplevel 2>/dev/null)" || return 1
  (cd "$root" && pwd -P)
}

repository_digest() {
  local root="$1" identity
  identity="$(git -C "$root" config --get remote.origin.url 2>/dev/null || true)"
  if [ -z "$identity" ]; then
    identity="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 1
  fi
  printf '%s' "$identity" | sha256_stream
}

diff_digest() {
  local root="$1" base_commit="$2" path
  {
    git -C "$root" diff --binary --full-index --no-ext-diff "$base_commit" --
    git -C "$root" ls-files --others --exclude-standard -z |
      while IFS= read -r -d '' path; do
        printf 'untracked %s\0' "$path"
        if [ -f "$root/$path" ] && [ ! -L "$root/$path" ]; then
          sha256_file "$root/$path"
        else
          printf '%s\n' unsupported
        fi
      done
  } | sha256_stream
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'
  fi
}

receipt_family() {
  local receipt_id="$1" candidate match=""
  case "$receipt_id" in *[!a-z0-9-]*|'') return 1 ;; esac
  [ -n "$RECEIPT_DIR" ] && [ -d "$RECEIPT_DIR" ] && [ ! -L "$RECEIPT_DIR" ] || return 1
  for candidate in "$RECEIPT_DIR"/*; do
    [ -f "$candidate" ] && [ ! -L "$candidate" ] || continue
    if jq -e --arg receipt_id "$receipt_id" '
      .receiptId == $receipt_id and .probeSource == "live" and
      .transportStub == false and (.served.family | type) == "string"
    ' "$candidate" >/dev/null 2>&1; then
      match="$candidate"
      break
    fi
  done
  [ -n "$match" ] || return 1
  jq -r '.served.family' "$match"
}

derive_families() {
  local origin_class="$1" contributor_json="$2" receipt_json="$3" family receipt_id
  local families='[]'
  case "$origin_class" in
    human-authored|unknown) ;;
    codex-host-authored) families='["openai"]' ;;
    claude-host-authored) families='["anthropic"]' ;;
    receipted-model-work|mixed-known)
      while IFS= read -r contributor; do
        case "$contributor" in
          codex-host-authored) family=openai ;;
          claude-host-authored) family=anthropic ;;
          *) return 1 ;;
        esac
        families="$(printf '%s' "$families" | jq -c --arg family "$family" '. + [$family] | unique | sort')"
      done < <(printf '%s' "$contributor_json" | jq -r '.[]')
      while IFS= read -r receipt_id; do
        family="$(receipt_family "$receipt_id")" || return 1
        families="$(printf '%s' "$families" | jq -c --arg family "$family" '. + [$family] | unique | sort')"
      done < <(printf '%s' "$receipt_json" | jq -r '.[]')
      ;;
    *) return 1 ;;
  esac
  case "$origin_class" in
    receipted-model-work) [ "$(printf '%s' "$receipt_json" | jq 'length')" -gt 0 ] || return 1 ;;
    mixed-known) [ "$(printf '%s' "$families" | jq 'length')" -gt 1 ] || return 1 ;;
    human-authored|codex-host-authored|claude-host-authored|unknown)
      [ "$(printf '%s' "$contributor_json" | jq 'length')" -eq 0 ] &&
        [ "$(printf '%s' "$receipt_json" | jq 'length')" -eq 0 ] || return 1
      ;;
  esac
  printf '%s\n' "$families"
}

case "$MODE" in
  create)
    [ -n "$REPOSITORY" ] && [ -n "$BASE" ] && [ -n "$HEAD_REF" ] &&
      [ -n "$ORIGIN_CLASS" ] && [ -n "$DECLARATION_SOURCE" ] && [ -n "$OUTPUT" ] || usage
    case "$DECLARATION_SOURCE" in *[!a-z0-9-]*|'') usage ;; esac
    [ -d "$(dirname "$OUTPUT")" ] && [ ! -L "$OUTPUT" ] || usage
    ROOT="$(repository_root)" || usage
    BASE_COMMIT="$(git -C "$ROOT" rev-parse --verify "$BASE^{commit}" 2>/dev/null)" || usage
    HEAD_COMMIT="$(git -C "$ROOT" rev-parse --verify "$HEAD_REF^{commit}" 2>/dev/null)" || usage
    [ "$(git -C "$ROOT" rev-parse --verify HEAD)" = "$HEAD_COMMIT" ] || usage
    CONTRIBUTOR_JSON='[]'
    if [ "$CONTRIBUTOR_COUNT" -gt 0 ]; then
      for contributor in "${CONTRIBUTOR_ORIGINS[@]}"; do
        CONTRIBUTOR_JSON="$(printf '%s' "$CONTRIBUTOR_JSON" | jq -c --arg value "$contributor" '. + [$value] | unique | sort')"
      done
    fi
    RECEIPT_JSON='[]'
    if [ "$RECEIPT_COUNT" -gt 0 ]; then
      for receipt_id in "${RECEIPT_IDS[@]}"; do
        RECEIPT_JSON="$(printf '%s' "$RECEIPT_JSON" | jq -c --arg value "$receipt_id" '. + [$value] | unique | sort')"
      done
    fi
    FAMILIES="$(derive_families "$ORIGIN_CLASS" "$CONTRIBUTOR_JSON" "$RECEIPT_JSON")" || usage
    REPOSITORY_DIGEST="sha256:$(repository_digest "$ROOT")" || usage
    DIFF_DIGEST="sha256:$(diff_digest "$ROOT" "$BASE_COMMIT")" || usage
    ORIGIN_ID="origin-$(printf '%s' "$REPOSITORY_DIGEST|$BASE_COMMIT|$HEAD_COMMIT|$DIFF_DIGEST|$ORIGIN_CLASS|$FAMILIES|$DECLARATION_SOURCE" | sha256_stream | cut -c1-24)"
    TMP_OUTPUT="$(mktemp "$(dirname "$OUTPUT")/.implementation-origin.XXXXXX")" || exit 1
    trap 'rm -f "$TMP_OUTPUT"' EXIT
    jq -n --arg origin_id "$ORIGIN_ID" --arg repository_digest "$REPOSITORY_DIGEST" \
      --arg base "$BASE_COMMIT" --arg head "$HEAD_COMMIT" --arg diff_digest "$DIFF_DIGEST" \
      --arg origin_class "$ORIGIN_CLASS" --arg declaration_source "$DECLARATION_SOURCE" \
      --argjson families "$FAMILIES" --argjson contributor_origins "$CONTRIBUTOR_JSON" \
      --argjson receipt_ids "$RECEIPT_JSON" \
      '{schemaVersion:1,originId:$origin_id,repositoryDigest:$repository_digest,base:$base,head:$head,
        diffDigest:$diff_digest,originClass:$origin_class,contributingFamilies:$families,
        contributorOrigins:$contributor_origins,receiptIds:$receipt_ids,declarationSource:$declaration_source}' > "$TMP_OUTPUT"
    chmod 600 "$TMP_OUTPUT"
    mv "$TMP_OUTPUT" "$OUTPUT"
    trap - EXIT
    printf '%s\n' "$ORIGIN_ID"
    ;;
  verify)
    [ -n "$REPOSITORY" ] && [ -n "$ORIGIN_FILE" ] && [ -r "$ORIGIN_FILE" ] && [ ! -L "$ORIGIN_FILE" ] || usage
    jq -e '
      type == "object" and .schemaVersion == 1 and
      ((keys | sort) == (["base","contributingFamilies","contributorOrigins","declarationSource","diffDigest","head","originClass","originId","receiptIds","repositoryDigest","schemaVersion"] | sort)) and
      (.originId | test("^origin-[a-f0-9]{24}$")) and
      (.repositoryDigest | test("^sha256:[a-f0-9]{64}$")) and
      (.base | test("^[a-f0-9]{40,64}$")) and (.head | test("^[a-f0-9]{40,64}$")) and
      (.diffDigest | test("^sha256:[a-f0-9]{64}$")) and
      (.originClass | IN("receipted-model-work","human-authored","codex-host-authored","claude-host-authored","mixed-known","unknown")) and
      (.contributingFamilies | type == "array") and (.contributorOrigins | type == "array") and
      (.receiptIds | type == "array") and (.declarationSource | test("^[a-z0-9][a-z0-9-]*$"))
    ' "$ORIGIN_FILE" >/dev/null || usage
    ROOT="$(repository_root)" || usage
    CURRENT_HEAD="$(git -C "$ROOT" rev-parse --verify HEAD)" || usage
    RECORDED_HEAD="$(jq -r '.head' "$ORIGIN_FILE")"
    [ "$CURRENT_HEAD" = "$RECORDED_HEAD" ] || { printf '%s\n' 'implementation-origin: stale head' >&2; exit 3; }
    RECORDED_BASE="$(jq -r '.base' "$ORIGIN_FILE")"
    git -C "$ROOT" cat-file -e "$RECORDED_BASE^{commit}" 2>/dev/null || usage
    [ "sha256:$(repository_digest "$ROOT")" = "$(jq -r '.repositoryDigest' "$ORIGIN_FILE")" ] || { printf '%s\n' 'implementation-origin: repository mismatch' >&2; exit 3; }
    [ "sha256:$(diff_digest "$ROOT" "$RECORDED_BASE")" = "$(jq -r '.diffDigest' "$ORIGIN_FILE")" ] || { printf '%s\n' 'implementation-origin: stale diff' >&2; exit 3; }
    ORIGIN_CLASS="$(jq -r '.originClass' "$ORIGIN_FILE")"
    CONTRIBUTOR_JSON="$(jq -c '.contributorOrigins' "$ORIGIN_FILE")"
    RECEIPT_JSON="$(jq -c '.receiptIds' "$ORIGIN_FILE")"
    FAMILIES="$(derive_families "$ORIGIN_CLASS" "$CONTRIBUTOR_JSON" "$RECEIPT_JSON")" || usage
    [ "$FAMILIES" = "$(jq -c '.contributingFamilies | unique | sort' "$ORIGIN_FILE")" ] || usage
    EXPECTED_ID="origin-$(printf '%s' "$(jq -r '.repositoryDigest' "$ORIGIN_FILE")|$RECORDED_BASE|$RECORDED_HEAD|$(jq -r '.diffDigest' "$ORIGIN_FILE")|$ORIGIN_CLASS|$FAMILIES|$(jq -r '.declarationSource' "$ORIGIN_FILE")" | sha256_stream | cut -c1-24)"
    [ "$EXPECTED_ID" = "$(jq -r '.originId' "$ORIGIN_FILE")" ] || usage
    KNOWN=true
    [ "$ORIGIN_CLASS" = unknown ] && KNOWN=false
    HUMAN=false
    [ "$ORIGIN_CLASS" = human-authored ] && HUMAN=true
    jq -cn --arg origin_id "$(jq -r '.originId' "$ORIGIN_FILE")" --arg origin_class "$ORIGIN_CLASS" \
      --argjson known "$KNOWN" --argjson human "$HUMAN" --argjson families "$FAMILIES" \
      '{originId:$origin_id,originClass:$origin_class,known:$known,humanAuthored:$human,excludedFamilies:$families}'
    ;;
  *) usage ;;
esac
