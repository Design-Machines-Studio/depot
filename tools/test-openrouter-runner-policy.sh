#!/usr/bin/env bash
# Behavioral fixtures for the OpenRouter runner's path and content boundary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
POLICY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
RUNNER="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
EXEC_RUNNER="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
BOUNDARY="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh"

FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

printf '%s\n' 'plugins/openrouter/README.md' > "$FIXTURE_ROOT/safe-files"
printf '%s\n' 'plugins/openrouter/README.md' '.env.local' > "$FIXTURE_ROOT/denied-files"
printf '%s\n' 'plugins/openrouter/README.md' 'internal/auth/session.go' > "$FIXTURE_ROOT/mixed-files"
printf '%s\n' 'plugins/openrouter/file with spaces.md' > "$FIXTURE_ROOT/quoted-files"

cat > "$FIXTURE_ROOT/safe.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/quoted.diff" <<'EOF'
diff --git "a/plugins/openrouter/file with spaces.md" "b/plugins/openrouter/file with spaces.md"
--- "a/plugins/openrouter/file with spaces.md"
+++ "b/plugins/openrouter/file with spaces.md"
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/removed-secret.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-token=sk-or-v1-abcdefghijklmnop
+token=${OPENROUTER_API_KEY}
EOF
cat > "$FIXTURE_ROOT/outside.diff" <<'EOF'
diff --git a/docs/outside.md b/docs/outside.md
--- a/docs/outside.md
+++ b/docs/outside.md
@@ -1 +1 @@
-old
+new
EOF
cat > "$FIXTURE_ROOT/mixed.diff" <<'EOF'
diff --git a/plugins/openrouter/README.md b/plugins/openrouter/README.md
--- a/plugins/openrouter/README.md
+++ b/plugins/openrouter/README.md
@@ -1 +1 @@
-old routing note
+new routing note
diff --git a/internal/auth/session.go b/internal/auth/session.go
--- a/internal/auth/session.go
+++ b/internal/auth/session.go
@@ -1 +1 @@
-old auth code
+token=sk-or-v1-sensitive-auth-section-1234567890
EOF
cat > "$FIXTURE_ROOT/sensitive-only.diff" <<'EOF'
diff --git a/internal/auth/session.go b/internal/auth/session.go
--- a/internal/auth/session.go
+++ b/internal/auth/session.go
@@ -1 +1 @@
-old auth code
+new auth code
EOF
cat > "$FIXTURE_ROOT/artifact-paths.md" <<'EOF'
Review the plan for changes to internal/auth/session.go and deploy/app.service.
These are path references, not file contents or credentials.
EOF
cat > "$FIXTURE_ROOT/artifact-secret.md" <<'EOF'
The captured provider key was sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789.
EOF
printf '%s\n' '+new without a diff header' > "$FIXTURE_ROOT/headerless.diff"

"$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" \
  --diff-file "$FIXTURE_ROOT/safe.diff" --output-paths "$FIXTURE_ROOT/safe.paths"
python3 - "$FIXTURE_ROOT/safe.paths" <<'PY'
import sys
assert open(sys.argv[1], "rb").read() == b"plugins/openrouter/README.md\0"
PY
"$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/quoted-files" --diff-file "$FIXTURE_ROOT/quoted.diff"

if "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/denied-files" --diff-file "$FIXTURE_ROOT/safe.diff"; then
  echo "denied changed-file fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi
if "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/removed-secret.diff"; then
  echo "removed-secret fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi
if "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/headerless.diff"; then
  echo "headerless diff fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 2 ]
fi
if "$BOUNDARY" --policy "$POLICY" --changed-files "$FIXTURE_ROOT/safe-files" --diff-file "$FIXTURE_ROOT/outside.diff"; then
  echo "out-of-allowlist patch fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi

# Execution remains fail-closed when any owned path is sensitive.
if "$BOUNDARY" --mode execution --policy "$POLICY" --changed-files "$FIXTURE_ROOT/mixed-files" --diff-file "$FIXTURE_ROOT/mixed.diff"; then
  echo "mixed execution fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi

