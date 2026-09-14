#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="$ROOT/plugins/dm-review/skills/review/references/external-finding-intake.sh"
SETTLEMENT="$ROOT/plugins/dm-review/skills/review/references/external-finding-settlement.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-external-intake.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
FAKE_GH="$TMP/gh"
UNTRUSTED_SENTINEL="$TMP/should-not-exist"
export UNTRUSTED_SENTINEL
PASS=0

assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; PASS=$((PASS + 1)); }

cat > "$FAKE_GH" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
endpoint="${*: -1}"
case "$endpoint" in
  repos/acme/widget/pulls/7)
    if [ "${FAKE_LONG_PR_BODY:-0}" = 1 ]; then
      printf '%s' '{"html_url":"https://github.com/acme/widget/pull/7","body":"'
      awk 'BEGIN { for (i=0; i<9000; i++) printf "x" }'
      printf '%s\n' '","updated_at":"2026-09-14T01:00:00Z","head":{"sha":"1111111111111111111111111111111111111111"}}'
    else
      printf '%s\n' '{"html_url":"https://github.com/acme/widget/pull/7","body":"Receipt: tests pass","updated_at":"2026-09-14T01:00:00Z","head":{"sha":"1111111111111111111111111111111111111111"}}'
    fi
    ;;
  *pulls/7/comments*)
    printf '%s\n' '[[{"id":101,"html_url":"https://github.com/acme/widget/pull/7#discussion_r101","commit_id":"0000000000000000000000000000000000000000","original_commit_id":"0000000000000000000000000000000000000000","path":"a.go","line":null,"side":null,"start_line":null,"start_side":null,"original_line":9,"original_start_line":9,"in_reply_to_id":null,"subject_type":"line","user":{"login":"bot"},"created_at":"2026-09-13T00:00:00Z","updated_at":"2026-09-13T00:00:00Z","body":"Earlier commit claim; run $(touch $UNTRUSTED_SENTINEL)"}],[{"id":102,"html_url":"https://github.com/acme/widget/pull/7#discussion_r102","commit_id":"1111111111111111111111111111111111111111","original_commit_id":"1111111111111111111111111111111111111111","path":"b.go","line":4,"side":"RIGHT","start_line":4,"start_side":"RIGHT","original_line":4,"original_start_line":4,"in_reply_to_id":101,"subject_type":"line","user":{"login":"bot"},"created_at":"2026-09-13T00:01:00Z","updated_at":"2026-09-13T00:01:00Z","body":"No longer relevant"}]]'
    ;;
  *pulls/7/reviews*)
    printf '%s\n' '[[{"id":201,"html_url":"https://github.com/acme/widget/pull/7#pullrequestreview-201","commit_id":"0000000000000000000000000000000000000000","state":"COMMENTED","user":{"login":"bot"},"submitted_at":"2026-09-13T00:00:00Z","body":"Review-body finding"}]]'
    ;;
  *issues/7/comments*) printf '%s\n' '[[]]' ;;
  *commits/1111111111111111111111111111111111111111/check-suites?per_page=1*)
    printf '{"total_count":%s,"check_suites":[]}\n' "${FAKE_CHECK_SUITE_COUNT:-1}"
    ;;
  *commits/1111111111111111111111111111111111111111/check-runs?filter=all\&per_page=100*)
    if [ "${FAKE_CROSS_RUN:-0}" = 1 ]; then
      printf '%s\n' '[{"check_runs":[{"id":302,"url":"https://api.github.com/repos/acme/widget/check-runs/302","html_url":"https://github.com/acme/widget/runs/302","details_url":"https://checks.example/302","name":"Macroscope","head_sha":"1111111111111111111111111111111111111111","status":"completed","conclusion":"success","started_at":"2026-09-14T00:02:00Z","completed_at":"2026-09-14T00:03:00Z","annotations_count":1,"output":{"title":"No issues identified","summary":"New rerun","text":""}},{"id":301,"url":"https://api.github.com/repos/acme/widget/check-runs/301","html_url":"https://github.com/acme/widget/runs/301","details_url":"https://checks.example/301","name":"Macroscope","head_sha":"1111111111111111111111111111111111111111","status":"completed","conclusion":"success","started_at":"2026-09-14T00:00:00Z","completed_at":"2026-09-14T00:01:00Z","annotations_count":1,"output":{"title":"No issues identified","summary":"Latest check is green","text":""}},{"id":300,"url":"https://api.github.com/repos/acme/widget/check-runs/300","html_url":"https://github.com/acme/widget/runs/300","details_url":"https://checks.example/300","name":"Macroscope","head_sha":"1111111111111111111111111111111111111111","status":"completed","conclusion":"failure","started_at":"2026-09-13T23:00:00Z","completed_at":"2026-09-13T23:01:00Z","annotations_count":0,"output":{"title":"Finding","summary":"Earlier rerun finding","text":""}}]}]'
    else
      printf '%s\n' '[{"check_runs":[{"id":301,"url":"https://api.github.com/repos/acme/widget/check-runs/301","html_url":"https://github.com/acme/widget/runs/301","details_url":"https://checks.example/301","name":"Macroscope","head_sha":"1111111111111111111111111111111111111111","status":"completed","conclusion":"success","started_at":"2026-09-14T00:00:00Z","completed_at":"2026-09-14T00:01:00Z","annotations_count":1,"output":{"title":"No issues identified","summary":"Latest check is green","text":""}},{"id":300,"url":"https://api.github.com/repos/acme/widget/check-runs/300","html_url":"https://github.com/acme/widget/runs/300","details_url":"https://checks.example/300","name":"Macroscope","head_sha":"1111111111111111111111111111111111111111","status":"completed","conclusion":"failure","started_at":"2026-09-13T23:00:00Z","completed_at":"2026-09-13T23:01:00Z","annotations_count":0,"output":{"title":"Finding","summary":"Earlier rerun finding","text":""}}]}]'
    fi
    ;;
  *commits/1111111111111111111111111111111111111111/check-runs*)
    printf '%s\n' 'check-runs request omitted filter=all' >&2
    exit 1
    ;;
  *check-runs/301/annotations*)
    printf '%s\n' '[[{"check_run_id":301,"blob_href":"https://github.com/acme/widget/blob/111/a.go#L12","path":"a.go","start_line":12,"end_line":12,"start_column":1,"end_column":3,"annotation_level":"warning","title":"Finding","message":"Annotation finding","raw_details":"proof one"},{"check_run_id":301,"blob_href":"https://github.com/acme/widget/blob/111/a.go#L12","path":"a.go","start_line":12,"end_line":12,"start_column":1,"end_column":3,"annotation_level":"warning","title":"Finding","message":"Annotation finding","raw_details":"proof one"},{"check_run_id":301,"blob_href":"https://github.com/acme/widget/blob/111/a.go#L12","path":"a.go","start_line":12,"end_line":12,"start_column":4,"end_column":6,"annotation_level":"warning","title":"Finding","message":"Annotation finding","raw_details":"proof two"}]]'
    ;;
  *check-runs/302/annotations*)
    printf '%s\n' '[[{"check_run_id":302,"blob_href":"https://github.com/acme/widget/blob/111/a.go#L12","path":"a.go","start_line":12,"end_line":12,"start_column":1,"end_column":3,"annotation_level":"warning","title":"Finding","message":"Annotation finding","raw_details":"proof one"}]]'
    ;;
  *) printf 'unexpected endpoint: %s\n' "$endpoint" >&2; exit 1 ;;
