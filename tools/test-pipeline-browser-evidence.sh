#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/dm-review/skills/review/references/browser-evidence-packet.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pipeline-browser-evidence.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repository"
PROTOTYPE="$TMP/prototype"
EVIDENCE="$TMP/evidence"
mkdir -p "$REPO" "$PROTOTYPE" "$EVIDENCE/artifacts"
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

git -C "$REPO" init -q
git -C "$REPO" remote add origin git@github.com:example/target.git
printf 'target\n' > "$REPO/tracked.txt"
git -C "$REPO" add tracked.txt
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm target
git -C "$PROTOTYPE" init -q
git -C "$PROTOTYPE" remote add origin git@github.com:example/prototype.git
printf 'prototype\n' > "$PROTOTYPE/tracked.txt"
git -C "$PROTOTYPE" add tracked.txt
git -C "$PROTOTYPE" -c user.name=test -c user.email=test@example.invalid commit -qm prototype
TARGET_SHA="$(git -C "$REPO" rev-parse HEAD)"
PROTOTYPE_SHA="$(git -C "$PROTOTYPE" rev-parse HEAD)"

printf 'png fixture\n' > "$EVIDENCE/artifacts/proposals.png"
printf 'snapshot fixture\n' > "$EVIDENCE/artifacts/proposals.snapshot.json"
cat > "$EVIDENCE/capture.json" <<'JSON'
{
  "schemaVersion":2,
  "automationTransport":"playwright",
  "completionStatus":"completed",
  "localNavigationConfirmed":true,
  "selectedCaseIds":["proposal-mobile","proposal-desktop"],
  "artifactRefs":["artifacts/proposals.png","artifacts/proposals.snapshot.json"],
  "domClassCopyActionObservations":["main wrapper uses stack; primary action follows proposal heading"],
  "layoutComputedStyleObservations":["desktop main grid columns resolve to the declared two-column composition"],
  "consoleAccessibilitySummary":"No console errors; accessibility snapshot contains one main heading."
}
JSON
cat > "$EVIDENCE/selected-cases.json" <<'JSON'
["proposal-desktop","proposal-mobile"]
JSON

"$HELPER" create --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
  --capture-file "$EVIDENCE/capture.json" --packet-file "$EVIDENCE/browser-evidence-v2.json" \
  > "$EVIDENCE/create-result.json"
assert jq -e '.status == "created"' "$EVIDENCE/create-result.json"
assert jq -e --arg target "$TARGET_SHA" --arg prototype "$PROTOTYPE_SHA" \
  '.repositoryCommit == $target and .prototypeCommit == $prototype and .completionStatus == "completed" and (.artifacts | length) == 2' \
  "$EVIDENCE/browser-evidence-v2.json"

# Exact-head final review accepts the named packet without another capture.
"$HELPER" validate --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
  --packet-file "$EVIDENCE/browser-evidence-v2.json" --selected-cases-file "$EVIDENCE/selected-cases.json" \
  --evidence-ref plans/feature/evidence/browser/final-review/browser-evidence-v2.json \
  > "$EVIDENCE/accepted.json"
assert jq -e '.status == "accepted" and (.selectedCaseIds | length) == 2' "$EVIDENCE/accepted.json"
assert test "$(grep -c '"status":"created"' "$EVIDENCE/create-result.json")" -eq 1

