#!/usr/bin/env bash
# Behavioral fixtures for the OpenRouter threat/content and output boundary.

set -euo pipefail

# Authorization mode is selected explicitly per fixture below. In particular,
# default-mode fixtures remove the variable from the environment so a caller's
# shell cannot mask a regression in the production default.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
POLICY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
RUNNER="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
EXEC_RUNNER="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
BOUNDARY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh"
WRAPPER="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
AUTHORIZATION="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/payload-authorization.sh"
RUNNER_BATCH_AUTHORIZATION="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/runner-batch-authorization.sh"

FIXTURE_ROOT="$(mktemp -d)"
FIXTURE_ROOT="$(cd "$FIXTURE_ROOT" && pwd -P)"
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

run_pty_with_reply() {
  local reply="$1"
  local command_text=""
  shift
  command -v expect >/dev/null 2>&1 || {
    echo 'PTY approval fixture requires expect' >&2
    return 125
  }
  printf -v command_text '%s\034' "$@"
  PTY_REPLY="$reply" PTY_COMMAND="$command_text" expect -c '
    set timeout 15
    set command [lrange [split $env(PTY_COMMAND) "\034"] 0 end-1]
    spawn -noecho {*}$command
    expect {
      "Type exactly" {
        send -- "$env(PTY_REPLY)\r"
        exp_continue
      }
      eof {}
      timeout { exit 124 }
    }
    set result [wait]
    exit [lindex $result 3]
  '
}

run_pty_and_interrupt() {
  local command_text=""
  command -v expect >/dev/null 2>&1 || return 125
  printf -v command_text '%s\034' "$@"
  PTY_COMMAND="$command_text" expect -c '
    set timeout 15
    set command [lrange [split $env(PTY_COMMAND) "\034"] 0 end-1]
    spawn -noecho {*}$command
    expect {
      "Type exactly" {
        set children [exec /usr/bin/pgrep -P [exp_pid]]
        set child [lindex $children end]
        exec /bin/kill -HUP $child
        catch {exec /bin/kill -TERM $child}
      }
      timeout { exit 124 }
    }
    expect {
      eof {}
      timeout { exit 124 }
    }
    wait
    exit 130
  '
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

AUTH_ROOT="$FIXTURE_ROOT/workflow-authority-fixture"
mkdir -p "$AUTH_ROOT" "$FIXTURE_ROOT/exec-repo/auth"
cp "$REPO_ROOT/tools/fixtures/fake-workflow-authority-client.py" "$AUTH_ROOT/fake-client.py"
/usr/bin/python3 - "$AUTH_ROOT/fake-client.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    '    case = os.environ.get("DM_WORKFLOW_AUTHORITY_FIXTURE_CASE", "signed-success")\n',
    '''    case = os.environ.get("DM_WORKFLOW_AUTHORITY_FIXTURE_CASE", "signed-success")
    counter = root / "request-count"
    try:
        count = int(counter.read_text())
    except (OSError, ValueError):
        count = 0
    counter.write_text(str(count + 1))
    terminal_case = case.startswith("terminal-")
    if case == "terminal-unsigned-ambiguity":
        fail(75, "post-dial result unverifiable")
''',
)
text = text.replace(
    '    models = [str(args["--model"])]\n',
    '''    if terminal_case:
        response = b""
    models = [str(args["--model"])]
''',
)
text = text.replace(
    '    if case == "wrong-scope":\n',
    '''    if terminal_case:
        terminal["outcome"] = "unknown" if case == "terminal-unknown" else "provider_failure"
        terminal["exit_code"] = 74 if case == "terminal-unknown" else 73
        terminal["selected_model"] = None
        terminal["generation_id"] = None
        terminal["serving_provider"] = None
        terminal["usage_sha256"] = None
        terminal["fallback"] = None
    if case == "terminal-wrong-scope":
        terminal["scope"]["candidate"] = "wrong-candidate"
    elif case == "terminal-wrong-workload":
        terminal["scope"]["workload"] = "wrong-workload"
    elif case == "terminal-wrong-body":
        terminal["request_body_sha256"] = digest(b"wrong-body")
    elif case == "terminal-wrong-model":
        terminal["models"] = ["fixture/wrong-model"]
    elif case == "terminal-wrong-exit":
        terminal["exit_code"] = 74
    elif case == "terminal-wrong-cleanup":
        terminal["cleanup"]["reservation"] = "released"
    elif case == "terminal-wrong-chain":
        terminal["prior_chain_digest"] = "invalid"
    elif case == "terminal-forged-signature":
        terminal["signature"]["value"] = "fixture-rsa-sha256-v1:" + "0" * 256
    if case == "wrong-scope":
''',
)
text = text.replace(
    '    os.write(3, response)\n',
    '''    os.write(3, b"unexpected-response" if case == "terminal-response-bytes" else response)
''',
)
text = text.replace(
    '    sys.stdout.buffer.write(canonical(terminal) + b"\\n")\n',
    '''    sys.stdout.buffer.write(canonical(terminal) + b"\\n")
    if terminal_case:
        sys.stdout.buffer.flush()
        raise SystemExit(74 if case == "terminal-unknown" else 73)
''',
)
path.write_text(text)
PY
cat > "$AUTH_ROOT/workflow-authority" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CASE="$(cat "$ROOT/case")"
exec env -i PATH=/usr/bin:/bin HOME="$ROOT" DM_AUTOMATION_TEST=1 \
  DM_AUTOMATION_TEST_ROOT="$ROOT" DM_WORKFLOW_AUTHORITY_FIXTURE_CASE="$CASE" \
  "$ROOT/fake-client.py" "$@"
EOF
chmod +x "$AUTH_ROOT/workflow-authority"
printf '%s\n' workflow-authority-fixture-v1 > "$AUTH_ROOT/.workflow-authority-fixture"
printf '%s\n' signed-success > "$AUTH_ROOT/case"

# Pin the usage probe so this offline policy gate does not depend on live
# account state. Use the production OpenRouter API-balance shape; this account
# auto-reloads, so a valid non-negative balance has no legacy $5 cutoff.
cat > "$AUTH_ROOT/usage-probe.sh" <<'PROBE_EOF'
#!/bin/sh
printf '%s\n' '{"codex":{"state":"ok","remaining_pct":100},"claude":{"state":"ok","remaining_pct":100},"openrouter":{"state":"ok","balance_usd":0.01}}'
PROBE_EOF
chmod +x "$AUTH_ROOT/usage-probe.sh"
export PROBE_CMD="$AUTH_ROOT/usage-probe.sh"
PRODUCTION_EXEC_RUNNER="$EXEC_RUNNER"
PRODUCTION_CASCADE="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
EXEC_RUNNER="$AUTH_ROOT/openrouter-exec.sh"
CASCADE="$AUTH_ROOT/cascade-dispatch.sh"
/usr/bin/python3 - "$PRODUCTION_EXEC_RUNNER" "$PRODUCTION_CASCADE" "$EXEC_RUNNER" "$CASCADE" \
  "$AUTH_ROOT/workflow-authority" "$REPO_ROOT/plugins/pipeline/references" <<'PY'
from pathlib import Path
import sys
source_exec, source_cascade, out_exec, out_cascade, client, refs = sys.argv[1:]
signature = '.signature.kind == "es256" and\n    (.signature.signature_der | test("^[A-Za-z0-9_-]{1,4096}$"))'
fixture_signature = '.signature.kind == "fixture-rsa-sha256-v1" and\n    .signature.domain == "fixture.workflow-authority.invalid" and\n    (.signature.value | test("^fixture-rsa-sha256-v1:a{256}$"))'
for source, output in ((source_exec, out_exec), (source_cascade, out_cascade)):
    text = Path(source).read_text()
    text = text.replace('WORKFLOW_AUTHORITY_CLIENT="/usr/local/bin/workflow-authority"', f'WORKFLOW_AUTHORITY_CLIENT="{client}"')
    text = text.replace('.production_ready == true and .m1_acceptance == true', '.production_ready == false and .fixture_ready == true')
    text = text.replace(signature, fixture_signature)
    text = text.replace(signature.replace('\n    ', '\n      '), fixture_signature.replace('\n    ', '\n      '))
    text = text.replace('DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"', f'DIR="{refs}"')
    if source == source_cascade:
        text = text.replace('[ -x "$DIR/openrouter-exec.sh" ] && printf \'%s\' "$DIR/openrouter-exec.sh"', f'[ -x "{out_exec}" ] && printf \'%s\' "{out_exec}"')
    Path(output).write_text(text)
PY
chmod +x "$EXEC_RUNNER" "$CASCADE"
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
  and .requestedModel == "z-ai/glm-5.2"
  and .actualModel == "z-ai/glm-5.2"
  and .servingProviderProvenance == "broker-verified"
  and .fallback == false' "$FIXTURE_ROOT/exec-receipt.json" >/dev/null
git -C "$FIXTURE_ROOT/exec-repo" diff --quiet

expect_rc 70 'host_authority_unavailable' 'production broker unavailable' \
  env OPENROUTER_API_KEY=caller-secret OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-02 \
  "$PRODUCTION_EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"

for bad_case in forged-signature malformed-frame missing-result; do
  printf '%s\n' "$bad_case" > "$AUTH_ROOT/case"
  expect_rc 2 'broker result scope mismatch' "$bad_case rejected" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_WORKFLOW_AUTHORITY_FIXTURE_CASE="$bad_case" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-$bad_case" \
    OPENROUTER_EXEC_FALLBACK_MODEL=moonshotai/kimi-k3 \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
done
grep -Fq 'security-auditor-codex-signoff` retries only on a non-implementing family' "$RUNNER"
grep -Fq 'continues only to a non-implementing family or `REVIEW INCOMPLETE`' "$RUNNER"
grep -Fq 'must use a non-implementing family for every held path' "$RUNNER"
grep -Fq 'Resolve the lane before its provider.' "$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
grep -Fq '[independent-family-fallback/{reviewer-family}/{agent-name}]' \
  "$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
grep -Fq 'Never same-family fallback completion' \
  "$REPO_ROOT/plugins/dm-review/skills/review/references/graceful-degradation.md"
jq -e '
  .agentType["security-auditor-codex-signoff"].failureResolution
  | [.runner_failure, .full_disclosure_decline, .partial_coverage]
  | all(. == "remaining-non-implementing-family-or-review-incomplete")
' "$REPO_ROOT/plugins/pipeline/references/routing-policy.json" >/dev/null
for bad_case in wrong-scope wrong-response-length wrong-response-digest unknown-outcome wrong-body wrong-model-order wrong-selected-model; do
  printf '%s\n' "$bad_case" > "$AUTH_ROOT/case"
  expect_rc 2 'broker result scope mismatch' "$bad_case rejected" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_WORKFLOW_AUTHORITY_FIXTURE_CASE="$bad_case" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-$bad_case" \
    OPENROUTER_EXEC_FALLBACK_MODEL=moonshotai/kimi-k3 \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
done
printf '%s\n' disclosure-declined > "$AUTH_ROOT/case"
expect_rc 77 'host_disclosure_declined' 'disclosure decline class' \
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
  DM_WORKFLOW_AUTHORITY_FIXTURE_CASE=disclosure-declined \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-decline \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
printf '%s\n' provider-failure > "$AUTH_ROOT/case"
expect_rc 75 'terminal provider result verification failed' 'unsigned provider failure is terminal' \
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
  DM_WORKFLOW_AUTHORITY_FIXTURE_CASE=provider-failure \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-provider \
  OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
[ ! -s "$FIXTURE_ROOT/cmd.out" ]

for terminal_case in terminal-provider-failure terminal-unknown; do
  printf '%s\n' 0 > "$AUTH_ROOT/request-count"
  printf '%s\n' "$terminal_case" > "$AUTH_ROOT/case"
  expect_rc 75 'external dispatch rail stopped' "$terminal_case is preserved and terminal" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-$terminal_case" \
    OPENROUTER_EXEC_FALLBACK_MODEL=moonshotai/kimi-k3 \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
  [ "$(cat "$AUTH_ROOT/request-count")" -eq 1 ]
  expected_outcome=provider_failure
  [ "$terminal_case" = terminal-unknown ] && expected_outcome=unknown
  jq -e --arg outcome "$expected_outcome" \
    '.outcome == $outcome and .response_length == 0 and
     .selected_model == null and .generation_id == null and .serving_provider == null and
     .usage_sha256 == null and .fallback == null' "$FIXTURE_ROOT/cmd.out" >/dev/null
