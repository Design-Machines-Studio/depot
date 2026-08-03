#!/usr/bin/env bash
# Behavioral fixtures for the OpenRouter threat/content and output boundary.

set -euo pipefail

# Keep strict-approval fixtures deterministic even when the developer's global
# harness environment opts into trusted-boundary authorization.
export OPENROUTER_PAYLOAD_AUTHORIZATION=exact-digest

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
POLICY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
RUNNER="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
EXEC_RUNNER="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
BOUNDARY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh"
WRAPPER="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
AUTHORIZATION="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/payload-authorization.sh"

FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

expect_rc() {
  local expected="$1"
  local reason="$2"
  local label="$3"
  shift 3
  local rc
  if "$@" >"$FIXTURE_ROOT/cmd.out" 2>"$FIXTURE_ROOT/cmd.err"; then
    rc=0
  else
    rc=$?
  fi
  if [ "$rc" -ne "$expected" ]; then
    echo "$label: expected exit $expected, got $rc" >&2
    cat "$FIXTURE_ROOT/cmd.err" >&2
    exit 1
  fi
  if [ -n "$reason" ] && ! grep -Fq "$reason" "$FIXTURE_ROOT/cmd.err"; then
    echo "$label: missing stable reason $reason" >&2
    cat "$FIXTURE_ROOT/cmd.err" >&2
    exit 1
  fi
}

expect_rc 2 'native-vendor-origin invariant' 'mixed-case wrapper origin' \
  env OPENROUTER_API_KEY=fixture "$WRAPPER" OpenAI/gpt-test prompt
expect_rc 2 'native-vendor-origin invariant' 'mixed-case exec origin' \
  "$EXEC_RUNNER" --dry-run --model Anthropic/claude-test

printf '%s\n' 'plugins/openrouter/README.md' > "$FIXTURE_ROOT/safe-files"
printf '%s\n' 'plugins/openrouter/README.md' '.airlift/uncommitted.patch' > "$FIXTURE_ROOT/mixed-files"
printf '%s\n' 'auth/session.go' 'federation/trust.go' 'deploy/app.service' > "$FIXTURE_ROOT/security-files"
printf '%s\n' 'plugins/openrouter/file with spaces.md' > "$FIXTURE_ROOT/quoted-files"
printf '%s\n' 'docs/outside.md' > "$FIXTURE_ROOT/outside-files"
printf '%s\n' 'docs/ghp_abcdefghijklmnop1234567890.md' > "$FIXTURE_ROOT/credential-path-files"

