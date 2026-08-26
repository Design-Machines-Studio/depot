#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASCADE="$ROOT/plugins/pipeline/references/cascade-dispatch.sh"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
ORCHESTRATOR="$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
ADAPTER="$ROOT/plugins/pipeline/references/codex-native-execution-adapter.md"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pipeline-role-dispatch.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

printf '%s\n' '{"codex":{"state":"ok","authMode":"subscription"},"claude":{"state":"unavailable"},"openrouter":{"state":"ok"}}' > "$TMP/availability"
cat > "$TMP/transport" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
output=""; receipt=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-file) output="$2"; shift 2 ;;
    --provider-receipt-file) receipt="$2"; shift 2 ;;
    *) shift 2 ;;
  esac
done
printf '%s\n' contact >> "$PIPELINE_CONTACT_LOG"
printf '%s\n' 'pipeline dispatch output' > "$output"
: > "$receipt"
STUB
chmod +x "$TMP/transport"
: > "$TMP/contact.log"

env -u WORKFLOW_KERNEL MODEL_ROUTER_TEST_MODE=1 \
  MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport" PIPELINE_CONTACT_LOG="$TMP/contact.log" \
  "$CASCADE" --class openrouter --prompt 'bounded pipeline prompt' \
    --workflow-kernel "$KERNEL" --output-file "$TMP/out" --receipt-file "$TMP/receipt" \
    > "$TMP/stdout"
assert grep -Fxq 'pipeline dispatch output' "$TMP/stdout"
assert jq -e '.requested.role == "builder-fast" and .requested.capabilities == ["structured-output"]' "$TMP/receipt"
assert test "$(grep -c '^contact$' "$TMP/contact.log")" -eq 1

set +e
MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport" PIPELINE_CONTACT_LOG="$TMP/contact.log" \
  "$CASCADE" --class openrouter --prompt 'missing launcher' >/dev/null 2>&1
missing_rc=$?
set -e
assert test "$missing_rc" -eq 2
assert test "$(grep -c '^contact$' "$TMP/contact.log")" -eq 1

assert grep -Fq -- '--workflow-kernel "$WORKFLOW_KERNEL"' "$ORCHESTRATOR"
assert grep -Fq -- '--workflow-kernel "$WORKFLOW_KERNEL"' "$ADAPTER"

printf 'pipeline-role-dispatch: %d assertions passed\n' "$pass"
