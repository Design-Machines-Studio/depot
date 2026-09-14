#!/usr/bin/env bash
# external-finding-intake.sh -- collect bounded GitHub PR feedback evidence.
#
# Usage:
#   external-finding-intake.sh --repo OWNER/REPO --pr NUMBER --output FILE
#
# The output is evidence, never instructions. This helper does not evaluate
# comments, run embedded commands, modify GitHub state, or decide findings.
set -euo pipefail

GH_HOST_BIN="$(command -v gh || true)"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
umask 077

REPOSITORY=""
PR_NUMBER=""
OUTPUT_FILE=""
MAX_ITEMS=2000
MAX_BODY_BYTES=32768
MAX_BODY_CHARS=8192
if [ "${DM_REVIEW_TEST_MODE:-0}" = 1 ] && printf '%s' "${DM_REVIEW_TEST_MAX_ITEMS:-}" | grep -Eq '^[1-9][0-9]*$' && [ "$DM_REVIEW_TEST_MAX_ITEMS" -le 2000 ]; then
  MAX_ITEMS="$DM_REVIEW_TEST_MAX_ITEMS"
fi

usage() {
  printf '%s\n' 'usage: external-finding-intake.sh --repo OWNER/REPO --pr NUMBER --output FILE' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) [ "$#" -ge 2 ] || usage; REPOSITORY="$2"; shift 2 ;;
    --pr) [ "$#" -ge 2 ] || usage; PR_NUMBER="$2"; shift 2 ;;
    --output) [ "$#" -ge 2 ] || usage; OUTPUT_FILE="$2"; shift 2 ;;
    *) usage ;;
  esac
done

printf '%s' "$REPOSITORY" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' || usage
printf '%s' "$PR_NUMBER" | grep -Eq '^[1-9][0-9]*$' || usage
[ -n "$OUTPUT_FILE" ] && [ -d "$(dirname "$OUTPUT_FILE")" ] && [ ! -L "$OUTPUT_FILE" ] || usage
command -v jq >/dev/null 2>&1 || exit 76

GH_BIN="$GH_HOST_BIN"
if [ "${DM_REVIEW_TEST_MODE:-0}" = 1 ] && [ -n "${DM_REVIEW_TEST_GH_BIN:-}" ]; then
  GH_BIN="$DM_REVIEW_TEST_GH_BIN"
