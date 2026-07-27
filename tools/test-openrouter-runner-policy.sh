#!/usr/bin/env bash
# Behavioral fixtures for the OpenRouter threat/content and output boundary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
POLICY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
RUNNER="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
EXEC_RUNNER="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
BOUNDARY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh"
WRAPPER="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"

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
printf '%s\n' 'auth/session.go' 'federation/trust.go' 'deploy/app.service' > "$FIXTURE_ROOT/security-files"
printf '%s\n' 'plugins/openrouter/file with spaces.md' > "$FIXTURE_ROOT/quoted-files"
printf '%s\n' 'docs/outside.md' > "$FIXTURE_ROOT/outside-files"

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
cat > "$FIXTURE_ROOT/token.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.real-session-token-1234567890
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
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" \
    --diff-file "$FIXTURE_ROOT/placeholder.diff"
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" \
    --diff-file "$FIXTURE_ROOT/private-key-header.diff"
)
cmp "$FIXTURE_ROOT/security.diff" "$FIXTURE_ROOT/security.out.diff"
python3 - "$FIXTURE_ROOT/safe.paths" <<'PY'
import sys
assert open(sys.argv[1], "rb").read() == b"plugins/openrouter/README.md\0"
PY

expect_rc 3 'disclosure-declined:high-confidence-credential' 'removed secret' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/removed-secret.diff"
expect_rc 3 'disclosure-declined:access-token' 'real bearer token' \
  "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/token.diff"
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
chmod +x "$BUNDLE_REFS/delegation-boundary.sh"
cat > "$FIXTURE_ROOT/fake-workflow-kernel.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[ "${1:-}" = "resolve-plugin-bundle" ] || exit 2
cat <<'JSON'
{"selected_root":"~/openrouter-bundle","version":"1.6.0","cache_class":"fixture","reason":"offline-test"}
JSON
EOF
chmod +x "$FIXTURE_ROOT/fake-workflow-kernel.sh"

printf '%s' 'Implement safe auth middleware; docs mention deploy/.env.example.' > "$FIXTURE_ROOT/expected.prompt"
cp "$FIXTURE_ROOT/wrapper-safe.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
(
  cd "$FIXTURE_ROOT/exec-repo"
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    OPENROUTER_EXEC_VERIFY_CMD='grep -Fq "new middleware" auth/session.go' \
    OPENROUTER_EXEC_COMMIT_MSG='test: bounded auth diff' \
    WRAPPER_PROMPT="$FIXTURE_ROOT/actual.prompt" \
    WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-safe" \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt" > "$FIXTURE_ROOT/exec-receipt.json"
)
[ -e "$FIXTURE_ROOT/exec-network-safe" ]
cmp "$FIXTURE_ROOT/expected.prompt" "$FIXTURE_ROOT/actual.prompt"
jq -e '.implementedBy == "openrouter" and .status == "committed"' "$FIXTURE_ROOT/exec-receipt.json" >/dev/null
jq -e '.requestedModel == "z-ai/glm-5.2" and .actualModel == "z-ai/glm-5.2" and .fallback == false' \
  "$FIXTURE_ROOT/exec-receipt.json" >/dev/null
git -C "$FIXTURE_ROOT/exec-repo" diff --quiet

cat > "$FIXTURE_ROOT/wrapper-fallback.sh" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
printf '%s\n' 'provider capacity; falling back to deepseek/deepseek-v4-pro' >&2
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
    OPENROUTER_EXEC_FALLBACK_MODEL=deepseek/deepseek-v4-pro \
    OPENROUTER_EXEC_VERIFY_CMD='grep -Fq "fallback middleware" auth/session.go' \
    OPENROUTER_EXEC_COMMIT_MSG='test: fallback receipt' \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt" > "$FIXTURE_ROOT/fallback-receipt.json"
)
jq -e '.requestedModel == "z-ai/glm-5.2" and .actualModel == "deepseek/deepseek-v4-pro" and .fallback == true' \
  "$FIXTURE_ROOT/fallback-receipt.json" >/dev/null

printf '%s' 'OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890' > "$FIXTURE_ROOT/secret.prompt"
cp "$FIXTURE_ROOT/wrapper-safe.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
expect_rc 77 'delegation declined' 'exec prompt disclosure' \
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  WRAPPER_PROMPT="$FIXTURE_ROOT/secret-actual.prompt" \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-secret" \
  "$EXEC_RUNNER" < "$FIXTURE_ROOT/secret.prompt"
[ ! -e "$FIXTURE_ROOT/exec-network-secret" ]

cp "$FIXTURE_ROOT/wrapper-provider-fail.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
expect_rc 1 'provider failure' 'provider receipt class' \
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/exec-network-provider-fail" \
  "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
[ -e "$FIXTURE_ROOT/exec-network-provider-fail" ]

cp "$FIXTURE_ROOT/wrapper-mismatch.sh" "$BUNDLE_REFS/openrouter-wrapper.sh"
expect_rc 2 'model patch could not be validated' 'malformed model output' \
  env HOME="$FAKE_HOME" WORKFLOW_KERNEL="$FIXTURE_ROOT/fake-workflow-kernel.sh" \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
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
grep -Fq 'independent Codex security' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
grep -Fq 'export PATH=' "$BOUNDARY"
grep -Fq 'artifact-delegation' "$BOUNDARY"
grep -Fq 'git apply --check' "$EXEC_RUNNER"
grep -Fq -- '--pathspec-file-nul' "$EXEC_RUNNER"
if grep -Eq 'eval.*RAW_OUT|bash.*RAW_OUT' "$EXEC_RUNNER"; then
  echo 'model output gained command authority' >&2
  exit 1
fi

printf '  OK    OpenRouter threat/content and output-boundary fixtures pass\n'
