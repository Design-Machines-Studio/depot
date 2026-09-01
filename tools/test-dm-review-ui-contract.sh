#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/dm-review/skills/review/references/ui-review-contract.sh"
CASE_SELECTION="$ROOT/plugins/dm-review/skills/review/references/ui-case-selection.md"
REVIEW_SKILL="$ROOT/plugins/dm-review/skills/review/SKILL.md"
UX_REVIEWER="$ROOT/plugins/dm-review/agents/review/ux-quality-reviewer.md"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-ui-contract.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

cat > "$TMP/ordinary.json" <<'JSON'
{"schemaVersion":1,"renderedEvidenceRequired":false,"applicableLanes":["ui-standards-reviewer","ux-quality-reviewer","visual-browser-tester"]}
JSON
cat > "$TMP/required.json" <<'JSON'
{"schemaVersion":1,"renderedEvidenceRequired":true,"applicableLanes":["ui-standards-reviewer","ux-quality-reviewer","visual-browser-tester"]}
JSON
cat > "$TMP/quick.json" <<'JSON'
{"schemaVersion":1,"renderedEvidenceRequired":false,"applicableLanes":["ui-standards-reviewer"]}
JSON
cat > "$TMP/no-target.json" <<'JSON'
{"reason":"visual_target_unavailable"}
JSON
cat > "$TMP/ready.json" <<'JSON'
{"reason":"available","evidenceRef":"review/browser/live-navigation.json"}
JSON
cat > "$TMP/accepted.json" <<'JSON'
{"status":"accepted","evidenceRef":"plans/feature/evidence/browser/final-review/browser-evidence-v1.json"}
JSON

"$HELPER" plan --request "$TMP/ordinary.json" --readiness-result "$TMP/no-target.json" > "$TMP/ordinary-result.json"
assert jq -e '.reviewDisposition == "completed" and (.lanes | length) == 3' "$TMP/ordinary-result.json"
assert jq -e '[.lanes[] | select(.lane == "ui-standards-reviewer" or .lane == "ux-quality-reviewer") | select(.status == "RUN" and .evidenceMode == "source-only")] | length == 2' "$TMP/ordinary-result.json"
assert jq -e '[.lanes[] | select(.lane == "visual-browser-tester" and .status == "NOT RUN")] | length == 1' "$TMP/ordinary-result.json"
assert jq -e '.browserCoverage == {reason:"visual_target_unavailable",status:"NOT RUN"} and (.nextActions | length) == 0' "$TMP/ordinary-result.json"

"$HELPER" plan --request "$TMP/quick.json" --readiness-result "$TMP/no-target.json" > "$TMP/quick-result.json"
assert jq -e '.reviewDisposition == "completed" and .lanes == [{lane:"ui-standards-reviewer",status:"RUN",evidenceMode:"source-only",evidenceRef:null}]' "$TMP/quick-result.json"
assert jq -e 'all(.lanes[]; .lane != "ux-quality-reviewer" and .lane != "visual-browser-tester")' "$TMP/quick-result.json"

"$HELPER" plan --request "$TMP/required.json" --readiness-result "$TMP/no-target.json" > "$TMP/required-result.json"
assert jq -e '.reviewDisposition == "REVIEW INCOMPLETE" and (.nextActions | length) == 1 and (.browserCoverage | length) == 2' "$TMP/required-result.json"
assert jq -e '[.lanes[] | select(.evidenceMode == "source-only" and .status == "RUN")] | length == 2' "$TMP/required-result.json"
assert test "$(grep -o 'visual_target_unavailable' "$TMP/required-result.json" | wc -l | tr -d ' ')" -eq 2
assert test "$(jq -r '.nextActions[]' "$TMP/required-result.json" | grep -Eic 'twelve|separate|three lanes' || true)" -eq 0

"$HELPER" plan --request "$TMP/ordinary.json" --readiness-result "$TMP/ready.json" \
  --evidence-validation-result "$TMP/accepted.json" > "$TMP/ready-result.json"
assert jq -e '.reviewDisposition == "completed" and .browserCoverage == null and (.lanes | length) == 3' "$TMP/ready-result.json"
assert jq -e '([.lanes[].evidenceRef] | unique | length) == 1 and all(.lanes[]; .status == "RUN")' "$TMP/ready-result.json"

"$HELPER" plan --request "$TMP/ordinary.json" --readiness-result "$TMP/ready.json" > "$TMP/live-result.json"
assert jq -e '.reviewDisposition == "completed" and all(.lanes[]; .status == "RUN" and .evidenceRef == "review/browser/live-navigation.json")' "$TMP/live-result.json"

"$HELPER" plan --request "$TMP/required.json" --readiness-result "$TMP/no-target.json" \
  --evidence-validation-result "$TMP/accepted.json" > "$TMP/reused-result.json"
assert jq -e '.reviewDisposition == "completed" and .readinessDecision == "available" and all(.lanes[]; .status == "RUN")' "$TMP/reused-result.json"

