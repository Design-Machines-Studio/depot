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
  env OPENROUTER_API_KEY=fixture "$WRAPPER" Anthropic/claude-test prompt
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

mkdir -p "$FIXTURE_ROOT/exec-repo/auth"
printf '%s\n' old > "$FIXTURE_ROOT/exec-repo/auth/session.go"
git -C "$FIXTURE_ROOT/exec-repo" init -q
git -C "$FIXTURE_ROOT/exec-repo" config user.email test@example.invalid
git -C "$FIXTURE_ROOT/exec-repo" config user.name 'Boundary Test'
git -C "$FIXTURE_ROOT/exec-repo" add auth/session.go
git -C "$FIXTURE_ROOT/exec-repo" commit -qm initial
cat > "$FIXTURE_ROOT/wrapper-safe.sh" <<'EOF'
#!/usr/bin/env bash
cat > "$WRAPPER_PROMPT"
touch "$WRAPPER_SENTINEL"
cat > "$OPENROUTER_RECEIPT_FILE" <<JSON
{"schemaVersion":1,"generationId":"fixture","requestedModel":"$1","attemptedModel":"$1","attemptedModels":["$1"],"fallbackUsed":false,"responseModel":"$1","responseModelProvenance":"response","servingProvider":null,"servingProviderProvenance":"not_reported_by_completion"}
JSON
cat <<'DIFF'
diff --git a/auth/session.go b/auth/session.go
--- a/auth/session.go
+++ b/auth/session.go
@@ -1 +1 @@
-old
+new middleware checks the Authorization header
DIFF
EOF
cat > "$FIXTURE_ROOT/wrapper-provider-fail.sh" <<'EOF'
#!/usr/bin/env bash
touch "$WRAPPER_SENTINEL"
exit 42
EOF
cat > "$FIXTURE_ROOT/wrapper-mismatch.sh" <<'EOF'
#!/usr/bin/env bash
touch "$WRAPPER_SENTINEL"
cat > "$OPENROUTER_RECEIPT_FILE" <<JSON
{"schemaVersion":1,"generationId":"fixture","requestedModel":"$1","attemptedModel":"$1","attemptedModels":["$1"],"fallbackUsed":false,"responseModel":"$1","responseModelProvenance":"response","servingProvider":null,"servingProviderProvenance":"not_reported_by_completion"}
JSON
cat <<'DIFF'
diff --git a/auth/session.go b/auth/session.go
--- a/auth/other.go
+++ b/auth/session.go
@@ -1 +1 @@
-old
+new
DIFF
EOF
chmod +x "$FIXTURE_ROOT"/wrapper-*.sh

# Build one coherent fake installed OpenRouter bundle. Production consumers must
# resolve the bundle as a unit, so fixtures replace only the wrapper inside that
# unit instead of injecting caller-selected production asset paths.
FAKE_HOME="$FIXTURE_ROOT/home"
BUNDLE_ROOT="$FAKE_HOME/openrouter-bundle"
BUNDLE_REFS="$BUNDLE_ROOT/skills/openrouter-delegate/references"
mkdir -p "$BUNDLE_REFS"
cp "$POLICY" "$BUNDLE_REFS/delegation-security-policy.json"
cp "$BOUNDARY" "$BUNDLE_REFS/delegation-boundary.sh"
cp "$AUTHORIZATION" "$BUNDLE_REFS/payload-authorization.sh"
chmod +x "$BUNDLE_REFS/delegation-boundary.sh" "$BUNDLE_REFS/payload-authorization.sh"
cat > "$FIXTURE_ROOT/fake-workflow-kernel.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[ "${1:-}" = "resolve-plugin-bundle" ] || exit 2
cat <<'JSON'
{"selected_root":"~/openrouter-bundle","version":"1.8.0","cache_class":"fixture","reason":"offline-test"}
JSON
EOF
chmod +x "$FIXTURE_ROOT/fake-workflow-kernel.sh"

printf '%s' 'Implement safe auth middleware; docs mention deploy/.env.example.' > "$FIXTURE_ROOT/expected.prompt"
printf '%s' 'You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences.' > "$FIXTURE_ROOT/expected.system"
expected_payload_sha="$("$AUTHORIZATION" snapshot \
  --output "$FIXTURE_ROOT/expected-authorization.json" \
  --content-file "$FIXTURE_ROOT/expected.system" \
  --content-file "$FIXTURE_ROOT/expected.prompt")"
