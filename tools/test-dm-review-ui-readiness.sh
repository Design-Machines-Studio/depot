#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.sh"
WORKFLOW_KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-ui-readiness.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repository"
mkdir -p "$REPO/.dm" "$REPO/tools"
git -C "$REPO" init -q
printf '%s\n' '.workflow-kernel/' >> "$REPO/.git/info/exclude"
"$WORKFLOW_KERNEL" init "$REPO/.workflow-kernel/runs/ui-readiness-fixture" \
  --run-id ui-readiness-fixture --occurred-at 2026-09-07T00:00:00Z >/dev/null
STATE_ROOT="$REPO/.workflow-kernel/ui-readiness"
mkdir -p "$STATE_ROOT"
REPOSITORY_SCOPE_ID="$(jq -r '.scope_id' "$REPO/.workflow-kernel/repository-scope.json")"
REGISTRY_ARGS=(
  --workflow-kernel "$WORKFLOW_KERNEL"
  --expected-registry-run-id fixture-run
  --expected-registry-node-id fixture-compose
)

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
cat > "$REPO/Makefile" <<'EOF'
dev:
	@:
EOF
git -C "$REPO" add AGENTS.md Makefile tools
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm fixture

export TEST_SERVER_MARKER="$TMP/server-ready"
export TEST_RESOURCE_LOG="$TMP/resources.log"
: > "$TEST_RESOURCE_LOG"

run_prepare() {
  local name="$1" rc=0
  shift
  rm -f "$STATE_ROOT/$name.state" "$TMP/$name.result"
  "$HELPER" prepare --repository-root "$REPO" --state-file "$STATE_ROOT/$name.state" \
    --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
    "${REGISTRY_ARGS[@]}" \
    "$@" > "$TMP/$name.result" || rc=$?
  printf '%s\n' "$rc"
}

run_confirm() {
  local name="$1" browser_file="$2" expected_ownership="${3:-}" rc=0
  local ownership_args=()
  [ -z "$expected_ownership" ] || ownership_args=(--expected-resource-ownership "$expected_ownership")
  "$HELPER" confirm-browser --repository-root "$REPO" --state-file "$STATE_ROOT/$name.state" \
    "${REGISTRY_ARGS[@]}" \
    "${ownership_args[@]}" \
    --browser-evidence-file "$browser_file" > "$TMP/$name.confirmed" || rc=$?
  printf '%s\n' "$rc"
}

# No declaration means no guessed localhost scan and one nonblocking coverage
# note in an ordinary review.
no_decl_rc="$(run_prepare no-declaration)"
assert test "$no_decl_rc" -eq 0
assert jq -e '.dispatchAllowed == false and .reason == "visual_target_unavailable" and .coverageDisposition == "NOT RUN" and .reviewDisposition == "completed"' "$TMP/no-declaration.result"
assert test ! -e "$STATE_ROOT/no-declaration.state"

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
"$HELPER" cleanup --repository-root "$REPO" --state-file "$STATE_ROOT/attached-preview.state" > "$TMP/attached-preview-cleanup.json"
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
"$HELPER" cleanup --repository-root "$REPO" --state-file "$STATE_ROOT/remote-explicit.state" > "$TMP/remote-explicit-cleanup.json"
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
    resourceOwnership:"pre-existing",resourceRegistryRef:"",resourceRegistryRunId:"",resourceRegistryNodeId:"",
    cleanupArgv:[],cleanupTimeoutSeconds:0}' \
  > "$TMP/repository-evidence.json"
repository_prepare_rc="$(run_prepare repository-declaration --target-source repository-declaration --repository-evidence-file "$TMP/repository-evidence.json")"
assert test "$repository_prepare_rc" -eq 0
assert jq -e '.targetSource == "repository-declaration" and .targetRef == "private-readiness-state" and
  (has("targetUrl") | not) and .createdResources == 0 and
  .repositoryEvidence.sources == [{path:"AGENTS.md",lineStart:1,lineEnd:4}] and
  .repositoryEvidence.attempts == [{kind:"status",exitStatus:0}] and
  (.repositoryEvidence.attempts[0] | has("argv") | not) and
  (.repositoryEvidence.attempts[0] | has("outputTail") | not) and
  .repositoryEvidence.resourceOwnership == "pre-existing"' "$TMP/repository-declaration.result"