# Mechanical review filters sensitive file sections and delegates the safe remainder.
"$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/mixed-files" \
  --diff-file "$FIXTURE_ROOT/mixed.diff" \
  --output-paths "$FIXTURE_ROOT/mixed.paths" \
  --output-diff "$FIXTURE_ROOT/mixed.filtered.diff"
grep -Fq 'plugins/openrouter/README.md' "$FIXTURE_ROOT/mixed.filtered.diff"
if grep -Fq 'internal/auth/session.go' "$FIXTURE_ROOT/mixed.filtered.diff"; then
  echo "mechanical-review output retained a sensitive path" >&2
  exit 1
fi
python3 - "$FIXTURE_ROOT/mixed.paths" <<'PY'
import sys
assert open(sys.argv[1], "rb").read() == b"plugins/openrouter/README.md\0"
PY

if "$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" \
  --diff-file "$FIXTURE_ROOT/removed-secret.diff"; then
  echo "credential-bearing safe mechanical-review fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi

if "$BOUNDARY" --mode mechanical-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/mixed-files" \
  --diff-file "$FIXTURE_ROOT/sensitive-only.diff"; then
  echo "sensitive-only mechanical-review fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi

# Plans and prompt packs may name sensitive paths, but may not carry credentials.
"$BOUNDARY" --mode artifact-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" \
  --content-file "$FIXTURE_ROOT/artifact-paths.md"
if "$BOUNDARY" --mode artifact-review --policy "$POLICY" \
  --changed-files "$FIXTURE_ROOT/safe-files" \
  --content-file "$FIXTURE_ROOT/artifact-secret.md"; then
  echo "credential-bearing artifact fixture was accepted" >&2
  exit 1
else
  [ "$?" -eq 3 ]
fi

cat > "$FIXTURE_ROOT/exec-77.sh" <<'EOF'
#!/usr/bin/env bash
exit 77
EOF
cat > "$FIXTURE_ROOT/wrapper-sentinel.sh" <<'EOF'
#!/usr/bin/env bash
touch "$WRAPPER_SENTINEL"
exit 99
EOF
chmod +x "$FIXTURE_ROOT/exec-77.sh" "$FIXTURE_ROOT/wrapper-sentinel.sh"
CASCADE="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
CASCADE_OUT="$(printf '%s' test | env \
  OPENROUTER_EXEC_ALLOWED_PATHS=plugins/openrouter/README.md \
  OPENROUTER_EXEC_CMD="$FIXTURE_ROOT/exec-77.sh" \
  WRAPPER_CMD="$FIXTURE_ROOT/wrapper-sentinel.sh" \
  WRAPPER_SENTINEL="$FIXTURE_ROOT/wrapper-called" \
  "$CASCADE" --class openrouter --prompt - --host codex 2>/dev/null || true)"
printf '%s' "$CASCADE_OUT" | jq -e '.dispatch == "native" and .role == "premium_sub"' >/dev/null
[ ! -e "$FIXTURE_ROOT/wrapper-called" ]

grep -Fq 'os.path.realpath(sys.argv[1])' "$RUNNER"
grep -Fq 'set(canon) | set(configured)' "$RUNNER"
grep -Fq 'delegation-boundary.sh' "$RUNNER"
grep -Fq 'RUNNER DECLINED -- SENSITIVE CONTENT' "$RUNNER"
grep -Fq 'Route this chunk to the Codex-native reviewer instead' "$RUNNER"
grep -Fq 'OPENROUTER_EXEC_ALLOWED_PATHS is required' "$EXEC_RUNNER"
grep -Fq 'delegation-boundary.sh' "$EXEC_RUNNER"
grep -Fq -- '--output-paths' "$EXEC_RUNNER"
grep -Fq -- '--pathspec-file-nul' "$EXEC_RUNNER"

printf '  OK    OpenRouter runner boundary fixtures pass\n'
