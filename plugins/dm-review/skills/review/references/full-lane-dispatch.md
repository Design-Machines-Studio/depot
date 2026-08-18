# Full-mode lane dispatch

Load this only in **full** mode at Phase 4.

### Phase 4: Parallel Agent Launch

Launch ALL selected agents simultaneously using multiple Agent tool calls in a single message. This is critical for performance -- agents must run in parallel, not sequentially.

#### How to launch each agent

For each selected role, resolve `second-perspective` and
`security-auditor-codex-signoff` against the implementing family first and use
Branches C and D. All other OpenRouter lanes, including
`openrouter-bulk-analyst`, use Branch A. The bulk analyst definition contains
review criteria only; the generic runner is the single boundary,
authorization, invocation, fallback, and provenance implementation.

**A. If the agent is routed to OpenRouter** (in the model table and `OPENROUTER_AVAILABLE=true`):

1. **Read the openrouter-agent-runner definition** from `$OPENROUTER_RUNNER_PATH` in the coherent bundle selected in Phase 3. If the selection receipt was not preserved, rerun the same workflow-kernel `resolve-plugin-bundle` request for the complete asset set; never resolve one asset independently.
2. **Build the runner prompt** by combining:
   - The full content of the runner definition file (this is the runner's instructions)
   - `target_agent_path` -- select the simple root variable bound for `TARGET_PLUGIN` (`DM_REVIEW_BUNDLE_ROOT`, `ACCESSIBILITY_BUNDLE_ROOT`, `LIVE_WIRES_BUNDLE_ROOT`, `GHOSTWRITER_BUNDLE_ROOT`, `COUNCIL_BUNDLE_ROOT`, or `OPENROUTER_BUNDLE_ROOT`) and append `TARGET_AGENT_ASSET`; if an optional plugin has no bound root, preserve its Phase 3 skip rather than re-resolving or using a depot-relative path
   - `target_agent_name` -- bare ID (e.g., `pattern-recognition-specialist`)
   - `target_model` -- full primary OpenRouter slug from policy or the inline table
   - `fallback_model` -- full fallback OpenRouter slug from policy or the inline table
   - `target_timeout` -- the workload-scaled 1800s, 3600s, or 7200s value from
     the table
   - `openrouter_bundle_ref` -- ephemeral home-relative selected root used only
     to bind runner execution to the definition that was loaded; never publish it
   - `openrouter_bundle_version`, `cache_class`, and `resolution_reason` --
     durable resolver evidence (never the selected root)
   - The unfiltered list of changed files (the runner filters it before disclosure)
   - The full diff content (the runner invokes `delegation-boundary.sh --mode mechanical-review` and sends only the emitted safe remainder)
   - Project context
3. **Launch without Claude coding execution:** on a Codex host, use a native Codex subagent with the combined runner prompt. On any other host, pipe the prompt to `codex exec -s read-only -c service_tier=fast --skip-git-repo-check -`. The runner performs mechanical orchestration and OpenRouter performs the review judgment; a Claude `Agent` call is not a valid Branch A launcher.
4. `security-auditor-openrouter` targets the installed
   `security-auditor.md` criteria but keeps its distinct logical lane ID.
   `security-auditor-codex-signoff` launches independently through Branch D
   with the full unfiltered diff and is tagged
   `[family-signoff/security-auditor]`. Neither output substitutes for the
   other. A full external decline may be completed by Codex under the external
   lane ID, but it still does not satisfy the independent signoff lane.

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

2. **Build the agent prompt** by combining:
   - The full content of the agent definition file (this is the agent's system prompt)
   - The list of changed files
   - The diff content
   - Any relevant context (project type, file paths)
3. On a Codex host, launch a native Codex subagent with the combined prompt. On another host, pipe the prompt to `codex exec -s read-only -c service_tier=fast --skip-git-repo-check -`. Legacy Claude-model frontmatter is compatibility metadata and must not override the coding-provider policy. Clearly non-coding agents such as `voice-editor` may use their declared Claude model.

Both A and B agents launch in parallel in the same message. The runner reads the target agent's definition file itself at runtime -- the orchestrator only needs to pass the path. The consolidator dedupes findings tagged `[openrouter/{model}/{agent}]` against findings from other agents using the same file:line key.

**C. If the selected role is `second-perspective`:**

1. Read `$DM_REVIEW_BUNDLE_ROOT/agents/review/codex-perspective.md`.
2. Build a read-only prompt with the changed files, diff content, project context, standard Fix Philosophy, `implementer_family`, `reviewer_family`, and `resolution_reason`.
3. Dispatch on the resolved family:
   - OpenAI/Codex: run:
   ```bash
   printf '%s' "$REVIEW_PROMPT" | codex exec -s read-only -c service_tier=fast --skip-git-repo-check -
   ```
   - Anthropic/Claude: dispatch through the native read-only Claude harness with the same prompt and no coding authority.
   - An OpenRouter-served third party: use Branch A only through the authorized path, preserving that model vendor as `reviewer_family`.
4. If the resolved family fails, continue down the remaining policy-derived non-implementing families in subscription-first order. Never retry on an implementing family.
5. If no independent family completes, record `second-perspective: unavailable` and its attempted resolution in the Agent Summary and Coverage Gaps. Do not mark the review clean until the remaining selected agents have completed and Phase 5 consolidation has run.

**D. If the selected role is `security-auditor-codex-signoff`:**

1. The compatibility lane ID remains stable, but provider resolution is family-aware. Codex is preferred when Codex did not implement the diff.
2. When Codex is the implementer, use the strongest available non-implementing family under subscription-first resolution. After eligible subscription rails, use the matrix security head, currently Kimi K3, only through its authorized path. Never fall back to Codex for this sign-off.
3. Dispatch `$DM_REVIEW_BUNDLE_ROOT/agents/review/security-auditor.md` with the complete unfiltered diff. The sign-off remains mandatory and full-diff regardless of which family performs it.
4. Record `implementer_family`, `reviewer_family`, and `resolution_reason`, including every family swap and why it occurred. If no independent family can complete, the lane is incomplete and the review cannot be clean.

**Authorization and failure handling:** Automated OpenRouter selection uses the
configured-key `trusted-boundary` path from Phase 3. Missing or invalid
credentials, unavailable provider/bundle, or an automatic disclosure decline
applies Phase 4.5 lane-aware resolution without a prompt. Ordinary lanes may
retry on Codex. The
`security-auditor-codex-signoff` compatibility lane is the exception: every
retry and partial/full-decline completion must use a non-implementing family,
and exhaustion is `REVIEW INCOMPLETE`. Do not mark the run clean until required
independent work completes.

Build each reviewer prompt from the agent definition, changed files, diff, project context, and Fix Philosophy. Determine ai-memory availability from the callable-tool inventory or tool search, never by probing. When callable, preserve the existing RAG lookup and ai-memory write behavior; if absent, omit RAG silently. If a rendered UI lane is selected, include `## Visual Finding Rules` from `${CLAUDE_SKILL_DIR}/references/visual-finding-rules.md`.

#### Diff scoping per lane

A scoped lane's `## Diff` section contains only the files its Phase 3 trigger
condition selects; the lane may still read any project file it needs (a
migration validator, for instance, must read earlier migrations that are not in
the diff at all). Build that section from the slice, and always include the file
list of the WHOLE diff (names only, no hunks) under `## Files to Review`, so the
lane still sees everything that moved. A lane never receives hunks it has no
mandate over.

Slice from the lane's FULL Phase 3 condition, not from its file extensions
alone. Several triggers are broader than an extension list -- `voice-editor`
fires on "`.md` or `.txt` changed, OR user-facing text in templates", so its
slice must carry those template files too. Slicing on the extension half of a
compound trigger silently drops the other half without ever failing, which the
fail-open path below cannot catch.

**Only the lanes named in the scoped list below are ever sliced. Every other
lane receives the FULL diff, and the full-diff list takes precedence over this
general rule wherever a lane appears extension-triggered.** That precedence is
why `test-coverage-reviewer` and `governance-domain` sit in the registry's
extension-triggered table and still get the whole diff. A lane named in neither
list is a classification gap, not a licence to narrow: give it the full diff and
record `diff_scope: full` with `slice_status: unclassified`.

**Scoped lanes** -- diff sliced to the lane's Phase 3 trigger condition:

- a11y-html-reviewer
- a11y-css-reviewer
- css-reviewer
- a11y-dynamic-content-reviewer
- voice-editor
- go-build-verifier
- craft-reviewer
- migration-validator
- visual-browser-tester
- ux-quality-reviewer
- ui-standards-reviewer

**Full-diff lanes** -- never scoped, and this list is closed:

- security-auditor-codex-signoff (`routing-policy.json` sets
  `inputScope: full-diff` and `required: true`; scoping it would contradict policy)
- security-auditor-openrouter
- architecture-reviewer
- second-perspective (default agent definition: `codex-perspective.md`)
- pattern-recognition-specialist
- code-simplicity-reviewer
- doc-sync-reviewer
- test-coverage-reviewer
- governance-domain
- openrouter-bulk-analyst

The always-run judgment lanes detect cross-file problems -- a coupling
violation, a pattern duplicated across two packages, a doc that no longer
matches the code it describes -- and a sliced diff hides exactly those. Scoping
them trades coverage for bytes, which this program refuses.

"Never scoped" means never sliced to a trigger set. It does not override the
byte-bound disclosure eligibility that governs what an OpenRouter lane may be
sent: `security-auditor-openrouter` and `openrouter-bulk-analyst` still receive
only the eligible sections their runner's disclosure boundary approves. That is
a separate, unchanged mechanism.

**Receipt:** every lane passes `diff_scope` to the kernel -- `full` for an
unscoped lane, or `scoped(<n> files of <total>)` for a sliced one, where `<n>`
is the slice count and `<total>` is the whole-diff count. Pass it with
`--diff-scope`, `--full-diff-override`, and `--slice-status` on the
`record-attempt` call below; the kernel validates and binds all three directly
to the lane receipt. Do not hand-write rows into the receipt array or overload
`--fallback-reason`, which carries independent executor-fallback semantics.

**Kill switch:** `DM_REVIEW_FULL_DIFF=1` disables scoping entirely. Every lane
receives the full diff, exactly as dispatch behaved before scoping existed, and
each lane records `diff_scope: full` alongside `full_diff_override: true`.
Default OFF, which means scoping is active. The switch fails OPEN: if slice
construction fails for any lane -- unparseable diff, a trigger condition that
resolves to no files, any error at all -- that lane receives the FULL diff and
its receipt records `diff_scope: full` with `slice_status: slice_failed`. A lane
is never dispatched against a slice nobody could verify, and never skipped
because its slice came out empty; uncertainty always widens the input.

#### Parallelization rules

- Launch ALL agents in a single message with multiple Agent tool calls
- Do not wait for one agent to finish before launching the next
- Each agent runs independently with its own copy of the diff, scoped per the
  diff scoping rules above

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
`attempt_usage` row -- and either both land or neither does. That is the whole
mechanism: there is no call that records a lane without its measurement, so a
lane cannot go unmeasured by being forgotten.

Supply the strongest evidence the lane actually has:

- **OpenRouter lanes:** `--openrouter-receipt`, the wrapper's
  `OPENROUTER_RECEIPT_FILE`. Also pass `--request-envelope-sha256` from that
  attempt's preparation manifest and the canonical
  `--state-dir .workflow-kernel/runs/<run-id>`. The
  kernel requires exact equality with the digest in the wrapper receipt, so a
  receipt from another call in the same run and lane cannot be crossed in. The
  same wrapper receipt is one-use evidence and cannot be recorded for a retry;
  every real retry must supply its own wrapper receipt.
- **Codex and Claude lanes:** `--agent-definition` and `--diff` (plus any
  `--boilerplate`). Deterministic input bytes -- never a token count, never
  comparable to one.
- **Neither available:** omit both. The row records `attempt_unmeasured`, which
  states that the lane ran and nothing measured it. That is a claim a reader can
  audit. An absent row is not -- it is indistinguishable from a lane that never
  ran, and the spend disappears with it.

Record failed and declined attempts too. A lane that burned a provider call and
returned nothing still cost money.

Do **not** hand-write lane receipts into the array, and do not call
`openrouter-usage` or `lane-input-bytes` with `--append-to` for a lane you are
recording here -- that is the older two-call path this replaces, and using both
double-counts the attempt. The standalone translators remain available for
measuring something that is not a recorded lane attempt.

#### Failure handling

Apply the failure policies from `${CLAUDE_SKILL_DIR}/references/guardrails.md`:

- If a non-browser agent fails or times out (>120s), record the failure in the Agent Summary table and apply the documented lane policy. A required browser agent instead runs browser recovery and, on exhaustion, blocks with `human_help_required` and asks the user for help.
- For agents routed to external LLMs, defer failure classification to Phase 4.5 before applying these policies
- If a **core agent** (security-auditor-codex-signoff, architecture-reviewer, code-simplicity-reviewer, pattern-recognition-specialist, doc-sync-reviewer) fails after any applicable Phase 4.5 retry, flag the review as "REVIEW INCOMPLETE" in the merge recommendation. A selected security-auditor-openrouter lane is also required until it completes externally or through an allowed non-implementing-family fallback.
- If all non-browser conditional agents fail but core agents succeed, the review is "Degraded" but still valid. Missing required browser evidence is never degraded-valid.
- See `${CLAUDE_SKILL_DIR}/references/graceful-degradation.md` for the full failure classification table

---

