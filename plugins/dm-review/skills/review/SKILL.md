---
name: review
description: Code review orchestrator that launches parallel specialized agents across accessibility, security, architecture, CSS, voice, and governance domains. Use when reviewing code changes, PRs, branches, or files. Invoke with /dm-review for full review or /dm-review quick for core agents only. Also use when the user says "review this", "check my code", "run a code review", or "review before merging".
disable-model-invocation: true
argument-hint: "[scope: PR number, branch, path, or blank]"
---

# DM Code Review

One-command code review launching parallel specialized agents for Design Machines stacks: Go+Templ+Datastar, Craft CMS+Twig, Live Wires CSS.

## Zero-Deferral Finding Policy

Every retained P1, P2, and P3 finding is mandatory work and prevents `CLEAN`
until fixed and rechecked. Severity controls priority and merge language; it
never makes a valid finding optional. Reject speculative, duplicate, disproved,
preference-only, or scope-expanding reviewer input during consolidation instead
of retaining it as a finding and deferring it. There is no deferral flag and no
clean-with-P3s outcome. See `${CLAUDE_SKILL_DIR}/references/severity-mapping.md`
(decision tree) and `${CLAUDE_SKILL_DIR}/references/output-format.md`
(merge-recommendation logic).

Every retained finding must identify an observable current defect, its location
or reachable path, and the smallest adequate repair. Every P1/P2 must also name
the affected current user or operator and realistic harm or regression; a
security P1/P2 also names the actual trust boundary. For Design Machines work,
apply the canonical deployment context from
`${CLAUDE_SKILL_DIR}/references/deployment-context.md` (loaded before dispatch
and inlined into external reviewer prompts): default to that scale and trust
model unless approved scope says otherwise. Hypothetical actors, future
marketplaces, enterprise scale, generic OWASP possibilities, defence-in-depth
preferences, and abstractions with no current consumer are not findings. Keep
real reachable boundaries blocking: authentication or
authorization bypass, credential disclosure, unsafe destructive operations,
corruptible state or backups, public untrusted input, release/update integrity
failures, and false verification claims.

## Usage

- `/dm-review` -- Full review: all applicable agents + optional memory enrichment when callable
- `/dm-review quick` -- Quick review: 2 core judgment lanes, plus applicable existing UI/build/domain verification lanes

## Review Tiers

Default to the cheapest tier that fits.

| When | Tier | What runs |
|------|------|-----------|
| Per chunk during pipeline execution | `dm-review-quick` | 2 core judgment lanes + applicable UI/build/domain lanes |
| Pre-merge, once per PR | full `dm-review` | All applicable agents + consolidation + optional memory enrichment when callable |
| Bulk second opinions / large-diff first pass | fixed lane-to-role mapping | Family-independent security analysis plus style, duplication, pattern, and doc lanes; eligible diff sections only; mandatory full-diff independent-family sign-off |
| Bounded repair review | full + one repair | One repair batch and one affected-lane recheck; repeat broad review only when the original was incomplete or the repair changed a real sensitive boundary |

**Escalation exception:** quick review is an early feedback gate, not the final
security boundary; every PR still receives one full pre-merge review. Escalate
a chunk early only when a changed path matches this bounded set:
`internal/auth/**`, `internal/federation/**`, `**/security/**`,
`**/middleware/auth*`, `**/middleware/security*`, `**/secretbox*`,
`**/destructive_confirmation*`, `internal/baseplate/email/settings*`,
`deploy/**`, `*.env*`, or the Depot credential-transport controls
`openrouter-wrapper.sh` / `delegation-boundary.sh`. Do not widen this set to all handlers, shell scripts, dependency manifests, or configuration files. A
matching chunk skips the quick tier and runs the role-selected
`security-auditor` analysis (eligible file sections) plus the mandatory full-diff independent-family security sign-off. Sections containing actual
secrets are held from external dispatch and completed within the role fallback
boundary; path names alone never decline disclosure.

## Shadow Workflow Kernel Contract

The selected lanes, role requests, review outputs, todos, consolidation, merge recommendation, and cleanup receipts remain authoritative. Kernel prediction is observation-only and cannot select roles or participants, waive a lane, alter fallback, create a clean recommendation, execute cleanup, or convert any finding.

Resolve `$WORKFLOW_KERNEL` once per review run per the workflow-kernel plugin's
`references/runtime-resolution.md`, which owns launcher discovery, trust
boundaries, semver, symlink/scope fail-closed rules, and exit codes. Use only
stable launcher subcommands; inline Python source is forbidden. Initialize each
run at `.workflow-kernel/runs/<run-id>`; a missing or incompatible
launcher/runtime records `shadow unavailable` and the review continues.
Before creating any temporary repository/cache or raw lane output, resolve and
read Workflow Kernel's `exact-owned-cleanup.md`, start one disposable root with
`owned-run-start --workflow dm-review --run-id <run-id>`, and record every
nested disposable path through `owned-run-create`. The final report and compact
machine-readable evidence remain the requested review deliverable; raw lane
transcripts are disposable.
Translate an explicit `workflowClass` unchanged; when absent use `feature` and
record `workflow_class_defaulted=true` -- never infer it from diff kind, path,
finding, or severity. Materialize the request at
`<exact-run-root>/review/request.json` and the cumulative ordered
redacted receipt array at `authoritative-receipts.json` beside it. Observe only
after an authoritative lane/consolidation/cleanup receipt exists.