done

for terminal_case in terminal-wrong-scope terminal-wrong-workload terminal-wrong-body \
    terminal-wrong-model terminal-wrong-exit terminal-wrong-cleanup terminal-wrong-chain \
    terminal-forged-signature terminal-response-bytes terminal-unsigned-ambiguity; do
  printf '%s\n' 0 > "$AUTH_ROOT/request-count"
  printf '%s\n' "$terminal_case" > "$AUTH_ROOT/case"
  expect_rc 75 'external dispatch rail stopped' "$terminal_case is terminal without evidence" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-$terminal_case" \
    OPENROUTER_EXEC_FALLBACK_MODEL=moonshotai/kimi-k3 \
    OPENROUTER_EXEC_ALLOWED_PATHS=auth/session.go \
    "$EXEC_RUNNER" < "$FIXTURE_ROOT/expected.prompt"
  [ "$(cat "$AUTH_ROOT/request-count")" -eq 1 ]
  [ ! -s "$FIXTURE_ROOT/cmd.out" ]
done

printf '%s\n' signed-success > "$AUTH_ROOT/case"
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

for terminal_case in terminal-provider-failure terminal-unknown terminal-unsigned-ambiguity; do
  printf '%s\n' 0 > "$AUTH_ROOT/request-count"
  printf '%s\n' "$terminal_case" > "$AUTH_ROOT/case"
  expect_rc 75 'terminal provider outcome' "cascade stops after $terminal_case" \
    env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
    DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
    DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
    DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE="nonce-cascade-$terminal_case" \
    OPENROUTER_EXEC_ALLOWED_PATHS=docs/assessment.md \
    "$CASCADE" --class openrouter --prompt 'terminal test' --host codex
  [ "$(cat "$AUTH_ROOT/request-count")" -eq 1 ]
  if [ "$terminal_case" = terminal-unsigned-ambiguity ]; then
    [ ! -s "$FIXTURE_ROOT/cmd.out" ]
  else
    jq -e '.response_length == 0 and (.outcome == "provider_failure" or .outcome == "unknown") and
      .selected_model == null and .generation_id == null and .serving_provider == null and
      .usage_sha256 == null and .fallback == null' \
      "$FIXTURE_ROOT/cmd.out" >/dev/null
  fi
done

# Exercise the single-turn wrapper branch independently of the agentic
# openrouter_exec rung. A terminal outcome must stop before the second wrapper
# model and before the following native Codex role.
jq '.cascades.openrouter.ladder = ["frontier_api", "premium_sub"]' \
  "$REPO_ROOT/plugins/pipeline/references/model-cascade.json" > "$AUTH_ROOT/wrapper-first-cascade.json"
printf '%s\n' 0 > "$AUTH_ROOT/request-count"
printf '%s\n' terminal-provider-failure > "$AUTH_ROOT/case"
expect_rc 75 'terminal provider outcome' 'wrapper rail stops after signed provider failure' \
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
  CASCADE_FILE="$AUTH_ROOT/wrapper-first-cascade.json" \
  DM_PROVIDER_REPOSITORY=design-machines/depot DM_PROVIDER_RUN_ID=run-01 \
  DM_PROVIDER_LANE=pipeline-assessment-artifact-delegation-v1 \
  DM_PROVIDER_CANDIDATE=candidate-01 DM_PROVIDER_NONCE=nonce-wrapper-terminal \
  "$CASCADE" --class openrouter --prompt 'terminal wrapper test' --host codex
[ "$(cat "$AUTH_ROOT/request-count")" -eq 1 ]
jq -e '.outcome == "provider_failure" and .response_length == 0 and
  .selected_model == null and .generation_id == null and .serving_provider == null and
  .usage_sha256 == null and .fallback == null' "$FIXTURE_ROOT/cmd.out" >/dev/null || {
  echo 'wrapper terminal receipt was not preserved as one valid JSON document' >&2
  cat "$FIXTURE_ROOT/cmd.out" >&2
  exit 1
}

printf '%s\n' 0 > "$AUTH_ROOT/request-count"
expect_rc 76 'ladder exhausted' 'ladder exhaustion remains distinct from provider terminal' \
  env DM_AUTOMATION_TEST=1 DM_AUTOMATION_TEST_ROOT="$AUTH_ROOT" \
  "$CASCADE" --class openrouter --prompt 'no eligible generic rung' --host generic
[ "$(cat "$AUTH_ROOT/request-count")" -eq 0 ]
[ ! -s "$FIXTURE_ROOT/cmd.out" ]

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
grep -Fq 'independent non-implementing-family security' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
for stale in \
  'Codex sign-off remains mandatory' \
  'requires a Codex security sign-off' \
  'independent full-diff Codex sign-off' \
  'available through a ready Workflow'; do
  if rg -Fq -- "$stale" \
    "$REPO_ROOT/plugins/openrouter" \
    "$REPO_ROOT/plugins/dm-review/commands/dm-review-quick.md" \
    "$REPO_ROOT/plugins/dm-review/skills/dm-review-quick/SKILL.md" \
    "$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"; then
    echo "stale security/broker contract survived: $stale" >&2
    exit 1
  fi
done
grep -Fq 'mcp-control-plane.md' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
grep -Fq 'OPENROUTER_RECEIPT_FILE' "$WRAPPER"
grep -Fq 'payload-authorization.sh' "$RUNNER"
grep -Fq 'AUTHORIZATION_MODE="${authorization_mode:-${OPENROUTER_PAYLOAD_AUTHORIZATION:-exact-digest}}"' "$RUNNER"
grep -Fq 'case "$target_model_origin" in' "$RUNNER"
grep -Fq 'case "$fallback_model_origin" in' "$RUNNER"
grep -Fq 'anthropic/*)' "$RUNNER"
grep -Fq '^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:-]*$' "$RUNNER"
grep -Fq 'export PATH=' "$BOUNDARY"
grep -Fq 'artifact-delegation' "$BOUNDARY"
grep -Fq 'git apply --check' "$EXEC_RUNNER"
grep -Fq -- '--pathspec-file-nul' "$EXEC_RUNNER"
grep -Fq '/usr/local/bin/workflow-authority' "$PRODUCTION_EXEC_RUNNER"
grep -Fq 'pipeline-assessment-artifact-delegation-v1' "$PRODUCTION_EXEC_RUNNER"
if grep -Eq 'openrouter-wrapper\.sh|curl[[:space:]]' "$PRODUCTION_EXEC_RUNNER"; then
  echo 'automated exec regained direct provider transport' >&2
  exit 1
fi
if grep -Eq 'OPENROUTER_PAYLOAD_AUTHORIZATION|OPENROUTER_PAYLOAD_APPROVAL_SHA256|OPENROUTER_BASE' "$PRODUCTION_EXEC_RUNNER"; then
  echo 'automated exec regained caller authority or transport selection' >&2
  exit 1
fi
if grep -Eq 'DM_AUTOMATION_TEST|DM_AUTOMATION_TEST_ROOT|FIXTURE_DOMAIN|fixture_ready' \
    "$PRODUCTION_EXEC_RUNNER" "$PRODUCTION_CASCADE"; then
  echo 'shipping adapter gained a fixture-selected client branch' >&2
  exit 1
fi
if grep -Eq 'eval.*RAW_OUT|bash.*RAW_OUT' "$EXEC_RUNNER"; then
  echo 'model output gained command authority' >&2
  exit 1
fi


# --- Interim operator-batch: transmission-point digest binding --------------
# Proves the WRAPPER refuses bytes absent from the approved lane/model mapping at the point
# of disclosure, without any verify-batch step having run. The batch file is
# hand-written on purpose: that is exactly the unauthenticated, same-user
# artifact the threat model now documents, and it is the reason the wrapper
# cannot treat the file's existence as proof that the payload was approved.
# NOT guarded by the calendar. The interim mode carries a program sunset, but
# the fixtures below must not evaporate when that date passes: a harness that
# silently stops asserting is exactly the failure these anchors exist to
# prevent, because after the sunset the enforcement could be deleted outright
# and every anchor would stay green.
#
# So the sunset-dependent cases run against a COPY of the wrapper whose sunset
# constant is repointed to a fixed far-future date -- the same
# rewrite-one-constant-in-a-copy pattern the broker fixtures use, and the same
# effect as an injected fixed clock. They keep executing and asserting
# identical behavior regardless of the real date. Both rewrites are verified,
# so a renamed or retuned constant fails the fixture instead of silently making
# it vacuous.
#
# The ONE genuinely date-dependent assertion -- what the SHIPPED constant does
# today -- is made separately at the end of this block, and it asserts in BOTH
# branches. There is no branch in which nothing is checked.
REAL_PROGRAM_SUNSET='2026-09-07'
FIXED_PROGRAM_SUNSET='2099-01-01'
MISMATCHED_PROGRAM_SUNSET='2098-01-01'
CLOCK_WRAPPER="$FIXTURE_ROOT/wrapper-fixed-sunset.sh"
CLOCK_AUTHORIZATION="$FIXTURE_ROOT/payload-authorization.sh"
grep -Fq "INTERIM_PROGRAM_SUNSET=\"$REAL_PROGRAM_SUNSET\"" "$WRAPPER" || {
  echo 'fixed-sunset fixture: shipped wrapper no longer pins the expected sunset constant' >&2
  exit 1
}
sed -e "s|^INTERIM_PROGRAM_SUNSET=.*|INTERIM_PROGRAM_SUNSET=\"$FIXED_PROGRAM_SUNSET\"|" \
  "$WRAPPER" > "$CLOCK_WRAPPER"
chmod 755 "$CLOCK_WRAPPER"
sed -e "s|^PROGRAM_SUNSET=.*|PROGRAM_SUNSET=\"$FIXED_PROGRAM_SUNSET\"|" \
  "$AUTHORIZATION" > "$CLOCK_AUTHORIZATION"
chmod 755 "$CLOCK_AUTHORIZATION"
cp "$(dirname "$WRAPPER")/model-matrix.json" "$FIXTURE_ROOT/model-matrix.json"
grep -Fq "INTERIM_PROGRAM_SUNSET=\"$FIXED_PROGRAM_SUNSET\"" "$CLOCK_WRAPPER" || {
  echo 'fixed-sunset fixture: could not repoint the wrapper sunset constant' >&2
  exit 1
}
if true; then
  # Execute the shipped runner control flow with deterministic mocks. These
  # fixtures fail if its renderer, snapshot, artifact, digest, or redispatch
  # verification checks are removed; no provider transport exists in the mocks.
  printf '%s' 'mock system' > "$FIXTURE_ROOT/runner.system"
  printf '%s' 'mock user' > "$FIXTURE_ROOT/runner.user"
  MOCK_RENDER_OK="$FIXTURE_ROOT/mock-render-ok.sh"
  MOCK_RENDER_DRIFT="$FIXTURE_ROOT/mock-render-drift.sh"
  MOCK_RENDER_FAIL="$FIXTURE_ROOT/mock-render-fail.sh"
  MOCK_AUTH_OK="$FIXTURE_ROOT/mock-auth-ok.sh"
  MOCK_AUTH_FAIL="$FIXTURE_ROOT/mock-auth-fail.sh"
  cat > "$MOCK_RENDER_OK" <<'SH'
#!/bin/sh
printf '%s' '{"model":"mock/model","provider":{},"messages":[{"role":"user","content":"mock"}]}' > "$OPENROUTER_REQUEST_ENVELOPE_OUTPUT"
SH
  cat > "$MOCK_RENDER_FAIL" <<'SH'
#!/bin/sh
exit 7
SH
  cat > "$MOCK_RENDER_DRIFT" <<'SH'
