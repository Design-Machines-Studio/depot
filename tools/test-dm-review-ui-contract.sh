#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/dm-review/skills/review/references/ui-review-contract.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-ui-contract.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

cat > "$TMP/ordinary.json" <<'JSON'
{"schemaVersion":1,"renderedEvidenceRequired":false,"templateExtensionsOnly":false,"applicableLanes":["ui-standards-reviewer","ux-quality-reviewer","visual-browser-tester"]}
JSON
cat > "$TMP/template-only.json" <<'JSON'
{"schemaVersion":1,"renderedEvidenceRequired":false,"templateExtensionsOnly":true,"applicableLanes":["ui-standards-reviewer","ux-quality-reviewer","visual-browser-tester"]}
JSON
cat > "$TMP/required.json" <<'JSON'
{"schemaVersion":1,"renderedEvidenceRequired":true,"templateExtensionsOnly":false,"applicableLanes":["ui-standards-reviewer","ux-quality-reviewer","visual-browser-tester"]}
JSON
cat > "$TMP/no-target.json" <<'JSON'
{"reason":"visual_target_unavailable"}
JSON
cat > "$TMP/ready.json" <<'JSON'
{"reason":"available"}
JSON
cat > "$TMP/accepted.json" <<'JSON'
{"status":"accepted","evidenceRef":"plans/feature/evidence/browser/final-review/browser-evidence-v1.json"}
JSON

"$HELPER" plan --request "$TMP/ordinary.json" --readiness-result "$TMP/no-target.json" > "$TMP/ordinary-result.json"
assert jq -e '.reviewDisposition == "completed" and (.lanes | length) == 3' "$TMP/ordinary-result.json"
assert jq -e '[.lanes[] | select(.lane == "ui-standards-reviewer" or .lane == "ux-quality-reviewer") | select(.status == "RUN" and .evidenceMode == "source-only")] | length == 2' "$TMP/ordinary-result.json"
assert jq -e '[.lanes[] | select(.lane == "visual-browser-tester" and .status == "NOT RUN")] | length == 1' "$TMP/ordinary-result.json"
assert jq -e '.browserCoverage == {reason:"visual_target_unavailable",status:"NOT RUN"} and (.nextActions | length) == 0' "$TMP/ordinary-result.json"

"$HELPER" plan --request "$TMP/required.json" --readiness-result "$TMP/no-target.json" > "$TMP/required-result.json"
assert jq -e '.reviewDisposition == "REVIEW INCOMPLETE" and (.nextActions | length) == 1 and (.browserCoverage | length) == 2' "$TMP/required-result.json"
assert jq -e '[.lanes[] | select(.evidenceMode == "source-only" and .status == "RUN")] | length == 2' "$TMP/required-result.json"
assert test "$(grep -o 'visual_target_unavailable' "$TMP/required-result.json" | wc -l | tr -d ' ')" -eq 2
assert test "$(jq -r '.nextActions[]' "$TMP/required-result.json" | grep -Eic 'twelve|separate|three lanes' || true)" -eq 0

"$HELPER" plan --request "$TMP/ordinary.json" --readiness-result "$TMP/ready.json" \
  --evidence-validation-result "$TMP/accepted.json" > "$TMP/ready-result.json"
assert jq -e '.reviewDisposition == "completed" and .browserCoverage == null and (.lanes | length) == 3' "$TMP/ready-result.json"
assert jq -e '([.lanes[].evidenceRef] | unique | length) == 1 and all(.lanes[]; .status == "RUN")' "$TMP/ready-result.json"

"$HELPER" plan --request "$TMP/template-only.json" --readiness-result "$TMP/no-target.json" > "$TMP/template-result.json"
assert jq -e '.reviewDisposition == "completed" and .browserCoverage.status == "NOT RUN"' "$TMP/template-result.json"

cat > "$TMP/cases-ordinary.json" <<'JSON'
{
  "schemaVersion":1,
  "reviewKind":"ordinary",
  "fullMatrixRequirement":"none",
  "changedRenderedFiles":["views/proposals.templ"],
  "changedRoutes":["/proposals"],
  "prototypeParityCaseIds":[],
  "acceptanceCaseIds":["member-desktop"],
  "affectedPersonas":["member"],
  "affectedStates":["list"],
  "affectedEngines":["chromium"],
  "affectedViewports":["390x844"],
  "baselineCaseId":null,
  "cases":[
    {"id":"proposal-mobile","route":"/proposals","renderedFiles":["views/proposals.templ"],"persona":"member","state":"list","engine":"chromium","viewport":"390x844"},
    {"id":"proposal-small","route":"/proposals","renderedFiles":["views/proposals.templ"],"persona":"member","state":"list","engine":"chromium","viewport":"320x800"},
    {"id":"proposal-desktop","route":"/proposals","renderedFiles":["views/proposals.templ"],"persona":"member","state":"list","engine":"chromium","viewport":"1440x900"},
    {"id":"member-desktop","route":"/members","renderedFiles":["views/members.templ"],"persona":"admin","state":"detail","engine":"chromium","viewport":"1440x900"}
  ]
}
JSON
"$HELPER" select-cases --request "$TMP/cases-ordinary.json" > "$TMP/cases-ordinary-result.json"
assert jq -e '.selectionMode == "affected-cases" and .selectedCaseIds == ["member-desktop","proposal-mobile"]' "$TMP/cases-ordinary-result.json"

jq '.acceptanceCaseIds=[] | .reviewKind="full"' "$TMP/cases-ordinary.json" > "$TMP/cases-full-review.json"
"$HELPER" select-cases --request "$TMP/cases-full-review.json" > "$TMP/cases-full-review-result.json"
assert jq -e '.selectionMode == "affected-cases" and .selectedCaseIds == ["proposal-mobile"]' "$TMP/cases-full-review-result.json"

jq '.reviewKind="full" | .fullMatrixRequirement="release-profile"' "$TMP/cases-ordinary.json" > "$TMP/cases-full.json"
"$HELPER" select-cases --request "$TMP/cases-full.json" > "$TMP/cases-full-result.json"
assert jq -e '.selectionMode == "full-matrix" and .fullMatrixReason == "release-profile" and (.selectedCaseIds | length) == 4' "$TMP/cases-full-result.json"

printf 'dm-review-ui-contract: %d assertions passed\n' "$pass"
