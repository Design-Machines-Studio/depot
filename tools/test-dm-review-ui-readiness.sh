#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-ui-readiness.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repository"
mkdir -p "$REPO/.dm" "$REPO/tools"
git -C "$REPO" init -q

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

cat > "$REPO/tools/ui-review-ready" <<'STUB'
#!/usr/bin/env bash
[ -f "$TEST_SERVER_MARKER" ]
STUB
cat > "$REPO/tools/ui-review-start" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' start >> "$TEST_RESOURCE_LOG"
touch "$TEST_SERVER_MARKER"
STUB
cat > "$REPO/tools/ui-review-stop" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' cleanup >> "$TEST_RESOURCE_LOG"
rm -f "$TEST_SERVER_MARKER"
STUB
cat > "$REPO/tools/ui-review-wrong-stop" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' wrong-cleanup >> "$TEST_RESOURCE_LOG"
STUB
chmod +x "$REPO"/tools/ui-review-*
git -C "$REPO" add tools
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm fixture

export TEST_SERVER_MARKER="$TMP/server-ready"
export TEST_RESOURCE_LOG="$TMP/resources.log"
: > "$TEST_RESOURCE_LOG"

run_prepare() {
  local name="$1" rc=0
  shift
  rm -f "$TMP/$name.state" "$TMP/$name.result"
  "$HELPER" prepare --repository-root "$REPO" --state-file "$TMP/$name.state" \
    "$@" > "$TMP/$name.result" || rc=$?
  printf '%s\n' "$rc"
}

run_confirm() {
  local name="$1" browser_file="$2" rc=0
  "$HELPER" confirm-browser --repository-root "$REPO" --state-file "$TMP/$name.state" \
    --browser-evidence-file "$browser_file" > "$TMP/$name.confirmed" || rc=$?
  printf '%s\n' "$rc"
}

# No declaration means no guessed localhost scan and one nonblocking coverage
# note in an ordinary review.
no_decl_rc="$(run_prepare no-declaration)"
assert test "$no_decl_rc" -eq 0
assert jq -e '.dispatchAllowed == false and .reason == "visual_target_unavailable" and .coverageDisposition == "NOT RUN" and .reviewDisposition == "completed"' "$TMP/no-declaration.result"
assert test ! -e "$TMP/no-declaration.state"

# Explicit visual review keeps one honest incomplete result when no target is
# available.
required_rc="$(run_prepare required-no-target --visual-required true)"
assert test "$required_rc" -eq 76
assert jq -e '.reason == "visual_target_unavailable" and .reviewDisposition == "REVIEW INCOMPLETE"' "$TMP/required-no-target.result"

cat > "$TMP/browser-preview.json" <<'JSON'
{"schemaVersion":1,"status":"ready","transportClass":"local-interactive","localNavigation":"confirmed","targetUrl":"http://localhost:9090/preview","evidenceRef":"review/browser/preview.json"}
JSON

# An attached automation-capable T3 preview precedes optional repository
# configuration and proceeds without a declaration.
preview_prepare_rc="$(run_prepare attached-preview --target-url http://localhost:9090/preview --target-source t3-preview)"
assert test "$preview_prepare_rc" -eq 0
assert jq -e '.targetSource == "t3-preview" and .createdResources == 0' "$TMP/attached-preview.result"
preview_ready_rc="$(run_confirm attached-preview "$TMP/browser-preview.json")"
assert test "$preview_ready_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true' "$TMP/attached-preview.confirmed"
"$HELPER" cleanup --repository-root "$REPO" --state-file "$TMP/attached-preview.state" > "$TMP/attached-preview-cleanup.json"
assert jq -e '.state == "already_clean" and .removedCount == 0' "$TMP/attached-preview-cleanup.json"

cat > "$TMP/browser-remote.json" <<'JSON'
{"schemaVersion":1,"status":"ready","transportClass":"local-interactive","localNavigation":"confirmed","targetUrl":"https://preview.example.com/review","evidenceRef":"review/browser/remote.json"}
JSON