#!/bin/sh
printf '%s' '{"model":"mock/model","messages":[{"role":"user","content":"drift"}]}' > "$OPENROUTER_REQUEST_ENVELOPE_OUTPUT"
SH
  cat > "$MOCK_AUTH_OK" <<'SH'
#!/bin/sh
mode="$1"; shift
case "$mode" in
  snapshot-envelope)
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --output|--manifest) output="$2"; shift 2 ;;
        --request-file) request="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    digest="$(shasum -a 256 "$request" | awk '{print $1}')"
    inspection="${output}.request.json"
    cp "$request" "$inspection"
    chmod 600 "$inspection"
    printf '{"requestEnvelopeSha256":"%s","inspectionPath":"%s"}\n' \
      "$digest" "$inspection" > "$output"
    printf '%s\n' "$digest"
    ;;
  verify-batch)
    batch="" manifest="" request=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --batch-file) batch="$2"; shift 2 ;;
        --manifest) manifest="$2"; shift 2 ;;
        --request-file) request="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    recorded="$(jq -r '.requestEnvelopeSha256 // empty' "$manifest")"
    actual="$(shasum -a 256 "$request" | awk '{print $1}')"
    [ -n "$recorded" ] && [ "$recorded" = "$actual" ] || exit 8
    if [ -n "${EXPECTED_ORIGINAL_BATCH:-}" ]; then
      [ "$batch" != "$EXPECTED_ORIGINAL_BATCH" ] || exit 9
      printf '%s' '{"batch":"mutated-after-snapshot"}' > "$EXPECTED_ORIGINAL_BATCH"
      [ "$(shasum -a 256 "$batch" | awk '{print $1}')" = "$EXPECTED_BATCH_DIGEST" ] || exit 10
    fi
    printf '%s\n' '{"authorizationMode":"interim-operator-batch"}'
    ;;
  *) exit 2 ;;
esac
SH
  cat > "$MOCK_AUTH_FAIL" <<'SH'
