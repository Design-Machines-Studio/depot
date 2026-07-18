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
