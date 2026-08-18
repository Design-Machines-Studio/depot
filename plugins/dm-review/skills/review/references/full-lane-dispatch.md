# Full-mode lane dispatch

Load this only in **full** mode at Phase 4.

### 0. Resolve OpenRouter availability

Before selecting Branch A, check external routing availability:

```bash
OPENROUTER_RUNNER_PATH=""
OPENROUTER_SECURITY_POLICY_PATH=""
OPENROUTER_BOUNDARY_PATH=""
OPENROUTER_BUNDLE_ROOT=""
OPENROUTER_BUNDLE_REF=""
OPENROUTER_BUNDLE_VERSION=""
OPENROUTER_CACHE_CLASS=""
OPENROUTER_RESOLUTION_REASON=""
if [ -n "${OPENROUTER_API_KEY:-}" ] || [ -n "${OPENROUTER_API_KEY_FILE:-}" ]; then
  : "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh once per review first}"
  OPENROUTER_ACTIVE_HOST=""
  [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && OPENROUTER_ACTIVE_HOST="claude"
  [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && OPENROUTER_ACTIVE_HOST="codex"
  OPENROUTER_ACTIVE_HOST_ARGS=()
  [ -n "$OPENROUTER_ACTIVE_HOST" ] && OPENROUTER_ACTIVE_HOST_ARGS=(--active-host "$OPENROUTER_ACTIVE_HOST")
  BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.15.0 "${OPENROUTER_ACTIVE_HOST_ARGS[@]}" \
    --required-asset agents/workflow/openrouter-agent-runner.md \
    --required-asset agents/review/openrouter-bulk-analyst.md \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
    --required-asset skills/openrouter-delegate/references/model-matrix.json \
    --required-asset skills/openrouter-delegate/references/prompt-templates.md) || BUNDLE_JSON=""
  OPENROUTER_BUNDLE_REF=$(printf '%s' "$BUNDLE_JSON" | jq -r '.selected_root // empty' 2>/dev/null)
  case "$OPENROUTER_BUNDLE_REF" in
    "~/"*) OPENROUTER_BUNDLE_ROOT="$HOME/${OPENROUTER_BUNDLE_REF#\~/}" ;;
  esac
  OPENROUTER_RUNNER_PATH="$OPENROUTER_BUNDLE_ROOT/agents/workflow/openrouter-agent-runner.md"
  OPENROUTER_SECURITY_POLICY_PATH="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
  OPENROUTER_BOUNDARY_PATH="$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
  OPENROUTER_BUNDLE_VERSION=$(printf '%s' "$BUNDLE_JSON" | jq -r '.version // empty' 2>/dev/null)
  OPENROUTER_CACHE_CLASS=$(printf '%s' "$BUNDLE_JSON" | jq -r '.cache_class // empty' 2>/dev/null)
  OPENROUTER_RESOLUTION_REASON=$(printf '%s' "$BUNDLE_JSON" | jq -r '.reason // empty' 2>/dev/null)
fi
# Availability is configured-key plus one coherent installed bundle. Payload
# eligibility is decided automatically at dispatch time by the disclosure
# boundary. This path has no broker dependency.
OPENROUTER_AVAILABLE=false
OPENROUTER_UNAVAILABLE_REASON=configured_key_or_bundle_unavailable
if { [ -n "${OPENROUTER_API_KEY:-}" ] || [ -n "${OPENROUTER_API_KEY_FILE:-}" ]; } &&
   [ -n "$OPENROUTER_BUNDLE_ROOT" ] && [ -f "$OPENROUTER_RUNNER_PATH" ] &&
   [ -r "$OPENROUTER_SECURITY_POLICY_PATH" ] && [ -x "$OPENROUTER_BOUNDARY_PATH" ]; then
  OPENROUTER_AVAILABLE=true
  OPENROUTER_UNAVAILABLE_REASON=""
fi
```

### Phase 4: Parallel Agent Launch