cat > "$FIXTURE_ROOT/safe.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/security.diff" <<'EOF'
diff --git a/auth/session.go b/auth/session.go
--- a/auth/session.go
+++ b/auth/session.go
@@ -1 +1 @@
-old middleware
+new middleware checks the Authorization header
diff --git a/federation/trust.go b/federation/trust.go
--- a/federation/trust.go
+++ b/federation/trust.go
@@ -1 +1 @@
-old trust code
+const envName = "OPENROUTER_API_KEY"
diff --git a/deploy/app.service b/deploy/app.service
--- a/deploy/app.service
+++ b/deploy/app.service
@@ -1 +1 @@
-old docs
+docs mention deploy/.env.example and Bearer <redacted>
EOF
cat > "$FIXTURE_ROOT/quoted.diff" <<'EOF'
diff --git "a/plugins/openrouter/file with spaces.md" "b/plugins/openrouter/file with spaces.md"
--- "a/plugins/openrouter/file with spaces.md"
+++ "b/plugins/openrouter/file with spaces.md"
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/placeholder.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1,4 @@
-old
+Authorization: Bearer <token>
+OPENROUTER_API_KEY=REDACTED
+dsn=postgres://user:@example/db
+token=${OPENROUTER_API_KEY}
EOF
cat > "$FIXTURE_ROOT/removed-secret.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnop1234567890
+OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
EOF
cat > "$FIXTURE_ROOT/mixed-secret.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+safe documentation change
diff --git a/.airlift/uncommitted.patch b/.airlift/uncommitted.patch
--- a/.airlift/uncommitted.patch
+++ b/.airlift/uncommitted.patch
@@ -1 +1 @@
-old snapshot
+OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnop1234567890
EOF
cat > "$FIXTURE_ROOT/token.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.real-session-token-1234567890
EOF
cat > "$FIXTURE_ROOT/raw-jwt.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkZpeHR1cmUifQ.c3ludGhldGljLXNpZ25hdHVyZS1maXh0dXJl
EOF
cat > "$FIXTURE_ROOT/slack-token.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+xoxb-synthetic-service-token-1234567890
EOF
cat > "$FIXTURE_ROOT/short-jwt.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+eyJhbGciOiJub25lIn0.e30.
EOF
cat > "$FIXTURE_ROOT/github-service-token.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+ghs_synthetic-service-token-1234567890
EOF
cat > "$FIXTURE_ROOT/access-key.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+AWS_SECRET_ACCESS_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/==
EOF
cat > "$FIXTURE_ROOT/private-key.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1,3 @@
-old
+-----BEGIN PRIVATE KEY-----
+QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo0123456789abcd
+-----END PRIVATE KEY-----
EOF
cat > "$FIXTURE_ROOT/private-key-header.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+-----BEGIN PRIVATE KEY-----
EOF
cat > "$FIXTURE_ROOT/symlink-retarget.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
index 1111111..2222222 120000
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-safe-target
+../../../../tmp/outside-target
EOF
cat > "$FIXTURE_ROOT/gitlink-retarget.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
index 1111111..2222222 160000
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-Subproject commit 1111111111111111111111111111111111111111
+Subproject commit 2222222222222222222222222222222222222222
EOF
cat > "$FIXTURE_ROOT/credential-path.diff" <<'EOF'
diff --git a/docs/ghp_abcdefghijklmnop1234567890.md b/docs/ghp_abcdefghijklmnop1234567890.md
--- a/docs/ghp_abcdefghijklmnop1234567890.md
+++ b/docs/ghp_abcdefghijklmnop1234567890.md
@@ -1 +1 @@
-old documentation
+new documentation
EOF
cat > "$FIXTURE_ROOT/dsn.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+postgres://app:hunter2@production-host/db
EOF
cat > "$FIXTURE_ROOT/outside.diff" <<'EOF'
diff --git a/docs/outside.md b/docs/outside.md
--- a/docs/outside.md
+++ b/docs/outside.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/mismatch.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/OTHER.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/traversal.diff" <<'EOF'
diff --git a/../outside.md b/../outside.md
--- a/../outside.md
+++ b/../outside.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/absolute.diff" <<'EOF'
diff --git a//tmp/outside.md b//tmp/outside.md
--- a//tmp/outside.md
+++ b//tmp/outside.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/binary.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
Binary files a/plugins/openrouter/README.md and b/plugins/openrouter/README.md differ
EOF
cat > "$FIXTURE_ROOT/bad-count.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1,2 +1 @@
-old
+new
EOF
printf '%s\n' '+new without a diff header' > "$FIXTURE_ROOT/headerless.diff"

(
  cd "$FIXTURE_ROOT"
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" \
    --diff-file "$FIXTURE_ROOT/safe.diff" --output-paths "$FIXTURE_ROOT/safe.paths"
  "$BOUNDARY" --mode execution --policy "$POLICY" \
    --changed-files "$FIXTURE_ROOT/security-files" --diff-file "$FIXTURE_ROOT/security.diff" \
    --output-diff "$FIXTURE_ROOT/security.out.diff"
  "$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
    --changed-files "$FIXTURE_ROOT/security-files" --diff-file "$FIXTURE_ROOT/security.diff"
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/quoted-files" \
    --diff-file "$FIXTURE_ROOT/quoted.diff"
  "$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
    --changed-files "$FIXTURE_ROOT/credential-path-files" \
    --diff-file "$FIXTURE_ROOT/credential-path.diff"
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" \
    --diff-file "$FIXTURE_ROOT/placeholder.diff"
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" \
    --diff-file "$FIXTURE_ROOT/private-key-header.diff"
  "$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
    --changed-files "$FIXTURE_ROOT/mixed-files" \
    --diff-file "$FIXTURE_ROOT/mixed-secret.diff" \
    --output-paths "$FIXTURE_ROOT/mixed.paths" \
    --output-diff "$FIXTURE_ROOT/mixed.out.diff" \
    --output-declined-paths "$FIXTURE_ROOT/mixed.declined.paths"
)
cmp "$FIXTURE_ROOT/security.diff" "$FIXTURE_ROOT/security.out.diff"
python3 - "$FIXTURE_ROOT/safe.paths" <<'PY'
import sys
assert open(sys.argv[1], "rb").read() == b"plugins/openrouter/README.md\0"
PY
python3 - "$FIXTURE_ROOT/mixed.paths" "$FIXTURE_ROOT/mixed.declined.paths" "$FIXTURE_ROOT/mixed.out.diff" <<'PY'
import sys
from pathlib import Path