#!/bin/sh
exit 8
SH
  chmod 755 "$MOCK_RENDER_OK" "$MOCK_RENDER_DRIFT" "$MOCK_RENDER_FAIL" "$MOCK_AUTH_OK" "$MOCK_AUTH_FAIL"
  RUNNER_HELPER_COMMON=(
    --system-file "$FIXTURE_ROOT/runner.system"
    --user-file "$FIXTURE_ROOT/runner.user"
    --model moonshotai/kimi-k3 --fallback z-ai/glm-5.2
    --timeout 60 --workload security
    --target-agent-name security-auditor-codex-signoff
  )
  expect_rc 2 'request envelope rendering failed' \
    'shipped runner helper detects renderer failure' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_FAIL" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-render-fail.manifest"
  expect_rc 2 'request envelope snapshot failed' \
    'shipped runner helper detects snapshot failure' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_FAIL" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-snapshot-fail.manifest"
  NONPRIVATE_PARENT="$FIXTURE_ROOT/nonprivate-parent"
  mkdir "$NONPRIVATE_PARENT"
  chmod 755 "$NONPRIVATE_PARENT"
  expect_rc 2 'manifest parent must be creator-owned mode 0700' \
    'creator refuses a non-private manifest parent before snapshot' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$NONPRIVATE_PARENT/refused.manifest"
  [ ! -e "$NONPRIVATE_PARENT/refused.manifest" ] &&
    [ ! -e "$NONPRIVATE_PARENT/refused.manifest.request.json" ] || {
    echo 'non-private manifest parent received preparation bytes' >&2
    exit 1
  }
  expect_rc 0 '' 'shipped runner helper prepares a manifest without provider contact' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-cleanup.manifest"
  [ -s "$FIXTURE_ROOT/mock-cleanup.manifest" ] || {
    echo 'shipped runner helper did not preserve its preparation manifest' >&2
    exit 1
  }
  MOCK_SUCCESS_INSPECTION="$FIXTURE_ROOT/mock-cleanup.manifest.request.json"
  [ -s "$MOCK_SUCCESS_INSPECTION" ] || {
    echo 'shipped runner helper did not retain its inspectable envelope' >&2
    exit 1
  }
  expect_rc 2 'required input unavailable or malformed' \
    'cross-process prepared-artifact cleanup is unavailable' \
    "$RUNNER_BATCH_AUTHORIZATION" cleanup \
      --manifest "$FIXTURE_ROOT/mock-cleanup.manifest"
  [ -e "$FIXTURE_ROOT/mock-cleanup.manifest" ] &&
    [ -e "$MOCK_SUCCESS_INSPECTION" ] || {
    echo 'rejected cross-process cleanup mutated preparation artifacts' >&2
    exit 1
  }
  printf '%s' '{"batch":"mock"}' > "$FIXTURE_ROOT/mock-batch.json"
  MOCK_BATCH_DIGEST="$(shasum -a 256 "$FIXTURE_ROOT/mock-batch.json" | awk '{print $1}')"
  expect_rc 0 '' 'creator prepares the failure-path cleanup fixture' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-failure.manifest"
  expect_rc 2 'redispatch request envelope is not authorized' \
    'shipped runner helper compares redispatch with the preparation manifest' \
    "$RUNNER_BATCH_AUTHORIZATION" verify --wrapper "$MOCK_RENDER_DRIFT" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-failure.manifest" \
      --batch-file "$FIXTURE_ROOT/mock-batch.json" \
      --batch-digest "$MOCK_BATCH_DIGEST" --run-id fixture-run
  [ -e "$FIXTURE_ROOT/mock-failure.manifest" ] &&
    [ -e "$FIXTURE_ROOT/mock-failure.manifest.request.json" ] || {
    echo 'failed redispatch mutated persisted preparation artifacts' >&2
    exit 1
  }
  expect_rc 0 '' 'creator prepares the missing-input cleanup fixture' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-missing-input.manifest"
  expect_rc 2 'required input unavailable or malformed' \
    'verify cleanup runs when a required input is unavailable' \
    "$RUNNER_BATCH_AUTHORIZATION" verify --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --user-file "$FIXTURE_ROOT/missing-runner.user" \
      --manifest "$FIXTURE_ROOT/mock-missing-input.manifest" \
      --batch-file "$FIXTURE_ROOT/mock-batch.json" \
      --batch-digest "$MOCK_BATCH_DIGEST" --run-id fixture-run
  [ -e "$FIXTURE_ROOT/mock-missing-input.manifest" ] &&
    [ -e "$FIXTURE_ROOT/mock-missing-input.manifest.request.json" ] || {
    echo 'missing-input redispatch mutated persisted preparation artifacts' >&2
    exit 1
  }
  expect_rc 0 '' 'creator prepares the render-failure cleanup fixture' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-verify-render-fail.manifest"
  expect_rc 2 'request envelope rendering failed' \
    'verify cleanup runs when request rendering fails' \
    "$RUNNER_BATCH_AUTHORIZATION" verify --wrapper "$MOCK_RENDER_FAIL" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-verify-render-fail.manifest" \
      --batch-file "$FIXTURE_ROOT/mock-batch.json" \
      --batch-digest "$MOCK_BATCH_DIGEST" --run-id fixture-run
  [ -e "$FIXTURE_ROOT/mock-verify-render-fail.manifest" ] &&
    [ -e "$FIXTURE_ROOT/mock-verify-render-fail.manifest.request.json" ] || {
    echo 'render-failed redispatch mutated persisted preparation artifacts' >&2
    exit 1
  }
  expect_rc 0 '' 'creator prepares the completed-path cleanup fixture' \
    "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-completed.manifest"
  expect_rc 0 '' 'shipped runner helper verifies an immutable private batch snapshot' \
    env EXPECTED_ORIGINAL_BATCH="$FIXTURE_ROOT/mock-batch.json" \
      EXPECTED_BATCH_DIGEST="$MOCK_BATCH_DIGEST" \
      "$RUNNER_BATCH_AUTHORIZATION" verify --wrapper "$MOCK_RENDER_OK" \
      --authorization-helper "$MOCK_AUTH_OK" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$FIXTURE_ROOT/mock-completed.manifest" \
      --batch-file "$FIXTURE_ROOT/mock-batch.json" \
      --batch-digest "$MOCK_BATCH_DIGEST" --run-id fixture-run
  [ -e "$FIXTURE_ROOT/mock-completed.manifest" ] &&
    [ -e "$FIXTURE_ROOT/mock-completed.manifest.request.json" ] || {
    echo 'completed redispatch mutated persisted preparation artifacts' >&2
    exit 1
  }

  # Schema-v2 request-envelope binding. The same approved message content sent
  # under a different model is a different authorization target: model and
  # provider routing are transmitted bytes, not harmless local metadata.
  ENVELOPE_SYSTEM='fixture system turn for full-envelope binding'
  ENVELOPE_PROMPT='fixture user turn for full-envelope binding'
  ENVELOPE_REQUEST="$FIXTURE_ROOT/approved-request-envelope.json"
  expect_rc 0 '' 'canonical wrapper renders the approvable request envelope' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_REQUEST_ENVELOPE_OUTPUT="$ENVELOPE_REQUEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT"
  expect_rc 2 'could not materialize the request envelope' \
    'runner preparation detects canonical renderer failure' \
    env OPENROUTER_API_KEY=test OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_REQUEST_ENVELOPE_OUTPUT="$FIXTURE_ROOT/missing/request.json" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT"
  expect_rc 2 'request file unavailable' \
    'runner preparation detects request-envelope snapshot failure' \
    "$CLOCK_AUTHORIZATION" snapshot-envelope \
      --output "$FIXTURE_ROOT/unusable-manifest.json" \
      --request-file "$FIXTURE_ROOT/missing-request.json"
  ENVELOPE_MANIFEST="$FIXTURE_ROOT/approved-request-envelope.manifest.json"
  if ! ENVELOPE_DIGEST=$("$CLOCK_AUTHORIZATION" snapshot-envelope \
       --output "$ENVELOPE_MANIFEST" --request-file "$ENVELOPE_REQUEST"); then
    echo 'runner preparation could not snapshot the rendered request envelope' >&2
    exit 1
  fi
  [[ "$ENVELOPE_DIGEST" =~ ^[0-9a-f]{64}$ ]] &&
    [ -r "$ENVELOPE_REQUEST" ] && [ -s "$ENVELOPE_REQUEST" ] &&
    [ -r "$ENVELOPE_MANIFEST" ] && [ -s "$ENVELOPE_MANIFEST" ] || {
    echo 'runner preparation did not produce a usable envelope and manifest' >&2
    exit 1
  }
  ENVELOPE_INSPECTION="$(jq -er '.inspectionPath | select(type == "string" and length > 0)' \
    "$ENVELOPE_MANIFEST")" || {
    echo 'canonical envelope manifest did not retain an operator inspection path' >&2
    exit 1
  }

  # Exact-digest approval is over the complete canonical request, not merely
  # the system/user strings. A model swap with unchanged messages must fail
  # before provider contact.
  EXACT_DRIFT_REQUEST="$FIXTURE_ROOT/exact-digest-model-drift.json"
  expect_rc 0 '' 'canonical wrapper renders a different-model request envelope' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_REQUEST_ENVELOPE_OUTPUT="$EXACT_DRIFT_REQUEST" \
      "$CLOCK_WRAPPER" openai/gpt-5.6-luna "$ENVELOPE_PROMPT"
  expect_rc 0 '' 'exact-digest accepts the unchanged canonical request envelope' \
    "$CLOCK_AUTHORIZATION" verify-envelope \
      --manifest "$ENVELOPE_MANIFEST" --approved-sha256 "$ENVELOPE_DIGEST" \
      --request-file "$ENVELOPE_REQUEST"
  expect_rc 2 'request envelope changed after authorization snapshot' \
    'exact-digest rejects a model-swapped canonical request envelope' \
    "$CLOCK_AUTHORIZATION" verify-envelope \
      --manifest "$ENVELOPE_MANIFEST" --approved-sha256 "$ENVELOPE_DIGEST" \
      --request-file "$EXACT_DRIFT_REQUEST"
  expect_rc 2 'transmitted request envelope digest was not approved' \
    'wrapper rejects a model-swapped exact-digest request before contact' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_AUTHORIZATION_MODE=exact-digest \
      OPENROUTER_APPROVED_REQUEST_ENVELOPE_SHA256="$ENVELOPE_DIGEST" \
      "$CLOCK_WRAPPER" openai/gpt-5.6-luna "$ENVELOPE_PROMPT"
  expect_rc 1 'transport error' \
    'exact-digest receipt preserves run lane invocation and envelope identity' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_AUTHORIZATION_MODE=exact-digest \
      OPENROUTER_AUTHORIZATION_RUN_ID=exact-fixture-run \
      OPENROUTER_LANE_ID=exact-fixture-lane \
      OPENROUTER_APPROVED_REQUEST_ENVELOPE_SHA256="$ENVELOPE_DIGEST" \
      OPENROUTER_RECEIPT_FILE="$FIXTURE_ROOT/exact-digest.receipt.json" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT"
  jq -e --arg request "$ENVELOPE_DIGEST" '
    .authorization.runId == "exact-fixture-run"
    and .authorization.laneId == "exact-fixture-lane"
    and .authorization.requestEnvelopeSha256 == $request
    and (.invocationId | test("^[0-9a-f]{64}$"))
  ' "$FIXTURE_ROOT/exact-digest.receipt.json" >/dev/null || {
    echo 'exact-digest receipt lost authorization replay identity' >&2
    exit 1
  }
  expect_rc 1 'transport error' \
    'trusted-boundary receipt carries canonical request envelope identity' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_AUTHORIZATION_MODE=trusted-boundary \
      OPENROUTER_AUTHORIZATION_RUN_ID=trusted-fixture-run \
      OPENROUTER_LANE_ID=trusted-fixture-lane \
      OPENROUTER_RECEIPT_FILE="$FIXTURE_ROOT/trusted-boundary.receipt.json" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT"
  jq -e --arg request "$ENVELOPE_DIGEST" '
    .authorization.runId == "trusted-fixture-run"
    and .authorization.laneId == "trusted-fixture-lane"
    and .authorization.requestEnvelopeSha256 == $request
    and (.invocationId | test("^[0-9a-f]{64}$"))
  ' "$FIXTURE_ROOT/trusted-boundary.receipt.json" >/dev/null || {
    echo 'trusted-boundary receipt lost canonical envelope identity' >&2
    exit 1
  }

  # A signal before canonical request bytes exist is a local preparation
  # failure, not a provider attempt receipt with a null envelope identity.
  PRE_ENVELOPE_WRAPPER="$FIXTURE_ROOT/wrapper-pre-envelope-signal.sh"
  PRE_ENVELOPE_MARKER="$FIXTURE_ROOT/pre-envelope.marker"
  PRE_ENVELOPE_RECEIPT="$FIXTURE_ROOT/pre-envelope.receipt.json"
  sed -e '/^provider="$(build_provider)"$/a\
: > "$PRE_ENVELOPE_MARKER"\
while :; do :; done' "$CLOCK_WRAPPER" > "$PRE_ENVELOPE_WRAPPER"
  chmod 755 "$PRE_ENVELOPE_WRAPPER"
  set +e
  env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
    OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
    OPENROUTER_AUTHORIZATION_MODE=trusted-boundary \
    OPENROUTER_AUTHORIZATION_RUN_ID=pre-envelope-run \
    OPENROUTER_LANE_ID=pre-envelope-lane \
    OPENROUTER_RECEIPT_FILE="$PRE_ENVELOPE_RECEIPT" \
    PRE_ENVELOPE_MARKER="$PRE_ENVELOPE_MARKER" \
    "$PRE_ENVELOPE_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT" \
    >"$FIXTURE_ROOT/pre-envelope.out" 2>"$FIXTURE_ROOT/pre-envelope.err" &
  PRE_ENVELOPE_PID=$!
  set -e
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    [ -e "$PRE_ENVELOPE_MARKER" ] && break
    sleep 0.1
  done
  [ -e "$PRE_ENVELOPE_MARKER" ] || {
    kill -KILL "$PRE_ENVELOPE_PID" 2>/dev/null || true
    echo 'pre-envelope signal fixture never reached its injection point' >&2
    exit 1
  }
  kill -TERM "$PRE_ENVELOPE_PID"
  set +e
  wait "$PRE_ENVELOPE_PID"
  PRE_ENVELOPE_RC=$?
  set -e
  [ "$PRE_ENVELOPE_RC" -ne 0 ] && [ ! -e "$PRE_ENVELOPE_RECEIPT" ] || {
    echo 'pre-envelope interruption emitted an unbound provider receipt' >&2
    exit 1
  }

  # Exercise the actual runner helper across both phases. This catches the
  # production-callsite bug where redispatch accidentally substituted a
  # content-mode authorization receipt for the preserved envelope manifest;
  # the mock helper cannot distinguish those artifact schemas.
  REAL_HELPER_MANIFEST="$FIXTURE_ROOT/real-helper-envelope.manifest.json"
  expect_rc 0 '' \
    'real runner helper prepares through the canonical wrapper and typed authorization helper' \
    env OPENROUTER_API_KEY=test \
      "$RUNNER_BATCH_AUTHORIZATION" prepare --wrapper "$CLOCK_WRAPPER" \
      --authorization-helper "$CLOCK_AUTHORIZATION" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$REAL_HELPER_MANIFEST"
  REAL_HELPER_DIGEST="$(jq -er '.requestEnvelopeSha256 | select(test("^[0-9a-f]{64}$"))' \
    "$REAL_HELPER_MANIFEST")" || {
    echo 'real runner helper did not preserve a valid preparation manifest' >&2
    exit 1
  }
  REAL_HELPER_INSPECTION="$(jq -er '.inspectionPath | select(type == "string" and length > 0)' \
    "$REAL_HELPER_MANIFEST")" || {
    echo 'real runner helper did not retain an operator inspection path' >&2
    exit 1
  }
  [ -r "$REAL_HELPER_INSPECTION" ] && [ -s "$REAL_HELPER_INSPECTION" ] &&
    jq -e '
      .modelCandidates == ["moonshotai/kimi-k3", "z-ai/glm-5.2"]
      and (.providerRouting | type) == "object"
      and [.messageRoleByteCounts[].role] == ["system", "user"]
    ' "$REAL_HELPER_MANIFEST" >/dev/null || {
    echo 'real runner helper did not preserve an inspectable model/provider/role summary' >&2
    exit 1
  }

  [ -s "$ENVELOPE_INSPECTION" ] && [ -s "$REAL_HELPER_INSPECTION" ] || {
    echo 'batch approval fixture lost an inspection copy before confirmation' >&2
    exit 1
  }
  BATCH_TRANSCRIPT="$FIXTURE_ROOT/batch-approve.transcript"
  if ! run_pty_with_reply 'APPROVE INTERIM BATCH' \
      "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FIXTURE_ROOT/batch-envelope-v2.json" \
      --run-id fixture-run --operator fixture-operator \
      --scope-note 'fixture batch covering canonical and runner-helper request envelopes' \
      --lane "fixture-envelope=$ENVELOPE_MANIFEST" \
      --lane "security-auditor-codex-signoff=$REAL_HELPER_MANIFEST" \
      >"$BATCH_TRANSCRIPT" 2>&1; then
    echo 'real interactive batch approval failed under the PTY fixture' >&2
    cat "$BATCH_TRANSCRIPT" >&2
    exit 1
  fi
  for expected_summary in \
      'fixture-envelope' \
      'security-auditor-codex-signoff' \
      'moonshotai/kimi-k3' \
      '"require_parameters":true' \
      'message bytes:' \
      "$ENVELOPE_INSPECTION" \
      "$REAL_HELPER_INSPECTION"; do
    grep -Fq "$expected_summary" "$BATCH_TRANSCRIPT" || {
      echo "interactive batch transcript omitted: $expected_summary" >&2
      cat "$BATCH_TRANSCRIPT" >&2
      exit 1
    }
  done
  [ -e "$ENVELOPE_INSPECTION" ] && [ -e "$REAL_HELPER_INSPECTION" ] || {
    echo 'batch approval deleted caller-owned inspection input' >&2
    exit 1
  }
  rm -f "$ENVELOPE_INSPECTION" "$REAL_HELPER_INSPECTION"

  # A lane path is input, not ownership. An unreadable/nonexistent manifest
  # must not make a similarly named pre-existing file eligible for cleanup.
  CALLER_MANIFEST="$FIXTURE_ROOT/caller-owned"
  CALLER_COMPANION="$CALLER_MANIFEST.request.json"
  printf '%s' 'caller-owned bytes' > "$CALLER_COMPANION"
  expect_rc 2 'lane authorization manifest unreadable' \
    'invalid lane path preserves a caller-owned request companion' \
    "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FIXTURE_ROOT/caller-owned-batch.json" \
      --run-id caller-owned-run --operator fixture-operator \
      --scope-note 'caller-owned cleanup refusal fixture' \
      --lane "fixture-envelope=$CALLER_MANIFEST"
  [ "$(cat "$CALLER_COMPANION")" = 'caller-owned bytes' ] || {
    echo 'invalid lane path deleted or changed a caller-owned companion' >&2
    exit 1
  }

  SYMLINK_REAL_PARENT="$FIXTURE_ROOT/symlink-real-parent"
  SYMLINK_PARENT="$FIXTURE_ROOT/symlink-parent"
  SYMLINK_VICTIM="$FIXTURE_ROOT/symlink-victim.json"
  mkdir "$SYMLINK_REAL_PARENT"
  ln -s "$SYMLINK_REAL_PARENT" "$SYMLINK_PARENT"
  printf '%s' 'symlink-victim-bytes' > "$SYMLINK_VICTIM"
  SYMLINK_MANIFEST="$SYMLINK_PARENT/missing.manifest.json"
  ln -s "$SYMLINK_VICTIM" "$SYMLINK_MANIFEST.request.json"
  expect_rc 2 'lane authorization manifest unreadable' \
    'symlinked parent and companion remain outside batch cleanup authority' \
    "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FIXTURE_ROOT/symlink-batch.json" \
      --run-id symlink-run --operator fixture-operator \
      --scope-note 'symlink cleanup refusal fixture' \
      --lane "fixture-envelope=$SYMLINK_MANIFEST"
  [ -L "$SYMLINK_MANIFEST.request.json" ] &&
    [ "$(cat "$SYMLINK_VICTIM")" = 'symlink-victim-bytes' ] || {
    echo 'batch refusal mutated a symlinked caller-owned path' >&2
    exit 1
  }

  # Adjacent metadata is caller-controlled too. Matching inode/digest claims
  # must not authorize deletion of a replacement companion.
  FORGED_MANIFEST="$FIXTURE_ROOT/forged-owner.json"
  FORGED_REQUEST="$ENVELOPE_REQUEST"
  expect_rc 0 '' 'snapshot creates forged-owner fixture metadata' \
    "$CLOCK_AUTHORIZATION" snapshot-envelope \
      --output "$FORGED_MANIFEST" --request-file "$FORGED_REQUEST"
  FORGED_COMPANION="$FORGED_MANIFEST.request.json"
  cp "$FORGED_REQUEST" "$FORGED_COMPANION"
  FORGED_DEVICE="$(stat -f '%d' "$FORGED_COMPANION")"
  FORGED_INODE="$(stat -f '%i' "$FORGED_COMPANION")"
  FORGED_DIGEST="$(shasum -a 256 "$FORGED_COMPANION" | awk '{print $1}')"
  jq -n --arg manifest "$FORGED_MANIFEST" --arg inspection "$FORGED_COMPANION" \
    --argjson device "$FORGED_DEVICE" --argjson inode "$FORGED_INODE" \
    --arg digest "$FORGED_DIGEST" \
    '{schemaVersion:1, manifestPath:$manifest, inspectionPath:$inspection,
      device:$device, inode:$inode, requestEnvelopeSha256:$digest}' \
    > "$FORGED_MANIFEST.ownership.json"
  expect_rc 2 'lane authorization manifest unreadable' \
    'forged ownership metadata cannot authorize caller companion cleanup' \
    "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FIXTURE_ROOT/forged-owner-batch.json" \
      --run-id forged-owner-run --operator fixture-operator \
      --scope-note 'forged ownership cleanup refusal fixture' \
      --lane "forged-owner=$FORGED_MANIFEST" \
      --lane "missing=$FIXTURE_ROOT/forged-owner-missing.json"
  [ -f "$FORGED_COMPANION" ] || {
    echo 'forged ownership metadata deleted a caller-owned companion' >&2
    exit 1
  }
  rm -f "$FORGED_COMPANION" "$FORGED_MANIFEST.ownership.json"
  jq -e --arg first "$ENVELOPE_DIGEST" --arg second "$REAL_HELPER_DIGEST" '
    [.lanes[].lane_id] == ["fixture-envelope", "security-auditor-codex-signoff"]
    and [.lanes[].requestEnvelopeSha256] == [$first, $second]
    and (.lanes[] | .modelCandidates | length > 0)
    and (.lanes[] | .providerRouting.require_parameters | type == "boolean")
    and (.lanes[] | .messageRoleByteCounts | length > 0)
  ' "$FIXTURE_ROOT/batch-envelope-v2.json" >/dev/null || {
    echo 'interactive batch approval did not persist the displayed lane mapping' >&2
    exit 1
  }

  # Approval consumes lane artifacts read-only. The creating context retains
  # cleanup authority on both successful and unsuccessful paths.
  NO_TTY_MANIFEST="$FIXTURE_ROOT/no-tty.manifest.json"
  "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$NO_TTY_MANIFEST" \
    --request-file "$ENVELOPE_REQUEST" >/dev/null
  NO_TTY_INSPECTION="$(jq -r '.inspectionPath' "$NO_TTY_MANIFEST")"
  expect_rc 2 'interactive confirmation unavailable' \
    'batch approval without a controlling terminal fails closed' \
    "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FIXTURE_ROOT/no-tty-batch.json" --run-id no-tty-run \
      --operator fixture-operator --scope-note 'no tty cleanup fixture' \
      --lane "fixture-envelope=$NO_TTY_MANIFEST"
  [ -e "$NO_TTY_INSPECTION" ] || {
    echo 'no-TTY batch refusal deleted caller-owned inspection input' >&2
    exit 1
  }
  rm -f "$NO_TTY_INSPECTION"

  DECLINE_MANIFEST="$FIXTURE_ROOT/decline.manifest.json"
  "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$DECLINE_MANIFEST" \
    --request-file "$ENVELOPE_REQUEST" >/dev/null
  DECLINE_INSPECTION="$(jq -r '.inspectionPath' "$DECLINE_MANIFEST")"
  set +e
  run_pty_with_reply 'DECLINE' "$CLOCK_AUTHORIZATION" batch-approve \
    --batch-file "$FIXTURE_ROOT/declined-batch.json" --run-id declined-run \
    --operator fixture-operator --scope-note 'decline cleanup fixture' \
    --lane "fixture-envelope=$DECLINE_MANIFEST" \
    >"$FIXTURE_ROOT/decline.transcript" 2>&1
  DECLINE_RC=$?
  set -e
  [ "$DECLINE_RC" -eq 2 ] &&
    grep -Fq 'interim batch authorization declined by operator' \
      "$FIXTURE_ROOT/decline.transcript" &&
  [ -e "$DECLINE_INSPECTION" ] && [ ! -e "$FIXTURE_ROOT/declined-batch.json" ] || {
    echo 'declined PTY approval mutated caller input or retained authorization' >&2
    cat "$FIXTURE_ROOT/decline.transcript" >&2
    exit 1
  }
  rm -f "$DECLINE_INSPECTION"

  INTERRUPT_MANIFEST="$FIXTURE_ROOT/interrupt.manifest.json"
  "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$INTERRUPT_MANIFEST" \
    --request-file "$ENVELOPE_REQUEST" >/dev/null
  INTERRUPT_INSPECTION="$(jq -r '.inspectionPath' "$INTERRUPT_MANIFEST")"
  set +e
  run_pty_and_interrupt "$CLOCK_AUTHORIZATION" batch-approve \
    --batch-file "$FIXTURE_ROOT/interrupted-batch.json" --run-id interrupted-run \
    --operator fixture-operator --scope-note 'signal cleanup fixture' \
    --lane "fixture-envelope=$INTERRUPT_MANIFEST" \
    >"$FIXTURE_ROOT/interrupt.transcript" 2>&1
  INTERRUPT_RC=$?
  set -e
  [ "$INTERRUPT_RC" -ne 0 ] && [ "$INTERRUPT_RC" -ne 124 ] &&
    grep -Fq 'interactive batch authorization interrupted by signal' \
      "$FIXTURE_ROOT/interrupt.transcript" &&
    [ "$(grep -Fc 'interactive batch authorization interrupted by signal' \
      "$FIXTURE_ROOT/interrupt.transcript")" -eq 1 ] &&
    [ -e "$INTERRUPT_INSPECTION" ] && [ ! -e "$FIXTURE_ROOT/interrupted-batch.json" ] || {
    echo 'interrupted PTY approval mutated caller input or retained authorization' >&2
    echo "interrupt rc=$INTERRUPT_RC inspection_exists=$([ -e "$INTERRUPT_INSPECTION" ] && echo yes || echo no) batch_exists=$([ -e "$FIXTURE_ROOT/interrupted-batch.json" ] && echo yes || echo no)" >&2
    cat "$FIXTURE_ROOT/interrupt.transcript" >&2
    exit 1
  }
  rm -f "$INTERRUPT_INSPECTION"

  PARTIAL_MANIFEST="$FIXTURE_ROOT/partial.manifest.json"
  "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$PARTIAL_MANIFEST" \
    --request-file "$ENVELOPE_REQUEST" >/dev/null
  PARTIAL_INSPECTION="$(jq -r '.inspectionPath' "$PARTIAL_MANIFEST")"
  MALFORMED_LANE_MANIFEST="$FIXTURE_ROOT/malformed-second.manifest.json"
  "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$MALFORMED_LANE_MANIFEST" \
    --request-file "$ENVELOPE_REQUEST" >/dev/null
  MALFORMED_LANE_INSPECTION="$(jq -r '.inspectionPath' "$MALFORMED_LANE_MANIFEST")"
  jq '.schemaVersion = 1' "$MALFORMED_LANE_MANIFEST" \
    > "$FIXTURE_ROOT/malformed-second.tmp"
  mv "$FIXTURE_ROOT/malformed-second.tmp" "$MALFORMED_LANE_MANIFEST"
  expect_rc 2 'lane authorization manifest schema unsupported' \
    'partial-lane validation preserves every caller-owned companion' \
    "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FIXTURE_ROOT/partial-batch.json" --run-id partial-run \
      --operator fixture-operator --scope-note 'partial lane cleanup fixture' \
      --lane "fixture-envelope=$PARTIAL_MANIFEST" \
      --lane "malformed=$MALFORMED_LANE_MANIFEST"
  [ -e "$PARTIAL_INSPECTION" ] && [ -e "$MALFORMED_LANE_INSPECTION" ] || {
    echo 'partial-lane batch refusal deleted caller-owned inspection input' >&2
    exit 1
  }
  rm -f "$PARTIAL_INSPECTION" "$MALFORMED_LANE_INSPECTION"

  for MANIFEST_FAILURE in invalid-json unreadable; do
    BROKEN_MANIFEST="$FIXTURE_ROOT/$MANIFEST_FAILURE.manifest.json"
    "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$BROKEN_MANIFEST" \
      --request-file "$ENVELOPE_REQUEST" >/dev/null
    BROKEN_INSPECTION="$(jq -r '.inspectionPath' "$BROKEN_MANIFEST")"
    if [ "$MANIFEST_FAILURE" = "invalid-json" ]; then
      printf '%s\n' '{not-json' > "$BROKEN_MANIFEST"
      BROKEN_REASON='lane authorization manifest unreadable'
    else
      chmod 000 "$BROKEN_MANIFEST"
      BROKEN_REASON='lane authorization manifest unreadable'
    fi
    expect_rc 2 "$BROKEN_REASON" \
      "$MANIFEST_FAILURE manifest refusal preserves caller-owned companion" \
      "$CLOCK_AUTHORIZATION" batch-approve \
        --batch-file "$FIXTURE_ROOT/$MANIFEST_FAILURE.batch.json" \
        --run-id "$MANIFEST_FAILURE-run" --operator fixture-operator \
        --scope-note "$MANIFEST_FAILURE cleanup fixture" \
        --lane "fixture-envelope=$BROKEN_MANIFEST"
    [ -e "$BROKEN_INSPECTION" ] || {
      echo "$MANIFEST_FAILURE manifest deleted caller-owned inspection input" >&2
      exit 1
    }
    rm -f "$BROKEN_INSPECTION"
    chmod 600 "$BROKEN_MANIFEST" 2>/dev/null || true
  done

  # Denial-only test stages exercise unexpected exceptions around each I/O
  # boundary. They can only abort and roll back; they cannot grant authority.
  for FAILURE_STAGE in tty-write mkdir mkstemp signal-before-temp-ownership \
      signal-before-batch-ownership final-read canonical-validation; do
    FAILURE_MANIFEST="$FIXTURE_ROOT/failure-$FAILURE_STAGE.manifest.json"
    FAILURE_BATCH="$FIXTURE_ROOT/failure-$FAILURE_STAGE.batch.json"
    "$CLOCK_AUTHORIZATION" snapshot-envelope --output "$FAILURE_MANIFEST" \
      --request-file "$ENVELOPE_REQUEST" >/dev/null
    FAILURE_INSPECTION="$(jq -r '.inspectionPath' "$FAILURE_MANIFEST")"
    set +e
    run_pty_with_reply 'APPROVE INTERIM BATCH' env \
      PAYLOAD_AUTH_TEST_MODE=1 PAYLOAD_AUTH_TEST_FAILURE_STAGE="$FAILURE_STAGE" \
      "$CLOCK_AUTHORIZATION" batch-approve \
      --batch-file "$FAILURE_BATCH" --run-id "failure-$FAILURE_STAGE-run" \
      --operator fixture-operator --scope-note "failure $FAILURE_STAGE fixture" \
      --lane "fixture-envelope=$FAILURE_MANIFEST" \
      >"$FIXTURE_ROOT/failure-$FAILURE_STAGE.transcript" 2>&1
    FAILURE_RC=$?
    set -e
    [ "$FAILURE_RC" -ne 0 ] && [ -e "$FAILURE_INSPECTION" ] &&
      [ ! -e "$FAILURE_BATCH" ] &&
      ! find "$FIXTURE_ROOT" -maxdepth 1 -name ".$(basename "$FAILURE_BATCH").*" \
        -print -quit | grep -q . || {
      echo "$FAILURE_STAGE failure deleted caller input or retained batch authorization" >&2
      cat "$FIXTURE_ROOT/failure-$FAILURE_STAGE.transcript" >&2
      exit 1
    }
    rm -f "$FAILURE_INSPECTION"
  done
  ENVELOPE_BATCH_DIGEST="$(shasum -a 256 "$FIXTURE_ROOT/batch-envelope-v2.json" | awk '{print $1}')"
  expect_rc 0 '' \
    'real runner helper verifies redispatch with the preserved preparation manifest' \
    env OPENROUTER_API_KEY=test \
      "$RUNNER_BATCH_AUTHORIZATION" verify --wrapper "$CLOCK_WRAPPER" \
      --authorization-helper "$CLOCK_AUTHORIZATION" "${RUNNER_HELPER_COMMON[@]}" \
      --manifest "$REAL_HELPER_MANIFEST" \
      --batch-file "$FIXTURE_ROOT/batch-envelope-v2.json" \
      --batch-digest "$ENVELOPE_BATCH_DIGEST" --run-id fixture-run
  expect_rc 0 '' \
    'runner redispatch verifies the re-rendered request envelope against the batch' \
    "$CLOCK_AUTHORIZATION" verify-batch \
      --batch-file "$FIXTURE_ROOT/batch-envelope-v2.json" \
      --run-id fixture-run --lane-id fixture-envelope --manifest "$ENVELOPE_MANIFEST" \
      --request-file "$ENVELOPE_REQUEST"
  expect_rc 1 'transport error' \
    'interim batch accepts the exact complete request envelope approved' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_TARGET_AGENT_NAME=fixture-envelope \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-envelope-v2.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$ENVELOPE_BATCH_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT"
  expect_rc 2 'transmitted request envelope is not bound to this approved lane and model set' \
    'interim batch refuses an unapproved model mutation with approved content' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" \
      OPENROUTER_TARGET_AGENT_NAME=fixture-envelope \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-envelope-v2.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$ENVELOPE_BATCH_DIGEST" \
      "$CLOCK_WRAPPER" z-ai/glm-5.2 "$ENVELOPE_PROMPT"
  expect_rc 2 'transmitted request envelope is not bound to this approved lane and model set' \
    'interim batch refuses an unapproved provider-routing mutation' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$ENVELOPE_SYSTEM" OPENROUTER_PROVIDER_SORT=throughput \
      OPENROUTER_TARGET_AGENT_NAME=fixture-envelope \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-envelope-v2.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$ENVELOPE_BATCH_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$ENVELOPE_PROMPT"

  expect_rc 2 'model slug exceeds 128 bytes' \
    'OpenRouter wrapper refuses oversized model metadata' \
    env OPENROUTER_API_KEY=test \
      "$WRAPPER" "vendor/$(printf 'a%.0s' {1..122})" ordinary
  expect_rc 2 'security review role requires Kimi K3 primary and GLM-5.2 fallback' \
    'security runner refuses a matrix-listed model assigned to the wrong role' \
    env OPENROUTER_API_KEY=test OPENROUTER_TARGET_AGENT_NAME=security-auditor-openrouter \
      "$WRAPPER" qwen/qwen3-coder ordinary 60 z-ai/glm-5.2
  expect_rc 2 'security review role requires Kimi K3 primary and GLM-5.2 fallback' \
    'Codex-signoff security runner refuses a matrix-listed model assigned to the wrong role' \
    env OPENROUTER_API_KEY=test OPENROUTER_TARGET_AGENT_NAME=security-auditor-codex-signoff \
      "$WRAPPER" qwen/qwen3-coder ordinary 60 z-ai/glm-5.2

  expect_rc 0 '' \
    'typed batch validator accepts a complete live schema-v2 batch' \
    "$CLOCK_AUTHORIZATION" validate-batch \
      --batch-file "$FIXTURE_ROOT/batch-envelope-v2.json" --run-id fixture-run

  typed_batch_refusal() {
    local name="$1" expression="$2" reason="$3"
    local mutated="$FIXTURE_ROOT/typed-$name.json"
    jq "$expression" "$FIXTURE_ROOT/batch-envelope-v2.json" > "$mutated"
    expect_rc 2 "$reason" "typed batch rejects $name" \
      "$CLOCK_AUTHORIZATION" validate-batch --batch-file "$mutated" --run-id fixture-run
  }
  typed_batch_refusal empty-model \
    '.lanes[0].modelCandidates = [""]' \
    'lane model candidates malformed'
  typed_batch_refusal boolean-byte-count \
    '.lanes[0].byteCount = true' \
    'lane byte count malformed'
  typed_batch_refusal string-provider-boolean \
    '.lanes[0].providerRouting.require_parameters = "true"' \
    'lane provider routing malformed'
  typed_batch_refusal unknown-provider-key \
    '.lanes[0].providerRouting.unknown = true' \
    'lane provider routing malformed'
  typed_batch_refusal malformed-role-record \
    '.lanes[0].messageRoleByteCounts[0].unexpected = 1' \
    'lane role byte counts malformed'

  python3 - "$FIXTURE_ROOT/batch-authorization.json" "$FIXED_PROGRAM_SUNSET" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc).replace(microsecond=0)
