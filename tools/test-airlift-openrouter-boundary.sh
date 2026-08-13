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
PLUGIN_ROOT="$HOME_FIXTURE/.codex/plugins/cache/depot/openrouter/1.14.0"
REFS="$PLUGIN_ROOT/skills/openrouter-delegate/references"
mkdir -p "$REFS" "$FIXTURE/bundle"
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json" "$REFS/"
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-credential.sh" "$REFS/"
cp "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-boundary.sh" \
  "$REFS/delegation-boundary.real.sh"
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
chmod +x "$REFS/delegation-boundary.sh" "$REFS/delegation-boundary.real.sh"

cat > "$REFS/openrouter-wrapper.sh" <<'EOF'
#!/usr/bin/env bash
touch "$AIRLIFT_WRAPPER_SENTINEL"
[ -n "${OPENROUTER_SYSTEM_FILE:-}" ] && [ -z "${OPENROUTER_SYSTEM:-}" ]
[ "$1" = "deepseek/deepseek-v4-flash-0731" ]
[ "$4" = "x-ai/grok-4.5" ]
cp "$OPENROUTER_SYSTEM_FILE" "$AIRLIFT_WRAPPER_CAPTURE.resume"
cat > "$AIRLIFT_WRAPPER_CAPTURE.handoff"
jq -n --arg run "$OPENROUTER_RUN_ID" --arg lane "$OPENROUTER_LANE_ID" '
  {schemaVersion:2,outcome:"success",authorization:{runId:$run,laneId:$lane,
   requestEnvelopeSha256:"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}
' > "$OPENROUTER_RECEIPT_FILE"
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
    printf '{"selected_root":"~/.codex/plugins/cache/depot/openrouter/1.14.0","cache_class":"codex","version":"1.14.0","reason":"highest_compatible_semver"}\n'
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
  # The documented block must fail closed without ambient errexit behavior.
  printf '%s\n' '#!/usr/bin/env bash' 'set -uo pipefail'
  sed -n '/^: "${WORKFLOW_KERNEL/,/^```/p' "$SOURCE" | sed '$d'
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
    AIRLIFT_WRAPPER_CAPTURE="$FIXTURE/captured" \
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
run_expect 0 "safe two-file delegation reaches wrapper without approval" env
[ -e "$FIXTURE/sentinel" ]
jq -e '.authorization.runId == "airlift-resume" and
  .authorization.laneId == "resume-via-deepseek"' \
  "$FIXTURE/bundle/OPENROUTER_RECEIPT.json" >/dev/null

printf 'Continue the listed work safely.\n' > "$FIXTURE/bundle/RESUME_PROMPT.md"
printf 'Objective: validate the handoff.\n' > "$FIXTURE/bundle/HANDOFF.md"
rm -f "$FIXTURE/sentinel" "$FIXTURE"/captured.*
run_expect 0 "post-scan source mutation cannot change delegated private copies" \
  env MUTATE_AFTER_SCAN=1
[ -e "$FIXTURE/sentinel" ]
grep -Fxq 'Continue the listed work safely.' "$FIXTURE/captured.resume"
grep -Fxq 'Objective: validate the handoff.' "$FIXTURE/captured.handoff"
if grep -Eq 'sk-or-v1|PRIVATE KEY' "$FIXTURE"/captured.*; then
  echo "  FAIL  mutable originals reached wrapper after private-copy screening" >&2
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
