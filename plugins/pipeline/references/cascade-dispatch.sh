#!/usr/bin/env bash
# Legacy compatibility adapter. New callers invoke model-router role-dispatch.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
umask 077

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLASS=""
KIND=""
PROMPT=""
RECEIPT=""
OUTPUT=""
ATTEMPT_RECEIPT_TEMPLATE=""
CONTRACT_DIGEST=""
CONTRACT_REVISION=""
WORKFLOW_KERNEL_LAUNCHER=""
DRY_RUN=0

usage() {
  printf '%s\n' 'usage: cascade-dispatch.sh --class <codex|openrouter|claude>|--kind <ui|logic|integration|config|docs|mechanical-logic> --prompt <text|-> --workflow-kernel PATH [--receipt-file PATH] [--output-file PATH] [--contract-digest SHA256 --contract-revision N] [legacy options]' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --class) [ "$#" -ge 2 ] || usage; CLASS="$2"; shift 2 ;;
    --kind) [ "$#" -ge 2 ] || usage; KIND="$2"; shift 2 ;;
    --prompt) [ "$#" -ge 2 ] || usage; PROMPT="$2"; shift 2 ;;
    --receipt-file) [ "$#" -ge 2 ] || usage; RECEIPT="$2"; shift 2 ;;
    --output-file) [ "$#" -ge 2 ] || usage; OUTPUT="$2"; shift 2 ;;
    --attempt-receipt-template) [ "$#" -ge 2 ] || usage; ATTEMPT_RECEIPT_TEMPLATE="$2"; shift 2 ;;
    --contract-digest) [ "$#" -ge 2 ] || usage; CONTRACT_DIGEST="$2"; shift 2 ;;
    --contract-revision) [ "$#" -ge 2 ] || usage; CONTRACT_REVISION="$2"; shift 2 ;;
    --workflow-kernel) [ "$#" -ge 2 ] || usage; WORKFLOW_KERNEL_LAUNCHER="$2"; shift 2 ;;
    --phase|--host|--timeout|--probe-file|--exhausted-rail) [ "$#" -ge 2 ] || usage; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) usage ;;
  esac
done

if [ -z "$CLASS" ]; then
  case "$KIND" in
    config|docs|mechanical-logic) CLASS=openrouter ;;
    ui|logic|integration) CLASS=codex ;;
    *) usage ;;
  esac
fi
case "$CLASS" in
  openrouter) ROLE=builder-fast ;;
  codex|claude) ROLE=builder-deep ;;
  *) usage ;;
esac
[ -n "$PROMPT" ] || usage
if [ -n "$ATTEMPT_RECEIPT_TEMPLATE" ]; then
  case "$ATTEMPT_RECEIPT_TEMPLATE" in *'{attempt}'*) ;; *) usage ;; esac
fi
if [ -n "$CONTRACT_DIGEST$CONTRACT_REVISION" ]; then
  [[ "$CONTRACT_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || usage
  [[ "$CONTRACT_REVISION" =~ ^[1-9][0-9]*$ ]] || usage
fi

if [ "$DRY_RUN" -eq 1 ]; then
  jq -n --arg role "$ROLE" --arg class "$CLASS" \
    '{schemaVersion:1,compatibilityAdapter:true,class:$class,role:$role,disposition:"dry-run"}'
  exit 0
fi
case "$WORKFLOW_KERNEL_LAUNCHER" in /*/workflow-kernel-launcher.sh) ;; *) usage ;; esac
[ -f "$WORKFLOW_KERNEL_LAUNCHER" ] && [ -x "$WORKFLOW_KERNEL_LAUNCHER" ] &&
  [ ! -L "$WORKFLOW_KERNEL_LAUNCHER" ] || usage

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/cascade-compat.XXXXXX")"
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT
PROMPT_FILE="$TMP_ROOT/prompt.txt"
PUBLIC_FILE="$TMP_ROOT/public.json"
if [ "$PROMPT" = - ]; then
  cat > "$PROMPT_FILE"
else
  printf '%s' "$PROMPT" > "$PROMPT_FILE"
fi
[ -n "$OUTPUT" ] || OUTPUT="$TMP_ROOT/output.txt"
[ -n "$RECEIPT" ] || RECEIPT="$TMP_ROOT/receipt.json"

DISPATCHER="$DIR/../../model-router/skills/model-router/references/role-dispatch.sh"
if [ ! -x "$DISPATCHER" ]; then
  BUNDLE_JSON="$("$WORKFLOW_KERNEL_LAUNCHER" resolve-plugin-bundle \
    --plugin model-router --minimum-version 0.4.0 \
    --required-executable skills/model-router/references/role-dispatch.sh \
    --required-asset skills/model-router/references/role-request-schema.json \
    --required-asset skills/model-router/references/role-policy.json 2>/dev/null)" || BUNDLE_JSON=""
  BUNDLE_REF="$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')"
  case "$BUNDLE_REF" in
    "~/"*) DISPATCHER="$HOME/${BUNDLE_REF#\~/}/skills/model-router/references/role-dispatch.sh" ;;
    *) DISPATCHER="" ;;
  esac
fi
[ -n "$DISPATCHER" ] || { printf '%s\n' 'cascade-dispatch: role router unavailable' >&2; exit 76; }

ROLE_ARGS=(--role "$ROLE" --capability structured-output --effort medium
  --workflow-kernel "$WORKFLOW_KERNEL_LAUNCHER"
  --prompt-file "$PROMPT_FILE"
  --output-file "$OUTPUT" --receipt-file "$RECEIPT")
if [ -n "$CONTRACT_DIGEST" ]; then
  ROLE_ARGS+=(--capability write-repository --contract-digest "$CONTRACT_DIGEST"
    --contract-revision "$CONTRACT_REVISION")
fi

set +e
"$DISPATCHER" "${ROLE_ARGS[@]}" > "$PUBLIC_FILE"
RC=$?
set -e
[ "$RC" -eq 0 ] || exit "$RC"

if [ -n "$ATTEMPT_RECEIPT_TEMPLATE" ]; then
  ATTEMPT_RECEIPT="${ATTEMPT_RECEIPT_TEMPLATE//\{attempt\}/1}"
  cp "$RECEIPT" "$ATTEMPT_RECEIPT"
fi
cat "$OUTPUT"