document = {
    "schema_version": 2,
    "authorization_mode": "interim_operator_batch",
    "run_id": "fixture-run",
    "operator": "fixture-operator",
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "request_envelope_digests": ["0" * 64],
    "lanes": [{
        "lane_id": "fixture-lane",
        "requestEnvelopeSha256": "0" * 64,
        "byteCount": 0,
        "modelCandidates": ["moonshotai/kimi-k3"],
        "providerRouting": {"require_parameters": True, "allow_fallbacks": True},
        "messageRoleByteCounts": [{"role": "user", "byteCount": 0}],
    }],
    "scope_note": "fixture batch covering no real payload",
    "program_sunset": sys.argv[2],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(document, handle, sort_keys=True)
    handle.write("\n")
PY
  FIXTURE_BATCH_DIGEST="$(shasum -a 256 "$FIXTURE_ROOT/batch-authorization.json" | awk '{print $1}')"
  expect_rc 2 'transmitted request envelope is not bound to this approved lane and model set' \
    'interim batch refuses unapproved transmitted bytes' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$FIXTURE_BATCH_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 'payload bytes the operator never approved'

  python3 - "$FIXTURE_ROOT/batch-authorization-sunset.json" "$MISMATCHED_PROGRAM_SUNSET" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc).replace(microsecond=0)