repository_ready_rc="$(run_confirm repository-declaration "$TMP/browser-repository.json" pre-existing)"
assert test "$repository_ready_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true and
  .targetRef == "private-readiness-state" and (has("targetUrl") | not)' "$TMP/repository-declaration.confirmed"
"$HELPER" cleanup --repository-root "$REPO" --state-file "$STATE_ROOT/repository-declaration.state" \
  --expected-resource-ownership pre-existing > "$TMP/repository-declaration-cleanup.json"
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

# Credential-bearing argv stays out of accepted private evidence, while all
# argv is omitted from the public projection even after validation succeeds.
jq '.attempts[0].argv = ["./tools/ui-review-ready","--api-key","not-for-public-output"]' \
  "$TMP/repository-evidence.json" > "$TMP/repository-evidence-secret-argv.json"
secret_argv_rc="$(run_prepare secret-argv --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-secret-argv.json" --visual-required true)"
assert test "$secret_argv_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("repository_evidence_invalid"))' "$TMP/secret-argv.result"

credential_case=0
for credential_arg in \
  '--token=fixture-value' \
  'token=fixture-value' \
  '--cookie=fixture-value' \
  '--authorization=fixture-value' \
  '--bearer=fixture-value' \
  '--x-api-key=fixture-value' \
  '--user=fixture-user:fixture-password' \
  '--proxy-user=fixture-user:fixture-password' \
  '-u=fixture-user:fixture-password' \
  '-u=alice:opaque-value' \
  '-ufixture-user:fixture-password'; do
  credential_case=$((credential_case + 1))
  jq --arg credential_arg "$credential_arg" \
    '.attempts[0].argv = ["./tools/ui-review-ready",$credential_arg]' \
    "$TMP/repository-evidence.json" > "$TMP/repository-evidence-credential-$credential_case.json"
  credential_rc="$(run_prepare "credential-$credential_case" --target-source repository-declaration \
    --repository-evidence-file "$TMP/repository-evidence-credential-$credential_case.json" --visual-required true)"
  assert test "$credential_rc" -eq 76
  assert jq -e '.reason == "dev_server_unavailable" and
    (.nextAction | contains("repository_evidence_invalid"))' "$TMP/credential-$credential_case.result"
done

paired_credential_case=0
for paired_flag in '--api-key' '--token' '--x-api-key' '--user' '-u'; do
  paired_credential_case=$((paired_credential_case + 1))
  jq --arg paired_flag "$paired_flag" \
    '.attempts[0].argv = ["./tools/ui-review-ready",$paired_flag,"fixture-value"]' \
    "$TMP/repository-evidence.json" > "$TMP/repository-evidence-paired-$paired_credential_case.json"
  paired_credential_rc="$(run_prepare "paired-$paired_credential_case" --target-source repository-declaration \
    --repository-evidence-file "$TMP/repository-evidence-paired-$paired_credential_case.json" --visual-required true)"
  assert test "$paired_credential_rc" -eq 76
  assert jq -e '.reason == "dev_server_unavailable" and
    (.nextAction | contains("repository_evidence_invalid"))' "$TMP/paired-$paired_credential_case.result"
done

output_credential_case=0
for credential_output in \
  '--api-key fixture-value' \
  '--token fixture-value' \
  '--x-api-key fixture-value' \
  '--user fixture-user:fixture-password' \
  '--proxy-user fixture-user:fixture-password' \
  '-u fixture-user:fixture-password' \
  'token: fixture-value' \
  'api-key: fixture-value' \
  'x-api-key: fixture-value' \
  'Bearer fixture-token' \
  'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==' \
  'curl -ualice:fixture-password http://localhost' \
  'curl -u=alice:opaque-value http://localhost' \
  '-----BEGIN OPENSSH PRIVATE KEY-----' \
  '-----BEGIN PGP PRIVATE KEY BLOCK-----' \
  '{"x-api-key":"fixture-value"}' \
  "{'token': 'fixture-value'}"; do
  output_credential_case=$((output_credential_case + 1))
  jq --arg credential_output "$credential_output" \
    '.attempts[0].outputTail = $credential_output' \
    "$TMP/repository-evidence.json" > "$TMP/repository-evidence-output-$output_credential_case.json"
  output_credential_rc="$(run_prepare "output-$output_credential_case" --target-source repository-declaration \
    --repository-evidence-file "$TMP/repository-evidence-output-$output_credential_case.json" --visual-required true)"
  assert test "$output_credential_rc" -eq 76
  assert jq -e '.reason == "dev_server_unavailable" and
    (.nextAction | contains("repository_evidence_invalid"))' "$TMP/output-$output_credential_case.result"