Launch ALL selected agents simultaneously using multiple Agent tool calls in a single message -- agents run in parallel, not sequentially. Build every reviewer prompt from `${CLAUDE_SKILL_DIR}/references/reviewer-prompt-template.md`.

**Routing report** -- print after availability resolves:

```
Provider routing (OPENROUTER_AVAILABLE={true|false}, authorization={trusted-boundary|none}):
- N analyses -> OpenRouter (Kimi security only; DeepSeek pattern/docs/tests; Qwen simplicity/bulk/ordinary second perspective)
- N native coding agents -> Codex (architecture, visual/UI, unavailable-provider and sensitive-section coverage)
- 1 required security sign-off -> resolved independent family (full diff)
- 1 second perspective -> resolved independent family when enabled
- N non-coding agents -> Claude when explicitly selected (for example voice/editorial)
```

#### How to launch each agent

For each selected role, resolve `second-perspective` and
`security-auditor-codex-signoff` against the implementing family first and use
Branches C and D. All other OpenRouter lanes, including
`openrouter-bulk-analyst`, use Branch A. The bulk analyst definition contains
review criteria only; the generic runner is the single boundary,
authorization, invocation, fallback, and provenance implementation.

**A. If the agent is routed to OpenRouter** (in the model table and `OPENROUTER_AVAILABLE=true`): load `${CLAUDE_SKILL_DIR}/references/openrouter-branch-a.md` and follow it exactly -- it owns the runner-definition read, the runner prompt fields, the non-Claude launch rule, and the `security-auditor-openrouter` lane identity. When `OPENROUTER_AVAILABLE=false`, do not load it; every lane takes Branch B.

**B. Otherwise, dispatch coding review on Codex:**

1. **Read the agent definition file** from the plugin root bound after roster selection:

   ```bash
   case "$AGENT_PLUGIN" in
     dm-review) PLUGIN_BUNDLE_ROOT="$DM_REVIEW_BUNDLE_ROOT" ;;
     accessibility-compliance) PLUGIN_BUNDLE_ROOT="$ACCESSIBILITY_BUNDLE_ROOT" ;;
     live-wires) PLUGIN_BUNDLE_ROOT="$LIVE_WIRES_BUNDLE_ROOT" ;;
     ghostwriter) PLUGIN_BUNDLE_ROOT="$GHOSTWRITER_BUNDLE_ROOT" ;;
     council) PLUGIN_BUNDLE_ROOT="$COUNCIL_BUNDLE_ROOT" ;;
     openrouter) PLUGIN_BUNDLE_ROOT="$OPENROUTER_BUNDLE_ROOT" ;;
     *) PLUGIN_BUNDLE_ROOT="" ;;
   esac
   [ -n "$PLUGIN_BUNDLE_ROOT" ] || { echo "ERROR: selected plugin bundle not bound: $AGENT_PLUGIN"; exit 1; }
   AGENT_PATH="$PLUGIN_BUNDLE_ROOT/$AGENT_ASSET"
   [ -f "$AGENT_PATH" ] || { echo "ERROR: bound agent missing: $AGENT_PLUGIN/$AGENT_ASSET"; exit 1; }
   ```

   Set `AGENT_PLUGIN` and `AGENT_ASSET` from the selected roster row. Never re-resolve a file independently or use depot-relative paths -- pipeline runs in worktrees.

2. **Build the agent prompt** per the common prompt contract: the agent definition, changed files, diff, and project context.
3. On a Codex host, launch a native Codex subagent with the combined prompt. On another host, pipe the prompt to `codex exec -s read-only -c service_tier=fast --skip-git-repo-check -`. Legacy Claude-model frontmatter is compatibility metadata and must not override the coding-provider policy. Clearly non-coding agents such as `voice-editor` may use their declared Claude model.

Both A and B agents launch in parallel in the same message. The runner reads the target agent's definition file itself at runtime -- the orchestrator only passes the path. The consolidator dedupes findings tagged `[openrouter/{model}/{agent}]` against other agents' findings using the same file:line key.

