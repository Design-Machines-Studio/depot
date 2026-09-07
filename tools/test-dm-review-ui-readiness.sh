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
cat > "$REPO/AGENTS.md" <<'EOF'
# UI development

Application: fixture-ui in this checkout. Use ./tools/ui-review-ready for
status. The owned process cleanup is ./tools/ui-review-stop.
EOF
git -C "$REPO" add AGENTS.md tools
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm fixture

export TEST_SERVER_MARKER="$TMP/server-ready"
export TEST_RESOURCE_LOG="$TMP/resources.log"
: > "$TEST_RESOURCE_LOG"

run_prepare() {
  local name="$1" rc=0
  shift
  rm -f "$TMP/$name.state" "$TMP/$name.result"
  "$HELPER" prepare --repository-root "$REPO" --state-file "$TMP/$name.state" \
    --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
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

cat > "$TMP/browser-repository.json" <<'JSON'
{"schemaVersion":1,"status":"ready","transportClass":"local-interactive","localNavigation":"confirmed","targetUrl":"http://127.0.0.1:49173/review","evidenceRef":"review/browser/repository.json"}
JSON

# Host interpretation remains distinct from helper discovery. The helper
# consumes the bounded ready evidence and preserves exact provenance.
jq -cn --arg checkout "$(cd "$REPO" && pwd -P)" \
  --arg head "$(git -C "$REPO" rev-parse HEAD)" \
  '{schemaVersion:1,status:"ready",targetSource:"repository-declaration",
    application:"fixture-ui",checkoutRoot:$checkout,repositoryCommit:$head,checkoutState:"clean",
    sources:[{path:"AGENTS.md",lineStart:1,lineEnd:4}],
    attempts:[{kind:"status",argv:["./tools/ui-review-ready"],exitStatus:0,outputTail:"fixture-ui ready"}],
    targetUrl:"http://127.0.0.1:49173/review",targetUrlProvenance:"status-output",
    resourceOwnership:"pre-existing",cleanupArgv:[],cleanupTimeoutSeconds:0}' \
  > "$TMP/repository-evidence.json"
repository_prepare_rc="$(run_prepare repository-declaration --target-source repository-declaration --repository-evidence-file "$TMP/repository-evidence.json")"
assert test "$repository_prepare_rc" -eq 0
assert jq -e '.targetSource == "repository-declaration" and .targetRef == "private-readiness-state" and
  (has("targetUrl") | not) and .createdResources == 0 and
  .repositoryEvidence.sources == [{path:"AGENTS.md",lineStart:1,lineEnd:4}] and
  .repositoryEvidence.attempts[0].argv == ["./tools/ui-review-ready"] and
  (.repositoryEvidence.attempts[0] | has("outputTail") | not) and
  .repositoryEvidence.resourceOwnership == "pre-existing"' "$TMP/repository-declaration.result"
repository_ready_rc="$(run_confirm repository-declaration "$TMP/browser-repository.json")"
assert test "$repository_ready_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true and
  .targetRef == "private-readiness-state" and (has("targetUrl") | not)' "$TMP/repository-declaration.confirmed"
"$HELPER" cleanup --repository-root "$REPO" --state-file "$TMP/repository-declaration.state" > "$TMP/repository-declaration-cleanup.json"
assert jq -e '.state == "already_clean" and .removedCount == 0' "$TMP/repository-declaration-cleanup.json"

# Stale repository evidence is rejected before navigation and cannot silently
# fall back to a guessed target.
jq '.repositoryCommit = "0000000000000000000000000000000000000000"' \
  "$TMP/repository-evidence.json" > "$TMP/repository-evidence-stale.json"
stale_repository_rc="$(run_prepare stale-repository --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-stale.json" --visual-required true)"
assert test "$stale_repository_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("repository_commit_mismatch"))' "$TMP/stale-repository.result"

jq '.sources[0].lineEnd = 50' "$TMP/repository-evidence.json" \
  > "$TMP/repository-evidence-unbounded-line.json"
unbounded_source_rc="$(run_prepare unbounded-source --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-unbounded-line.json" --visual-required true)"
assert test "$unbounded_source_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("source_line_out_of_range"))' "$TMP/unbounded-source.result"

jq '.attempts[0].outputTail = "set-cookie: session=not-for-public-output"' \
  "$TMP/repository-evidence.json" > "$TMP/repository-evidence-secret.json"
secret_output_rc="$(run_prepare secret-output --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-secret.json" --visual-required true)"
assert test "$secret_output_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("repository_evidence_invalid"))' "$TMP/secret-output.result"

jq '.attempts = [range(0;4) |
  {kind:"status",argv:["./tools/ui-review-ready"],exitStatus:0,outputTail:("x" * 7000)}]' \
  "$TMP/repository-evidence.json" > "$TMP/repository-evidence-aggregate.json"