cp "$FIXTURE_ROOT/wrapper-safe.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
(
  cd "$FIXTURE_ROOT/exec-repo"
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    OPENROUTER_PAYLOAD_APPROVAL_SHA256="$expected_payload_sha" \
    OPENROUTER_EXEC_VERIFY_CMD="touch $FIXTURE_ROOT/untrusted-verifier-ran" \
    OPENROUTER_EXEC_COMMIT_MSG='test: bounded auth diff' \
    WRAPPER_PROMPT="$FIXTURE_ROOT/actual.prompt" \
    WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-safe" \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt" > "$FIXTURE_ROOT/exec-receipt.json"
)
[ -e "$FIXTURE_ROOT/exec-network-safe" ]
[ ! -e "$FIXTURE_ROOT/untrusted-verifier-ran" ]
cmp "$FIXTURE_ROOT/expected.prompt" "$FIXTURE_ROOT/actual.prompt"
jq -e '.implementedBy == "openrouter" and .status == "committed"
  and (.verification | startswith("deferred_to_native_reviewer:"))' \
  "$FIXTURE_ROOT/exec-receipt.json" >/dev/null
jq -e '.requestedModel == "z-ai/glm-5.2"
  and .attemptedModels == ["z-ai/glm-5.2"]
  and .actualModel == "z-ai/glm-5.2"
  and .servingProviderProvenance == "not_reported_by_completion"
  and .fallback == false' \
  "$FIXTURE_ROOT/exec-receipt.json" >/dev/null
git -C "$FIXTURE_ROOT/exec-repo" diff --quiet

mkdir -p "$FIXTURE_ROOT/magic-repo"
printf '%s\n' old > "$FIXTURE_ROOT/magic-repo/:(glob)*"
printf '%s\n' original > "$FIXTURE_ROOT/magic-repo/unrelated.md"
git -C "$FIXTURE_ROOT/magic-repo" init -q
git -C "$FIXTURE_ROOT/magic-repo" config user.email test@example.invalid
git -C "$FIXTURE_ROOT/magic-repo" config user.name 'Boundary Test'
git -C "$FIXTURE_ROOT/magic-repo" add --all
git -C "$FIXTURE_ROOT/magic-repo" commit -qm initial
printf '%s\n' 'unrelated user edit' > "$FIXTURE_ROOT/magic-repo/unrelated.md"
cat > "$FIXTURE_ROOT/wrapper-magic-path.sh" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
cat > "$OPENROUTER_RECEIPT_FILE" <<JSON
{"schemaVersion":1,"generationId":"fixture-magic","requestedModel":"$1","attemptedModel":"$1","attemptedModels":["$1"],"fallbackUsed":false,"responseModel":"$1","responseModelProvenance":"response","servingProvider":null,"servingProviderProvenance":"not_reported_by_completion"}
JSON
cat <<'DIFF'
diff --git a/:(glob)* b/:(glob)*
--- a/:(glob)*
+++ b/:(glob)*
@@ -1 +1 @@
-old
+new
DIFF
EOF
chmod +x "$FIXTURE_ROOT/wrapper-magic-path.sh"
cp "$FIXTURE_ROOT/wrapper-magic-path.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
(
  cd "$FIXTURE_ROOT/magic-repo"
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
    'OPENROUTER_EXEC_ALLOWED_PATHS=:(glob)*' \
    OPENROUTER_PAYLOAD_APPROVAL_SHA256="$expected_payload_sha" \
    OPENROUTER_EXEC_COMMIT_MSG='test: literal pathspec staging' \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt" > "$FIXTURE_ROOT/magic-receipt.json"
)
[ "$(git -C "$FIXTURE_ROOT/magic-repo" show --pretty=format: --name-only HEAD)" = ':(glob)*' ]
[ "$(git -C "$FIXTURE_ROOT/magic-repo" diff --name-only)" = 'unrelated.md' ]
git -C "$FIXTURE_ROOT/magic-repo" diff --cached --quiet