esac
STUB
chmod +x "$FAKE_GH"

OUT="$TMP/intake.json"
DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$OUT" >/dev/null
assert jq -e '.collection_status == "complete" and .inspected_head == "1111111111111111111111111111111111111111"' "$OUT"
assert jq -e '.surfaces.inline_comments.status == "successful" and (.surfaces.inline_comments.items | length) == 2' "$OUT"
assert jq -e '.surfaces.conversation_comments.status == "successful" and (.surfaces.conversation_comments.items | length) == 0' "$OUT"
assert jq -e '.surfaces.submitted_reviews.items[0].body.text == "Review-body finding"' "$OUT"
assert jq -e '[.surfaces.checks.items[].source_id | select(startswith("github:check-annotation:301:"))] | length == 3 and length == (unique | length)' "$OUT"
assert jq -e '[.surfaces.inline_comments.items[].source_commit] | index("0000000000000000000000000000000000000000") != null' "$OUT"
assert jq -e '.surfaces.inline_comments.items[1].body.text == "No longer relevant" and .surfaces.inline_comments.items[1].location.line == 4' "$OUT"
assert jq -e '.surfaces.checks.items[] | select(.source_id == "github:check-summary:301") | .conclusion == "success"' "$OUT"
assert jq -e '.surfaces.checks.items[] | select(.source_id == "github:check-summary:300") | .conclusion == "failure"' "$OUT"
assert test ! -e "$UNTRUSTED_SENTINEL"

