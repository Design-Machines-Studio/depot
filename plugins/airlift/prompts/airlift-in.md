Note: `~/.codex/prompts/` is deprecated by OpenAI in favor of skills, but it is still functional.

Resume work from an existing airlift bundle in the current repository.

Use the path argument when present. Otherwise default to `.airlift/`.

Read:

- `HANDOFF.md`
- `state.json`
- `RESUME_PROMPT.md` when present

If the supplied path is a directory, read files inside it. If the supplied path is a `HANDOFF.md` file, use its parent directory as the bundle.

Inspect `uncommitted.patch`. If it is non-empty and `git status --porcelain` is empty, offer to apply it with:

```bash
git apply .airlift/uncommitted.patch
```

Never apply the patch silently. If the working tree is dirty, skip patch application with a note that the current tree is not clean.

Read local `CLAUDE.md` and `AGENTS.md` conventions when those files exist. Detect the current harness via the airlift harness registry at `references/harness-profiles.json` from the installed airlift skill cache when available.

The registry is helpful but not required. This prompt works from the markdown alone: `HANDOFF.md` plus `RESUME_PROMPT.md` are sufficient even if the current harness is not in the registry. In that case, use the paste-prompt fallback by pasting `RESUME_PROMPT.md` into the new session and attaching or pasting `HANDOFF.md`.

Summarize the resume plan back to the user before changing files:

- Objective from `HANDOFF.md`
- Current status and git baseline from `state.json`
- Patch application decision
- Applicable local conventions
- Next steps to continue

Then continue from the `Next steps` section in `HANDOFF.md`.

For `resume-via-deepseek`, require either `OPENROUTER_API_KEY` or the validated
`OPENROUTER_API_KEY_FILE`. The target name remains stable for compatibility,
but transport is through OpenRouter using `deepseek/deepseek-v4-flash-0731`
with `x-ai/grok-4.5` fallback. Resolve
one coherent OpenRouter bundle, then privately copy and screen both resume
artifacts together before invoking the wrapper immediately:

```bash
: "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh first}"
"$WORKFLOW_KERNEL" kernel-info --minimum-version 0.5.0 >/dev/null || {
  echo "airlift-openrouter: kernel-incompatible" >&2; exit 1;
}
BUNDLE_DIR="${BUNDLE_DIR:-.airlift}"
ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && ACTIVE_HOST="codex"
resolve_bundle() {
  if [ -n "$ACTIVE_HOST" ]; then
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 --active-host "$ACTIVE_HOST" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  fi
}
BUNDLE_JSON=$(resolve_bundle) || {
    echo "airlift-openrouter: bundle-unavailable" >&2; exit 1;
  }
BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty')
case "$BUNDLE_REF" in "~/"*) OPENROUTER_ROOT="$HOME/${BUNDLE_REF#\~/}";; *) echo "airlift-openrouter: bundle-invalid" >&2; exit 1;; esac
WRAPPER="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
POLICY="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
RESUME_FILE="$BUNDLE_DIR/RESUME_PROMPT.md"
HANDOFF_FILE="$BUNDLE_DIR/HANDOFF.md"
PRIVATE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/airlift-openrouter.XXXXXX") || {
  echo "airlift-openrouter: private-copy-unavailable" >&2; exit 2;
}
trap 'rm -rf "$PRIVATE_DIR"' EXIT
RESUME_COPY="$PRIVATE_DIR/RESUME_PROMPT.md"
HANDOFF_COPY="$PRIVATE_DIR/HANDOFF.md"
"$WORKFLOW_KERNEL" snapshot-files \
  --source-root "$BUNDLE_DIR" \
  --destination-root "$PRIVATE_DIR" \
  --name RESUME_PROMPT.md \
  --name HANDOFF.md >/dev/null || {
  echo "airlift-openrouter: private-copy-invalid" >&2; exit 2;
}
if "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
    --content-file "$RESUME_COPY" --content-file "$HANDOFF_COPY"; then
  :
else
  echo "airlift-openrouter: boundary-invalid" >&2; exit 2
fi
RECEIPT_FILE="$BUNDLE_DIR/OPENROUTER_RECEIPT.json"
if env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$RESUME_COPY" \
    OPENROUTER_RUN_ID="airlift-resume" OPENROUTER_LANE_ID="resume-via-deepseek" \
    OPENROUTER_WORKLOAD="quality" OPENROUTER_RECEIPT_FILE="$RECEIPT_FILE" \
    bash "$WRAPPER" "deepseek/deepseek-v4-flash-0731" - 180 "x-ai/grok-4.5" \
    < "$HANDOFF_COPY"; then
  :
else
  WRAPPER_RC=$?
  echo "airlift-openrouter: wrapper-failed" >&2
  exit "$WRAPPER_RC"
fi
jq -e '
  .schemaVersion == 2 and .outcome == "success" and
  .authorization.runId == "airlift-resume" and
  .authorization.laneId == "resume-via-deepseek" and
  (.authorization.requestEnvelopeSha256 | test("^[0-9a-f]{64}$")) and
  ([(.. | objects) | keys[] |
    select(test("^(prompt|response|content|api_?key|secret)$"; "i"))] | length) == 0
' "$RECEIPT_FILE" >/dev/null || {
  echo "airlift-openrouter: receipt-invalid" >&2; exit 2;
}
```