done

json_argv_case=0
for credential_json in \
  '{"x-api-key":"fixture-value"}' \
  '{"token":"fixture-value"}' \
  'token: fixture-value' \
  'x-api-key: fixture-value' \
  'Bearer fixture-token' \
  'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==' \
  '-----BEGIN PRIVATE KEY-----'; do
  json_argv_case=$((json_argv_case + 1))
  jq --arg credential_json "$credential_json" \
    '.attempts[0].argv = ["./tools/ui-review-ready",$credential_json]' \
    "$TMP/repository-evidence.json" > "$TMP/repository-evidence-json-argv-$json_argv_case.json"
  json_argv_rc="$(run_prepare "json-argv-$json_argv_case" --target-source repository-declaration \
    --repository-evidence-file "$TMP/repository-evidence-json-argv-$json_argv_case.json" --visual-required true)"
  assert test "$json_argv_rc" -eq 76
  assert jq -e '.reason == "dev_server_unavailable" and
    (.nextAction | contains("repository_evidence_invalid"))' "$TMP/json-argv-$json_argv_case.result"
done

# A harmless command or Make target whose whole argument is a sensitive noun
# carries no value and remains valid; only paired/value-bearing forms fail.
jq '.attempts[0].argv = ["make","token"]' "$TMP/repository-evidence.json" \
  > "$TMP/repository-evidence-harmless-token.json"
harmless_token_rc="$(run_prepare harmless-token --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-evidence-harmless-token.json" --visual-required true)"
assert test "$harmless_token_rc" -eq 0
"$HELPER" cleanup --repository-root "$REPO" --state-file "$STATE_ROOT/harmless-token.state" \
  --expected-resource-ownership pre-existing \
  > "$TMP/harmless-token-cleanup.json"
assert jq -e '.state == "already_clean" and .removedCount == 0' "$TMP/harmless-token-cleanup.json"

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
dirty_repository_browser_rc="$(run_confirm dirty-repository "$TMP/browser-repository.json" pre-existing)"
assert test "$dirty_repository_browser_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("checkout content changed"))' "$TMP/dirty-repository.confirmed"
git -C "$REPO" show HEAD:AGENTS.md > "$REPO/AGENTS.md"

# Host-interpreted repository discovery cannot claim a process that was
# started before cleanup supervision. Stopped raw processes use the structured
# .dm declaration path later in this test instead.
jq '.resourceOwnership = "review-created-process" |
  .cleanupArgv = ["./tools/ui-review-stop"] | .cleanupTimeoutSeconds = 2 |
  .attempts += [{kind:"start",argv:["./tools/ui-review-start"],exitStatus:0,outputTail:"http://127.0.0.1:49173/review"}] |
  .targetUrlProvenance = "start-output"' \
  "$TMP/repository-evidence.json" > "$TMP/repository-created-evidence.json"
created_repository_rc="$(run_prepare repository-created --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-created-evidence.json" --visual-required true)"
assert test "$created_repository_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("repository_evidence_invalid"))' "$TMP/repository-created.result"

# Directly named Make targets remain valid for a Compose author loop. The
# helper binds the safe Workflow Kernel registry reference, exposes no argv,
# and leaves cleanup to the registry owner.
cat > "$STATE_ROOT/resources.jsonl" <<JSON
{"event":"registered","resource":{"resource_id":"fixture-compose-container","kind":"container","run_id":"fixture-run","node_id":"fixture-compose","lifecycle":"run","cleanup_policy":"stop-remove","created_at":"2026-09-07T00:00:00+00:00","dependent_node_ids":[],"labels":{"com.designmachines.depot.managed":"true","com.designmachines.depot.run-id":"fixture-run","com.designmachines.depot.node-id":"fixture-compose","com.designmachines.depot.created-at":"2026-09-07T00:00:00+00:00","com.designmachines.depot.lifecycle":"run","com.designmachines.depot.cleanup-policy":"stop-remove","com.designmachines.depot.repository-scope-id":"$REPOSITORY_SCOPE_ID"}}}
JSON
cp "$STATE_ROOT/resources.jsonl" "$STATE_ROOT/resources-valid.jsonl"
jq '.sources += [{path:"Makefile",lineStart:1,lineEnd:2}] |
  .attempts[0].argv = ["make","dev","ACTION=status"] |
  .resourceOwnership = "review-created-compose" |
  .resourceRegistryRef = "resources.jsonl" |
  .resourceRegistryRunId = "fixture-run" |
  .resourceRegistryNodeId = "fixture-compose"' \
  "$TMP/repository-evidence.json" > "$TMP/repository-compose-evidence.json"