document = {
    "schema_version": 2,
    "authorization_mode": "interim_operator_batch",
    "run_id": "fixture-run",
    "operator": "fixture-operator",
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "request_envelope_digests": ["0" * 64],
    "lanes": [{
        "lane_id": "fixture-lane",
        "requestEnvelopeSha256": "0" * 64,
        "byteCount": 0,
        "modelCandidates": ["moonshotai/kimi-k3"],
        "providerRouting": {"require_parameters": True, "allow_fallbacks": True},
        "messageRoleByteCounts": [{"role": "user", "byteCount": 0}],
    }],
    "scope_note": "fixture batch asserting its own sunset",
    "program_sunset": sys.argv[2],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(document, handle, sort_keys=True)
    handle.write("\n")
PY
  FIXTURE_SUNSET_DIGEST="$(shasum -a 256 "$FIXTURE_ROOT/batch-authorization-sunset.json" | awk '{print $1}')"
  expect_rc 2 'batch program sunset does not match the wrapper release' \
    'interim batch refuses a self-asserted program sunset' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization-sunset.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$FIXTURE_SUNSET_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 'payload bytes the operator never approved'

  # POSITIVE fixture: framing parity between the wrapper and
  # `snapshot-envelope`.
  # Negative paths alone cannot tell a correct binding from a framing mismatch
  # that silently bricks every legitimate interim lane -- that fails closed,
  # but it leaves the mode dead and undetected. So build the batch through
  # payload-authorization.sh's REAL digest path over the same ordered content
  # the wrapper is about to transmit, then prove the wrapper clears the
  # membership check and reaches the network stage.
  #
  # Two entries on purpose: the system turn is index 0 and the user turn is
  # index 1. A wrapper that bound only the user turn, dropped the system turn,
  # or framed the entries in the wrong order produces a different digest and
  # fails here.
  POSITIVE_SYSTEM='fixture system turn for ordered-content binding'
  POSITIVE_PROMPT='fixture user turn for ordered-content binding'
  expect_rc 0 '' 'canonical wrapper renders the positive request envelope' \
    env OPENROUTER_API_KEY=test OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
      OPENROUTER_REQUEST_ENVELOPE_OUTPUT="$FIXTURE_ROOT/positive-request.json" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT"
  POSITIVE_DIGEST="$("$CLOCK_AUTHORIZATION" snapshot-envelope \
    --manifest "$FIXTURE_ROOT/positive-manifest.json" \
    --request-file "$FIXTURE_ROOT/positive-request.json")"
  case "$POSITIVE_DIGEST" in
    [0-9a-f][0-9a-f]*) : ;;
    *)
      echo 'positive interim fixture: snapshot did not return a digest' >&2
      exit 1
      ;;
  esac
  python3 - "$FIXTURE_ROOT/batch-authorization-positive.json" "$POSITIVE_DIGEST" \
    "$FIXED_PROGRAM_SUNSET" "$FIXTURE_ROOT/positive-manifest.json" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc).replace(microsecond=0)