cat > "$FIXTURE_ROOT/wrapper-fallback.sh" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
printf '%s\n' 'provider capacity; falling back to z-ai/glm-5.2' >&2
cat > "$OPENROUTER_RECEIPT_FILE" <<JSON
{"schemaVersion":1,"generationId":"fixture-fallback","requestedModel":"$1","attemptedModel":"$4","attemptedModels":["$1","$4"],"fallbackUsed":true,"responseModel":"$4","responseModelProvenance":"response","servingProvider":"Fixture","servingProviderProvenance":"response"}
JSON
cat <<'DIFF'
diff --git a/auth/session.go b/auth/session.go
--- a/auth/session.go
+++ b/auth/session.go
@@ -1 +1 @@
-new middleware checks the Authorization header
+fallback middleware checks the Authorization header
DIFF
EOF
chmod +x "$FIXTURE_ROOT/wrapper-fallback.sh"
cp "$FIXTURE_ROOT/wrapper-fallback.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
(
  cd "$FIXTURE_ROOT/exec-repo"
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    OPENROUTER_PAYLOAD_APPROVAL_SHA256="$expected_payload_sha" \
    OPENROUTER_EXEC_MODEL=moonshotai/kimi-k3 \
    OPENROUTER_EXEC_FALLBACK_MODEL=z-ai/glm-5.2 \
    OPENROUTER_EXEC_VERIFY_CMD='grep -Fq "fallback middleware" auth/session.go' \
    OPENROUTER_EXEC_COMMIT_MSG='test: fallback receipt' \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt" > "$FIXTURE_ROOT/fallback-receipt.json"
)
jq -e '.requestedModel == "moonshotai/kimi-k3"
  and .attemptedModels == ["moonshotai/kimi-k3", "z-ai/glm-5.2"]
  and .actualModel == "z-ai/glm-5.2"
  and .fallback == true' \
  "$FIXTURE_ROOT/fallback-receipt.json" >/dev/null

printf '%s' 'OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890' > "$FIXTURE_ROOT/secret.prompt"
cp "$FIXTURE_ROOT/wrapper-safe.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
expect_rc 77 'delegation declined' 'exec prompt disclosure' \
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  OPENROUTER_PAYLOAD_APPROVAL_SHA256="$expected_payload_sha" \
  WRAPPER_PROMPT="$FIXTURE_ROOT/secret-actual.prompt" \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-secret" \
  "$EXEC_RUNNER" < "$FIXTURE_ROOT/secret.prompt"
[ ! -e "$FIXTURE_ROOT/exec-network-secret" ]

cp "$FIXTURE_ROOT/wrapper-provider-fail.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
expect_rc 1 'provider failure' 'provider receipt class' \
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  OPENROUTER_PAYLOAD_APPROVAL_SHA256="$expected_payload_sha" \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-provider-fail" \
  "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
[ -e "$FIXTURE_ROOT/exec-network-provider-fail" ]

cp "$FIXTURE_ROOT/wrapper-mismatch.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
expect_rc 2 'model patch could not be validated' 'malformed model output' \
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  OPENROUTER_PAYLOAD_APPROVAL_SHA256="$expected_payload_sha" \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-mismatch" \
  "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
[ -e "$FIXTURE_ROOT/exec-network-mismatch" ]

cat > "$FIXTURE_ROOT/cascade-sentinel.sh" <<'EOF'
#!/usr/bin/env bash
touch "$WRAPPER_SENTINEL"
exit 99
EOF
chmod +x "$FIXTURE_ROOT/cascade-sentinel.sh"
cp "$FIXTURE_ROOT/cascade-sentinel.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
CASCADE="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
set +e
CASCADE_APPROVAL_OUT="$(printf '%s' 'Implement safe documentation wording.' | env \
  HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_API_KEY=fixture \
  OPENROUTER_EXEC_ALLOWED_PATHS=plugins/openrouter/README.md \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/cascade-approval-wrapper-called" \
  "$CASCADE" --class openrouter --prompt - --host codex 2>/dev/null)"
CASCADE_APPROVAL_RC=$?
set -e
[ "$CASCADE_APPROVAL_RC" -eq 78 ]
printf '%s' "$CASCADE_APPROVAL_OUT" | jq -e '
  .status == "approval_required"
  and .authority == "user"
  and (.payloadSha256 | test("^[0-9a-f]{64}$"))
' >/dev/null
[ ! -e "$FIXTURE_ROOT/cascade-approval-wrapper-called" ]

CASCADE_OUT="$(printf '%s' 'OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890' | env \
  HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=plugins/openrouter/README.md \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/cascade-wrapper-called" \
  "$CASCADE" --class openrouter --prompt - --host codex 2>/dev/null || true)"
printf '%s' "$CASCADE_OUT" | jq -e '.dispatch == "native" and .role == "premium_sub"' >/dev/null
[ ! -e "$FIXTURE_ROOT/cascade-wrapper-called" ]

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
if grep -Eq 'eval.*RAW_OUT|bash.*RAW_OUT' "$EXEC_RUNNER"; then
  echo 'model output gained command authority' >&2
  exit 1
fi

printf '  OK    OpenRouter threat/content and output-boundary fixtures pass\n'