Produce independent prediction receipts before corresponding authoritative actions, then seal them exactly once:

```text
"$WORKFLOW_KERNEL" init .workflow-kernel/runs/<run-id> --run-id <run-id> --mode shadow --occurred-at <timezone-aware-ISO-8601>
"$WORKFLOW_KERNEL" bind-prediction --type review --request <exact-run-root>/review/request.json --prediction-receipts <exact-run-root>/review/independent-prediction-receipts.json --state-dir <exact-run-root>/review
```

Use these exact later observation interfaces:

```text
"$WORKFLOW_KERNEL" observe-review --request <exact-run-root>/review/request.json --receipts <exact-run-root>/review/authoritative-receipts.json --state-dir <exact-run-root>/review
"$WORKFLOW_KERNEL" compare --state-dir <exact-run-root>/review --authoritative-receipts <exact-run-root>/review/authoritative-receipts.json --output <exact-run-root>/review/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events <exact-run-root>/review/authoritative-receipts.json --output <exact-run-root>/review/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events <exact-run-root>/review/authoritative-receipts.json --output <exact-run-root>/review/run-cost-summary.json --receipt <exact-run-root>/review/run-receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> <exact-run-root>/review/run-receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> <exact-run-root>/review/run-receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file, writes a schema-bound `run-cost-summary.json` beside that run's `authoritative-receipts.json`, and appends exactly one receipt line -- the artifact path, or `run-cost-summary: skipped (<reason>)` on any internal failure. It is observation-only: it exits 0 for every measurement outcome, never gates or alters a review, lane, or phase outcome, and its absence never fails one. Exit 6 (receipt write failed after acceptance) appends `skipped (receipt-write-failed)` through the status-aware `||` fallback; exit 2 is an invalid invocation and propagates; any other non-zero status appends `skipped (kernel-unresolvable)`, and a failing final append keeps its own status visible. A refused symlinked receipt path still exits 0 and reports on stderr alone -- a non-zero exit would append through the symlink just refused. Receipt paths are fixed per directory, so concurrent runs sharing one directory overwrite each other: use the invocation's exact-owned root or serialize callers that intentionally share a documented deliverable directory. Pass a coherent installed bundle's matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; an unreadable or invalid matrix emits one stderr line, skips imputation, and never fails the emission. Populate events with `record-attempt` as each lane settles -- a standalone `--append-to` translator double-counts the attempt, and `lanes: 0` after a run that executed lanes means this boundary is not wired. Full flags: `cli-measurement-commands.md`; otherwise the flags named here are the complete required set.

If this review creates any Docker/Compose resource, load `${CLAUDE_SKILL_DIR}/references/review-docker-create.md` and follow it exactly.

## Fix Philosophy

All review agents and fix workflows follow:

1. **Smallest adequate repair** -- the clearest direct change resolving the evidenced current failure within approved scope; a one-use handler or concrete implementation is valid when clear and tested.
2. **Relevant practices first** -- framework conventions when they serve the current requirement or reachable risk; a preferred layer or abstraction is not a repair by itself.
3. **Replace, don't preserve** -- when old code is the problem, replace it; don't wrap broken patterns in compatibility layers.
4. **No scope expansion** -- a fix touches only the approved behavior and the evidenced defect. Reject unrelated hardening, future-marketplace defenses, and new product scope during consolidation; do not retain them as P3 findings.

## Orchestration Phases

Execute in order; do not skip. Majors are 1--8; lettered sub-phases run in sequence with their parent.

---

### Phase 1: Target Detection

Determine changed files; try in order: (1) PR number/URL given: `gh pr diff <number>`; (2) feature branch: `git diff main...HEAD --name-only`; (3) uncommitted: `git diff --name-only` + `git diff --cached --name-only`; (4) path given: use it. Store changed files and extensions; if none, tell the user and stop. Also capture the full diff (`git diff main...HEAD` or matching command) for the agents.

---

### Phase 1b: Evidence Source Fallback

**Absence of threads is never absence of findings.** When reviewer threads and
PR comments come back empty, or no PR exists, load
`${CLAUDE_SKILL_DIR}/references/evidence-source-fallback.md` and walk its
ordered sources. Record the source in the report header:

```text
**Evidence source:** PR threads | receipts | merge bodies | closed issues | verification files | none found
```

If every source is empty, say so explicitly and review the diff alone: a review
that found no prior evidence and stays quiet about it is indistinguishable from
one that never looked.

---

### Phase 2: Project Type Detection

| Check | Project Type |
|-------|-------------|
| `go.mod` exists | Go project |
| `docker-compose.yml` exists AND Go project | Go+Templ+Datastar |
| `craft/` or `.ddev/` directory exists | Craft CMS |
| `package.json` exists AND `.css` files changed | CSS Framework |

A project can be multiple types. Reviewing the depot itself: "Plugin Marketplace (Markdown+JSON)".

---

### Phase 3: Agent Selection

Select agents by mode, changed file extensions, and project type; resolve each through the plugin cache (resolver below). Diff size may inform budgets but never widens the quick roster by itself.

#### Provider-neutral role dispatch

dm-review selects the complete roster, review criteria, role, required
capabilities, effort, and whether family independence is required. It never
selects or receives a model, provider, transport, family, subscription, billing
rail, availability judgment, or fallback order.

Load `${CLAUDE_SKILL_DIR}/references/full-lane-dispatch.md` for the fixed
lane-to-role mapping and one-shot dispatcher contract. For independent lanes,
pass the run-private receipt registry plus opaque implementing receipt IDs;
model-router reads private family evidence and excludes every implementing
family. A verified human-authored diff uses the explicit origin flag instead.
Public lane companions and peer prompts use stable lane names and anonymous
participants only. Exact identity stays in content-free private receipts.

The dispatcher applies provider-neutral request-shape and workload eligibility
automatically. Its external boundary validates UTF-8, paths, and diff structure
without adding OpenRouter-only content screening. A structurally invalid or
unavailable rail falls through within the requested role without an approval
prompt. Broker state is not consulted.

#### Quick Mode

Ordinary quick review always selects exactly these two core judgment lanes:

1. **pattern-recognition-specialist** -- `dm-review/*/agents/review/pattern-recognition-specialist.md`
2. **code-simplicity-reviewer** -- `dm-review/*/agents/review/code-simplicity-reviewer.md`

Add only applicable lanes using their existing triggers:

- **ui-standards-reviewer** when `.templ`, `.twig`, `.html`, or `.css` files changed.
- **go-build-verifier** when `.go` or `.templ` files changed and the project has `go.mod` + `docker-compose.yml`.
- **craft-reviewer** when `.twig` or `.php` files changed and the project has `craft/` or `.ddev/`.

Do not add `second-perspective`, security, architecture, documentation, or full-mode conditional lanes to an ordinary quick review. When a security-sensitive path from the escalation exception is present, quick mode escalates to the existing full mode instead of dispatching this roster. Log the selected applicable lanes; log an unavailable or skipped lane only when its trigger made it required.

#### Always-Run Agents (Full mode)

These five review criteria always run as five logical lanes:

1. **security-auditor** -- `security-review`, independent family, full diff, always required
2. **architecture-reviewer** -- `review-deep`
3. **pattern-recognition-specialist** -- `review-deep`
4. **code-simplicity-reviewer** -- `review-deep`
5. **doc-sync-reviewer** -- `review-fast`

#### Configurable Second Perspective

`DM_REVIEW_SECOND_PERSPECTIVE` fails OPEN: unset, empty, unreadable, or any
value other than exactly `0` launches second-perspective; only exactly `0`
disables it, and a disabled lane is receipted in Coverage Gaps. The legacy name
`DM_REVIEW_CODEX_PERSPECTIVE` is still honoured -- exactly `0` in EITHER
variable disables the lane.

When enabled, add **second-perspective** as a parallel read-only
`plan-critic` at high effort in full mode only. Pass every opaque implementing
receipt ID with the run-private registry, or pass the explicit verified
human-authored origin, and require `independent-family`. Use
`dm-review/*/agents/review/codex-perspective.md` as the compatibility-named
criteria file; its filename does not select a participant. Normalize output to
P1/P2/P3 and let the consolidator merge every in-scope finding.

#### Conditional Agents (Full mode only)

Add agents by changed-file extension. Every path below is depot-relative for readability, but the orchestrator MUST resolve selected assets through Workflow Kernel before dispatch -- pipeline runs in worktrees outside the depot. Build the fixed per-plugin indexed arrays while selecting the roster: for every selected agent, strip the table's `<plugin>/*/` display prefix, set `AGENT_PLUGIN` and `AGENT_ASSET` from that row, and run the append `case` once. The dm-review array starts with the two workflow assets used later, so the required set is never empty. Resolve each non-empty plugin group once after the roster is final:

<!-- active-cache-resolution-shell:start -->
```bash
: "${WORKFLOW_KERNEL:?resolve workflow-kernel-launcher.sh once per review first}"
CACHE_ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && CACHE_ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && CACHE_ACTIVE_HOST="codex"
CACHE_ACTIVE_HOST_ARGS=()
[ -n "$CACHE_ACTIVE_HOST" ] && CACHE_ACTIVE_HOST_ARGS=(--active-host "$CACHE_ACTIVE_HOST")