manifest = json.load(open(sys.argv[4], encoding="utf-8"))
document = {
    "schema_version": 2,
    "authorization_mode": "interim_operator_batch",
    "run_id": "fixture-run",
    "operator": "fixture-operator",
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "request_envelope_digests": [sys.argv[2]],
    "lanes": [{
        "lane_id": "fixture-lane",
        "requestEnvelopeSha256": sys.argv[2],
        "byteCount": manifest["byteCount"],
        "modelCandidates": manifest["modelCandidates"],
        "providerRouting": manifest["providerRouting"],
        "messageRoleByteCounts": manifest["messageRoleByteCounts"],
    }],
    "scope_note": "fixture batch covering the exact request envelope transmitted",
    "program_sunset": sys.argv[3],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(document, handle, sort_keys=True)
    handle.write("\n")
PY
  POSITIVE_BATCH_DIGEST="$(shasum -a 256 \
    "$FIXTURE_ROOT/batch-authorization-positive.json" | awk '{print $1}')"
  # Reaching the transport is the proof: the loopback fixture base refuses the
  # connection, so curl fails with a transport error AFTER the membership check
  # has already been cleared. No live API call is made.
  expect_rc 1 'transport error' \
    'interim batch accepts the exact ordered content snapshot approved' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization-positive.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$POSITIVE_BATCH_DIGEST" \
      OPENROUTER_RECEIPT_FILE="$FIXTURE_ROOT/positive-interim.receipt.json" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT"
  if grep -Eq 'transmitted request envelope is not bound to this approved lane and model set|could not compute the transmitted request envelope digest|could not read transmitted content|non-string message content' \
      "$FIXTURE_ROOT/cmd.err"; then
    echo 'positive interim fixture: approved ordered content was refused at the membership check' >&2
    cat "$FIXTURE_ROOT/cmd.err" >&2
    exit 1
  fi
  jq -e --arg run fixture-run --arg lane fixture-lane \
    --arg request "$POSITIVE_DIGEST" '
      .authorization.runId == $run
      and .authorization.laneId == $lane
      and .authorization.requestEnvelopeSha256 == $request
      and (.invocationId | test("^[0-9a-f]{64}$"))
    ' "$FIXTURE_ROOT/positive-interim.receipt.json" >/dev/null || {
    echo 'positive interim fixture: receipt lost run, lane, or envelope identity' >&2
    exit 1
  }

  # --- BEHAVIORAL fixtures for the interim-mode security properties ---------
  # These deliberately reuse the POSITIVE payload and the POSITIVE ordered
  # content. Every case below would otherwise reach the transport stage (rc 1),
  # so deleting the broker gate, the run binding, the timestamp parsing, the
  # sunset comparison or the membership logic FLIPS a case here. Prose anchors
  # in validate-workflow-contracts.sh Group 8 pin the honesty language; these
  # pin the enforcement.

  # Emits a batch document with every field parameterised so a fixture can vary
  # exactly one property. A numeric spec is an offset in seconds from now; any
  # other spec is written through verbatim, which is how malformed timestamps
  # reach the wrapper.
  write_batch_fixture() {
    python3 - "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

path, run_id, created_spec, expires_spec, sunset, digest = sys.argv[1:7]
now = datetime.now(timezone.utc).replace(microsecond=0)


def stamp(spec):
    if spec.lstrip("+-").isdigit():
        return (now + timedelta(seconds=int(spec))).strftime("%Y-%m-%dT%H:%M:%SZ")
    return spec


document = {
    "schema_version": 2,
    "authorization_mode": "interim_operator_batch",
    "run_id": run_id,
    "operator": "fixture-operator",
    "created_at": stamp(created_spec),
    "expires_at": stamp(expires_spec),
    "request_envelope_digests": [digest],
    "lanes": [{
        "lane_id": "fixture-lane",
        "requestEnvelopeSha256": digest,
        "byteCount": 0,
        "modelCandidates": ["moonshotai/kimi-k3"],
        "providerRouting": {"require_parameters": True, "allow_fallbacks": True},
        "messageRoleByteCounts": [{"role": "user", "byteCount": 0}],
    }],
    "scope_note": "behavioral fixture batch",
    "program_sunset": sunset,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(document, handle, sort_keys=True)
    handle.write("\n")
PY
  }

  # Runs the wrapper over the POSITIVE ordered content with the given batch
  # file, expecting a fail-closed refusal carrying the named reason.
  expect_batch_refusal() {
    local label="$1" expected="$2" path="$3" wrapper="${4:-$CLOCK_WRAPPER}"
    local digest
    digest="$(shasum -a 256 "$path" | awk '{print $1}')"
    expect_rc 2 "$expected" "$label" \
      env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
        OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
        OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
        OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
        OPENROUTER_BATCH_RUN_ID=fixture-run \
        OPENROUTER_BATCH_AUTHORIZATION_FILE="$path" \
        OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$digest" \
        "$wrapper" moonshotai/kimi-k3 "$POSITIVE_PROMPT"
  }

  # Timestamp handling. A lexical `.expires_at > $now` accepts "zzzz" as a
  # distant future; epoch parsing cannot.
  write_batch_fixture "$FIXTURE_ROOT/batch-malformed-stamp.json" \
    fixture-run -60 zzzz "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a malformed expiry timestamp' \
    'not well-formed UTC timestamps' "$FIXTURE_ROOT/batch-malformed-stamp.json"

  write_batch_fixture "$FIXTURE_ROOT/batch-future-issued.json" \
    fixture-run 3600 7200 "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a future-issued authorization' \
    'issued in the future' "$FIXTURE_ROOT/batch-future-issued.json"

  write_batch_fixture "$FIXTURE_ROOT/batch-long-lifetime.json" \
    fixture-run -60 90000 "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a lifetime over 24 hours' \
    'lifetime exceeds the 24-hour maximum' "$FIXTURE_ROOT/batch-long-lifetime.json"

  write_batch_fixture "$FIXTURE_ROOT/batch-expired.json" \
    fixture-run -7200 -3600 "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses an expired authorization' \
    'batch authorization is expired' "$FIXTURE_ROOT/batch-expired.json"

  # Impossible calendar dates. A parser that only range-checks the fields
  # accepts 2025-02-29 and 2026-04-31, and days-from-civil converts both into a
  # real epoch -- so a date that never existed would become a usable
  # authorization window. Seconds are capped at 59 for the same reason: this
  # schema carries no leap second and :60 has no epoch here.
  write_batch_fixture "$FIXTURE_ROOT/batch-nonexistent-leap-day.json" \
    fixture-run -60 2025-02-29T00:00:00Z "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a non-existent leap day' \
    'not well-formed UTC timestamps' "$FIXTURE_ROOT/batch-nonexistent-leap-day.json"

  write_batch_fixture "$FIXTURE_ROOT/batch-short-month-overflow.json" \
    fixture-run -60 2026-04-31T00:00:00Z "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a day past the end of a short month' \
    'not well-formed UTC timestamps' "$FIXTURE_ROOT/batch-short-month-overflow.json"

  write_batch_fixture "$FIXTURE_ROOT/batch-sixtieth-second.json" \
    fixture-run -60 2026-08-08T00:00:60Z "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a sixtieth second' \
    'not well-formed UTC timestamps' "$FIXTURE_ROOT/batch-sixtieth-second.json"

  # ...and a GENUINE leap day must still parse. A parser that rejected valid
  # leap days would fail closed on every legitimate batch issued on 2028-02-29
  # and silently brick the mode -- a fail-closed bug is still a bug. Proof of
  # acceptance is that the wrapper gets PAST timestamp parsing and refuses for
  # the future-issued reason instead.
  write_batch_fixture "$FIXTURE_ROOT/batch-real-leap-day.json" \
    fixture-run 2028-02-29T00:00:00Z 2028-02-29T01:00:00Z \
    "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch parses a genuine leap day' \
    'issued in the future' "$FIXTURE_ROOT/batch-real-leap-day.json"

  # Run binding, enforced at the wrapper without any verify-batch step.
  write_batch_fixture "$FIXTURE_ROOT/batch-wrong-run.json" \
    some-other-run -60 3600 "$FIXED_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  expect_batch_refusal 'interim batch refuses a batch issued for another run' \
    'issued for a different run' "$FIXTURE_ROOT/batch-wrong-run.json"

  # And the run id is REQUIRED, not merely compared when supplied.
  expect_rc 2 'requires the current run id' \
    'interim batch refuses when the current run id is absent' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
      OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization-positive.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$POSITIVE_BATCH_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT"

  # Broker states. The shipped probe path is a non-overridable constant, which
  # is the correct production posture, so the fixture repoints that ONE
  # constant in a copy of the wrapper rather than adding a test hook to the
  # shipped script. The rewrite is verified, so a renamed constant fails the
  # fixture instead of silently making it vacuous.
  BROKER_STUB_DIR="$FIXTURE_ROOT/broker-stubs"
  mkdir -p "$BROKER_STUB_DIR"
  make_broker_stub() {
    printf '#!/bin/sh\n%s\n' "$2" > "$1"
    chmod 755 "$1"
  }
  wrapper_with_broker() {
    local dest="$1" broker="$2" path_override="${3:-}"
    sed -e "s|^BROKER_CLIENT=.*|BROKER_CLIENT=\"$broker\"|" "$CLOCK_WRAPPER" > "$dest"
    if [ -n "$path_override" ]; then
      sed -e "s|^export PATH=.*|export PATH=\"$path_override\"|" "$dest" > "$dest.rewritten"
      mv "$dest.rewritten" "$dest"
      grep -Fq "export PATH=\"$path_override\"" "$dest" || {
        echo 'broker fixture: could not repoint the wrapper PATH' >&2
        exit 1
      }
    fi
    chmod 755 "$dest"
    grep -Fq "BROKER_CLIENT=\"$broker\"" "$dest" || {
      echo 'broker fixture: could not repoint the broker probe path' >&2
      exit 1
    }
  }

  make_broker_stub "$BROKER_STUB_DIR/ready" \
    'printf "{\"status\": \"ready\"}\n"'
  make_broker_stub "$BROKER_STUB_DIR/degraded" \
    'printf "{\"status\": \"degraded\"}\n"'
  make_broker_stub "$BROKER_STUB_DIR/failing" \
    'echo "probe failed" >&2; exit 1'

  authorization_with_broker() {
    local dest="$1" broker="$2"
    sed -e "s|^BROKER_CLIENT=.*|BROKER_CLIENT=\"$broker\"|" \
      "$CLOCK_AUTHORIZATION" > "$dest"
    chmod 755 "$dest"
    grep -Fq "BROKER_CLIENT=\"$broker\"" "$dest" || {
      echo 'broker fixture: could not repoint the authorization helper probe path' >&2
      exit 1
    }
  }

  authorization_with_broker "$FIXTURE_ROOT/auth-broker-ready.sh" "$BROKER_STUB_DIR/ready"
  expect_rc 2 'broker available; interim mode retired on this host' \
    'typed batch validation retires interim mode when the broker is ready' \
    "$FIXTURE_ROOT/auth-broker-ready.sh" validate-batch \
      --batch-file "$FIXTURE_ROOT/batch-envelope-v2.json" --run-id fixture-run

  authorization_with_broker "$FIXTURE_ROOT/auth-broker-degraded.sh" "$BROKER_STUB_DIR/degraded"
  expect_rc 2 'broker_present_not_ready' \
    'typed batch validation withholds interim mode when the broker is degraded' \
    "$FIXTURE_ROOT/auth-broker-degraded.sh" validate-batch \
      --batch-file "$FIXTURE_ROOT/batch-envelope-v2.json" --run-id fixture-run

  wrapper_with_broker "$FIXTURE_ROOT/wrapper-broker-ready.sh" "$BROKER_STUB_DIR/ready"
  expect_batch_refusal 'a ready broker retires interim mode at the wrapper' \
    'broker available; interim mode retired on this host' \
    "$FIXTURE_ROOT/batch-authorization-positive.json" \
    "$FIXTURE_ROOT/wrapper-broker-ready.sh"

  wrapper_with_broker "$FIXTURE_ROOT/wrapper-broker-degraded.sh" "$BROKER_STUB_DIR/degraded"
  expect_batch_refusal 'a present-but-not-ready broker withholds interim mode' \
    'broker_present_not_ready' \
    "$FIXTURE_ROOT/batch-authorization-positive.json" \
    "$FIXTURE_ROOT/wrapper-broker-degraded.sh"

  wrapper_with_broker "$FIXTURE_ROOT/wrapper-broker-failing.sh" "$BROKER_STUB_DIR/failing"
  expect_batch_refusal 'a failing broker probe withholds interim mode' \
    'broker_present_not_ready' \
    "$FIXTURE_ROOT/batch-authorization-positive.json" \
    "$FIXTURE_ROOT/wrapper-broker-failing.sh"

  # The broker can appear while the wrapper is blocked ingesting a large
  # prompt. The disclosure-time check must observe that transition rather than
  # relying on the process-start sample. The fixture inserts only a marker
  # immediately before the real stdin read so timing is deterministic; broker
  # enforcement remains production code.
  for TRANSITION_STATE in ready degraded; do
    TRANSITION_BROKER="$BROKER_STUB_DIR/transition-$TRANSITION_STATE"
    TRANSITION_WRAPPER="$FIXTURE_ROOT/wrapper-broker-transition-$TRANSITION_STATE.sh"
    TRANSITION_MARKER="$FIXTURE_ROOT/broker-transition-$TRANSITION_STATE.marker"
    TRANSITION_FIFO="$FIXTURE_ROOT/broker-transition-$TRANSITION_STATE.fifo"
    wrapper_with_broker "$TRANSITION_WRAPPER" "$TRANSITION_BROKER"
    sed -e "/^PROMPT_SOURCE_FILE=/a\\
: > \"$TRANSITION_MARKER\"" "$TRANSITION_WRAPPER" > "$TRANSITION_WRAPPER.marked"
    mv "$TRANSITION_WRAPPER.marked" "$TRANSITION_WRAPPER"
    chmod 755 "$TRANSITION_WRAPPER"
    mkfifo "$TRANSITION_FIFO"
    set +e
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
      OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization-positive.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$POSITIVE_BATCH_DIGEST" \
      "$TRANSITION_WRAPPER" moonshotai/kimi-k3 - \
      <"$TRANSITION_FIFO" >"$FIXTURE_ROOT/transition-$TRANSITION_STATE.out" \
      2>"$FIXTURE_ROOT/transition-$TRANSITION_STATE.err" &
    TRANSITION_PID=$!
    set -e
    exec 9>"$TRANSITION_FIFO"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      [ -e "$TRANSITION_MARKER" ] && break
      sleep 0.1
    done
    [ -e "$TRANSITION_MARKER" ] || {
      echo "broker $TRANSITION_STATE transition never reached prompt ingestion" >&2
      kill "$TRANSITION_PID" 2>/dev/null || true
      exit 1
    }
    make_broker_stub "$TRANSITION_BROKER" \
      "printf '{\"status\": \"$TRANSITION_STATE\"}\\n'"
    printf '%s' "$POSITIVE_PROMPT" >&9
    exec 9>&-
    set +e
    wait "$TRANSITION_PID"
    TRANSITION_RC=$?
    set -e
    [ "$TRANSITION_RC" -eq 2 ] || {
      echo "broker $TRANSITION_STATE transition was not refused before transport" >&2
      cat "$FIXTURE_ROOT/transition-$TRANSITION_STATE.err" >&2
      exit 1
    }
    case "$TRANSITION_STATE" in
      ready) TRANSITION_REASON='broker available; interim mode retired on this host' ;;
      degraded) TRANSITION_REASON='broker_present_not_ready' ;;
    esac
    grep -Fq "$TRANSITION_REASON" "$FIXTURE_ROOT/transition-$TRANSITION_STATE.err" || {
      echo "broker $TRANSITION_STATE transition missed its stable refusal" >&2
      exit 1
    }
  done

  # Interrupting the wrapper must own the live provider child, not merely its
  # temporary files. A sleeping fake curl makes natural child exit impossible.
  SIGNAL_BIN="$FIXTURE_ROOT/signal-bin"
  mkdir -p "$SIGNAL_BIN"
  for tool in sh cat tr sed awk wc date mktemp chmod rm shasum sleep kill jq dirname pwd mv; do
    tool_path="$(command -v "$tool" 2>/dev/null || true)"
    [ -n "$tool_path" ] && ln -sf "$tool_path" "$SIGNAL_BIN/$tool"
  done
  cat > "$SIGNAL_BIN/curl" <<'EOF'