# Invocation-supplied URLs may point at staging or other remote HTTP(S) hosts;
# only tracked repository declarations are restricted to local targets.
remote_prepare_rc="$(run_prepare remote-explicit --target-url https://preview.example.com/review --target-source explicit)"
assert test "$remote_prepare_rc" -eq 0
assert jq -e '.targetSource == "explicit" and .targetUrl == "https://preview.example.com/review"' "$TMP/remote-explicit.result"
remote_ready_rc="$(run_confirm remote-explicit "$TMP/browser-remote.json")"
assert test "$remote_ready_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true' "$TMP/remote-explicit.confirmed"
"$HELPER" cleanup --repository-root "$REPO" --state-file "$TMP/remote-explicit.state" > "$TMP/remote-explicit-cleanup.json"
assert jq -e '.state == "already_clean" and .removedCount == 0' "$TMP/remote-explicit-cleanup.json"

# Invocation targets still require a real authority/hostname.
hostless_rc="$(run_prepare hostless-explicit --target-url 'https://?' --target-source explicit 2> "$TMP/hostless-explicit.stderr")"
assert test "$hostless_rc" -eq 2
assert test ! -e "$TMP/hostless-explicit.state"
assert grep -Fq 'ui-review-readiness: invalid invocation' "$TMP/hostless-explicit.stderr"

cat > "$REPO/.dm/ui-review.json" <<'JSON'
{
  "schemaVersion": 1,
  "targetUrl": "http://localhost:8080/review",
  "readiness": {
    "argv": ["./tools/ui-review-ready"],
    "attempts": 2,
    "timeoutSeconds": 2
  },
  "start": {
    "resourceKind": "process",
    "argv": ["./tools/ui-review-start"],
    "cleanupArgv": ["./tools/ui-review-stop"],
    "timeoutSeconds": 2
  }
}
JSON
git -C "$REPO" add .dm/ui-review.json
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm declaration

# Fractional retry/timeout values are rejected before Bash integer loops.
jq '.readiness.attempts = 1.5' "$REPO/.dm/ui-review.json" > "$TMP/fractional.json"
cp "$TMP/fractional.json" "$REPO/.dm/ui-review.json"
fractional_rc="$(run_prepare fractional)"
assert test "$fractional_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and .dispatchAllowed == false' "$TMP/fractional.result"
git -C "$REPO" show HEAD:.dm/ui-review.json > "$REPO/.dm/ui-review.json"

cat > "$TMP/browser-ready.json" <<'JSON'
{"schemaVersion":1,"status":"ready","transportClass":"local-interactive","localNavigation":"confirmed","targetUrl":"http://localhost:8080/review","evidenceRef":"review/browser/navigation.json"}
JSON
cat > "$TMP/browser-web-search.json" <<'JSON'
{"schemaVersion":1,"status":"ready","transportClass":"remote-web-search","localNavigation":"confirmed","targetUrl":"http://localhost:8080/review","evidenceRef":"review/browser/navigation.json"}
JSON

# A server started by the review is cleaned immediately when the local browser
# is unavailable. Remote web search never satisfies the browser gate.
web_prepare_rc="$(run_prepare remote-web)"
assert test "$web_prepare_rc" -eq 0
assert jq -e '.state == "app_ready" and .dispatchAllowed == false and .reason == "browser_evidence_required"' "$TMP/remote-web.result"
assert test -e "$TEST_SERVER_MARKER"
"$HELPER" prepare --repository-root "$REPO" --state-file "$TMP/remote-web.state" \
  > "$TMP/remote-web-reprepare.result"
assert jq -e '.createdResources == 1 and .dispatchAllowed == false' "$TMP/remote-web-reprepare.result"
assert jq -e '.createdByReview == true and .cleanupPending == true and .stage == "app_ready"' "$TMP/remote-web.state"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 1
web_rc="$(run_confirm remote-web "$TMP/browser-web-search.json")"
assert test "$web_rc" -eq 76
assert jq -e '.dispatchAllowed == false and .reason == "browser_transport_unavailable"' "$TMP/remote-web.confirmed"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 1
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 1
assert test ! -e "$TEST_SERVER_MARKER"