aggregate_output_rc="$(run_prepare aggregate-output --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-aggregate.json" --visual-required true)"
assert test "$aggregate_output_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("repository_evidence_invalid"))' "$TMP/aggregate-output.result"

# Dirty source is bound by content, not merely by the word "dirty".
printf '%s\n' '# dirty snapshot one' >> "$REPO/AGENTS.md"
jq '.checkoutState = "dirty" | .sources[0].lineEnd = 5' \
  "$TMP/repository-evidence.json" > "$TMP/repository-evidence-dirty.json"
dirty_repository_rc="$(run_prepare dirty-repository --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-dirty.json" --visual-required true)"
assert test "$dirty_repository_rc" -eq 0
printf '%s\n' '# dirty snapshot two' >> "$REPO/AGENTS.md"
dirty_repository_browser_rc="$(run_confirm dirty-repository "$TMP/browser-repository.json")"
assert test "$dirty_repository_browser_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("checkout content changed"))' "$TMP/dirty-repository.confirmed"
git -C "$REPO" show HEAD:AGENTS.md > "$REPO/AGENTS.md"

# A review-created discovered process keeps its immutable cleanup in readiness
# state. Browser failure cleans that process exactly once.
touch "$TEST_SERVER_MARKER"
: > "$TEST_RESOURCE_LOG"
jq '.resourceOwnership = "review-created-process" |
  .cleanupArgv = ["./tools/ui-review-stop"] | .cleanupTimeoutSeconds = 2 |
  .attempts += [{kind:"start",argv:["./tools/ui-review-start"],exitStatus:0,outputTail:"http://127.0.0.1:49173/review"}] |
  .targetUrlProvenance = "start-output"' \
  "$TMP/repository-evidence.json" > "$TMP/repository-created-evidence.json"
created_repository_rc="$(run_prepare repository-created --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-created-evidence.json" --visual-required true)"
assert test "$created_repository_rc" -eq 0
assert jq -e '.createdByReview == true and .cleanupPending == true and
  .repositoryEvidence.resourceOwnership == "review-created-process" and
  .cleanupArgv == ["./tools/ui-review-stop"]' "$TMP/repository-created.state"
created_repository_browser_rc="$(run_confirm repository-created "$TMP/missing-browser.json")"
assert test "$created_repository_browser_rc" -eq 76
assert jq -e '.reason == "browser_transport_unavailable"' "$TMP/repository-created.confirmed"
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 1
assert test ! -e "$TEST_SERVER_MARKER"
: > "$TEST_RESOURCE_LOG"

# Dirty initialized submodules are rejected because the root dirty marker does
# not bind their changing content.
SUBMODULE="$TMP/source-submodule"
mkdir -p "$SUBMODULE"
git -C "$SUBMODULE" init -q
printf '%s\n' initial > "$SUBMODULE/source.txt"
git -C "$SUBMODULE" add source.txt
git -C "$SUBMODULE" -c user.name=test -c user.email=test@example.invalid commit -qm initial
git -C "$REPO" -c protocol.file.allow=always submodule add -q "$SUBMODULE" vendor/source
git -C "$REPO" add .gitmodules vendor/source
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm submodule
printf '%s\n' changed >> "$REPO/vendor/source/source.txt"
jq --arg head "$(git -C "$REPO" rev-parse HEAD)" \
  '.repositoryCommit = $head | .checkoutState = "dirty"' \
  "$TMP/repository-evidence.json" > "$TMP/repository-evidence-dirty-submodule.json"
dirty_submodule_rc="$(run_prepare dirty-submodule --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-dirty-submodule.json" --visual-required true)"
assert test "$dirty_submodule_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("dirty_submodule_unsupported"))' "$TMP/dirty-submodule.result"
git -C "$REPO/vendor/source" show HEAD:source.txt > "$REPO/vendor/source/source.txt"

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
fractional_rc="$(run_prepare fractional --visual-required true)"
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
web_prepare_rc="$(run_prepare remote-web --visual-required true)"
assert test "$web_prepare_rc" -eq 0
assert jq -e '.state == "app_ready" and .dispatchAllowed == false and .reason == "browser_evidence_required"' "$TMP/remote-web.result"
assert test -e "$TEST_SERVER_MARKER"
"$HELPER" prepare --repository-root "$REPO" --state-file "$TMP/remote-web.state" \
  --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
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
assert test "$preexisting_rc" -eq 0
assert jq -e '.reason == "browser_transport_unavailable" and .dispatchAllowed == false and .coverageDisposition == "NOT RUN" and .reviewDisposition == "completed"' "$TMP/preexisting.confirmed"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 1
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 1
assert test -e "$TEST_SERVER_MARKER"