**C/D. Independent-family lanes.** When the selected roster includes
`second-perspective` or `security-auditor-codex-signoff`, load
`${CLAUDE_SKILL_DIR}/references/independent-family-lanes.md` and follow its
Branch C and Branch D resolution: reviewer family must differ from every
implementing family, retries continue down the remaining policy-derived
non-implementing families, and exhaustion leaves the lane incomplete rather
than falling back to an implementer. With neither role selected, do not load it.

**Authorization and failure handling:** Automated OpenRouter selection uses the
configured-key `trusted-boundary` path from Phase 3. Missing or invalid
credentials, unavailable provider/bundle, or an automatic disclosure decline
applies Phase 4.5 lane-aware resolution without a prompt. Ordinary lanes may
retry on Codex. The `security-auditor-codex-signoff` compatibility lane is the
exception: every retry and partial/full-decline completion must use a
non-implementing family, and exhaustion is `REVIEW INCOMPLETE`. Do not mark the
run clean until required independent work completes.

#### Diff scoping per lane

A scoped lane's `## Diff` section contains only the files its Phase 3 trigger
condition selects; the lane may still read any project file it needs. Always
include the file list of the WHOLE diff (names only, no hunks) under
`## Files to Review`.

Slice from the lane's FULL Phase 3 condition, not its file extensions alone --
`voice-editor` fires on "`.md` or `.txt` changed, OR user-facing text in
templates", so its slice must carry those template files too.

**Only the lanes named scoped below are ever sliced. Every other lane receives
the FULL diff, and the full-diff list takes precedence wherever a lane appears
extension-triggered** -- which is why `test-coverage-reviewer` and
`governance-domain` are extension-triggered and still get the whole diff. A
lane in neither list is a classification gap, not a licence to narrow: give it
the full diff and record `diff_scope: full` with `slice_status: unclassified`.

**Scoped lanes** -- diff sliced to the lane's Phase 3 trigger condition:
a11y-html-reviewer, a11y-css-reviewer, css-reviewer, a11y-dynamic-content-reviewer, voice-editor, go-build-verifier, craft-reviewer, migration-validator, visual-browser-tester, ux-quality-reviewer, ui-standards-reviewer.

**Full-diff lanes** -- never scoped, and this list is closed:
security-auditor-codex-signoff (`routing-policy.json` sets `inputScope: full-diff` and `required: true`), security-auditor-openrouter, architecture-reviewer, second-perspective (default definition: `codex-perspective.md`), pattern-recognition-specialist, code-simplicity-reviewer, doc-sync-reviewer, test-coverage-reviewer, governance-domain, openrouter-bulk-analyst.