#!/bin/sh
printf '%s\n' "$$" > "$FAKE_CURL_PID_FILE"
sleep 30
EOF
  chmod 755 "$SIGNAL_BIN/curl"
  SIGNAL_WRAPPER="$FIXTURE_ROOT/wrapper-signal-child.sh"
  sed -e "s|^export PATH=.*|export PATH=\"$SIGNAL_BIN\"|" \
    "$CLOCK_WRAPPER" > "$SIGNAL_WRAPPER"
  chmod 755 "$SIGNAL_WRAPPER"
  SIGNAL_CHILD_PID_FILE="$FIXTURE_ROOT/signal-child.pid"
  SIGNAL_RECEIPT="$FIXTURE_ROOT/signal-child.receipt.json"
  set +e
  env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
    OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
    OPENROUTER_RECEIPT_FILE="$SIGNAL_RECEIPT" \
    FAKE_CURL_PID_FILE="$SIGNAL_CHILD_PID_FILE" \
    "$SIGNAL_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT" \
    >"$FIXTURE_ROOT/signal-child.out" 2>"$FIXTURE_ROOT/signal-child.err" &
  SIGNAL_WRAPPER_PID=$!
  set -e
  for _ in 1 2 3 4 5 6 7 8 9 10 \
      11 12 13 14 15 16 17 18 19 20 \
      21 22 23 24 25 26 27 28 29 30 \
      31 32 33 34 35 36 37 38 39 40 \
      41 42 43 44 45 46 47 48 49 50; do
    [ -s "$SIGNAL_CHILD_PID_FILE" ] && break
    sleep 0.1
  done
  [ -s "$SIGNAL_CHILD_PID_FILE" ] || {
    echo 'signal fixture never started its transport child' >&2
    kill "$SIGNAL_WRAPPER_PID" 2>/dev/null || true
    exit 1
  }
  SIGNAL_CHILD_PID="$(cat "$SIGNAL_CHILD_PID_FILE")"
  kill -TERM "$SIGNAL_WRAPPER_PID"
  set +e
  wait "$SIGNAL_WRAPPER_PID"
  SIGNAL_WRAPPER_RC=$?
  set -e
  [ "$SIGNAL_WRAPPER_RC" -ne 0 ] || {
    echo 'interrupted wrapper returned success' >&2
    exit 1
  }
  SIGNAL_CHILD_GONE=0
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$SIGNAL_CHILD_PID" 2>/dev/null; then
      SIGNAL_CHILD_GONE=1
      break
    fi
    sleep 0.1
  done
  if [ "$SIGNAL_CHILD_GONE" -ne 1 ]; then
    kill -KILL "$SIGNAL_CHILD_PID" 2>/dev/null || true
    echo 'interrupted wrapper left its transport child running' >&2
    exit 1
  fi
  jq -e '.outcome == "error" and .failureKind == "interrupted"
    and (.invocationId | test("^[0-9a-f]{64}$"))' \
    "$SIGNAL_RECEIPT" >/dev/null || {
    echo 'interrupted wrapper did not emit one terminal failure receipt' >&2
    exit 1
  }

  # Move the signal into the exact launch-to-PID-publication window in a copy
  # of the shipped wrapper. The handler defers cleanup until curl_pid is owned;
  # deleting that handoff strands the sleeping child.
  SIGNAL_WINDOW_WRAPPER="$FIXTURE_ROOT/wrapper-signal-window.sh"
  sed -e "s|^export PATH=.*|export PATH=\"$SIGNAL_BIN\"|" \
    -e 's/^curl_pid=\$!$/kill -TERM \$\$\ncurl_pid=\$!/' \
    "$CLOCK_WRAPPER" > "$SIGNAL_WINDOW_WRAPPER"
  chmod 755 "$SIGNAL_WINDOW_WRAPPER"
  grep -Fq 'kill -TERM $$' "$SIGNAL_WINDOW_WRAPPER" || {
    echo 'signal-window fixture could not inject before PID publication' >&2
    exit 1
  }
  SIGNAL_WINDOW_PID_FILE="$FIXTURE_ROOT/signal-window-child.pid"
  SIGNAL_WINDOW_RECEIPT="$FIXTURE_ROOT/signal-window.receipt.json"
  SIGNAL_WINDOW_STARTED="$(date +%s)"
  set +e
  env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
    OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
    OPENROUTER_RECEIPT_FILE="$SIGNAL_WINDOW_RECEIPT" \
    FAKE_CURL_PID_FILE="$SIGNAL_WINDOW_PID_FILE" \
    "$SIGNAL_WINDOW_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT" \
    >"$FIXTURE_ROOT/signal-window.out" 2>"$FIXTURE_ROOT/signal-window.err"
  SIGNAL_WINDOW_RC=$?
  set -e
  SIGNAL_WINDOW_ELAPSED=$(( $(date +%s) - SIGNAL_WINDOW_STARTED ))
  [ "$SIGNAL_WINDOW_RC" -ne 0 ] && [ "$SIGNAL_WINDOW_ELAPSED" -lt 8 ] || {
    echo 'launch-window signal fixture did not interrupt the wrapper promptly' >&2
    exit 1
  }
  jq -e '.outcome == "error" and .failureKind == "interrupted"
    and (.invocationId | test("^[0-9a-f]{64}$"))' \
    "$SIGNAL_WINDOW_RECEIPT" >/dev/null || {
    echo 'launch-window signal did not emit the interrupted receipt' >&2
    exit 1
  }
  # The repaired wrapper may terminate the child before the fake curl gets
  # scheduled to publish its PID. A broken handoff leaves it alive long enough
  # to publish, so briefly wait for that observable before checking liveness.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -s "$SIGNAL_WINDOW_PID_FILE" ] && break
    sleep 0.1
  done
  if [ -s "$SIGNAL_WINDOW_PID_FILE" ]; then
    SIGNAL_WINDOW_CHILD="$(cat "$SIGNAL_WINDOW_PID_FILE")"
    if kill -0 "$SIGNAL_WINDOW_CHILD" 2>/dev/null; then
      kill -KILL "$SIGNAL_WINDOW_CHILD" 2>/dev/null || true
      echo 'launch-window signal left its unowned transport child running' >&2
      exit 1
    fi
  fi

  # Timeout cleanup must remain bounded even when the transport ignores TERM.
  cat > "$SIGNAL_BIN/curl" <<'EOF'
#!/bin/sh
printf '%s\n' "$$" > "$FAKE_CURL_PID_FILE"
trap '' TERM
sleep 5
EOF
  chmod 755 "$SIGNAL_BIN/curl"
  TIMEOUT_CHILD_PID_FILE="$FIXTURE_ROOT/timeout-child.pid"
  TIMEOUT_STARTED="$(date +%s)"
  set +e
  env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
    OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
    OPENROUTER_FIRST_BYTE_TIMEOUT=1 \
    FAKE_CURL_PID_FILE="$TIMEOUT_CHILD_PID_FILE" \
    "$SIGNAL_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT" 10 \
    >"$FIXTURE_ROOT/timeout-child.out" 2>"$FIXTURE_ROOT/timeout-child.err"
  TIMEOUT_RC=$?
  set -e
  TIMEOUT_ELAPSED=$(( $(date +%s) - TIMEOUT_STARTED ))
  [ "$TIMEOUT_RC" -eq 28 ] && [ "$TIMEOUT_ELAPSED" -lt 5 ] || {
    echo 'TERM-resistant timeout cleanup was not bounded' >&2
    exit 1
  }
  TIMEOUT_CHILD_PID="$(cat "$TIMEOUT_CHILD_PID_FILE")"
  ! kill -0 "$TIMEOUT_CHILD_PID" 2>/dev/null || {
    kill -KILL "$TIMEOUT_CHILD_PID" 2>/dev/null || true
    echo 'timeout cleanup left its TERM-resistant child running' >&2
    exit 1
  }

  # Missing jq must NOT make an installed broker look absent. Readiness is a jq
  # decision; if an absent jq collapsed to "absent broker" the interim mode
  # would run above a ready broker. Build a PATH that has everything the
  # wrapper touches before the broker gate and nothing named jq.
  NOJQ_BIN="$FIXTURE_ROOT/nojq-bin"
  rm -rf "$NOJQ_BIN"
  mkdir -p "$NOJQ_BIN"
  for tool in sh cat tr sed awk wc date mktemp chmod rm shasum sleep kill curl; do
    tool_path="$(command -v "$tool" 2>/dev/null || true)"
    [ -n "$tool_path" ] && ln -sf "$tool_path" "$NOJQ_BIN/$tool"
  done
  if env PATH="$NOJQ_BIN" sh -c 'command -v jq' >/dev/null 2>&1; then
    echo 'missing-jq fixture: jq is still reachable, the fixture would pass vacuously' >&2
    exit 1
  fi
  wrapper_with_broker "$FIXTURE_ROOT/wrapper-broker-nojq.sh" \
    "$BROKER_STUB_DIR/ready" "$NOJQ_BIN"
  expect_batch_refusal 'a missing jq withholds interim mode above an installed broker' \
    'broker_present_not_ready' \
    "$FIXTURE_ROOT/batch-authorization-positive.json" \
    "$FIXTURE_ROOT/wrapper-broker-nojq.sh"

  # The ONE genuinely date-dependent assertion: what the SHIPPED sunset
  # constant does today, run against the SHIPPED wrapper. Both branches assert
  # -- there is no silent skip, and there is no calendar date on which this
  # harness stops checking something.
  write_batch_fixture "$FIXTURE_ROOT/batch-shipped-sunset.json" \
    fixture-run -60 3600 "$REAL_PROGRAM_SUNSET" "$POSITIVE_DIGEST"
  SHIPPED_BATCH_DIGEST="$(shasum -a 256 \
    "$FIXTURE_ROOT/batch-shipped-sunset.json" | awk '{print $1}')"
  if [ "$(date -u +%Y-%m-%d)" \< "$REAL_PROGRAM_SUNSET" ]; then
    expect_rc 1 'transport error' \
      'shipped sunset constant still admits the interim mode today' \
      env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
        OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
        OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
        OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
        OPENROUTER_BATCH_RUN_ID=fixture-run \
        OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-shipped-sunset.json" \
        OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$SHIPPED_BATCH_DIGEST" \
        "$WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT"
  else
    printf '  NOTE  the interim operator-batch program sunset (%s) has passed.\n' \
      "$REAL_PROGRAM_SUNSET" >&2
    printf '        Remove the interim mode, or consciously re-issue the sunset in a\n' >&2
    printf '        reviewed commit. The fixtures above keep running either way.\n' >&2
    expect_rc 2 'past program sunset' \
      'shipped sunset constant has passed and the interim mode is dead' \
      env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
        OPENROUTER_SYSTEM="$POSITIVE_SYSTEM" \
        OPENROUTER_TARGET_AGENT_NAME=fixture-lane \
        OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
        OPENROUTER_BATCH_RUN_ID=fixture-run \
        OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-shipped-sunset.json" \
        OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$SHIPPED_BATCH_DIGEST" \
        "$WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT"
  fi
fi

# Broker-state case statements must both carry a fail-closed catch-all. An
# empty or unexpected state is not an absent broker.
grep -Fq 'broker state unresolved; interim mode withheld' "$WRAPPER"
grep -Fq 'broker state unresolved; interim mode withheld' "$AUTHORIZATION"

printf '  OK    OpenRouter threat/content and output-boundary fixtures pass\n'