# Provenance is mandatory at creation and reuse. A T3/legacy packet is not
# relabeled as Playwright merely because source, cases and artifact hashes match.
for provenance_case in t3 legacy; do
  if [ "$provenance_case" = t3 ]; then
    jq '.automationTransport="t3"' "$EVIDENCE/capture.json" > "$EVIDENCE/bad-capture.json"
    jq '.automationTransport="t3"' "$EVIDENCE/browser-evidence-v2.json" > "$EVIDENCE/bad-packet.json"
  else
    jq 'del(.automationTransport) | .schemaVersion=1' "$EVIDENCE/capture.json" > "$EVIDENCE/bad-capture.json"
    jq 'del(.automationTransport) | .schemaVersion=1' "$EVIDENCE/browser-evidence-v2.json" > "$EVIDENCE/bad-packet.json"
  fi
  set +e
  "$HELPER" create --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
    --capture-file "$EVIDENCE/bad-capture.json" --packet-file "$EVIDENCE/not-created.json" >/dev/null 2>&1
  bad_capture_rc=$?
  "$HELPER" validate --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
    --packet-file "$EVIDENCE/bad-packet.json" --selected-cases-file "$EVIDENCE/selected-cases.json" \
    --evidence-ref plans/feature/evidence/browser/final-review/browser-evidence-v2.json > "$EVIDENCE/bad-packet-result.json"
  bad_packet_rc=$?
  set -e
  assert test "$bad_capture_rc" -eq 2
  assert test "$bad_packet_rc" -eq 76
  assert jq -e '.reason == "packet_schema"' "$EVIDENCE/bad-packet-result.json"
  assert test ! -e "$EVIDENCE/not-created.json"
done

git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit --allow-empty -qm newer-target
set +e
"$HELPER" validate --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
  --packet-file "$EVIDENCE/browser-evidence-v2.json" --selected-cases-file "$EVIDENCE/selected-cases.json" \
  --evidence-ref plans/feature/evidence/browser/final-review/browser-evidence-v2.json > "$EVIDENCE/wrong-target.json"
wrong_target_rc=$?
set -e
assert test "$wrong_target_rc" -eq 76
assert jq -e '.reason == "repository_commit_mismatch"' "$EVIDENCE/wrong-target.json"
git -C "$REPO" checkout -q --detach "$TARGET_SHA"

git -C "$PROTOTYPE" -c user.name=test -c user.email=test@example.invalid commit --allow-empty -qm newer-prototype
set +e
"$HELPER" validate --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
  --packet-file "$EVIDENCE/browser-evidence-v2.json" --selected-cases-file "$EVIDENCE/selected-cases.json" \
  --evidence-ref plans/feature/evidence/browser/final-review/browser-evidence-v2.json > "$EVIDENCE/wrong-prototype.json"
wrong_prototype_rc=$?
set -e
assert test "$wrong_prototype_rc" -eq 76
assert jq -e '.reason == "prototype_commit_mismatch"' "$EVIDENCE/wrong-prototype.json"
git -C "$PROTOTYPE" checkout -q --detach "$PROTOTYPE_SHA"

printf '%s\n' '["proposal-mobile"]' > "$EVIDENCE/wrong-cases.json"
set +e
"$HELPER" validate --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
  --packet-file "$EVIDENCE/browser-evidence-v2.json" --selected-cases-file "$EVIDENCE/wrong-cases.json" \
  --evidence-ref plans/feature/evidence/browser/final-review/browser-evidence-v2.json > "$EVIDENCE/wrong-cases-result.json"
wrong_cases_rc=$?
set -e
assert test "$wrong_cases_rc" -eq 76
assert jq -e '.reason == "selected_case_set_mismatch"' "$EVIDENCE/wrong-cases-result.json"

printf 'tampered\n' > "$EVIDENCE/artifacts/proposals.png"
set +e
"$HELPER" validate --repository-root "$REPO" --prototype-root "$PROTOTYPE" \
  --packet-file "$EVIDENCE/browser-evidence-v2.json" --selected-cases-file "$EVIDENCE/selected-cases.json" \
  --evidence-ref plans/feature/evidence/browser/final-review/browser-evidence-v2.json > "$EVIDENCE/wrong-hash.json"
wrong_hash_rc=$?
set -e
assert test "$wrong_hash_rc" -eq 76
assert jq -e '.reason == "artifact_hash_mismatch"' "$EVIDENCE/wrong-hash.json"

printf 'pipeline-browser-evidence: %d assertions passed\n' "$pass"