# Compose evidence is not authority by itself. The helper requires the trusted
# launcher and host-selected run/node context, and fails closed when either is
# unavailable.
missing_launcher_rc=0
"$HELPER" prepare --repository-root "$REPO" \
  --state-file "$STATE_ROOT/compose-missing-launcher.state" \
  --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
  --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" \
  --visual-required true > "$TMP/compose-missing-launcher.result" || missing_launcher_rc=$?
assert test "$missing_launcher_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/compose-missing-launcher.result"
cat > "$TMP/unavailable-workflow-kernel" <<'STUB'
#!/usr/bin/env bash
exit 4
STUB
chmod +x "$TMP/unavailable-workflow-kernel"
unavailable_launcher_rc=0
"$HELPER" prepare --repository-root "$REPO" \
  --state-file "$STATE_ROOT/compose-unavailable-launcher.state" \
  --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
  --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" \
  --workflow-kernel "$TMP/unavailable-workflow-kernel" \
  --expected-registry-run-id fixture-run \
  --expected-registry-node-id fixture-compose \
  --visual-required true > "$TMP/compose-unavailable-launcher.result" || unavailable_launcher_rc=$?
assert test "$unavailable_launcher_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/compose-unavailable-launcher.result"

FOREIGN_REPO="$TMP/foreign-repository"
mkdir -p "$FOREIGN_REPO"
git -C "$FOREIGN_REPO" init -q
printf '%s\n' '.workflow-kernel/' >> "$FOREIGN_REPO/.git/info/exclude"
"$WORKFLOW_KERNEL" init "$FOREIGN_REPO/.workflow-kernel/runs/foreign-fixture" \
  --run-id foreign-fixture --occurred-at 2026-09-07T00:00:00Z >/dev/null
FOREIGN_STATE_ROOT="$FOREIGN_REPO/.workflow-kernel/ui-readiness"
mkdir -p "$FOREIGN_STATE_ROOT"
FOREIGN_SCOPE_ID="$(jq -r '.scope_id' "$FOREIGN_REPO/.workflow-kernel/repository-scope.json")"
cat > "$FOREIGN_STATE_ROOT/resources.jsonl" <<JSON
{"event":"registered","resource":{"resource_id":"foreign-compose-container","kind":"container","run_id":"fixture-run","node_id":"fixture-compose","lifecycle":"run","cleanup_policy":"stop-remove","created_at":"2026-09-07T00:00:00+00:00","dependent_node_ids":[],"labels":{"com.designmachines.depot.managed":"true","com.designmachines.depot.run-id":"fixture-run","com.designmachines.depot.node-id":"fixture-compose","com.designmachines.depot.created-at":"2026-09-07T00:00:00+00:00","com.designmachines.depot.lifecycle":"run","com.designmachines.depot.cleanup-policy":"stop-remove","com.designmachines.depot.repository-scope-id":"$FOREIGN_SCOPE_ID"}}}
JSON
foreign_registry_rc=0
"$HELPER" prepare --repository-root "$REPO" \
  --state-file "$FOREIGN_STATE_ROOT/foreign-compose.state" \
  --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
  --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" \
  "${REGISTRY_ARGS[@]}" \
  --visual-required true > "$TMP/compose-foreign-registry.result" || foreign_registry_rc=$?
assert test "$foreign_registry_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/compose-foreign-registry.result"

compose_repository_rc="$(run_prepare repository-compose --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$compose_repository_rc" -eq 0
assert jq -e '.createdByReview == false and .cleanupPending == false and
  .repositoryEvidence.resourceOwnership == "review-created-compose" and
  .repositoryEvidence.resourceRegistryRef == "resources.jsonl" and
  .cleanupArgv == []' "$STATE_ROOT/repository-compose.state"
assert jq -e '.createdResources == 1 and
  .repositoryEvidence.attempts == [{kind:"status",exitStatus:0}] and
  (.repositoryEvidence | has("resourceRegistryRef") | not)' "$TMP/repository-compose.result"

