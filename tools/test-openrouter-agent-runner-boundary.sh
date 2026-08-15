#!/usr/bin/env bash
# Behaviorally prove the dm-review OpenRouter runner scans once before dispatch.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
FIXTURE="$(mktemp -d "${TMPDIR:-/tmp}/openrouter-runner-boundary.XXXXXX")"
trap 'rm -rf "$FIXTURE"' EXIT

OPENROUTER_ROOT="$FIXTURE/openrouter"
REFS="$OPENROUTER_ROOT/skills/openrouter-delegate/references"
mkdir -p "$REFS"
printf '{}\n' > "$REFS/delegation-security-policy.json"

if command -v sha256sum >/dev/null 2>&1; then
  HASH_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  HASH_CMD="shasum -a 256"
else
  echo "sha256sum or shasum is required" >&2
  exit 1
fi
export HASH_CMD

cat > "$FIXTURE/boundary" <<'EOF'
#!/usr/bin/env bash
count=0
[ ! -f "$BOUNDARY_COUNT" ] || count="$(cat "$BOUNDARY_COUNT")"
printf '%s\n' "$((count + 1))" > "$BOUNDARY_COUNT"
printf '%s\0' "$@" > "$BOUNDARY_ARGS"
printf 'boundary\n' >> "$EVENT_LOG"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --content-file)
      shift
      printf '%s\t' "$1" >> "$SCREENED_FILES"
      $HASH_CMD "$1" | awk '{print $1}' >> "$SCREENED_DIGESTS"
      ;;
  esac
  shift
done
EOF
chmod +x "$FIXTURE/boundary"

cat > "$REFS/openrouter-wrapper.sh" <<'EOF'
#!/usr/bin/env bash
touch "$WRAPPER_SENTINEL"
[ -f "$OPENROUTER_SYSTEM_FILE" ]
printf 'wrapper\n' >> "$EVENT_LOG"
$HASH_CMD "$OPENROUTER_SYSTEM_FILE" | awk '{print $1}' > "$WRAPPER_DIGESTS"
user_copy="${TMPDIR:-/tmp}/runner-boundary-user.$$"
trap 'rm -f "$user_copy"' EXIT
cat > "$user_copy"
$HASH_CMD "$user_copy" | awk '{print $1}' >> "$WRAPPER_DIGESTS"
printf 'fixture response\n'
EOF
chmod +x "$REFS/openrouter-wrapper.sh"

{
  printf '%s\n' '#!/usr/bin/env bash' 'set -uo pipefail'
  printf '%s\n' \
    'target_agent_name="doc-sync-reviewer"' \
    'target_model="openai/gpt-5.6-luna"' \
    'fallback_model="openai/gpt-5.6-terra"' \
    'target_timeout=10' \
    'review_run_id="runner-boundary-test"' \
    'TARGET_BODY="Review documentation consistency."' \
    'USER_PROMPT="Review this harmless fixture."' \
    'SECURITY_POLICY_RESOLVED="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"'
  sed -n '/^WRAPPER_PATH=/,/^EXIT_CODE=\$?/p' "$SOURCE"
} > "$FIXTURE/run"
chmod +x "$FIXTURE/run"

HOME="$FIXTURE/home" OPENROUTER_ROOT="$OPENROUTER_ROOT" \
  BOUNDARY_HELPER="$FIXTURE/boundary" BOUNDARY_COUNT="$FIXTURE/count" \
  BOUNDARY_ARGS="$FIXTURE/args" WRAPPER_SENTINEL="$FIXTURE/wrapper-called" \
  EVENT_LOG="$FIXTURE/events" SCREENED_FILES="$FIXTURE/screened-files" \
  SCREENED_DIGESTS="$FIXTURE/screened-digests" WRAPPER_DIGESTS="$FIXTURE/wrapper-digests" \
  "$FIXTURE/run" >/dev/null

[ "$(cat "$FIXTURE/count")" = "1" ]
[ -e "$FIXTURE/wrapper-called" ]
grep -Fq -- '--mode' "$FIXTURE/args"
grep -Fq -- 'artifact-delegation' "$FIXTURE/args"
[ "$(tr '\n' ' ' < "$FIXTURE/events")" = "boundary wrapper " ]
[ "$(wc -l < "$FIXTURE/screened-digests" | tr -d ' ')" = "2" ]
cmp "$FIXTURE/screened-digests" "$FIXTURE/wrapper-digests"

{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  sed -n '/^read_http_failure_reason() {/,/^}/p' "$SOURCE"
  sed -n '/^map_wrapper_failure_reason() {/,/^}/p' "$SOURCE"
  cat <<'EOF'
receipt="$1"
expected="$2"
[ "$(read_http_failure_reason "$receipt")" = "$expected" ]
EOF
} > "$FIXTURE/read-failure-reason"
chmod +x "$FIXTURE/read-failure-reason"

for reason in \
  organization_monthly_budget_exceeded key_permission_denied guardrail_blocked \
  insufficient_credits rate_limited unknown_http_error; do
  jq -n --arg reason "$reason" '{
    schemaVersion: 2,
    outcome: "error",
    failureKind: "http_error",
    failureReason: $reason
  }' > "$FIXTURE/receipt"
  "$FIXTURE/read-failure-reason" "$FIXTURE/receipt" "$reason"
done

for invalid in unexpected_reason null; do
  if [ "$invalid" = null ]; then
    value=null
  else
    value='"unexpected_reason"'
  fi
  printf '{"schemaVersion":2,"outcome":"error","failureKind":"http_error","failureReason":%s}\n' \
    "$value" > "$FIXTURE/receipt"
  ! "$FIXTURE/read-failure-reason" "$FIXTURE/receipt" "$invalid" >/dev/null 2>&1
done
printf 'not-json\n' > "$FIXTURE/receipt"
! "$FIXTURE/read-failure-reason" "$FIXTURE/receipt" ignored >/dev/null 2>&1

{
  sed -n '/^map_wrapper_failure_reason() {/,/^}/p' "$SOURCE"
  printf '%s\n' 'map_wrapper_failure_reason organization_monthly_budget_exceeded'
} > "$FIXTURE/map-failure-reason"
organization_reason=$(bash "$FIXTURE/map-failure-reason")
[ "$organization_reason" = "The OpenRouter organization monthly budget is exhausted; its administrator must raise or reset that limit" ]
case "$organization_reason" in
  *"buy"*|*"credit"*|*"replace"*|*"key"*) exit 1 ;;
esac

echo "  OK    OpenRouter agent runner performs one behavioral boundary scan and validates closed HTTP failure reasons"
