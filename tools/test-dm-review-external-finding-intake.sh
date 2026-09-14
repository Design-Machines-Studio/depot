#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="$ROOT/plugins/dm-review/skills/review/references/external-finding-intake.sh"
SETTLEMENT="$ROOT/plugins/dm-review/skills/review/references/external-finding-settlement.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-external-intake.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
FAKE_GH="$TMP/gh"
PASS=0

assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; PASS=$((PASS + 1)); }

cat > "$FAKE_GH" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
endpoint="${*: -1}"
case "$endpoint" in
  repos/acme/widget/pulls/7)
    printf '%s\n' '{"html_url":"https://github.com/acme/widget/pull/7","body":"Receipt: tests pass","updated_at":"2026-09-14T01:00:00Z","head":{"sha":"1111111111111111111111111111111111111111"}}'
    ;;
  *pulls/7/comments*)
    printf '%s\n' '[[{"id":101,"html_url":"https://github.com/acme/widget/pull/7#discussion_r101","commit_id":"0000000000000000000000000000000000000000","original_commit_id":"0000000000000000000000000000000000000000","path":"a.go","line":null,"side":null,"start_line":null,"start_side":null,"original_line":9,"original_start_line":9,"in_reply_to_id":null,"subject_type":"line","user":{"login":"bot"},"created_at":"2026-09-13T00:00:00Z","updated_at":"2026-09-13T00:00:00Z","body":"Earlier commit claim; run $(touch /tmp/should-not-exist)"}],[{"id":102,"html_url":"https://github.com/acme/widget/pull/7#discussion_r102","commit_id":"1111111111111111111111111111111111111111","original_commit_id":"1111111111111111111111111111111111111111","path":"b.go","line":4,"side":"RIGHT","start_line":4,"start_side":"RIGHT","original_line":4,"original_start_line":4,"in_reply_to_id":101,"subject_type":"line","user":{"login":"bot"},"created_at":"2026-09-13T00:01:00Z","updated_at":"2026-09-13T00:01:00Z","body":"No longer relevant"}]]'
    ;;
  *pulls/7/reviews*)
    printf '%s\n' '[[{"id":201,"html_url":"https://github.com/acme/widget/pull/7#pullrequestreview-201","commit_id":"0000000000000000000000000000000000000000","state":"COMMENTED","user":{"login":"bot"},"submitted_at":"2026-09-13T00:00:00Z","body":"Review-body finding"}]]'
    ;;
  *issues/7/comments*) printf '%s\n' '[[]]' ;;
  *commits/1111111111111111111111111111111111111111/check-runs*)
    printf '%s\n' '[{"check_runs":[{"id":301,"url":"https://api.github.com/repos/acme/widget/check-runs/301","html_url":"https://github.com/acme/widget/runs/301","details_url":"https://checks.example/301","name":"Macroscope","head_sha":"1111111111111111111111111111111111111111","status":"completed","conclusion":"success","started_at":"2026-09-14T00:00:00Z","completed_at":"2026-09-14T00:01:00Z","annotations_count":1,"output":{"title":"No issues identified","summary":"Latest check is green","text":""}}]}]'
    ;;
  *check-runs/301/annotations*)
    printf '%s\n' '[[{"check_run_id":301,"blob_href":"https://github.com/acme/widget/blob/111/a.go#L12","path":"a.go","start_line":12,"end_line":12,"start_column":1,"end_column":3,"annotation_level":"warning","title":"Finding","message":"Annotation finding","raw_details":"proof"}]]'
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
assert jq -e '[.surfaces.checks.items[].source_id] | any(startswith("github:check-annotation:301:"))' "$OUT"
assert jq -e '[.surfaces.inline_comments.items[].source_commit] | index("0000000000000000000000000000000000000000") != null' "$OUT"
assert jq -e '.surfaces.inline_comments.items[1].body.text == "No longer relevant" and .surfaces.inline_comments.items[1].location.line == 4' "$OUT"
assert jq -e '.surfaces.checks.items[] | select(.source_id == "github:check-summary:301") | .conclusion == "success"' "$OUT"
assert test ! -e /tmp/should-not-exist