# Later actions bind the host-retained ownership mode. Private state cannot
# downgrade a review-created Compose resource to pre-existing and bypass its
# registry validation or cleanup handoff.
jq '.repositoryEvidence.resourceOwnership = "pre-existing" |
  .repositoryEvidence.resourceRegistryRef = "" |
  .repositoryEvidence.resourceRegistryRunId = "" |
  .repositoryEvidence.resourceRegistryNodeId = ""' \
  "$STATE_ROOT/repository-compose.state" > "$STATE_ROOT/repository-compose-downgraded.state"
downgraded_ownership_rc=0
"$HELPER" confirm-browser --repository-root "$REPO" \
  --state-file "$STATE_ROOT/repository-compose-downgraded.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose \
  --browser-evidence-file "$TMP/browser-repository.json" \
  > "$TMP/repository-compose-downgraded.result" 2>&1 || downgraded_ownership_rc=$?
assert test "$downgraded_ownership_rc" -eq 2
assert grep -Fq 'ui-review-readiness: invalid invocation' "$TMP/repository-compose-downgraded.result"

compose_repository_browser_rc="$(run_confirm repository-compose "$TMP/browser-repository.json" review-created-compose)"
assert test "$compose_repository_browser_rc" -eq 0
assert jq -e '.state == "ready" and .dispatchAllowed == true and
  .targetRef == "private-readiness-state" and .createdResources == 1 and
  .cleanup == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/repository-compose.confirmed"
cat > "$TMP/repository-compose-analysis.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[{"lane":"visual-browser-tester","role":"review-deep","capabilities":["read-repository","structured-output"],"disposition":"completed"},{"lane":"ux-quality-reviewer","role":"review-deep","capabilities":["read-repository","structured-output"],"disposition":"completed"},{"lane":"ui-standards-reviewer","role":"review-deep","capabilities":["read-repository","structured-output"],"disposition":"completed"}]}
JSON
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/repository-compose.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose \
  --analysis-result-file "$TMP/repository-compose-analysis.json" \
  > "$TMP/repository-compose-settled.json"
assert jq -e '.state == "completed" and .cleanup == "registry_cleanup_required" and
  .registryCleanupPending == true' "$TMP/repository-compose-settled.json"
"$HELPER" cleanup --repository-root "$REPO" --state-file "$STATE_ROOT/repository-compose.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose \
  > "$TMP/repository-compose-cleanup.json"
assert jq -e '.state == "registry_cleanup_required" and .removedCount == 0 and
  .preexistingUntouched == false and .registryCleanupPending == true' \
  "$TMP/repository-compose-cleanup.json"
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 0

# The alternate exact-run-root reference resolves from a state nested under
# <run-root>/review and completes the same readiness/settlement handoff.
mkdir -p "$STATE_ROOT/review"
cp "$STATE_ROOT/resources.jsonl" "$STATE_ROOT/review/resources.jsonl"
jq '.resourceRegistryRef = "review/resources.jsonl"' "$TMP/repository-compose-evidence.json" \
  > "$TMP/repository-compose-run-root-evidence.json"
run_root_compose_rc=0
"$HELPER" prepare --repository-root "$REPO" \
  --state-file "$STATE_ROOT/review/run-root-compose.state" \
  "${REGISTRY_ARGS[@]}" \
  --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
  --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-run-root-evidence.json" \
  --visual-required true > "$TMP/run-root-compose.result" || run_root_compose_rc=$?
assert test "$run_root_compose_rc" -eq 0
"$HELPER" confirm-browser --repository-root "$REPO" \
  --state-file "$STATE_ROOT/review/run-root-compose.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose \
  --browser-evidence-file "$TMP/browser-repository.json" > "$TMP/run-root-compose.confirmed"
assert jq -e '.state == "ready" and .createdResources == 1' "$TMP/run-root-compose.confirmed"
"$HELPER" settle --repository-root "$REPO" \
  --state-file "$STATE_ROOT/review/run-root-compose.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose \
  --analysis-result-file "$TMP/repository-compose-analysis.json" > "$TMP/run-root-compose.settled"
assert jq -e '.cleanup == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/run-root-compose.settled"
"$HELPER" cleanup --repository-root "$REPO" \
  --state-file "$STATE_ROOT/review/run-root-compose.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose > "$TMP/run-root-compose-cleanup.json"
assert jq -e '.state == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/run-root-compose-cleanup.json"