# Server plus real local browser permits the provider-neutral analysis lane.
ready_prepare_rc="$(run_prepare ready)"
assert test "$ready_prepare_rc" -eq 0
ready_rc="$(run_confirm ready "$TMP/browser-ready.json")"
assert test "$ready_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true and .browserTransport == "local-interactive"' "$TMP/ready.confirmed"
cat > "$TMP/analysis-completed.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[
  {"lane":"visual-browser-tester","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"},
  {"lane":"ux-quality-reviewer","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"},
  {"lane":"ui-standards-reviewer","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"}
]}
JSON
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/ready.state" \
  --analysis-result-file "$TMP/analysis-completed.json" > "$TMP/ready-settled.json"
assert jq -e '.state == "completed" and .dispatchAllowed == false and .cleanup == "complete"' "$TMP/ready-settled.json"
assert test -e "$TEST_SERVER_MARKER"
set +e
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/ready.state" \
  --analysis-result-file "$TMP/analysis-completed.json" >/dev/null 2>&1
repeated_settle_rc=$?
set -e
assert test "$repeated_settle_rc" -eq 2

# Settlement is bound to the exact lane set selected before readiness. A
# submitted subset cannot silently stand in for the three planned lanes.
missing_lanes_prepare_rc="$(run_prepare missing-lanes)"
assert test "$missing_lanes_prepare_rc" -eq 0
missing_lanes_ready_rc="$(run_confirm missing-lanes "$TMP/browser-ready.json")"
assert test "$missing_lanes_ready_rc" -eq 0
cat > "$TMP/analysis-missing-lanes.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[
  {"lane":"visual-browser-tester","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"}
]}
JSON
set +e
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/missing-lanes.state" \
  --analysis-result-file "$TMP/analysis-missing-lanes.json" > "$TMP/missing-lanes-settled.json"
missing_lanes_settle_rc=$?
set -e
assert test "$missing_lanes_settle_rc" -eq 76
assert jq -e '.reason == "model_participant_unavailable" and .reviewDisposition == "REVIEW INCOMPLETE"' "$TMP/missing-lanes-settled.json"

# An intentional subset remains valid when prepare binds that exact set and
# every planned lane completes.
"$HELPER" prepare --repository-root "$REPO" --state-file "$TMP/subset.state" \
  --applicable-lanes-json '["ui-standards-reviewer"]' > "$TMP/subset.result"
assert jq -e '.state == "app_ready" and .dispatchAllowed == false' "$TMP/subset.result"
"$HELPER" confirm-browser --repository-root "$REPO" --state-file "$TMP/subset.state" \
  --browser-evidence-file "$TMP/browser-ready.json" > "$TMP/subset.confirmed"
assert jq -e '.state == "ready" and .dispatchAllowed == true' "$TMP/subset.confirmed"
cat > "$TMP/analysis-subset.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[
  {"lane":"ui-standards-reviewer","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"}
]}
JSON
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/subset.state" \
  --analysis-result-file "$TMP/analysis-subset.json" > "$TMP/subset-settled.json"
assert jq -e '.state == "completed" and .reviewDisposition == "completed"' "$TMP/subset-settled.json"

# Browser evidence can be ready while the analysis participant is unavailable;
# that cause is distinct, and only the resource created by this run is cleaned.
rm -f "$TEST_SERVER_MARKER"
participant_prepare_rc="$(run_prepare participant-unavailable)"
assert test "$participant_prepare_rc" -eq 0
participant_ready_rc="$(run_confirm participant-unavailable "$TMP/browser-ready.json")"
assert test "$participant_ready_rc" -eq 0
assert jq -e '.createdResources == 1 and .dispatchAllowed == true' "$TMP/participant-unavailable.confirmed"
cat > "$TMP/analysis-unavailable.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[
  {"lane":"visual-browser-tester","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"},
  {"lane":"ux-quality-reviewer","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"unavailable"},
  {"lane":"ui-standards-reviewer","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"}
]}
JSON
set +e
"$HELPER" settle --repository-root "$REPO" --state-file "$TMP/participant-unavailable.state" \
  --analysis-result-file "$TMP/analysis-unavailable.json" > "$TMP/participant-unavailable-settled.json"
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
  --analysis-result-file "$TMP/analysis-completed.json" > "$TMP/completed-created-settled.json"
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
assert test "$(grep -c 'Do not repeat that note for the three UI lanes.' "$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md")" -eq 1
assert grep -Fq 'OpenRouter web search is remote public-web retrieval.' "$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md"

printf 'dm-review-ui-readiness: %d assertions passed\n' "$pass"