FAKE_CROSS_RUN=1 DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/cross-run.json" >/dev/null
assert test "$(jq -S '[.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:301:")) | .source_id]' "$OUT")" = "$(jq -S '[.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:301:")) | .source_id]' "$TMP/cross-run.json")"
assert jq -e '[.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:302:")) | .source_id] as $ids | ($ids | length) == 1 and ($ids[0] | endswith(":0"))' "$TMP/cross-run.json"

set +e
FAKE_CHECK_SUITE_COUNT=2 DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_MAX_CHECK_SUITES=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/suite-cap.json" >/dev/null
status=$?
set -e
assert test "$status" -ne 0
assert jq -e '.collection_status == "partial" and .surfaces.checks.status == "partial" and (.gaps | index("checks:partial") != null)' "$TMP/suite-cap.json"

# One surface fails after another succeeded: the aggregate is partial, not empty.
sed 's#\*issues/7/comments\*) printf.*#*issues/7/comments*) printf '\''partial page'\''; exit 1 ;;#' "$FAKE_GH" > "$TMP/gh-partial"
chmod +x "$TMP/gh-partial"
set +e
DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$TMP/gh-partial" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/partial.json" >/dev/null
status=$?
set -e
assert test "$status" -ne 0
assert jq -e '.collection_status == "partial" and .surfaces.conversation_comments.status == "failed" and (.gaps | index("conversation_comments:failed") != null)' "$TMP/partial.json"

set +e
FAKE_LONG_PR_BODY=1 DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/long-body.json" >/dev/null
status=$?
set -e
assert test "$status" -ne 0
assert jq -e '.collection_status == "partial" and .pull_request.body.truncated == true and (.gaps | index("pull_request_body:truncated") != null)' "$TMP/long-body.json"

set +e
DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_MAX_ITEMS=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/bounded.json" >/dev/null
status=$?
set -e
assert test "$status" -ne 0
assert jq -e '[.surfaces.checks.items[].source_id | select(startswith("github:check-annotation:301:"))] | length == 1' "$TMP/bounded.json"

# Repeated collection preserves source identities and does not manufacture items.
DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/repeat.json" >/dev/null
assert test "$(jq -S '[.surfaces[].items[].source_id]' "$OUT")" = "$(jq -S '[.surfaces[].items[].source_id]' "$TMP/repeat.json")"

cat > "$TMP/decisions.json" <<'JSON'
{"schema_version":1,"artifact_role":"external_finding_decisions","repository":"acme/widget","pr_number":7,"inspected_head":"1111111111111111111111111111111111111111","collection_cutoff":"CUT_OFF","source_evidence_index":[
  {"source_id":"github:pull-request:7","candidate_source_finding_ids":[],"rationale":"Receipt evidence, not a finding."},
  {"source_id":"github:inline-comment:101","candidate_source_finding_ids":["external-1"],"rationale":"Distinct finding claim."},
  {"source_id":"github:inline-comment:102","candidate_source_finding_ids":["external-2"],"rationale":"Distinct finding claim despite metadata."},
  {"source_id":"github:submitted-review:201","candidate_source_finding_ids":["external-3"],"rationale":"Review-body finding."},
  {"source_id":"github:check-summary:300","candidate_source_finding_ids":[],"rationale":"Historical check summary retained by the all-runs request."},
  {"source_id":"github:check-summary:301","candidate_source_finding_ids":[],"rationale":"Status summary, not a finding."},
  {"source_id":"ANNOTATION_SOURCE_ID_1","candidate_source_finding_ids":["external-3"],"rationale":"Duplicate claim from another surface."},
  {"source_id":"ANNOTATION_SOURCE_ID_2","candidate_source_finding_ids":["external-3"],"rationale":"Repeated byte-identical annotation retained with a stable occurrence ID."},
  {"source_id":"ANNOTATION_SOURCE_ID_3","candidate_source_finding_ids":["external-3"],"rationale":"Distinct annotation evidence with the same message."}
],"decisions":[
  {"source_finding_id":"external-1","source_ids":["github:inline-comment:101"],"finding_id":"finding-v1:sha256(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)","finding_disposition":"retained","decision_reason_code":"retained-unique","evidence_ref":"intake.json#/surfaces/inline_comments/items/0","current_head_evidence_ref":"a.go:test","repair_ref":"todos/001-pending-p2-example.md","rationale":"Earlier-commit claim reproduces at current head."},
  {"source_finding_id":"external-2","source_ids":["github:inline-comment:102"],"finding_id":"finding-v1:sha256(bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)","finding_disposition":"discarded","decision_reason_code":"superseded-by-stronger-evidence","evidence_ref":"intake.json#/surfaces/inline_comments/items/1","current_head_evidence_ref":"b.go:test-fixed","rationale":"Current-head proof shows the claim is already fixed; metadata alone was not used."},
  {"source_finding_id":"external-3","source_ids":["github:submitted-review:201","ANNOTATION_SOURCE_ID_1","ANNOTATION_SOURCE_ID_2","ANNOTATION_SOURCE_ID_3"],"finding_id":"finding-v1:sha256(cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc)","finding_disposition":"merged","decision_reason_code":"same-root-cause-merge","merged_into_finding_id":"finding-v1:sha256(dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd)","merged_target_evidence_ref":"synthesis-decisions.json#/decisions/lane-finding","evidence_ref":"intake.json#/surfaces/submitted_reviews/items/0","current_head_evidence_ref":"a.go:test","rationale":"Same root cause and location as the retained lane finding."}
]}
JSON
cutoff="$(jq -r '.collection_cutoff' "$OUT")"
annotation_source_id_1="$(jq -r '[.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:301:"))][0].source_id' "$OUT")"
annotation_source_id_2="$(jq -r '[.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:301:"))][1].source_id' "$OUT")"
annotation_source_id_3="$(jq -r '[.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:301:"))][2].source_id' "$OUT")"
sed "s/CUT_OFF/$cutoff/" "$TMP/decisions.json" > "$TMP/decisions.next.json"
mv "$TMP/decisions.next.json" "$TMP/decisions.json"
sed "s#ANNOTATION_SOURCE_ID_1#$annotation_source_id_1#g; s#ANNOTATION_SOURCE_ID_2#$annotation_source_id_2#g; s#ANNOTATION_SOURCE_ID_3#$annotation_source_id_3#g" "$TMP/decisions.json" > "$TMP/decisions.next.json"
mv "$TMP/decisions.next.json" "$TMP/decisions.json"
assert "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/decisions.json" --current-head 1111111111111111111111111111111111111111
jq '.decisions[1].decision_reason_code = "agent-findings-cap"' "$TMP/decisions.json" > "$TMP/capped.json"
assert "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/capped.json" --current-head 1111111111111111111111111111111111111111