# Registry authority is live evidence, not a prepare-time snapshot. Invalidating
# the complete journal before browser confirmation closes the review and keeps
# the registry cleanup requirement visible.
cp "$STATE_ROOT/resources-valid.jsonl" "$STATE_ROOT/resources.jsonl"
revalidate_prepare_rc="$(run_prepare compose-revalidate --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$revalidate_prepare_rc" -eq 0
printf '%s\n' '{"event":"not-a-registration"}' >> "$STATE_ROOT/resources.jsonl"
printf '%s\n' '# simultaneous checkout drift' >> "$REPO/AGENTS.md"
revalidate_browser_rc="$(run_confirm compose-revalidate "$TMP/browser-repository.json" review-created-compose)"
assert test "$revalidate_browser_rc" -eq 76
assert jq -e '.reason == "resource_cleanup_failed" and
  (.nextAction | contains("registry authority")) and
  .cleanup == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/compose-revalidate.confirmed"
git -C "$REPO" show HEAD:AGENTS.md > "$REPO/AGENTS.md"
cp "$STATE_ROOT/resources-valid.jsonl" "$STATE_ROOT/resources.jsonl"

# Browser failure on still-valid Compose ownership also returns the cleanup
# handoff instead of silently closing with a live registry resource.
browser_failure_prepare_rc="$(run_prepare compose-browser-failure --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$browser_failure_prepare_rc" -eq 0
browser_failure_rc="$(run_confirm compose-browser-failure "$TMP/missing-browser.json" review-created-compose)"
assert test "$browser_failure_rc" -eq 76
assert jq -e '.reason == "browser_transport_unavailable" and
  .cleanup == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/compose-browser-failure.confirmed"

# Signals on Compose paths close the state and preserve the registry cleanup
# handoff without attempting process cleanup.
signal_prepare_rc="$(run_prepare compose-interrupted --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$signal_prepare_rc" -eq 0
cat > "$TMP/signalling-workflow-kernel" <<STUB
#!/usr/bin/env bash
if [ ! -e "$TMP/compose-signal-sent" ]; then
  touch "$TMP/compose-signal-sent"
  kill -TERM "\$PPID"
fi
printf '%s\n' '{"active_resource_count":1,"kind":"resource-registry-validation","schema_version":1,"valid":true}'
STUB
chmod +x "$TMP/signalling-workflow-kernel"
signal_rc=0
"$HELPER" confirm-browser --repository-root "$REPO" \
  --state-file "$STATE_ROOT/compose-interrupted.state" \
  --browser-evidence-file "$TMP/browser-repository.json" \
  --workflow-kernel "$TMP/signalling-workflow-kernel" \
  --expected-registry-run-id fixture-run \
  --expected-registry-node-id fixture-compose \
  --expected-resource-ownership review-created-compose \
  > "$TMP/compose-interrupted.result" || signal_rc=$?
assert test "$signal_rc" -eq 130
assert jq -e '.reason == "resource_cleanup_failed" and
  .cleanup == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/compose-interrupted.result"
assert jq -e '.stage == "closed" and .dispatchAllowed == false' \
  "$STATE_ROOT/compose-interrupted.state"
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 0

# Optional rendered coverage keeps its ordinary NOT RUN disposition while
# still surfacing the mandatory Compose registry cleanup handoff.
optional_gap_prepare_rc="$(run_prepare compose-optional-gap --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json")"
assert test "$optional_gap_prepare_rc" -eq 0
optional_gap_rc="$(run_confirm compose-optional-gap "$TMP/missing-browser.json" review-created-compose)"
assert test "$optional_gap_rc" -eq 0
assert jq -e '.state == "not_available" and .coverageDisposition == "NOT RUN" and
  .reviewDisposition == "completed" and .createdResources == 1 and
  .cleanup == "registry_cleanup_required" and
  .registryCleanupPending == true' "$TMP/compose-optional-gap.confirmed"

# Analysis failure retains the same Compose cleanup handoff.
analysis_failure_prepare_rc="$(run_prepare compose-analysis-failure --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$analysis_failure_prepare_rc" -eq 0
analysis_failure_browser_rc="$(run_confirm compose-analysis-failure "$TMP/browser-repository.json" review-created-compose)"
assert test "$analysis_failure_browser_rc" -eq 0
cat > "$TMP/repository-compose-analysis-unavailable.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[{"lane":"visual-browser-tester","role":"review-deep","capabilities":["read-repository","structured-output"],"disposition":"completed"},{"lane":"ux-quality-reviewer","role":"review-deep","capabilities":["read-repository","structured-output"],"disposition":"unavailable"},{"lane":"ui-standards-reviewer","role":"review-deep","capabilities":["read-repository","structured-output"],"disposition":"completed"}]}
JSON
analysis_failure_rc=0
"$HELPER" settle --repository-root "$REPO" \
  --state-file "$STATE_ROOT/compose-analysis-failure.state" \
  "${REGISTRY_ARGS[@]}" \
  --expected-resource-ownership review-created-compose \
  --analysis-result-file "$TMP/repository-compose-analysis-unavailable.json" \
  > "$TMP/compose-analysis-failure.settled" || analysis_failure_rc=$?