DM_REVIEW_REQUIRED_ASSETS=(
  "agents/workflow/review-consolidator.md"
  "agents/workflow/review-memory-recorder.md"
  "skills/review/references/reviewer-output-contract.md"
)
ACCESSIBILITY_REQUIRED_ASSETS=()
LIVE_WIRES_REQUIRED_ASSETS=()
GHOSTWRITER_REQUIRED_ASSETS=()
COUNCIL_REQUIRED_ASSETS=()

append_selected_asset() {
  local agent_plugin="$1" agent_asset="$2"
  case "$agent_plugin" in
    dm-review) DM_REVIEW_REQUIRED_ASSETS+=("$agent_asset") ;;
    accessibility-compliance) ACCESSIBILITY_REQUIRED_ASSETS+=("$agent_asset") ;;
    live-wires) LIVE_WIRES_REQUIRED_ASSETS+=("$agent_asset") ;;
    ghostwriter) GHOSTWRITER_REQUIRED_ASSETS+=("$agent_asset") ;;
    council) COUNCIL_REQUIRED_ASSETS+=("$agent_asset") ;;
    *) echo "SKIP: optional plugin has no declared resolution floor: $agent_plugin" ;;
  esac
}
# Run this call once for every selected roster row before resolving any bundle.
append_selected_asset "$AGENT_PLUGIN" "$AGENT_ASSET"