assert Path(sys.argv[1]).read_bytes() == b"plugins/openrouter/README.md\0"
assert Path(sys.argv[2]).read_bytes() == b".airlift/uncommitted.patch\0"
outbound = Path(sys.argv[3]).read_text(encoding="utf-8")
assert "safe documentation change" in outbound
assert ".airlift/uncommitted.patch" not in outbound
assert "sk-or-v1-" not in outbound
PY

expect_rc 3 'disclosure-declined:high-confidence-credential' 'removed secret' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/removed-secret.diff"
expect_rc 3 'disclosure-declined:no-safe-review-remainder' 'all-sensitive mechanical review' \
  "$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/removed-secret.diff"
expect_rc 3 'disclosure-declined:access-token' 'real bearer token' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/token.diff"
expect_rc 3 'disclosure-declined:access-token' 'raw JWT' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/raw-jwt.diff"
expect_rc 3 'disclosure-declined:high-confidence-credential' 'Slack service token' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/slack-token.diff"
expect_rc 3 'disclosure-declined:access-token' 'short alg-none JWT' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/short-jwt.diff"
expect_rc 3 'disclosure-declined:high-confidence-credential' 'GitHub service token' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/github-service-token.diff"
expect_rc 3 'disclosure-declined:high-confidence-credential' 'AWS secret access key diff' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/access-key.diff"
expect_rc 3 'disclosure-declined:private-key' 'private key' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/private-key.diff"
expect_rc 3 'disclosure-declined:authenticated-dsn' 'authenticated DSN' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/dsn.diff"
expect_rc 2 'input-invalid:headerless-diff' 'headerless diff' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/headerless.diff"
expect_rc 2 'input-invalid:diff-header-mismatch' 'mismatched headers' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/mismatch.diff"
expect_rc 2 'input-invalid:path-not-normalized' 'traversal path' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/traversal.diff"
expect_rc 2 'input-invalid:path-not-normalized' 'absolute path' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/absolute.diff"
expect_rc 2 'input-invalid:undeclared-output-path' 'undeclared output' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/outside.diff"
expect_rc 2 'input-invalid:binary-or-symlink-diff' 'binary diff' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/binary.diff"
expect_rc 2 'input-invalid:binary-or-symlink-diff' 'existing symlink retarget' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/symlink-retarget.diff"
expect_rc 2 'input-invalid:binary-or-symlink-diff' 'existing gitlink retarget' \
  "$BOUNDARY" --mode execution --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/gitlink-retarget.diff"
expect_rc 2 'input-invalid:hunk-count-mismatch' 'malformed hunk' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/bad-count.diff"
expect_rc 2 'input-invalid:missing-argument' 'missing option value' \
  "$BOUNDARY" --policy

printf 'escape/file.md\n' > "$FIXTURE_ROOT/symlink-files"
ln -s /tmp "$FIXTURE_ROOT/escape"
expect_rc 2 'input-invalid:symlink-escape' 'symlink escape' \
  bash -c 'cd "$1" && "$2" --policy "$3" --changed-files "$4"' _ \
  "$FIXTURE_ROOT" "$BOUNDARY" "$POLICY" "$FIXTURE_ROOT/symlink-files"
printf 'safe\0path\n' > "$FIXTURE_ROOT/nul-files"
expect_rc 2 'input-invalid:changed-files-unreadable-nul' 'NUL path' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/nul-files"