# A pre-existing ready server remains untouched when browser readiness fails.
touch "$TEST_SERVER_MARKER"
preexisting_prepare_rc="$(run_prepare preexisting)"
assert test "$preexisting_prepare_rc" -eq 0
preexisting_rc="$(run_confirm preexisting "$TMP/missing-browser.json")"
assert test "$preexisting_rc" -eq 76
assert jq -e '.reason == "browser_transport_unavailable" and .dispatchAllowed == false' "$TMP/preexisting.confirmed"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 1
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 1
assert test -e "$TEST_SERVER_MARKER"

# Server plus real local browser permits the provider-neutral analysis lane.
ready_prepare_rc="$(run_prepare ready)"
assert test "$ready_prepare_rc" -eq 0
ready_rc="$(run_confirm ready "$TMP/browser-ready.json")"
assert test "$ready_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true and .browserTransport == "local-interactive"' "$TMP/ready.confirmed"
cat > "$TMP/participant-completed.json" <<'JSON'
{"role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed","evidenceSource":"live","transportStub":false}
JSON
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/ready.state" \
  --participant-result-file "$TMP/participant-completed.json" > "$TMP/ready-settled.json"
assert jq -e '.state == "completed" and .dispatchAllowed == false and .cleanup == "complete"' "$TMP/ready-settled.json"
assert test -e "$TEST_SERVER_MARKER"
set +e
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/ready.state" \
  --participant-result-file "$TMP/participant-completed.json" >/dev/null 2>&1
repeated_settle_rc=$?
set -e
assert test "$repeated_settle_rc" -eq 2

# Browser evidence can be ready while the analysis participant is unavailable;
# that cause is distinct, and only the resource created by this run is cleaned.
rm -f "$TEST_SERVER_MARKER"
participant_prepare_rc="$(run_prepare participant-unavailable)"
assert test "$participant_prepare_rc" -eq 0
participant_ready_rc="$(run_confirm participant-unavailable "$TMP/browser-ready.json")"
assert test "$participant_ready_rc" -eq 0
assert jq -e '.createdResources == 1 and .dispatchAllowed == true' "$TMP/participant-unavailable.confirmed"
cat > "$TMP/participant-unavailable.json" <<'JSON'
{"role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"unavailable","evidenceSource":"live","transportStub":false}
JSON
set +e
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/participant-unavailable.state" \
  --participant-result-file "$TMP/participant-unavailable.json" > "$TMP/participant-unavailable-settled.json"
settle_rc=$?
set -e
assert test "$settle_rc" -eq 76
assert jq -e '.reason == "model_participant_unavailable" and .reviewDisposition == "REVIEW INCOMPLETE"' "$TMP/participant-unavailable-settled.json"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 2
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 2
assert test ! -e "$TEST_SERVER_MARKER"

# Successful created-resource path also performs exactly one cleanup.
completed_prepare_rc="$(run_prepare completed-created)"
assert test "$completed_prepare_rc" -eq 0
jq '.start.cleanupArgv = ["./tools/ui-review-wrong-stop"]' "$REPO/.dm/ui-review.json" > "$TMP/changed-declaration.json"
cp "$TMP/changed-declaration.json" "$REPO/.dm/ui-review.json"
completed_ready_rc="$(run_confirm completed-created "$TMP/browser-ready.json")"
assert test "$completed_ready_rc" -eq 0
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/completed-created.state" \
  --participant-result-file "$TMP/participant-completed.json" > "$TMP/completed-created-settled.json"
assert jq -e '.state == "completed" and .cleanup == "complete"' "$TMP/completed-created-settled.json"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 3
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 3
assert test "$(grep -c '^wrong-cleanup$' "$TEST_RESOURCE_LOG" || true)" -eq 0
assert test ! -e "$TEST_SERVER_MARKER"

# Cleanup is idempotent and reports what this invocation actually removed.
"$HELPER" cleanup --repository-root "$REPO" --state-file "$TMP/completed-created.state" \
  > "$TMP/already-clean.json"
assert jq -e '.state == "already_clean" and .removedCount == 0' "$TMP/already-clean.json"

# Missing readiness is aggregated once even when three UI analysis lanes apply,
# and remote web search never counts as local navigation.
assert test "$(grep -c 'one aggregated `visual_target_unavailable` coverage note' "$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md")" -eq 1
assert grep -Fq 'OpenRouter web search is remote public-web retrieval.' "$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md"

printf 'dm-review-ui-readiness: %d assertions passed\n' "$pass"