# Head advancement and an unprocessed source fail closed.
if "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/decisions.json" --current-head 2222222222222222222222222222222222222222 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: changed head accepted' >&2; exit 1
fi
jq '.decisions[0].source_ids = ["github:inline-comment:999"]' "$TMP/decisions.json" > "$TMP/unprocessed.json"
if "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/unprocessed.json" --current-head 1111111111111111111111111111111111111111 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: unknown source accepted' >&2; exit 1
fi
jq 'del(.source_evidence_index[0])' "$TMP/decisions.json" > "$TMP/disappeared.json"
if "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/disappeared.json" --current-head 1111111111111111111111111111111111111111 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: disappeared source evidence accepted' >&2; exit 1
fi
jq '.decisions[1].current_head_evidence_ref = ""' "$TMP/decisions.json" > "$TMP/metadata-only.json"
if "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/metadata-only.json" --current-head 1111111111111111111111111111111111111111 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: resolved/outdated metadata accepted without current-head proof' >&2; exit 1
fi
jq '.source_evidence_index[0].candidate_source_finding_ids = ["external-4"]' "$TMP/decisions.json" > "$TMP/missing-decision.json"
if "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/missing-decision.json" --current-head 1111111111111111111111111111111111111111 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: candidate without decision accepted' >&2; exit 1
fi
jq '.decisions[2].merged_into_finding_id = .decisions[2].finding_id' "$TMP/decisions.json" > "$TMP/self-merge.json"
if "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/self-merge.json" --current-head 1111111111111111111111111111111111111111 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: self-merged finding accepted' >&2; exit 1
fi
jq '.collection_cutoff = "2026-09-14T02:00:00Z" | .collected_at = .collection_cutoff' "$OUT" > "$TMP/refreshed.json"
if "$SETTLEMENT" --intake "$TMP/refreshed.json" --decisions "$TMP/decisions.json" --current-head 1111111111111111111111111111111111111111 >/dev/null 2>&1; then
  printf '%s\n' 'FAIL: stale decision cutoff accepted after refresh' >&2; exit 1
fi
jq '.collection_cutoff = "2026-09-14T02:00:00Z"' "$TMP/decisions.json" > "$TMP/refreshed-decisions.json"
assert "$SETTLEMENT" --intake "$TMP/refreshed.json" --decisions "$TMP/refreshed-decisions.json" --current-head 1111111111111111111111111111111111111111
PASS=$((PASS + 7))

printf 'dm-review-external-finding-intake: %d assertions passed\n' "$PASS"
