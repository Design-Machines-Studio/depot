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
DM_REVIEW_ROOT="$FIXTURE/dm-review"
CONTRACT="$DM_REVIEW_ROOT/skills/review/references/reviewer-output-contract.md"
mkdir -p "$(dirname "$CONTRACT")"
cat > "$CONTRACT" <<'EOF'
# Canonical Reviewer Output Contract

Bounded findings-only reporting: return `NOT-COVERED:` and `COMMANDS-RUN:`.
EOF

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
cp "$OPENROUTER_SYSTEM_FILE" "$CAPTURED_SYSTEM"
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
    'TARGET_BODY="## Domain Criteria\n\nReview documentation consistency."' \
    'USER_PROMPT="Review this harmless fixture."' \
    'BOUNDARY_STDERR="$FIXTURE/artifact-boundary-stderr"' \
    'SECURITY_POLICY_RESOLVED="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"'
  printf 'REVIEWER_OUTPUT_CONTRACT=%q\n' "$CONTRACT"
  sed -n '/^CONTRACT_SENTINEL=/,/^CONTRACT_HEADING=/p' "$SOURCE"
  sed -n '/^case "\$TARGET_BODY" in/,/^esac$/p' "$SOURCE"
  sed -n '/^TARGET_BODY="${TARGET_BODY%/,/^esac$/p' "$SOURCE"
  sed -n '/^WRAPPER_PATH=/,/^EXIT_CODE=\$?/p' "$SOURCE"
} > "$FIXTURE/run"
chmod +x "$FIXTURE/run"

HOME="$FIXTURE/home" FIXTURE="$FIXTURE" OPENROUTER_ROOT="$OPENROUTER_ROOT" \
  BOUNDARY_HELPER="$FIXTURE/boundary" BOUNDARY_COUNT="$FIXTURE/count" \
  BOUNDARY_ARGS="$FIXTURE/args" WRAPPER_SENTINEL="$FIXTURE/wrapper-called" \
  EVENT_LOG="$FIXTURE/events" SCREENED_FILES="$FIXTURE/screened-files" \
  SCREENED_DIGESTS="$FIXTURE/screened-digests" WRAPPER_DIGESTS="$FIXTURE/wrapper-digests" CAPTURED_SYSTEM="$FIXTURE/captured-system" \
  "$FIXTURE/run" >/dev/null

[ "$(cat "$FIXTURE/count")" = "1" ]
[ -e "$FIXTURE/wrapper-called" ]
grep -Fq -- '--mode' "$FIXTURE/args"
grep -Fq -- 'artifact-delegation' "$FIXTURE/args"
[ "$(tr '\n' ' ' < "$FIXTURE/events")" = "boundary wrapper " ]
[ "$(wc -l < "$FIXTURE/screened-digests" | tr -d ' ')" = "2" ]
cmp "$FIXTURE/screened-digests" "$FIXTURE/wrapper-digests"
captured_system="$FIXTURE/captured-system"
grep -Fqx '# Canonical Reviewer Output Contract' "$captured_system"
[ "$(grep -Fc '# Canonical Reviewer Output Contract' "$captured_system")" = 1 ]
contract_bytes="$(wc -c < "$CONTRACT" | tr -d ' ')"
tail -c "$contract_bytes" "$captured_system" > "$FIXTURE/captured-contract"
cmp "$CONTRACT" "$FIXTURE/captured-contract"
grep -Fq 'Review documentation consistency.' "$captured_system"
! grep -Fq '### Approved' "$captured_system"
! grep -Fq 'if a severity tier is empty, say so explicitly' "$captured_system"
! grep -Fq '${CLAUDE_SKILL_DIR}' "$captured_system"

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

cat > "$REFS/openrouter-wrapper.sh" <<'EOF'
#!/usr/bin/env bash
jq -n '{
  schemaVersion: 2,
  outcome: "error",
  failureKind: "http_error",
  failureReason: "organization_monthly_budget_exceeded"
}' > "$OPENROUTER_RECEIPT_FILE"
printf '%s\n' 'PRIVATE_PROVIDER_BODY_MARKER' >&2
exit 1
EOF
chmod +x "$REFS/openrouter-wrapper.sh"

{
  printf '%s\n' '#!/usr/bin/env bash' 'set -uo pipefail'
  printf '%s\n' \
    'target_agent_name="doc-sync-reviewer"' \
    'target_model="openai/gpt-5.6-luna"' \
    'fallback_model="openai/gpt-5.6-terra"' \
    'target_timeout=10' \
    'review_run_id="runner-http-failure-test"' \
    'TARGET_BODY="Review documentation consistency."' \
    'USER_PROMPT="Review this harmless fixture."' \
    'BOUNDARY_STDERR="$FIXTURE/http-boundary-stderr"' \
    'SECURITY_POLICY_RESOLVED="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"'
  sed -n '/^WRAPPER_PATH=/,/^EXIT_CODE=\$?/p' "$SOURCE"
  sed -n '/^ACTUAL_MODEL=/,/^fi$/p' "$SOURCE"
  sed -n '/^case "\$EXIT_CODE" in/,/^fi$/p' "$SOURCE"
} > "$FIXTURE/run-http-failure"
chmod +x "$FIXTURE/run-http-failure"