DM_REVIEW_BUNDLE_ROOT=""
DM_REVIEW_BUNDLE_REF=""
DM_REVIEW_BUNDLE_VERSION=""
DM_REVIEW_CACHE_CLASS=""
DM_REVIEW_RESOLUTION_REASON=""
ACCESSIBILITY_BUNDLE_ROOT=""
LIVE_WIRES_BUNDLE_ROOT=""
GHOSTWRITER_BUNDLE_ROOT=""
COUNCIL_BUNDLE_ROOT=""
for PLUGIN in dm-review accessibility-compliance live-wires ghostwriter council; do
  case "$PLUGIN" in
    dm-review)
      PLUGIN_MINIMUM_VERSION="1.71.0"
      REQUIRED_ASSETS=("${DM_REVIEW_REQUIRED_ASSETS[@]}")
      ;;
    accessibility-compliance)
      PLUGIN_MINIMUM_VERSION="1.2.0"
      REQUIRED_ASSETS=("${ACCESSIBILITY_REQUIRED_ASSETS[@]}")
      ;;
    live-wires)
      PLUGIN_MINIMUM_VERSION="1.8.0"
      REQUIRED_ASSETS=("${LIVE_WIRES_REQUIRED_ASSETS[@]}")
      ;;
    ghostwriter)
      PLUGIN_MINIMUM_VERSION="3.7.0"
      REQUIRED_ASSETS=("${GHOSTWRITER_REQUIRED_ASSETS[@]}")
      ;;
    council)
      PLUGIN_MINIMUM_VERSION="1.5.0"
      REQUIRED_ASSETS=("${COUNCIL_REQUIRED_ASSETS[@]}")
      ;;
  esac
  [ "${#REQUIRED_ASSETS[@]}" -gt 0 ] || continue
  REQUIRED_ASSET_ARGS=()
  for ASSET in "${REQUIRED_ASSETS[@]}"; do
    REQUIRED_ASSET_ARGS+=(--required-asset "$ASSET")
  done
  if ! PLUGIN_BUNDLE_JSON=$("$WORKFLOW_KERNEL" resolve-plugin-bundle \
    --plugin "$PLUGIN" --minimum-version "$PLUGIN_MINIMUM_VERSION" \
    "${CACHE_ACTIVE_HOST_ARGS[@]}" "${REQUIRED_ASSET_ARGS[@]}"); then
    echo "ERROR: required plugin bundle unavailable: $PLUGIN" >&2
    exit 1
  fi
  PLUGIN_BUNDLE_REF=$(printf '%s' "$PLUGIN_BUNDLE_JSON" | jq -r '.selected_root // empty')
  case "$PLUGIN_BUNDLE_REF" in
    "~/"*) PLUGIN_BUNDLE_ROOT="$HOME/${PLUGIN_BUNDLE_REF#\~/}" ;;
    *) echo "ERROR: invalid plugin bundle root: $PLUGIN" >&2; exit 1 ;;
  esac
  if [ "$PLUGIN" = dm-review ]; then
    DM_REVIEW_BUNDLE_REF="$PLUGIN_BUNDLE_REF"
    DM_REVIEW_BUNDLE_VERSION=$(printf '%s' "$PLUGIN_BUNDLE_JSON" | jq -r '.version // empty')
    DM_REVIEW_CACHE_CLASS=$(printf '%s' "$PLUGIN_BUNDLE_JSON" | jq -r '.cache_class // empty')
    DM_REVIEW_RESOLUTION_REASON=$(printf '%s' "$PLUGIN_BUNDLE_JSON" | jq -r '.reason // empty')
  fi
  case "$PLUGIN" in
    dm-review) DM_REVIEW_BUNDLE_ROOT="$PLUGIN_BUNDLE_ROOT" ;;
    accessibility-compliance) ACCESSIBILITY_BUNDLE_ROOT="$PLUGIN_BUNDLE_ROOT" ;;
    live-wires) LIVE_WIRES_BUNDLE_ROOT="$PLUGIN_BUNDLE_ROOT" ;;
    ghostwriter) GHOSTWRITER_BUNDLE_ROOT="$PLUGIN_BUNDLE_ROOT" ;;
    council) COUNCIL_BUNDLE_ROOT="$PLUGIN_BUNDLE_ROOT" ;;
  esac
