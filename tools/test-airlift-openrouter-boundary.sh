#!/usr/bin/env bash
# Exercise the canonical Airlift two-artifact pre-wrapper boundary offline.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$ROOT/plugins/airlift/commands/airlift-in.md"
FIXTURE="$(mktemp -d "${TMPDIR:-/tmp}/airlift-openrouter.XXXXXX")"
trap 'rm -rf "$FIXTURE"' EXIT

HOME_FIXTURE="$FIXTURE/home"
PLUGIN_ROOT="$HOME_FIXTURE/.codex/plugins/cache/depot/openrouter/1.7.0"
REFS="$PLUGIN_ROOT/skills/openrouter-delegate/references"
mkdir -p "$REFS" "$FIXTURE/bundle"
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json" "$REFS/"
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh" \
  "$REFS/delegation-boundary.real.sh"
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/payload-authorization.sh" \
  "$REFS/payload-authorization.sh"
cat > "$REFS/delegation-boundary.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/delegation-boundary.real.sh" "$@"
if [ "${MUTATE_AFTER_SCAN:-0}" = "1" ]; then
  printf 'OPENROUTER_API_KEY=sk-or-v1-mutated-after-scan-1234567890\n' \
    > "$BUNDLE_DIR/RESUME_PROMPT.md"
  printf '%s\n' \
    '-----BEGIN PRIVATE KEY-----' \
    'QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo0123456789abcd' \
    '-----END PRIVATE KEY-----' > "$BUNDLE_DIR/HANDOFF.md"
fi
EOF
chmod +x "$REFS/delegation-boundary.sh" "$REFS/delegation-boundary.real.sh" \
  "$REFS/payload-authorization.sh"

cat > "$REFS/openrouter-wrapper.sh" <<'EOF'
#!/usr/bin/env bash
touch "$AIRLIFT_WRAPPER_SENTINEL"
printf '%s' "$OPENROUTER_SYSTEM" > "$AIRLIFT_WRAPPER_CAPTURE.resume"
cat > "$AIRLIFT_WRAPPER_CAPTURE.handoff"
printf 'controlled safe delegation\n'
EOF
chmod +x "$REFS/openrouter-wrapper.sh"

cat > "$FIXTURE/kernel" <<'EOF'
#!/usr/bin/env bash
[ "${FAKE_KERNEL_FAIL:-0}" = "0" ] || exit 4
case "${1:-}" in
  kernel-info)
    exec "$REAL_WORKFLOW_KERNEL" "$@"
    ;;
  resolve-plugin-bundle)
    printf '{"selected_root":"~/.codex/plugins/cache/depot/openrouter/1.7.0","cache_class":"codex","version":"1.7.0","reason":"highest_compatible_semver"}\n'
    ;;
  snapshot-files)
    exec "$REAL_WORKFLOW_KERNEL" "$@"
    ;;
  *)
    exit 4
    ;;
esac
EOF
chmod +x "$FIXTURE/kernel"

{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  sed -n '/^: "${WORKFLOW_KERNEL/,/^```/p' "$SOURCE" | sed '$d'
  printf '%s\n' \
    'if [ "${AUTO_APPROVE:-1}" != "1" ]; then' \
    '  printf '\''{"status":"approval_required","payloadSha256":"%s"}\n'\'' "$PAYLOAD_SHA256"' \
    '  exit 78' \
    'fi' \
    'approved_payload_sha256="$PAYLOAD_SHA256"' \
    'if [ "${MUTATE_APPROVED_PAYLOAD:-0}" = "1" ]; then' \
    '  printf '\''changed\n'\'' >> "$HANDOFF_SNAPSHOT"' \
    'fi'
  sed -n '/^"\$AUTHORIZATION" verify/,/^```/p' "$SOURCE" | sed '$d'
} > "$FIXTURE/resume"
chmod +x "$FIXTURE/resume"

printf 'Continue the listed work safely.\n' > "$FIXTURE/bundle/RESUME_PROMPT.md"
printf 'Objective: validate the handoff.\n' > "$FIXTURE/bundle/HANDOFF.md"