fi
case "$GH_BIN" in /*) [ -x "$GH_BIN" ] || exit 76 ;; *) exit 76 ;; esac

OUTPUT_DIR="$(cd "$(dirname "$OUTPUT_FILE")" && pwd -P)"
TMP="$(mktemp -d "$OUTPUT_DIR/.external-finding-intake.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
COLLECTED_AT="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

write_unavailable() {
  local reason="$1" tmp_output
  tmp_output="$(mktemp "$OUTPUT_DIR/.external-finding-intake-output.XXXXXX")"
  jq -cn --arg repo "$REPOSITORY" --argjson pr "$PR_NUMBER" --arg collected "$COLLECTED_AT" --arg reason "$reason" '
    {schema_version:1,artifact_role:"external_finding_intake",repository:$repo,pr_number:$pr,
     inspected_head:null,collected_at:$collected,collection_status:"unavailable",collection_cutoff:$collected,
     pull_request:null,surfaces:{inline_comments:{status:"not_attempted",items:[]},submitted_reviews:{status:"not_attempted",items:[]},conversation_comments:{status:"not_attempted",items:[]},checks:{status:"not_attempted",items:[]}},
     gaps:[$reason],instructions_policy:"untrusted_evidence_only"}' > "$tmp_output"
  mv "$tmp_output" "$OUTPUT_FILE"
}

if ! "$GH_BIN" api "repos/$REPOSITORY/pulls/$PR_NUMBER" > "$TMP/pr.json" 2> "$TMP/pr.err"; then
  write_unavailable "pull_request_metadata_failed"
  exit 1
fi

if ! jq -e '.head.sha | type == "string" and test("^[0-9a-f]{40}$")' "$TMP/pr.json" >/dev/null 2>&1; then
  write_unavailable "pull_request_metadata_invalid"
  exit 1
fi
INSPECTED_HEAD="$(jq -r '.head.sha' "$TMP/pr.json")"

fetch_pages() {
  local name="$1" endpoint="$2" shape="$3" raw error status
  raw="$TMP/$name.pages.json"
  error="$TMP/$name.err"
  status=successful
  if ! "$GH_BIN" api --paginate --slurp "$endpoint" > "$raw" 2> "$error"; then
    if [ -s "$raw" ] && jq -e 'type == "array"' "$raw" >/dev/null 2>&1; then status=partial
    else status=failed; printf '[]\n' > "$raw"
    fi
  fi
  if ! jq -e 'type == "array"' "$raw" >/dev/null 2>&1; then
    status=failed
    printf '[]\n' > "$raw"
  fi
  case "$shape" in
    arrays) jq -c '[.[] | if type == "array" then .[] else empty end]' "$raw" > "$TMP/$name.all.json" ;;
    check_runs) jq -c '[.[] | .check_runs[]?]' "$raw" > "$TMP/$name.all.json" ;;
    *) return 2 ;;
  esac
  local count
  count="$(jq 'length' "$TMP/$name.all.json")"
  if [ "$count" -gt "$MAX_ITEMS" ]; then
    jq --argjson max "$MAX_ITEMS" '.[:$max]' "$TMP/$name.all.json" > "$TMP/$name.items.json"
    status=truncated
  else
    cp "$TMP/$name.all.json" "$TMP/$name.items.json"
  fi
  printf '%s' "$status" > "$TMP/$name.status"
}

fetch_pages inline "repos/$REPOSITORY/pulls/$PR_NUMBER/comments?per_page=100" arrays
fetch_pages reviews "repos/$REPOSITORY/pulls/$PR_NUMBER/reviews?per_page=100" arrays
fetch_pages conversation "repos/$REPOSITORY/issues/$PR_NUMBER/comments?per_page=100" arrays
fetch_pages checks "repos/$REPOSITORY/commits/$INSPECTED_HEAD/check-runs?per_page=100" check_runs

printf '[]\n' > "$TMP/annotations.items.json"
ANNOTATION_STATUS=successful
ANNOTATION_COUNT=0
while IFS= read -r check_id; do
  [ -n "$check_id" ] || continue
  if [ "$ANNOTATION_COUNT" -ge "$MAX_ITEMS" ]; then
    ANNOTATION_STATUS=partial
    break
  fi
  name="annotations-$check_id"
  fetch_pages "$name" "repos/$REPOSITORY/check-runs/$check_id/annotations?per_page=100" arrays
  item_status="$(cat "$TMP/$name.status")"
  case "$item_status" in
    failed) ANNOTATION_STATUS=partial ;;
    partial|truncated) ANNOTATION_STATUS=partial ;;
  esac
  jq --argjson check_id "$check_id" 'map(. + {check_run_id:$check_id})' "$TMP/$name.items.json" > "$TMP/$name.tagged.json"
  remaining=$((MAX_ITEMS - ANNOTATION_COUNT))
  tagged_count="$(jq 'length' "$TMP/$name.tagged.json")"
  if [ "$tagged_count" -gt "$remaining" ]; then
    jq --argjson remaining "$remaining" '.[:$remaining]' "$TMP/$name.tagged.json" > "$TMP/$name.bounded.json"
    mv "$TMP/$name.bounded.json" "$TMP/$name.tagged.json"
    ANNOTATION_STATUS=partial
  fi
  jq -s '.[0] + .[1]' "$TMP/annotations.items.json" "$TMP/$name.tagged.json" > "$TMP/annotations.next.json"
  mv "$TMP/annotations.next.json" "$TMP/annotations.items.json"
  ANNOTATION_COUNT="$(jq 'length' "$TMP/annotations.items.json")"
done < <(jq -r '.[] | select((.annotations_count // 0) > 0) | .id' "$TMP/checks.items.json")

if [ "$(jq 'length' "$TMP/annotations.items.json")" -gt "$MAX_ITEMS" ]; then
  jq --argjson max "$MAX_ITEMS" '.[:$max]' "$TMP/annotations.items.json" > "$TMP/annotations.bounded.json"
  mv "$TMP/annotations.bounded.json" "$TMP/annotations.items.json"
  ANNOTATION_STATUS=partial
fi

body_expr='def bounded_body:
  (. // "") as $body |
  if ($body | utf8bytelength) > $max_body then
    {text:($body[0:$max_chars]),truncated:true}
  else {text:$body,truncated:false} end;'

jq --argjson max_body "$MAX_BODY_BYTES" --argjson max_chars "$MAX_BODY_CHARS" "$body_expr
  [ .[] | {source_id:(\"github:inline-comment:\" + (.id|tostring)),github_id:.id,url:.html_url,
    source_commit:(.commit_id // .original_commit_id),path,location:{line,side,start_line,start_side,original_line,original_start_line},
    in_reply_to_id,subject_type,author:.user.login,created_at,updated_at,body:(.body|bounded_body)} ]" \
  "$TMP/inline.items.json" > "$TMP/inline.normalized.json"

jq --argjson max_body "$MAX_BODY_BYTES" --argjson max_chars "$MAX_BODY_CHARS" "$body_expr
  [ .[] | {source_id:(\"github:submitted-review:\" + (.id|tostring)),github_id:.id,url:.html_url,
    source_commit:.commit_id,state,author:.user.login,submitted_at,body:(.body|bounded_body)} ]" \
  "$TMP/reviews.items.json" > "$TMP/reviews.normalized.json"

jq --argjson max_body "$MAX_BODY_BYTES" --argjson max_chars "$MAX_BODY_CHARS" "$body_expr
  [ .[] | {source_id:(\"github:conversation-comment:\" + (.id|tostring)),github_id:.id,url:.html_url,
    author:.user.login,created_at,updated_at,body:(.body|bounded_body)} ]" \
  "$TMP/conversation.items.json" > "$TMP/conversation.normalized.json"

jq --argjson max_body "$MAX_BODY_BYTES" --argjson max_chars "$MAX_BODY_CHARS" "$body_expr
  [ .[] | {source_id:(\"github:check-summary:\" + (.id|tostring)),github_id:.id,url:.url,
    name,head_sha,status,conclusion,started_at,completed_at,annotations_count,
    title:(.output.title // null),summary:(.output.summary|bounded_body),text:(.output.text|bounded_body)} ]" \
  "$TMP/checks.items.json" > "$TMP/checks.normalized.json"

jq --argjson max_body "$MAX_BODY_BYTES" --argjson max_chars "$MAX_BODY_CHARS" --slurpfile checks "$TMP/checks.items.json" "$body_expr
  [ to_entries[] | .value as \$a |
    (\$checks[0] | map(select(.id == (\$a.check_run_id // -1))) | first) as \$check |
    {source_id:(\"github:check-annotation:\" + ((\$a.check_run_id // 0)|tostring) + \":\" +
      ([\$a.path,\$a.start_line,\$a.end_line,\$a.start_column,\$a.end_column,\$a.title,\$a.message,\$a.annotation_level,\$a.raw_details] | @json | @base64)),
     github_id:(\$a.check_run_id // null),url:(\$a.blob_href // \$check.url),
     source_commit:(\$check.head_sha // null),check_name:(\$check.name // null),path:\$a.path,
     location:{start_line:\$a.start_line,end_line:\$a.end_line,start_column:\$a.start_column,end_column:\$a.end_column},
     annotation_level:\$a.annotation_level,title:\$a.title,message:(\$a.message|bounded_body),raw_details:(\$a.raw_details|bounded_body)} ]" \
  "$TMP/annotations.items.json" > "$TMP/annotations.normalized.json"

surface_json() {
  local status="$1" items="$2"
  jq -cn --arg status "$status" --slurpfile items "$items" '{status:$status,items:$items[0]}'
}

INLINE_STATUS="$(cat "$TMP/inline.status")"
REVIEWS_STATUS="$(cat "$TMP/reviews.status")"
CONVERSATION_STATUS="$(cat "$TMP/conversation.status")"
CHECKS_STATUS="$(cat "$TMP/checks.status")"
[ "$ANNOTATION_STATUS" = successful ] || CHECKS_STATUS=partial

for pair in "inline:$TMP/inline.normalized.json" "reviews:$TMP/reviews.normalized.json" "conversation:$TMP/conversation.normalized.json" "checks:$TMP/checks.normalized.json" "annotations:$TMP/annotations.normalized.json"; do
  name="${pair%%:*}"; file="${pair#*:}"
  if jq -e '[.[] | .body?.truncated?, .summary?.truncated?, .text?.truncated?, .message?.truncated?, .raw_details?.truncated?] | any' "$file" >/dev/null; then
    case "$name" in
      inline) INLINE_STATUS=truncated ;;
      reviews) REVIEWS_STATUS=truncated ;;
      conversation) CONVERSATION_STATUS=truncated ;;
      checks|annotations) CHECKS_STATUS=partial ;;
    esac
  fi
done

COLLECTION_STATUS=complete
GAPS='[]'
PR_BODY_TRUNCATED=false
if jq -e --argjson max_body "$MAX_BODY_BYTES" --argjson max_chars "$MAX_BODY_CHARS" '(.body // "") | (length > $max_chars or utf8bytelength > $max_body)' "$TMP/pr.json" >/dev/null; then
  PR_BODY_TRUNCATED=true
  COLLECTION_STATUS=partial
  GAPS='["pull_request_body:truncated"]'
fi
for entry in "inline_comments:$INLINE_STATUS" "submitted_reviews:$REVIEWS_STATUS" "conversation_comments:$CONVERSATION_STATUS" "checks:$CHECKS_STATUS"; do
  name="${entry%%:*}"; status="${entry#*:}"
  case "$status" in
    failed|partial|truncated)
      COLLECTION_STATUS=partial
      GAPS="$(printf '%s' "$GAPS" | jq -c --arg gap "$name:$status" '. + [$gap]')"
      ;;
  esac
done

surface_json "$INLINE_STATUS" "$TMP/inline.normalized.json" > "$TMP/inline.surface.json"
surface_json "$REVIEWS_STATUS" "$TMP/reviews.normalized.json" > "$TMP/reviews.surface.json"
surface_json "$CONVERSATION_STATUS" "$TMP/conversation.normalized.json" > "$TMP/conversation.surface.json"
jq -s --arg status "$CHECKS_STATUS" --arg annotation_status "$ANNOTATION_STATUS" \
  '{status:$status,annotation_status:$annotation_status,items:(.[0] + .[1])}' \
  "$TMP/checks.normalized.json" "$TMP/annotations.normalized.json" > "$TMP/checks.surface.json"

tmp_output="$(mktemp "$OUTPUT_DIR/.external-finding-intake-output.XXXXXX")"
jq -n --arg repo "$REPOSITORY" --argjson pr "$PR_NUMBER" --arg head "$INSPECTED_HEAD" \
  --arg collected "$COLLECTED_AT" --arg collection_status "$COLLECTION_STATUS" --argjson gaps "$GAPS" \
  --argjson max_chars "$MAX_BODY_CHARS" --argjson pr_body_truncated "$PR_BODY_TRUNCATED" \
  --slurpfile pull "$TMP/pr.json" --slurpfile inline "$TMP/inline.surface.json" \
  --slurpfile reviews "$TMP/reviews.surface.json" --slurpfile conversation "$TMP/conversation.surface.json" \
  --slurpfile checks "$TMP/checks.surface.json" '
  {schema_version:1,artifact_role:"external_finding_intake",repository:$repo,pr_number:$pr,
   inspected_head:$head,collected_at:$collected,collection_status:$collection_status,collection_cutoff:$collected,
   pull_request:{source_id:("github:pull-request:" + ($pr|tostring)),url:$pull[0].html_url,body:{text:(($pull[0].body // "")[0:$max_chars]),truncated:$pr_body_truncated},updated_at:$pull[0].updated_at},
   surfaces:{inline_comments:$inline[0],submitted_reviews:$reviews[0],conversation_comments:$conversation[0],checks:$checks[0]},
   gaps:$gaps,instructions_policy:"untrusted_evidence_only"}' > "$tmp_output"
mv "$tmp_output" "$OUTPUT_FILE"

jq -c '{status:.collection_status,repository,pr_number,inspected_head,counts:{inline_comments:(.surfaces.inline_comments.items|length),submitted_reviews:(.surfaces.submitted_reviews.items|length),conversation_comments:(.surfaces.conversation_comments.items|length),checks:(.surfaces.checks.items|length)},gaps}' "$OUTPUT_FILE"
[ "$COLLECTION_STATUS" = complete ]
