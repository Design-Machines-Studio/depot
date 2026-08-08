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

# Pin the usage probe. cascade-dispatch.sh skips any rail whose probe reports
# state "low" or "limited", so an unpinned probe couples this offline policy
# gate to the live OpenRouter account balance: once real credit runs low the
# terminal-outcome cases below fall through to the native rung and exit 64
# instead of 75, failing validate-composition.sh on every machine regardless of
# the code. validate-openrouter-cascade.sh pins --probe-file for the same
# reason; PROBE_CMD covers every cascade invocation here without editing each.
cat > "$AUTH_ROOT/usage-probe.sh" <<'PROBE_EOF'
#!/bin/sh
printf '%s\n' '{"codex":{"state":"ok","remaining_pct":100},"claude":{"state":"ok","remaining_pct":100},"openrouter":{"state":"ok","remaining_pct":100}}'
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
grep -Fq 'independent Codex security' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
grep -Fq 'mcp-control-plane.md' "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
grep -Fq 'OPENROUTER_RECEIPT_FILE' "$WRAPPER"
grep -Fq 'payload-authorization.sh' "$RUNNER"
grep -Fq 'AUTHORIZATION_MODE="${OPENROUTER_PAYLOAD_AUTHORIZATION:-exact-digest}"' "$RUNNER"
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
# Proves the WRAPPER refuses bytes that are not in payload_digests, at the point
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
grep -Fq "INTERIM_PROGRAM_SUNSET=\"$REAL_PROGRAM_SUNSET\"" "$WRAPPER" || {
  echo 'fixed-sunset fixture: shipped wrapper no longer pins the expected sunset constant' >&2
  exit 1
}
sed -e "s|^INTERIM_PROGRAM_SUNSET=.*|INTERIM_PROGRAM_SUNSET=\"$FIXED_PROGRAM_SUNSET\"|" \
  "$WRAPPER" > "$CLOCK_WRAPPER"
chmod 755 "$CLOCK_WRAPPER"
grep -Fq "INTERIM_PROGRAM_SUNSET=\"$FIXED_PROGRAM_SUNSET\"" "$CLOCK_WRAPPER" || {
  echo 'fixed-sunset fixture: could not repoint the wrapper sunset constant' >&2
  exit 1
}
if true; then
  python3 - "$FIXTURE_ROOT/batch-authorization.json" "$FIXED_PROGRAM_SUNSET" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc).replace(microsecond=0)
document = {
    "schema_version": 1,
    "authorization_mode": "interim_operator_batch",
    "run_id": "fixture-run",
    "operator": "fixture-operator",
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "payload_digests": ["0" * 64],
    "scope_note": "fixture batch covering no real payload",
    "program_sunset": sys.argv[2],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(document, handle, sort_keys=True)
    handle.write("\n")
PY
  FIXTURE_BATCH_DIGEST="$(shasum -a 256 "$FIXTURE_ROOT/batch-authorization.json" | awk '{print $1}')"
  expect_rc 2 'transmitted payload digest is not in the batch authorization' \
    'interim batch refuses unapproved transmitted bytes' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
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
    "schema_version": 1,
    "authorization_mode": "interim_operator_batch",
    "run_id": "fixture-run",
    "operator": "fixture-operator",
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "payload_digests": ["0" * 64],
    "scope_note": "fixture batch asserting its own sunset",
    "program_sunset": sys.argv[2],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(document, handle, sort_keys=True)
    handle.write("\n")
PY
  FIXTURE_SUNSET_DIGEST="$(shasum -a 256 "$FIXTURE_ROOT/batch-authorization-sunset.json" | awk '{print $1}')"
  expect_rc 2 'sunset-mismatched' \
    'interim batch refuses a self-asserted program sunset' \
    env OPENROUTER_API_KEY=test OPENROUTER_BASE=http://127.0.0.1:9/v1 \
      OPENROUTER_AUTHORIZATION_MODE=interim-operator-batch \
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization-sunset.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$FIXTURE_SUNSET_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 'payload bytes the operator never approved'

  # POSITIVE fixture: framing parity between the wrapper and `snapshot`.
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
  printf '%s' "$POSITIVE_SYSTEM" > "$FIXTURE_ROOT/positive.system"
  printf '%s' "$POSITIVE_PROMPT" > "$FIXTURE_ROOT/positive.user"
  POSITIVE_DIGEST="$("$AUTHORIZATION" snapshot \
    --manifest "$FIXTURE_ROOT/positive-manifest.json" \
    --content-file "$FIXTURE_ROOT/positive.system" \
    --content-file "$FIXTURE_ROOT/positive.user")"
  case "$POSITIVE_DIGEST" in
    [0-9a-f][0-9a-f]*) : ;;
    *)
      echo 'positive interim fixture: snapshot did not return a digest' >&2
      exit 1
      ;;
  esac
  python3 - "$FIXTURE_ROOT/batch-authorization-positive.json" "$POSITIVE_DIGEST" \
    "$FIXED_PROGRAM_SUNSET" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc).replace(microsecond=0)
document = {
    "schema_version": 1,
    "authorization_mode": "interim_operator_batch",
    "run_id": "fixture-run",
    "operator": "fixture-operator",
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "payload_digests": [sys.argv[2]],
    "scope_note": "fixture batch covering the exact ordered content transmitted",
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
      OPENROUTER_BATCH_RUN_ID=fixture-run \
      OPENROUTER_BATCH_AUTHORIZATION_FILE="$FIXTURE_ROOT/batch-authorization-positive.json" \
      OPENROUTER_BATCH_AUTHORIZATION_DIGEST="$POSITIVE_BATCH_DIGEST" \
      "$CLOCK_WRAPPER" moonshotai/kimi-k3 "$POSITIVE_PROMPT"
  if grep -Eq 'transmitted payload digest is not in the batch authorization|could not compute the transmitted payload digest|could not read transmitted content|non-string message content' \
      "$FIXTURE_ROOT/cmd.err"; then
    echo 'positive interim fixture: approved ordered content was refused at the membership check' >&2
    cat "$FIXTURE_ROOT/cmd.err" >&2
    exit 1
  fi

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
    "schema_version": 1,
    "authorization_mode": "interim_operator_batch",
    "run_id": run_id,
    "operator": "fixture-operator",
    "created_at": stamp(created_spec),
    "expires_at": stamp(expires_spec),
    "payload_digests": [digest],
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