assert test "$analysis_failure_rc" -eq 76
assert jq -e '.reason == "model_participant_unavailable" and
  .cleanup == "registry_cleanup_required" and .registryCleanupPending == true' \
  "$TMP/compose-analysis-failure.settled"

# Compose ownership fails closed unless the registry reference is one of the
# exact bounded forms and resolves to a real registry containing a Docker
# registration.
registry_case=0
for invalid_ref in '' '../resources.jsonl' 'review/resources$.jsonl' "$(printf 'a%.0s' {1..257})" 'missing/resources.jsonl'; do
  registry_case=$((registry_case + 1))
  jq --arg invalid_ref "$invalid_ref" '.resourceRegistryRef = $invalid_ref' \
    "$TMP/repository-compose-evidence.json" > "$TMP/repository-registry-$registry_case.json"
  registry_rc="$(run_prepare "registry-$registry_case" --target-source repository-declaration \
    --repository-evidence-file "$TMP/repository-registry-$registry_case.json" --visual-required true)"
  assert test "$registry_rc" -eq 76
  assert jq -e '.reason == "dev_server_unavailable"' "$TMP/registry-$registry_case.result"
done
jq '.resourceRegistryNodeId = "another-node"' "$TMP/repository-compose-evidence.json" \
  > "$TMP/repository-registry-mismatched-node.json"
mismatched_registry_rc="$(run_prepare registry-mismatched-node --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-registry-mismatched-node.json" --visual-required true)"
assert test "$mismatched_registry_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/registry-mismatched-node.result"
cat > "$STATE_ROOT/resources.jsonl" <<JSON
{"event":"registered","resource":{"resource_id":"fixture-compose-container","kind":"container","run_id":"fixture-run","node_id":"fixture-compose","lifecycle":"run","cleanup_policy":"stop-remove","created_at":"2026-09-07T00:00:00+00:00","dependent_node_ids":[],"labels":{"com.designmachines.depot.managed":"true","com.designmachines.depot.run-id":"fixture-run","com.designmachines.depot.node-id":"fixture-compose","com.designmachines.depot.created-at":"2026-09-07T00:00:00+00:00","com.designmachines.depot.lifecycle":"run","com.designmachines.depot.cleanup-policy":"stop-remove","com.designmachines.depot.repository-scope-id":"$REPOSITORY_SCOPE_ID"}}}
{"event":"not-a-registration"}
JSON
jq '.resourceRegistryRef = "resources.jsonl"' "$TMP/repository-compose-evidence.json" \
  > "$TMP/repository-registry-invalid.json"
invalid_registry_rc="$(run_prepare registry-invalid --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-registry-invalid.json" --visual-required true)"
assert test "$invalid_registry_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/registry-invalid.result"
cat > "$STATE_ROOT/resources.jsonl" <<'JSON'
{"event":"registered","resource":{"resource_id":"fixture-compose-container","kind":"container","run_id":"fixture-run","node_id":"fixture-compose","lifecycle":"run","cleanup_policy":"stop-remove","created_at":"2026-09-07T00:00:00+00:00","dependent_node_ids":[],"labels":{"proof":"owned"}}}
JSON
unlabelled_registry_rc="$(run_prepare registry-unlabelled --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$unlabelled_registry_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/registry-unlabelled.result"
cp "$STATE_ROOT/resources-valid.jsonl" "$STATE_ROOT/resources.jsonl"
jq '.resource.labels["com.designmachines.depot.created-at"] = "2026-09-07T00:10:01+00:00"' \
  "$STATE_ROOT/resources.jsonl" > "$STATE_ROOT/resources-timestamp-mismatch.jsonl"