runner_failure_output=$(HOME="$FIXTURE/home" FIXTURE="$FIXTURE" OPENROUTER_ROOT="$OPENROUTER_ROOT" \
  BOUNDARY_HELPER="$FIXTURE/boundary" BOUNDARY_COUNT="$FIXTURE/http-count" \
  BOUNDARY_ARGS="$FIXTURE/http-args" WRAPPER_SENTINEL="$FIXTURE/http-wrapper-called" \
  EVENT_LOG="$FIXTURE/http-events" SCREENED_FILES="$FIXTURE/http-screened-files" \
  SCREENED_DIGESTS="$FIXTURE/http-screened-digests" WRAPPER_DIGESTS="$FIXTURE/http-wrapper-digests" \
  "$FIXTURE/run-http-failure")

case "$runner_failure_output" in
  *"### RUNNER FAILURE"*) ;;
  *) exit 1 ;;
esac
case "$runner_failure_output" in
  *"Provider adapter (doc-sync-reviewer): unavailable. Review unavailable."*) ;;
  *) exit 1 ;;
esac
case "$runner_failure_output" in
  *"PRIVATE_PROVIDER_BODY_MARKER"*|*"All models exhausted, key missing, or HTTP error"*) exit 1 ;;
esac

grep -Fq -- '--output-decision "$BOUNDARY_DECISION"' "$SOURCE"
grep -Fq 'it does not decide whether content is eligible for OpenRouter' "$SOURCE"
! grep -Fq 'Request the same role only for these held paths' "$SOURCE"
! grep -Fq 'OpenRouter reviewed only the eligible file sections.' "$SOURCE"

cat > "$FIXTURE/runner-partial.diff" <<'EOF'
diff --git a/internal/auth/session.go b/internal/auth/session.go
--- a/internal/auth/session.go
+++ b/internal/auth/session.go
@@ -1 +1 @@
-before
+SAFE_REMAINDER_MARKER
diff --git a/tests/integration/compose-release-command.sh b/tests/integration/compose-release-command.sh
--- a/tests/integration/compose-release-command.sh
+++ b/tests/integration/compose-release-command.sh
@@ -1 +1 @@
-before
+GITHUB_TOKEN=ghp_0123456789abcdefABCDEF
EOF
printf '%s\n' internal/auth/session.go tests/integration/compose-release-command.sh \
  > "$FIXTURE/runner-partial.changed"

{
  printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
  printf '%s\n' \
    'target_agent_name="security-auditor-openrouter"' \
    'target_model="moonshotai/kimi-k3"' \
    'diff_content="$(cat "$RUNNER_DIFF")"' \
    'changed_files="$(cat "$RUNNER_CHANGED")"' \
    'SECURITY_POLICY_RESOLVED="$RUNNER_POLICY"'
  sed -n '/^BOUNDARY_HELPER=/,/^DECLINED_CHANGED_FILES=/p' "$SOURCE"
  printf '%s\n' \
    'printf "%s\t%s\t%s\t%s\n" "$BOUNDARY_DECISION_REASON" "$ELIGIBLE_SECTION_COUNT" "$DECLINED_SECTION_COUNT" "$DECLINED_CHANGED_FILES"'
} > "$FIXTURE/run-mechanical"
chmod +x "$FIXTURE/run-mechanical"

mechanical_output=$(RUNNER_DIFF="$FIXTURE/runner-partial.diff" \
  RUNNER_CHANGED="$FIXTURE/runner-partial.changed" \
  RUNNER_POLICY="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json" \
  "$FIXTURE/run-mechanical")
[ "$mechanical_output" = $'none\t2\t0\t' ]

cat > "$FIXTURE/runner-credential.diff" <<'EOF'
diff --git a/tests/integration/compose-release-command.sh b/tests/integration/compose-release-command.sh
--- a/tests/integration/compose-release-command.sh
+++ b/tests/integration/compose-release-command.sh
@@ -1 +1 @@
-before
+GITHUB_TOKEN=ghp_0123456789abcdefABCDEF
EOF
printf '%s\n' tests/integration/compose-release-command.sh \
  > "$FIXTURE/runner-credential.changed"
credential_output=$(RUNNER_DIFF="$FIXTURE/runner-credential.diff" \
  RUNNER_CHANGED="$FIXTURE/runner-credential.changed" \
  RUNNER_POLICY="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json" \
  "$FIXTURE/run-mechanical" 2>"$FIXTURE/runner-credential.stderr")
[ ! -s "$FIXTURE/runner-credential.stderr" ]
[ "$credential_output" = $'none\t1\t0\t' ]

echo "  OK    OpenRouter agent runner scans once and preserves credential parity/closed decisions"