cat > "$FIXTURE_ROOT/artifact-a.md" <<'EOF'
Review auth/session.go, deploy/.env.example, and the Authorization header.
The variable name is OPENROUTER_API_KEY and the example is Bearer <redacted>.
EOF
cat > "$FIXTURE_ROOT/artifact-b.txt" <<'EOF'
Ordinary federation design notes with an empty postgres://user:@example/db DSN.
EOF
cat > "$FIXTURE_ROOT/artifact-token.txt" <<'EOF'
session_secret=r4nd0m-session-secret-value-123456789
EOF
cat > "$FIXTURE_ROOT/artifact-access-key.txt" <<'EOF'
AWS_SECRET_ACCESS_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/==
EOF
cat > "$FIXTURE_ROOT/artifact-classified.txt" <<'EOF'
data_classification=regulated
customer_record=real private content
EOF

"$BOUNDARY" --mode artifact-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" --content-file "$FIXTURE_ROOT/artifact-a.md"
"$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" --content-file "$FIXTURE_ROOT/artifact-b.txt"
expect_rc 3 'disclosure-declined:high-confidence-credential' 'artifact token' \
  "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" --content-file "$FIXTURE_ROOT/artifact-token.txt"
expect_rc 3 'disclosure-declined:high-confidence-credential' 'artifact AWS secret access key' \
  "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
  --content-file "$FIXTURE_ROOT/artifact-access-key.txt"
expect_rc 3 'disclosure-declined:classified-private-data' 'classified artifact' \
  "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
  --content-file "$FIXTURE_ROOT/artifact-classified.txt"
expect_rc 2 'input-invalid:artifact-delegation-authority' 'artifact execution authority' \
  "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" --content-file "$FIXTURE_ROOT/artifact-a.md"

artifact_delegate() {
  local sentinel="$1"
  shift
  "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" "$@" || return $?
  touch "$sentinel"
}
artifact_delegate "$FIXTURE_ROOT/artifact-network-safe" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" --content-file "$FIXTURE_ROOT/artifact-b.txt"
[ -e "$FIXTURE_ROOT/artifact-network-safe" ]
expect_rc 3 'disclosure-declined:high-confidence-credential' 'artifact sentinel decline' \
  artifact_delegate "$FIXTURE_ROOT/artifact-network-secret" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" --content-file "$FIXTURE_ROOT/artifact-token.txt"
[ ! -e "$FIXTURE_ROOT/artifact-network-secret" ]

authorization_manifest="$FIXTURE_ROOT/authorization.json"
authorization_sha="$("$AUTHORIZATION" snapshot --output "$authorization_manifest" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" \
  --content-file "$FIXTURE_ROOT/artifact-b.txt")"
"$AUTHORIZATION" verify --manifest "$authorization_manifest" \
  --approved-sha256 "$authorization_sha" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" \
  --content-file "$FIXTURE_ROOT/artifact-b.txt"
cp "$FIXTURE_ROOT/artifact-b.txt" "$FIXTURE_ROOT/artifact-b-original.txt"
printf '%s\n' mutation >> "$FIXTURE_ROOT/artifact-b.txt"
expect_rc 2 'payload changed after authorization snapshot' 'payload mutation' \
  "$AUTHORIZATION" verify --manifest "$authorization_manifest" \
  --approved-sha256 "$authorization_sha" \
  --content-file "$FIXTURE_ROOT/artifact-a.md" \
  --content-file "$FIXTURE_ROOT/artifact-b.txt"
mv "$FIXTURE_ROOT/artifact-b-original.txt" "$FIXTURE_ROOT/artifact-b.txt"
expect_rc 2 'payload changed after authorization snapshot' 'payload membership change' \
  "$AUTHORIZATION" verify --manifest "$authorization_manifest" \
  --approved-sha256 "$authorization_sha" \
  --content-file "$FIXTURE_ROOT/artifact-b.txt" \
  --content-file "$FIXTURE_ROOT/artifact-a.md"