# One surface fails after another succeeded: the aggregate is partial, not empty.
sed 's#\*issues/7/comments\*) printf.*#*issues/7/comments*) printf '\''partial page'\''; exit 1 ;;#' "$FAKE_GH" > "$TMP/gh-partial"
chmod +x "$TMP/gh-partial"
set +e
DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$TMP/gh-partial" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/partial.json" >/dev/null
status=$?
set -e
assert test "$status" -ne 0
assert jq -e '.collection_status == "partial" and .surfaces.conversation_comments.status == "failed" and (.gaps | index("conversation_comments:failed") != null)' "$TMP/partial.json"

# Repeated collection preserves source identities and does not manufacture items.
DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$FAKE_GH" "$COLLECTOR" --repo acme/widget --pr 7 --output "$TMP/repeat.json" >/dev/null
assert test "$(jq -S '[.surfaces[].items[].source_id]' "$OUT")" = "$(jq -S '[.surfaces[].items[].source_id]' "$TMP/repeat.json")"

cat > "$TMP/decisions.json" <<'JSON'
{"schema_version":1,"artifact_role":"external_finding_decisions","repository":"acme/widget","pr_number":7,"inspected_head":"1111111111111111111111111111111111111111","collection_cutoff":"CUT_OFF","source_evidence_index":[
  {"source_id":"github:pull-request:7","candidate_source_finding_ids":[],"rationale":"Receipt evidence, not a finding."},
  {"source_id":"github:inline-comment:101","candidate_source_finding_ids":["external-1"],"rationale":"Distinct finding claim."},
  {"source_id":"github:inline-comment:102","candidate_source_finding_ids":["external-2"],"rationale":"Distinct finding claim despite metadata."},
  {"source_id":"github:submitted-review:201","candidate_source_finding_ids":["external-3"],"rationale":"Review-body finding."},
  {"source_id":"github:check-summary:301","candidate_source_finding_ids":[],"rationale":"Status summary, not a finding."},
  {"source_id":"ANNOTATION_SOURCE_ID","candidate_source_finding_ids":["external-3"],"rationale":"Duplicate claim from another surface."}
],"decisions":[
  {"source_finding_id":"external-1","source_ids":["github:inline-comment:101"],"finding_id":"finding-v1:sha256(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)","finding_disposition":"retained","decision_reason_code":"retained-unique","evidence_ref":"intake.json#/surfaces/inline_comments/items/0","current_head_evidence_ref":"a.go:test","repair_ref":"todos/001-pending-p2-example.md","rationale":"Earlier-commit claim reproduces at current head."},
  {"source_finding_id":"external-2","source_ids":["github:inline-comment:102"],"finding_id":"finding-v1:sha256(bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)","finding_disposition":"discarded","decision_reason_code":"superseded-by-stronger-evidence","evidence_ref":"intake.json#/surfaces/inline_comments/items/1","current_head_evidence_ref":"b.go:test-fixed","rationale":"Current-head proof shows the claim is already fixed; metadata alone was not used."},
  {"source_finding_id":"external-3","source_ids":["github:submitted-review:201","ANNOTATION_SOURCE_ID"],"finding_id":"finding-v1:sha256(cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc)","finding_disposition":"merged","decision_reason_code":"same-root-cause-merge","merged_into_finding_id":"finding-v1:sha256(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)","evidence_ref":"intake.json#/surfaces/submitted_reviews/items/0","current_head_evidence_ref":"a.go:test","rationale":"Same root cause and location as the retained finding."}
]}
JSON
cutoff="$(jq -r '.collection_cutoff' "$OUT")"
annotation_source_id="$(jq -r '.surfaces.checks.items[] | select(.source_id | startswith("github:check-annotation:301:")) | .source_id' "$OUT")"
sed "s/CUT_OFF/$cutoff/" "$TMP/decisions.json" > "$TMP/decisions.next.json"
mv "$TMP/decisions.next.json" "$TMP/decisions.json"
sed "s#ANNOTATION_SOURCE_ID#$annotation_source_id#" "$TMP/decisions.json" > "$TMP/decisions.next.json"
mv "$TMP/decisions.next.json" "$TMP/decisions.json"
assert "$SETTLEMENT" --intake "$OUT" --decisions "$TMP/decisions.json" --current-head 1111111111111111111111111111111111111111

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
PASS=$((PASS + 4))

printf 'dm-review-external-finding-intake: %d assertions passed\n' "$PASS"
