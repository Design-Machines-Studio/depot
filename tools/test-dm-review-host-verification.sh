#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LANES="$ROOT/plugins/dm-review/skills/review/references/full-lane-dispatch.md"
HOST_CONTRACT="$ROOT/plugins/dm-review/skills/review/references/host-verification-evidence.md"
ROUTER="$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-host-verification.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

assert grep -Fq '| tests/build analysis | `review-fast` | `read-repository`, `structured-output` | `medium` |' "$LANES"
assert grep -Fq 'run it before any analysis participant' "$HOST_CONTRACT"
assert grep -Fq '8,192 UTF-8 bytes' "$HOST_CONTRACT"
assert grep -Fq 'tests/build lane does not meet that condition.' "$HOST_CONTRACT"

printf '%s\n' 'host verification completed' > "$TMP/host.log"
printf '%s\n' 'analyze the supplied host verification evidence' > "$TMP/prompt"
printf '%s\n' '{"schemaVersion":1,"lane":"tests/build","commandArgv":["./tools/verify"],"exitStatus":0,"result":"passed","stdoutTail":"ok","stderrTail":""}' > "$TMP/evidence"
printf '%s\n' '{"codex":{"state":"ok","authMode":"subscription"},"claude":{"state":"unavailable","authMode":"none"},"openrouter":{"state":"ok"}}' > "$TMP/availability"
cat > "$TMP/transport" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
[ -s "$HOST_EVIDENCE_SETTLED" ]
transport=""; output=""; receipt=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --transport) transport="$2"; shift 2 ;;
    --output-file) output="$2"; shift 2 ;;
    --provider-receipt-file) receipt="$2"; shift 2 ;;
    *) shift 2 ;;
  esac
done
printf '%s\n' "$transport" > "$HOST_TRANSPORT_LOG"
printf '%s\n' 'analysis complete' > "$output"
: > "$receipt"
STUB
chmod +x "$TMP/transport"

MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport" HOST_EVIDENCE_SETTLED="$TMP/host.log" \
  HOST_TRANSPORT_LOG="$TMP/transport.log" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium \
    --capability read-repository --capability structured-output \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/out" --receipt-file "$TMP/receipt" >/dev/null
assert grep -Fxq openrouter "$TMP/transport.log"
assert jq -e '.requested.capabilities == ["read-repository","structured-output"]' "$TMP/receipt"

rm -f "$TMP/out" "$TMP/receipt" "$TMP/transport.log"
MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_AVAILABILITY_FILE="$TMP/availability" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/transport" HOST_EVIDENCE_SETTLED="$TMP/host.log" \
  HOST_TRANSPORT_LOG="$TMP/transport.log" \
  "$ROUTER" --workflow-kernel "$KERNEL" --role review-fast --effort medium \
    --capability read-repository --capability tool-use --capability structured-output \
    --prompt-file "$TMP/prompt" --repository-evidence-file "$TMP/evidence" \
    --output-file "$TMP/out" --receipt-file "$TMP/receipt" >/dev/null
assert grep -Fxq codex-cli "$TMP/transport.log"
assert jq -e '.requested.capabilities | index("tool-use") != null' "$TMP/receipt"

printf 'dm-review-host-verification: %d assertions passed\n' "$pass"