mv "$STATE_ROOT/resources-timestamp-mismatch.jsonl" "$STATE_ROOT/resources.jsonl"
timestamp_registry_rc="$(run_prepare registry-timestamp-mismatch --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$timestamp_registry_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_invalid"))' "$TMP/registry-timestamp-mismatch.result"
rm -f "$STATE_ROOT/resources.jsonl"
missing_registry_rc="$(run_prepare registry-missing --target-source repository-declaration \
  --repository-evidence-file "$TMP/repository-compose-evidence.json" --visual-required true)"
assert test "$missing_registry_rc" -eq 76
assert jq -e '.reason == "dev_server_unavailable" and
  (.nextAction | contains("resource_registry_unavailable"))' "$TMP/registry-missing.result"

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
assert test ! -e "$STATE_ROOT/hostless-explicit.state"
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
"$HELPER" prepare --repository-root "$REPO" --state-file "$STATE_ROOT/remote-web.state" \
  --applicable-lanes-json '["visual-browser-tester","ux-quality-reviewer","ui-standards-reviewer"]' \
  > "$TMP/remote-web-reprepare.result"
assert jq -e '.createdResources == 1 and .dispatchAllowed == false' "$TMP/remote-web-reprepare.result"
assert jq -e '.createdByReview == true and .cleanupPending == true and .stage == "app_ready"' "$STATE_ROOT/remote-web.state"
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
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/ready.state" \
  --analysis-result-file "$TMP/analysis-completed.json" > "$TMP/ready-settled.json"
assert jq -e '.state == "completed" and .dispatchAllowed == false and .cleanup == "complete"' "$TMP/ready-settled.json"
assert test -e "$TEST_SERVER_MARKER"
set +e
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/ready.state" \
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
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/missing-lanes.state" \
  --analysis-result-file "$TMP/analysis-missing-lanes.json" > "$TMP/missing-lanes-settled.json"
missing_lanes_settle_rc=$?
set -e
assert test "$missing_lanes_settle_rc" -eq 76
assert jq -e '.reason == "model_participant_unavailable" and .reviewDisposition == "REVIEW INCOMPLETE"' "$TMP/missing-lanes-settled.json"

# An intentional subset remains valid when prepare binds that exact set and
# every planned lane completes.
"$HELPER" prepare --repository-root "$REPO" --state-file "$STATE_ROOT/subset.state" \
  --applicable-lanes-json '["ui-standards-reviewer"]' > "$TMP/subset.result"
assert jq -e '.state == "app_ready" and .dispatchAllowed == false' "$TMP/subset.result"
"$HELPER" confirm-browser --repository-root "$REPO" --state-file "$STATE_ROOT/subset.state" \
  --browser-evidence-file "$TMP/browser-ready.json" > "$TMP/subset.confirmed"
assert jq -e '.state == "ready" and .dispatchAllowed == true' "$TMP/subset.confirmed"
cat > "$TMP/analysis-subset.json" <<'JSON'
{"evidenceSource":"live","transportStub":false,"lanes":[
  {"lane":"ui-standards-reviewer","role":"review-deep","capabilities":["read-repository","long-context","structured-output"],"disposition":"completed"}
]}
JSON
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/subset.state" \
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
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/participant-unavailable.state" \
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
"$HELPER" settle --repository-root "$REPO" --state-file "$STATE_ROOT/completed-created.state" \
  --analysis-result-file "$TMP/analysis-completed.json" > "$TMP/completed-created-settled.json"
assert jq -e '.state == "completed" and .cleanup == "complete"' "$TMP/completed-created-settled.json"
assert test "$(grep -c '^start$' "$TEST_RESOURCE_LOG")" -eq 3
assert test "$(grep -c '^cleanup$' "$TEST_RESOURCE_LOG")" -eq 3
assert test "$(grep -c '^wrong-cleanup$' "$TEST_RESOURCE_LOG" || true)" -eq 0
assert test ! -e "$TEST_SERVER_MARKER"

# Cleanup is idempotent and reports what this invocation actually removed.
"$HELPER" cleanup --repository-root "$REPO" --state-file "$STATE_ROOT/completed-created.state" \
  > "$TMP/already-clean.json"
assert jq -e '.state == "already_clean" and .removedCount == 0' "$TMP/already-clean.json"

# Missing readiness is aggregated once even when three UI analysis lanes apply,
# and remote web search never counts as local navigation.
assert test "$(grep -c 'Do not repeat that note for the three UI lanes.' "$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md")" -eq 1
assert grep -Fq 'OpenRouter web search is remote public-web retrieval.' "$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md"

printf 'dm-review-ui-readiness: %d assertions passed\n' "$pass"