run_expect() {
  expected="$1" label="$2"
  shift 2
  set +e
  output="$(HOME="$HOME_FIXTURE" WORKFLOW_KERNEL="$FIXTURE/kernel" \
    REAL_WORKFLOW_KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh" \
    BUNDLE_DIR="$FIXTURE/bundle" AIRLIFT_WRAPPER_SENTINEL="$FIXTURE/sentinel" \
    AIRLIFT_WRAPPER_CAPTURE="$FIXTURE/captured" AUTO_APPROVE="${AUTO_APPROVE:-1}" \
    "$@" "$FIXTURE/resume" 2>&1)"
  rc=$?
  set -e
  [ "$rc" -eq "$expected" ] || {
    echo "  FAIL  $label (rc=$rc output=$output)" >&2
    exit 1
  }
  printf '  OK    %s\n' "$label"
}

rm -f "$FIXTURE/sentinel"
AUTO_APPROVE=0 run_expect 78 "safe payload pauses for exact user approval" env
[ ! -e "$FIXTURE/sentinel" ]

rm -f "$FIXTURE/sentinel"
run_expect 0 "safe two-file delegation reaches controlled wrapper" env
[ -e "$FIXTURE/sentinel" ]

rm -f "$FIXTURE/sentinel"
run_expect 2 "approved payload mutation is rejected before wrapper" \
  env MUTATE_APPROVED_PAYLOAD=1
[ ! -e "$FIXTURE/sentinel" ]

printf 'Continue the listed work safely.\n' > "$FIXTURE/bundle/RESUME_PROMPT.md"
printf 'Objective: validate the handoff.\n' > "$FIXTURE/bundle/HANDOFF.md"
rm -f "$FIXTURE/sentinel" "$FIXTURE"/captured.*
run_expect 0 "post-scan source mutation cannot change delegated snapshots" \
  env MUTATE_AFTER_SCAN=1
[ -e "$FIXTURE/sentinel" ]
grep -Fxq 'Continue the listed work safely.' "$FIXTURE/captured.resume"
grep -Fxq 'Objective: validate the handoff.' "$FIXTURE/captured.handoff"
if grep -Eq 'sk-or-v1|PRIVATE KEY' "$FIXTURE"/captured.*; then
  echo "  FAIL  mutable originals reached wrapper after snapshot validation" >&2
  exit 1
fi

printf 'private text outside the handoff\n' > "$FIXTURE/private.txt"
rm -f "$FIXTURE/bundle/HANDOFF.md"
ln -s "$FIXTURE/private.txt" "$FIXTURE/bundle/HANDOFF.md"
rm -f "$FIXTURE/sentinel"
run_expect 2 "symlink handoff is rejected before disclosure screening" env
[ ! -e "$FIXTURE/sentinel" ]
rm -f "$FIXTURE/bundle/HANDOFF.md"

printf 'OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890\n' > "$FIXTURE/bundle/RESUME_PROMPT.md"
printf 'Objective: validate the handoff.\n' > "$FIXTURE/bundle/HANDOFF.md"
rm -f "$FIXTURE/sentinel"
run_expect 3 "resume prompt disclosure declines distinctly" env
[ ! -e "$FIXTURE/sentinel" ]

printf 'Continue safely.\n' > "$FIXTURE/bundle/RESUME_PROMPT.md"
printf '%s\n' \
  '-----BEGIN PRIVATE KEY-----' \
  'QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo0123456789abcd' \
  '-----END PRIVATE KEY-----' > "$FIXTURE/bundle/HANDOFF.md"
rm -f "$FIXTURE/sentinel"
run_expect 3 "handoff disclosure declines distinctly" env
[ ! -e "$FIXTURE/sentinel" ]

printf 'Objective: safe.\n' > "$FIXTURE/bundle/HANDOFF.md"
cp "$REFS/delegation-boundary.sh" "$FIXTURE/boundary-good"
printf '%s\n' '#!/usr/bin/env bash' 'exit 2' > "$REFS/delegation-boundary.sh"
chmod +x "$REFS/delegation-boundary.sh"
rm -f "$FIXTURE/sentinel"
run_expect 2 "malformed boundary is distinct from disclosure decline" env
[ ! -e "$FIXTURE/sentinel" ]
cp "$FIXTURE/boundary-good" "$REFS/delegation-boundary.sh"
chmod +x "$REFS/delegation-boundary.sh"

rm -f "$FIXTURE/sentinel"
run_expect 1 "missing coherent bundle is distinct" env FAKE_KERNEL_FAIL=1
[ ! -e "$FIXTURE/sentinel" ]

echo "  OK    Airlift OpenRouter boundary fixtures pass"