AUTH_ROOT="$FIXTURE_ROOT/workflow-authority-fixture"
mkdir -p "$AUTH_ROOT" "$FIXTURE_ROOT/exec-repo/auth"
cp "$REPO_ROOT/tools/fixtures/fake-workflow-authority-client.py" "$AUTH_ROOT/workflow-authority"
chmod +x "$AUTH_ROOT/workflow-authority"
printf '%s\n' workflow-authority-fixture-v1 > "$AUTH_ROOT/.workflow-authority-fixture"
printf '%s\n' old > "$FIXTURE_ROOT/exec-repo/auth/session.go"
git -C "$FIXTURE_ROOT/exec-repo" init -q
git -C "$FIXTURE_ROOT/exec-repo" config user.email test@example.invalid
git -C "$FIXTURE_ROOT/exec-repo" config user.name 'Boundary Test'
git -C "$FIXTURE_ROOT/exec-repo" add auth/session.go
git -C "$FIXTURE_ROOT/exec-repo" commit -qm initial
cat > "$AUTH_ROOT/response" <<'DIFF'
diff --git a/auth/session.go b/auth/session.go
--- a/auth/session.go
+++ b/auth/session.go
@@ -1 +1 @@
-old
+new middleware checks the Authorization header
DIFF
printf '%s' 'Implement safe auth middleware; docs mention deploy/.env.example.' > "$FIXTURE_ROOT/expected.prompt"
printf '%s' 'You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences.' > "$FIXTURE_ROOT/expected.system"

(
  cd "$FIXTURE_ROOT/exec-repo"
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-01 \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    OPENROUTER_API_KEY=caller-secret OPENROUTER_BASE=https://evil.invalid \
    OPENROUTER_PAYLOAD_AUTHORIZATION=trusted-boundary \
    OPENROUTER_PAYLOAD_APPROVAL_SHA256=sha256:caller \
    OPENROUTER_EXEC_VERIFY_CMD="touch $FIXTURE_ROOT/untrusted-verifier-ran" \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt" > "$FIXTURE_ROOT/exec-receipt.json"
)
[ ! -e "$FIXTURE_ROOT/untrusted-verifier-ran" ]
cmp "$FIXTURE_ROOT/expected.prompt" "$AUTH_ROOT/observed-user"
cmp "$FIXTURE_ROOT/expected.system" "$AUTH_ROOT/observed-system"
jq -e '.implementedBy == "openrouter" and .status == "committed"
  and .requestedModel == "moonshotai/kimi-k3"
  and .actualModel == "moonshotai/kimi-k3"
  and .servingProviderProvenance == "broker-verified"
  and .fallback == false' "$FIXTURE_ROOT/exec-receipt.json" >/dev/null
git -C "$FIXTURE_ROOT/exec-repo" diff --quiet

expect_rc 70 'host_authority_unavailable' 'production broker unavailable' \
  env OPENROUTER_API_KEY=caller-secret OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-02 \
  "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"

for bad_case in forged-signature malformed-frame missing-result; do
  expect_rc 2 'broker result verification failed' "$bad_case rejected" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_WORKFLOW_AUTHORITY_FIXTURE_CASE="$bad_case" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-$bad_case" \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
done
for bad_case in wrong-scope wrong-response-length unknown-outcome; do
  expect_rc 2 'broker result scope mismatch' "$bad_case rejected" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_WORKFLOW_AUTHORITY_FIXTURE_CASE="$bad_case" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-$bad_case" \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
done
expect_rc 77 'host_disclosure_declined' 'disclosure decline class' \
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
  DM_WORKFLOW_AUTHORITY_FIXTURE_CASE=disclosure-declined \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-decline \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
expect_rc 1 'provider failure' 'provider failure class' \
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
  DM_WORKFLOW_AUTHORITY_FIXTURE_CASE=provider-failure \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-provider \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"