done
[ -n "$DM_REVIEW_BUNDLE_ROOT" ] || { echo "ERROR: required dm-review bundle unavailable" >&2; exit 1; }
```
<!-- active-cache-resolution-shell:end -->

The indexed arrays are the final roster's resolution projection, not a second selection mechanism. `AGENT_ASSET` is always a path such as `agents/review/<agent-id>.md`. The five bundles in this loop are required dm-review dependencies, so failure to resolve any non-empty selected group fails closed; never remove one of their selected lanes or fall back to a repository-relative path. Every path for a resolved plugin derives from its one root variable. Participant resolution is entirely in `full-lane-dispatch.md`.

| Condition | Agent | Cache-relative path components |
|-----------|-------|--------------------------------|
| `.templ`, `.twig`, or `.html` changed | **a11y-html-reviewer** | `accessibility-compliance/*/agents/review/a11y-html-reviewer.md` |
| `.css` changed | **a11y-css-reviewer** | `accessibility-compliance/*/agents/review/a11y-css-reviewer.md` |
| `.css` changed | **css-reviewer** | `live-wires/*/agents/review/css-reviewer.md` |
| `.templ`, `.js`, or `.ts` changed AND Go+Templ+Datastar | **a11y-dynamic-content-reviewer** | `accessibility-compliance/*/agents/review/a11y-dynamic-content-reviewer.md` |
| `.md` or `.txt` changed, OR user-facing text in templates | **voice-editor** | `ghostwriter/*/agents/review/voice-editor.md` |
| Any source file changed AND test infrastructure exists | **test-coverage-reviewer** -- `review-fast` | `dm-review/*/agents/review/test-coverage-reviewer.md` |
| Paths contain `governance`, `proposal`, `voting`, `member`, `resolution`, or `bylaw` | **governance-domain** | `council/*/agents/review/governance-domain.md` |
| `.go` or `.templ` changed AND `go.mod` exists | **go-build-verifier** | `dm-review/*/agents/review/go-build-verifier.md` |
| `.twig` or `.php` changed AND (`craft/` or `.ddev/` exists) | **craft-reviewer** | `dm-review/*/agents/review/craft-reviewer.md` |
| `.sql` changed under `migrations/` or `seeds/` | **migration-validator** | `dm-review/*/agents/review/migration-validator.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **visual-browser-tester** | `dm-review/*/agents/review/visual-browser-tester.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **ux-quality-reviewer** | `dm-review/*/agents/review/ux-quality-reviewer.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **ui-standards-reviewer** | `dm-review/*/agents/review/ui-standards-reviewer.md` |
| A large diff needs a bounded bulk first pass | **bulk-analyst** -- `review-deep` + `long-context` | `openrouter/*/agents/review/openrouter-bulk-analyst.md` |

#### Selective Lane Allowlist (internal loop input)

When `review_lane_allowlist` input is present, load `${CLAUDE_SKILL_DIR}/references/selective-lane-allowlist.md` and apply its validation contract exactly. When absent, run the recomputed selected full set and record `selective_input_absent`.

#### Report Selection

After selecting agents, tell the user:

```
Launching X agents for [project type] review ([Full/Quick] mode):
- [agent-name-1]
- [agent-name-2]

Skipping Y agents:
- [agent-name] -- reason (e.g., "no .css files changed")
```

---

### Phase 3.25: Design Spec Discovery

If the change includes `.templ`, `.twig`, `.html`, or `.css`, load `${CLAUDE_SKILL_DIR}/references/design-spec-discovery.md` and inject any found spec as `## Design Spec Context`.

### Phase 3.5: Input Guardrails

Before dispatching agents, apply `${CLAUDE_SKILL_DIR}/references/guardrails.md`:

1. **Diff size check:** >5000 lines -> retain the complete diff for every core lane while its materialized input remains below ~80K tokens. Conditional lanes may receive the file list plus the first 200 lines per file and must record truncation. If a core lane exceeds the ceiling, use a repository-capable candidate or mark coverage incomplete; prompt-only review never settles omitted bytes. A selected bulk lane receives the full untruncated diff when it fits.
2. **Structural boundary:** Materialize each lane's exact input. model-router applies provider-neutral request-shape and structural validation automatically. Credentials, private keys, classified material, auth/security/deployment code, and `.env` content remain eligible whenever a native candidate may receive them. Malformed or unverifiable evidence falls through within the role; content never creates OpenRouter-only held paths.
3. **Per-agent token check:** Estimate ~2K system prompt + (diff lines × ~4 tokens) + ~4K output headroom. If >~80K tokens, drop the lowest-priority non-browser conditional agents per the degradation order in `${CLAUDE_SKILL_DIR}/references/guardrails.md`. Core agents and browser agents required by the verification profile are never dropped; if required browser input cannot fit safely, block with `human_help_required` and ask the user to narrow or restore the verification input.

If any agents were dropped or input was modified, report before proceeding:

```
Input guardrails applied:
- Diff truncated from 8,200 to 5,000 lines (200 lines/file cap)
- reviewer-a completed through a role-level fallback after structural validation failed.
- Blocked required browser lane: human_help_required (token budget; user input needed)
```

---

### Phase 3.75: Role Dispatch Reference

Load `${CLAUDE_SKILL_DIR}/references/full-lane-dispatch.md`. It owns the closed
lane-to-role mapping and anonymous public receipt. Do not load a provider/model
table or print concrete routing identity.

---

### Phase 4: Parallel Agent Launch

In **both modes**, before dispatching any lane, load `${CLAUDE_SKILL_DIR}/references/reviewer-prompt-template.md` and build every reviewer prompt from that common contract. Launch every selected lane in one message.

In **quick** mode, dispatch only the selected core/triggered lanes through their
mapped roles. Give the two core judgment lanes the full diff and slice each
triggered lane (`go-build-verifier`, `craft-reviewer`,
`ui-standards-reviewer`) to its trigger files. Keep the established diff-scope
and attempt receipts.

In **full** mode, follow `${CLAUDE_SKILL_DIR}/references/full-lane-dispatch.md`
exactly. Agent files are review criteria only; model-router is the single
resolution, availability, invocation, fallback, and private-provenance boundary.

As each lane settles, record it with `record-attempt`, its anonymous lane
companion, and the private router receipt reference. Never copy exact identity
into another lane's prompt or the ordinary report.

### Phase 4.5: Lane Fallback

A failed, declined, or unavailable lane must be named. Load `${CLAUDE_SKILL_DIR}/references/lane-fallback.md` only when that happens.

There is no additional authorization or caller-owned fallback rail. When this
review is Pipeline's final full dm-review, “record the gap and continue” and the
headless gap-and-continue default are unavailable. Independent lanes pass opaque
receipt IDs; only private router receipts retain family evidence.

### Phase 5: Consolidation

After all agents complete, synthesize findings into the unified report.

#### Output guardrails (apply first)

Per `${CLAUDE_SKILL_DIR}/references/guardrails.md`: (1) **Structure check** -- each agent output carries severity classifications (P0/P1/P2/P3 or Critical/Serious/Moderate) or a no-findings indicator; flag malformed outputs. (2) **Ghost file check** -- discard findings referencing files not in the changed list. (3) **Findings cap** -- >25 findings from one agent truncates to top 25 by severity. (4) **Failure summary** -- timeouts, errors, and empty returns are recorded in the Agent Summary table.

#### Consolidation steps

Read the consolidator from the dm-review root already bound for the selected required asset set:

```bash
CONSOLIDATOR_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-consolidator.md"
RECORDER_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-memory-recorder.md"
[ -f "$CONSOLIDATOR_PATH" ] || { echo "ERROR: bound dm-review consolidator missing" >&2; exit 1; }
```

Read from `$CONSOLIDATOR_PATH` and follow it exactly:

1. **Collect** all findings, including entries excluded from canonical counts by output guardrails, assigning each an addressable ID and recording its literal lane, role, anonymous participant, evidence, and `raw_ref`. Raw reviewer artifacts remain untouched and are never replaced by the summary.
2. **Assign stable identity** as `finding-v1:sha256(<normalized-key>)`: lowercase POSIX path + smallest stable structural anchor (normalized line span only if no anchor exists) + normalized issue category + whitespace-collapsed root-cause invariant, excluding reviewer/participant/role/severity/remediation/discovery order. Input reorder preserves IDs; severity disagreement changes the ledger, not identity.
3. **Classify and decide** using `agreement: unique|corroborated|disputed` independently from `finding_disposition: retained|merged|discarded`, each with a rationale and a closed reason code. Preserve contradictions, source severities, selected severity, and evidence rationale; exact duplicates do not inflate counts and distinct root causes stay separate but receive sorted reciprocal cross-ID dispute links when positions contradict. A linked root-cause position is disputed, never unique. Reproducible test/runtime evidence outranks direct HEAD evidence, diff/context evidence, standards-based reasoning, and reviewer consensus.
4. **Map severity** per `${CLAUDE_SKILL_DIR}/references/severity-mapping.md`.
5. **Determine merge recommendation** per `${CLAUDE_SKILL_DIR}/references/output-format.md` §Merge Recommendation Logic: any P1 -> "BLOCKS MERGE"; any P2 -> "APPROVE WITH FIXES"; any P3 with no P1 -> "APPROVE WITH FIXES"; zero findings -> "CLEAN".
6. **Generate the unified report** following `${CLAUDE_SKILL_DIR}/references/output-format.md`, including required P1/P2/P3 detail, `Synthesis Decisions`, and the compact Raw Evidence Index from existing receipts; never copy full reviewer output.

Materialize the decisions, sealed raw-finding inventory, and literal lane receipts as `synthesis-decisions.json`, `raw-finding-inventory.json`, `review-lane-receipts.json`, and `raw-lane-outputs.json`. Then invoke the trusted launcher -- the sole producer of canonical contribution IDs, receipt sequences, and the durable coverage receipt:

```bash
"$WORKFLOW_KERNEL" export-review-contributions \
  --request <exact-run-root>/review/request.json \
  --decisions <exact-run-root>/review/synthesis-decisions.json \
  --raw-findings <exact-run-root>/review/raw-finding-inventory.json \
  --lane-receipts <exact-run-root>/review/review-lane-receipts.json \
  --raw-lane-outputs <exact-run-root>/review/raw-lane-outputs.json \
  --receipts <exact-run-root>/review/authoritative-receipts.json \
  --state-dir <exact-run-root>/review \
  --output <exact-run-root>/review/authoritative-receipts.json
```

The command rejects credential-shaped content and credential-bearing URIs before hashing or persistence, content-addresses all four canonical inputs and every raw lane output under `contribution-inputs/`, and fails closed unless raw inventory, synthesis decisions, literal lane provenance, finding counts, raw lane-output union, and lane evidence references agree exactly. Exactly one receipt and raw output is required per requested lane, including zero-finding lanes; never hand-author `canonical_finding_id`, `sequence`, `finding_contribution`, or coverage receipts. A zero-finding synthesis still runs the command with count zero and all required lane receipts so missing producer coverage is observable.

Keep the consolidated report body provisional through the remaining phases. Do not write `.claude/ux-review/report.md` or deliver the compact human handoff yet: mandatory repository cleanup in Phase 8 supplies the report's final cleanup truth.

#### Coverage receipt and shadow observation

Emit an authoritative coverage receipt after consolidation with one row per selected lane and per required verification case: role, requested/effective effort, anonymous participant, fallback/reason, completed/degraded/unavailable status, finding count, and evidence reference. Required browser rows bind persona, scenario, concrete route, engine, viewport, authentication state, evaluation, attempt, and recovery receipt. Missing or failed required rows keep the review `REVIEW INCOMPLETE` or blocked; they are never omitted from a clean report.

The receipt also records whether `review_lane_allowlist` was received and its disposition (`APPLIED`, `DISCARDED`, or `ABSENT`; a discarded input records the exact closed-set reason). It records the exact set of logical lanes actually `DISPATCHED` on this pass and the exact set in the recomputed selected full set that were deliberately `NOT_DISPATCHED` because an applied allowlist omitted them. The caller verifies the restriction against this receipt rather than assuming it was honored. Deliberately not-dispatched lanes under an applied allowlist are distinct from missing or failed required rows and do not by themselves make the review `REVIEW INCOMPLETE`; a dispatched lane that does not complete still does.

Only after this receipt exists, run `observe-review` when the trusted runtime is available. The earlier `bind-prediction` atomically seals the independent source, translated events, event digest, and RunSpec context as `review-shadow-prediction.json`, then appends binding evidence while the run is still `planned`; the next transition must be `run.started`, and observation/compare reject missing, post-start, reordered, or artifact-mismatched authority. Byte-identical prediction and authoritative sources are valid when this pre-start ordering proves independence. Observation requires the matching artifact and never creates it; source and bound artifact remain through comparison. `.workflow-kernel/repository-scope.json` is repository-lifetime durable and never auto-deleted. After fresh exact-scope Docker inventory proves zero exact-run objects, success removes terminal run state and disposable roots; failure/interruption may retain only one bounded diagnostic root. Adapter failure or semantic parity gap is appended to the compact report without changing consolidation. At the terminal boundary, `compare` and `metrics` report `match`, `explained_host_difference`, `explained_host_economics_difference`, `missing_authoritative_evidence`, `unexpected_authoritative_transition`, `kernel_prediction_gap`, or `unsafe_to_promote`; economics differences are explicit non-matches and internal diagnostics appear only in `differences`.

#### Verify-before-close gate

Before any stale, already-fixed, or close disposition is applied to an existing finding, require code-evidence re-verification at HEAD; a single-pass assessment scan is not enough. Acceptable evidence: `grep`/`rg` proving the cited pattern is gone or the guard exists; a focused test/build command exercising the cited path; direct file inspection at current `HEAD`. If evidence is missing or points the other way, keep the finding open and route every retained severity through the normal fix flow. Record the command or file evidence when marking anything stale or already fixed.

**Airlift checkpoint (`dm-review-consolidation`):** When the optional `airlift`
plugin is installed, load `${CLAUDE_SKILL_DIR}/references/airlift-checkpoint.md`
and fire its `dm-review-consolidation` checkpoint once the consolidated report
exists, so partially-complete findings survive a usage cap, rate limit, or model
switch. When airlift is absent, skip it silently and do not load that file.


---

### Phase 6: Issue Tracking

After consolidation, determine tracking method automatically:

**1. If `todos/` exists** in the project root -- use text file tracking automatically; do NOT ask the user. Create todo files for every retained P1, P2, and P3 finding.

**2. If `todos/` does not exist** -- ask the user:

```
No todos/ directory found. How should I track these findings?
1. Create todos/ directory with text file tracking
2. GitHub Issues
```

Tracking may change location, but it never waives the finding or permits a clean recommendation. Do not offer a skip or defer option.

**Text file tracking:** First clean stale completed files: `rm -- todos/*-done-*.md 2>/dev/null`. Create `todos/` if missing. For each retained finding, create `todos/{id}-pending-{priority}-{slug}.md` per the template in `${CLAUDE_SKILL_DIR}/references/issue-tracking.md` (e.g. `todos/001-pending-p1-sql-injection-in-search.md`), then summarize what was created and name `/dm-review-fix` as the resolver. After the pending todo files are written and the optional `airlift` plugin is installed, load `${CLAUDE_SKILL_DIR}/references/airlift-checkpoint.md` and fire its `dm-review-findings` checkpoint so the `todos/*-pending-*.md` findings survive a usage cap, rate limit, or model switch before `/dm-review-fix` runs; when airlift is absent, skip it silently.

**GitHub Issues:** If tracking via GitHub Issues, load `${CLAUDE_SKILL_DIR}/references/review-github-tracking.md`.

### Phase 7: Optional Memory Enrichment (Full mode only)

Skip in Quick mode. Determine ai-memory availability from the callable-tool inventory or tool search, never by invoking a memory tool as a probe. When callable, preserve the existing RAG lookup and ai-memory write behavior. Load `${CLAUDE_SKILL_DIR}/references/review-optional-enrichment.md` only when those tools are callable. If absent, omit Phase 7 and 7b silently. Callable-tool failures append `Memory capture: failed -- <safe reason>` without blocking.

### Phase 8: Repository Cleanup

Runs in **every mode** (quick and full), on every exit path -- including `REVIEW INCOMPLETE`, `BLOCKS MERGE`, and a stalled convergence loop. Read `${CLAUDE_SKILL_DIR}/references/repo-cleanup-contract.md`; it is authoritative.

dm-review creates no worktrees, so its obligations are narrower than pipeline's:

1. **Do not adopt or prune refs.** Query only exact refs this invocation registered. Pre-existing/user refs and interrupted Pipeline refs are foreign.
2. **Delete only branches this review created** -- in practice the batch-cleanup branch from `references/issue-tracking.md`, and only once decision-table row 1 passes.
3. **Leave foreign refs alone.** Orphan `.worktrees/pipeline/**` paths and `pipeline/**` branches from an interrupted pipeline run are not dm-review's to delete; report them under "Remaining after cleanup" with a follow-up command. Deleting a ref you did not create is how a review loses someone's work.
4. **Assert a clean tree.** `git status --porcelain` empty, or the exact residue listed.
5. **Emit the inventory.** The `### Repository Cleanup` block in the report (see `references/output-format.md`).

If this review created Docker resources for a dev server or review harness, load `${CLAUDE_SKILL_DIR}/references/review-docker-cleanup.md` and follow it exactly: clean only resources registered by this review, after validation, consolidation, and browser evidence are authoritative, writing the complete fresh dependent-node status proof before planning and again before every guarded execute.

After comparison and fresh exact-scope Docker inventory prove zero resources,
remove the exact `.workflow-kernel/runs/<run-id>/` directory and finish the
disposable root. Review abort before execution uses outcome `review-aborted`.
On failure or `SIGINT`/`SIGTERM`, retain nothing unless one compact diagnostic
root is genuinely useful. Its terminal report must state the exact path, reason,
contents, and exact removal command; never retain both a kernel run root and a
dirty worktree. Install this same Phase 8 sequence on every exit path.

Never delete the feature branch under review. There is no condition under which a code review deletes the branch it was asked to review.

---

### Finalize Report and Deliver Handoff

Only after Phase 8 has completed, add its authoritative repository and Docker cleanup results to the provisional unified report. Then write the complete report to `.claude/ux-review/report.md` -- the existing dm-review artifact flow, not a new report subsystem.

Deliver the compact human handoff after that write, following `references/output-format.md`. Preserve the complete unified report and all machine-readable companions in the established evidence flow. The compact handoff links `.claude/ux-review/report.md` and names any blocked cleanup requiring operator action. Do not dump the expanded report, provider tables, agent transcripts, synthesis ledger, cleanup inventory, or raw reports into visible chat by default.

---

## Reference Files

Loaded on demand during review: `reviewer-prompt-template.md` (common reviewer prompt contract, loaded before dispatch in both modes), `selective-lane-allowlist.md` (only when `review_lane_allowlist` input is present), `severity-mapping.md` (P1/P2/P3 mapping), `agent-registry.md` (agent catalog and triggers), `output-format.md` (report template), `issue-tracking.md` (todo template and GitHub conventions), `guardrails.md` (input/output validation, failure policies), `graceful-degradation.md` (failure classification and merge overrides), `ai-slop-detector.md` (25-point AI output checklist), `ui-design-patterns.md`, `token-discovery.md`, `repo-cleanup-contract.md` (exact worktree/branch registry, safe-to-delete table, feature-branch protection, inventory; shared with pipeline), and `datastar-pro.md` (Pro attributes/actions, substitution table, bundle-presence rule). All under `${CLAUDE_SKILL_DIR}/references/`.

## Agent Definition Paths

See `${CLAUDE_SKILL_DIR}/references/agent-registry.md` for the complete catalog. Files: `plugins/dm-review/agents/review/*.md`, `plugins/{accessibility-compliance,live-wires,ghostwriter,council}/agents/review/*.md`, `plugins/dm-review/agents/workflow/*.md`.

## Notes

- Agent definitions are read at runtime from the depot; if the exact path is inaccessible (remote install), search by file name.
- Maximum 16 parallel agents (full mode, all triggers). Ordinary quick mode has 2 core lanes plus triggered UI/build/domain lanes.
- Routed agent cards inherit participant selection from the caller's role request.
- The consolidator and memory recorder run after all review agents complete, never in parallel.