cat > "$TMP/cases-ordinary.json" <<'JSON'
{
  "schemaVersion":1,
  "renderedEvidenceRequired":false,
  "fullMatrixRequirement":"none",
  "changedRenderedFiles":["views/proposals.templ"],
  "renderedRouteMappings":[{"renderedFile":"views/proposals.templ","status":"resolved","route":"/proposals"}],
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
assert jq -e '.reviewDisposition == "completed" and .incompleteReasons == [] and .unresolvedRenderedFiles == []' "$TMP/cases-ordinary-result.json"

jq '.acceptanceCaseIds=[]' "$TMP/cases-ordinary.json" > "$TMP/cases-full-review.json"
"$HELPER" select-cases --request "$TMP/cases-full-review.json" > "$TMP/cases-full-review-result.json"
assert jq -e '.selectionMode == "affected-cases" and .selectedCaseIds == ["proposal-mobile"]' "$TMP/cases-full-review-result.json"

jq '.fullMatrixRequirement="release-profile"' "$TMP/cases-ordinary.json" > "$TMP/cases-full.json"
"$HELPER" select-cases --request "$TMP/cases-full.json" > "$TMP/cases-full-result.json"
assert jq -e '.selectionMode == "full-matrix" and .fullMatrixReason == "release-profile" and (.selectedCaseIds | length) == 4' "$TMP/cases-full-result.json"

jq '.acceptanceCaseIds=[] | .changedRenderedFiles=["views/renamed-proposals.templ"] |
    .renderedRouteMappings=[{"renderedFile":"views/renamed-proposals.templ","status":"resolved","route":"/proposals"}]' \
  "$TMP/cases-ordinary.json" > "$TMP/cases-route-mapped.json"
"$HELPER" select-cases --request "$TMP/cases-route-mapped.json" > "$TMP/cases-route-mapped-result.json"
assert jq -e '.selectionMode == "affected-cases" and .selectedCaseIds == ["proposal-mobile"]' "$TMP/cases-route-mapped-result.json"

jq '.renderedEvidenceRequired=true |
    .renderedRouteMappings=[{"renderedFile":"views/renamed-proposals.templ","status":"unresolved","route":null}]' \
  "$TMP/cases-route-mapped.json" > "$TMP/cases-unresolved.json"
"$HELPER" select-cases --request "$TMP/cases-unresolved.json" > "$TMP/cases-unresolved-result.json"
assert jq -e '.reviewDisposition == "REVIEW INCOMPLETE" and .selectedCaseIds == [] and
  .incompleteReasons == ["unresolved-rendered-route"] and
  .unresolvedRenderedFiles == ["views/renamed-proposals.templ"]' "$TMP/cases-unresolved-result.json"

jq '.renderedEvidenceRequired=true | .cases=[]' \
  "$TMP/cases-route-mapped.json" > "$TMP/cases-required-empty.json"
"$HELPER" select-cases --request "$TMP/cases-required-empty.json" > "$TMP/cases-required-empty-result.json"
assert jq -e '.reviewDisposition == "REVIEW INCOMPLETE" and .selectedCaseIds == [] and
  .incompleteReasons == ["rendered-case-unavailable"] and .unresolvedRenderedFiles == []' \
  "$TMP/cases-required-empty-result.json"

jq '.renderedEvidenceRequired=false' \
  "$TMP/cases-required-empty.json" > "$TMP/cases-optional-empty.json"
"$HELPER" select-cases --request "$TMP/cases-optional-empty.json" > "$TMP/cases-optional-empty-result.json"
assert jq -e '.reviewDisposition == "completed" and .selectedCaseIds == [] and .incompleteReasons == []' \
  "$TMP/cases-optional-empty-result.json"

jq '.renderedEvidenceRequired=true | .acceptanceCaseIds=["member-desktop","missing-required-case"]' \
  "$TMP/cases-ordinary.json" > "$TMP/cases-partial-missing.json"
"$HELPER" select-cases --request "$TMP/cases-partial-missing.json" > "$TMP/cases-partial-missing-result.json"
assert jq -e '.reviewDisposition == "REVIEW INCOMPLETE" and
  .selectedCaseIds == ["member-desktop","proposal-mobile"] and
  .incompleteReasons == ["rendered-case-unavailable"] and
  .missingExplicitCaseIds == ["missing-required-case"]' "$TMP/cases-partial-missing-result.json"

jq '.renderedRouteMappings=[]' "$TMP/cases-route-mapped.json" > "$TMP/cases-missing-mapping.json"
if "$HELPER" select-cases --request "$TMP/cases-missing-mapping.json" >/dev/null 2>&1; then
  printf 'FAIL: missing per-file mapping was accepted\n' >&2
  exit 1
fi
pass=$((pass + 1))

assert grep -Fq 'Host route-mapping preflight' "$CASE_SELECTION"
assert grep -Fq '`unresolved-rendered-route`' "$REVIEW_SKILL"
assert grep -Fq 'In `source-only`, compare only source-visible hierarchy' "$UX_REVIEWER"
assert grep -Fq 'Only this mode may note' "$UX_REVIEWER"
assert grep -Fq 'Source-only runs do not create a screenshot directory' "$UX_REVIEWER"
assert grep -Fq 'never add a lane during fallback' "$REVIEW_SKILL"

printf 'dm-review-ui-contract: %d assertions passed\n' "$pass"