CASCADE="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
rm -f "$AUTH_ROOT/observed-user"
mkdir -p "$FIXTURE_ROOT/cascade-repo/docs"
printf '%s\n' old > "$FIXTURE_ROOT/cascade-repo/docs/assessment.md"
git -C "$FIXTURE_ROOT/cascade-repo" init -q
git -C "$FIXTURE_ROOT/cascade-repo" config user.email test@example.invalid
git -C "$FIXTURE_ROOT/cascade-repo" config user.name 'Boundary Test'
git -C "$FIXTURE_ROOT/cascade-repo" add docs/assessment.md
git -C "$FIXTURE_ROOT/cascade-repo" commit -qm initial
cat > "$AUTH_ROOT/response" <<'DIFF'
diff --git a/docs/assessment.md b/docs/assessment.md
--- a/docs/assessment.md
+++ b/docs/assessment.md
@@ -1 +1 @@
-old
+broker-mediated assessment
DIFF
(
  cd "$FIXTURE_ROOT/cascade-repo"
  printf '%s' 'Implement safe documentation wording.' | env \
    DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-cascade \
    OPENROUTER_API_KEY=caller-secret OPENROUTER_BASE=https://evil.invalid \
    OPENROUTER_EXEC_ALLOWED_PATHS=docs/assessment.md \
    "$CASCADE" --class openrouter --prompt - --host codex > "$FIXTURE_ROOT/cascade-receipt.json"
)
jq -e '.implementedBy == "openrouter" and .status == "committed"
  and .servingProviderProvenance == "broker-verified"' "$FIXTURE_ROOT/cascade-receipt.json" >/dev/null
[ -e "$AUTH_ROOT/observed-user" ]

rm -f "$AUTH_ROOT/observed-user"
for lane in research adversarial-review execution dm-review airlift unknown ''; do
  CASCADE_OUT="$(printf '%s' 'safe input' | env \
    DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE="$lane" DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-lane \
    "$CASCADE" --class openrouter --prompt - --host codex 2>/dev/null || true)"
  printf '%s' "$CASCADE_OUT" | jq -e '.dispatch == "native" and .role == "premium_sub"' >/dev/null
  [ ! -e "$AUTH_ROOT/observed-user" ]
done

DRY_OUT="$(env DM_PROVIDER_LANE=research "$CASCADE" --class openrouter \
  --prompt 'dry run' --host codex --dry-run)"
printf '%s' "$DRY_OUT" | jq -e '.requestedProvider == "openrouter" and .fallback == false' >/dev/null
[ ! -e "$AUTH_ROOT/observed-user" ]

grep -Fq 'os.path.realpath(sys.argv[1])' "$RUNNER"
grep -Fq 'delegation-boundary.sh' "$RUNNER"
grep -Fq 'RUNNER DECLINED -- SENSITIVE CONTENT' "$RUNNER"
grep -Fq '### CODEX PARTIAL COVERAGE REQUIRED' "$RUNNER"
grep -Fq 'OpenRouter full disclosure decline' "$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
grep -Fq 'fallbackReason: host-disclosure-declined' "$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
grep -Fq 'independent Codex security' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
grep -Fq 'mcp-control-plane.md' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
grep -Fq 'OPENROUTER_RECEIPT_FILE' "$WRAPPER"
grep -Fq 'payload-authorization.sh' "$RUNNER"
grep -Fq 'export PATH=' "$BOUNDARY"
grep -Fq 'artifact-delegation' "$BOUNDARY"
grep -Fq 'git apply --check' "$EXEC_RUNNER"
grep -Fq -- '--pathspec-file-nul' "$EXEC_RUNNER"
grep -Fq '/usr/local/bin/workflow-authority' "$EXEC_RUNNER"
grep -Fq 'pipeline-assessment-artifact-delegation-v1' "$EXEC_RUNNER"
if grep -Eq 'openrouter-wrapper\.sh|curl[[:space:]]' "$EXEC_RUNNER"; then
  echo 'automated exec regained direct provider transport' >&2
  exit 1
fi
if grep -Eq 'OPENROUTER_PAYLOAD_AUTHORIZATION|OPENROUTER_PAYLOAD_APPROVAL_SHA256|OPENROUTER_BASE' "$EXEC_RUNNER"; then
  echo 'automated exec regained caller authority or transport selection' >&2
  exit 1
fi
if grep -Eq 'eval.*RAW_OUT|bash.*RAW_OUT' "$EXEC_RUNNER"; then
  echo 'model output gained command authority' >&2
  exit 1
fi

printf '  OK    OpenRouter threat/content and output-boundary fixtures pass\n'