The always-run judgment lanes detect cross-file problems a sliced diff hides.
"Never scoped" means never sliced to a trigger set; it does not override the
byte-bound disclosure eligibility governing what an OpenRouter lane may be sent
(`security-auditor-openrouter` and `openrouter-bulk-analyst` still receive only
the eligible sections their runner's disclosure boundary approves).

**Receipt:** every lane passes `diff_scope` to the kernel -- `full` for an
unscoped lane, or `scoped(<n> files of <total>)` for a sliced one -- via
`--diff-scope`, `--full-diff-override`, and `--slice-status` on
`record-attempt`. Do not hand-write receipt rows or overload
`--fallback-reason`, which carries independent executor-fallback semantics.

**Kill switch:** `DM_REVIEW_FULL_DIFF=1` disables scoping entirely: every lane
receives the full diff and records `diff_scope: full` with
`full_diff_override: true`. Default OFF. The switch fails OPEN: if slice
construction fails for any lane -- unparseable diff, a trigger resolving to no
files, any error at all -- that lane receives the FULL diff and records
`slice_status: slice_failed`. A lane is never dispatched against an unverifiable
slice, and never skipped because its slice came out empty; uncertainty widens
the input.

#### Parallelization rules

- Launch ALL agents in a single message with multiple Agent tool calls
- Do not wait for one agent to finish before launching the next
- Each agent runs independently with its own copy of the diff, scoped per the rules above

#### Recording each lane (mandatory, one call per attempt)

**As each lane settles -- completed, failed, declined, or skipped -- record it
with `record-attempt`. This is not optional and it is not deferred to the
terminal emission block.**

```bash
"$WORKFLOW_KERNEL" record-attempt \
  --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json \
  --run-id <run-id> --occurred-at <ISO-8601> \
  --authoritative-receipt receipts/review/<lane>.json \
  --stage review_dispatch --status <completed|failed|declined|skipped> \
  --lane <lane-id> --chunk-id <review-target> --node-id <lane-id> \
  --attempt <n> --host <claude|codex> --duration-seconds <elapsed> \
  --requested-executor <codex|openrouter|claude> \
  --attempted-executor <what actually ran> \
  --implemented-by <what produced the output> \
  --matrix-snapshot-date <model-matrix snapshot_date> \
  --rung-rationale <cost|context|strength|availability> \
  --diff-scope <full|scoped(n files of total)> \
  --full-diff-override <true|false> \
  --slice-status <sliced|not_sliced|unclassified|slice_failed|full_diff_override> \
  [--fallback-reason <reason>] \
  # exactly one measurement source, in this order of preference:
  [--openrouter-receipt <wrapper receipt path> \
   --request-envelope-sha256 <approved request envelope digest> \
   --state-dir .workflow-kernel/runs/<run-id>] \
  [--agent-definition <path> --diff <path> [--boilerplate <path> ...] \
   --provider <p> --model <m>]
```

One call appends **two** receipts under one lock -- the lane outcome and its
`attempt_usage` row -- and either both land or neither does: there is no call
that records a lane without its measurement, so a lane cannot go unmeasured by
being forgotten. Supply the strongest evidence the lane actually has:

- **OpenRouter lanes:** `--openrouter-receipt` (the wrapper's `OPENROUTER_RECEIPT_FILE`), `--request-envelope-sha256` from that attempt's preparation manifest, and `--state-dir .workflow-kernel/runs/<run-id>`. The kernel requires exact equality with the digest in the wrapper receipt, so a receipt from another call cannot be crossed in. The same wrapper receipt is one-use evidence; every real retry supplies its own.
- **Codex and Claude lanes:** `--agent-definition` and `--diff` (plus any `--boilerplate`) -- deterministic input bytes, never a token count.
- **Neither available:** omit both. The row records `attempt_unmeasured` -- the lane ran and nothing measured it, a claim a reader can audit. An absent row is not: it is indistinguishable from a lane that never ran.

Record failed and declined attempts too -- a lane that burned a provider call and returned nothing still cost money. Do **not** hand-write lane receipts into the array, and do not call `openrouter-usage` or `lane-input-bytes` with `--append-to` for a lane recorded here; that is the older two-call path this replaces, and using both double-counts the attempt.

#### Failure handling

Apply the failure policies from `${CLAUDE_SKILL_DIR}/references/guardrails.md`:

- If a non-browser agent fails or times out (>120s), record the failure in the Agent Summary table and apply the documented lane policy. A required browser agent instead runs browser recovery and, on exhaustion, blocks with `human_help_required` and asks the user for help.
- For agents routed to external LLMs, defer failure classification to Phase 4.5 before applying these policies.
- If a **core agent** (security-auditor-codex-signoff, architecture-reviewer, code-simplicity-reviewer, pattern-recognition-specialist, doc-sync-reviewer) fails after any applicable Phase 4.5 retry, flag the review as "REVIEW INCOMPLETE" in the merge recommendation. A selected security-auditor-openrouter lane is also required until it completes externally or through an allowed non-implementing-family fallback.
- If all non-browser conditional agents fail but core agents succeed, the review is "Degraded" but still valid. Missing required browser evidence is never degraded-valid.
- See `${CLAUDE_SKILL_DIR}/references/graceful-degradation.md` for the full failure classification table.

---
