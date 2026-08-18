---
name: review
description: Code review orchestrator that launches parallel specialized agents across accessibility, security, architecture, CSS, voice, and governance domains. Use when reviewing code changes, PRs, branches, or files. Invoke with /dm-review for full review or /dm-review quick for core agents only. Also use when the user says "review this", "check my code", "run a code review", or "review before merging".
disable-model-invocation: true
argument-hint: "[scope: PR number, branch, path, or blank]"
---

# DM Code Review

A single-command code review system that launches parallel specialized agents tailored to Design Machines stacks: Go+Templ+Datastar, Craft CMS+Twig, and Live Wires CSS.

## Zero-Deferral Finding Policy

Every retained P1, P2, and P3 finding is mandatory work and prevents `CLEAN`
until fixed and rechecked. Severity controls priority and merge language; it
never makes a valid finding optional. Reject speculative, duplicate, disproved,
preference-only, or scope-expanding reviewer input during consolidation instead
of retaining it as a finding and deferring it. There is no deferral flag and no
clean-with-P3s outcome. See `${CLAUDE_SKILL_DIR}/references/severity-mapping.md`
for the decision tree and `${CLAUDE_SKILL_DIR}/references/output-format.md` for
the merge-recommendation logic.

Every retained finding must identify an observable current defect, its location
or reachable path, and the smallest adequate repair. Every P1/P2 must also name
the affected current user or operator and realistic harm or regression. A
security P1/P2 must additionally name the actual trust boundary. For Design
Machines work, default to the current context unless approved scope says
otherwise: two developers, primarily private first-party repositories, trusted
Fixture authors, and self-hosted co-op applications serving roughly 4--50
people. Do not invent a public Fixture marketplace or hostile third-party
plugin channel. Hypothetical actors, future marketplaces, enterprise scale, a
generic OWASP possibility, defence-in-depth preferences, and abstractions with
no current consumer are not findings.

Keep real reachable boundaries blocking at their supported severity: authentication or authorization bypass, credential disclosure, unsafe destructive operations, corruptible state or backups, public untrusted input, release/update integrity failures, and false verification claims.

## Reviewer Output Style (applies to all review agents)

Every review agent dispatched by this skill operates under a terse-output contract:

- No preamble sentences ("I'll review...", "Let me check...", "Here is my analysis..."). Start with the first finding.
- No summary paragraphs. The consolidator composes the summary.
- Findings are structured blocks (severity, file:line, description, fix). One block per finding, no prose between.
- An agent that found nothing writes exactly one line: `<agent-name>: clean.` Nothing more.
- Every sentence must advance a specific finding or state a verified fact. If you catch yourself narrating your process, delete that sentence.

## Usage

- `/dm-review` -- Full review: all applicable agents + optional memory enrichment when callable
- `/dm-review quick` -- Quick review: 2 core judgment lanes, plus applicable existing UI/build/domain verification lanes

## Review Tiers

Default to the cheapest tier that fits.

| When | Tier | What runs |
|------|------|-----------|
| **Per chunk during pipeline execution** | `dm-review-quick` | 2 core judgment lanes, plus applicable existing UI/build/domain verification lanes. |
| **Pre-merge, once per PR** | full `dm-review` | All applicable agents + consolidation + optional memory enrichment when callable. Run once, not per chunk. |
| **Bulk second opinions / large-diff first pass** | Model selected by `routing-policy.json` | Family-independent security analysis plus style, duplication, pattern, and doc-consistency lanes. The exact diff is content-scanned immediately before external disclosure; sensitive file sections stay local while eligible sections proceed. Security completion always includes mandatory full-diff independent-family sign-off. |
| **Bounded repair review** | full + one repair | Use one repair batch and one affected-lane recheck for supported P1/P2/P3 findings. Repeat broad review only when the original required review was incomplete or the repair changed a real sensitive boundary. |

**Escalation exception:** quick review is an early feedback gate, not the final
security boundary. Every PR still receives one full pre-merge review. Escalate
a chunk early only when a changed path matches this bounded deterministic set:

- `internal/auth/**`, `internal/federation/**`, `**/security/**`,
  `**/middleware/auth*`, or `**/middleware/security*`
- `**/secretbox*`, `**/destructive_confirmation*`,
  `internal/baseplate/email/settings*`, `deploy/**`, or `*.env*`
- Depot credential-transport controls named `openrouter-wrapper.sh` or
  `delegation-boundary.sh`

Do not widen this set to all handlers, shell scripts, dependency manifests, or
configuration files. For these small self-hosted applications, that would turn
ordinary quick review back into a security fan-out. A matching chunk skips the
quick tier and runs both the matrix-selected `security-auditor` analysis (for
eligible file sections) and the mandatory full-diff independent-family security sign-off.
File sections containing actual secret/private data stay on an eligible native
family; path names alone never decline disclosure.

## Shadow Workflow Kernel Contract

The selected agents, provider routing, review outputs, todos, consolidation, merge recommendation, and cleanup receipts remain authoritative. Kernel prediction is observation-only and cannot select lanes, waive a lane, alter fallback, create a clean recommendation, execute cleanup, or convert any finding.

Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per review run, following the single fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md` (launcher discovery snippet, repo-vs-cache trust boundaries, semver compatibility, symlink and scope fail-closed rules, and stable exit codes all live there; do not restate them here). Use only the launcher's stable subcommands; inline Python source is forbidden. Initialize each review run at `.workflow-kernel/runs/<run-id>`. Missing or incompatible launcher/runtime records `shadow unavailable` and the canonical review continues.

Translate an explicit `workflowClass` unchanged; when absent, use `feature` and record `workflow_class_defaulted=true`. Never infer it from diff kind, path, finding, or severity. Materialize that request at `.claude/ux-review/workflow-kernel/request.json` and the cumulative ordered redacted receipt array at `.claude/ux-review/workflow-kernel/authoritative-receipts.json`. Observe only after an authoritative lane/consolidation/cleanup receipt exists. At the end, compare and aggregate metrics without changing review state. Shadow events and builder observations never replace authoritative dispatch/resume receipts.

Produce independent prediction receipts before corresponding authoritative actions, then seal them exactly once:

```text
"$WORKFLOW_KERNEL" init .workflow-kernel/runs/<run-id> --run-id <run-id> --mode shadow --occurred-at <timezone-aware-ISO-8601>
"$WORKFLOW_KERNEL" bind-prediction --type review --request .claude/ux-review/workflow-kernel/request.json --prediction-receipts .claude/ux-review/workflow-kernel/independent-prediction-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

Use these exact later observation interfaces:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be status-aware: exit 6 triggers one final append of `skipped (receipt-write-failed)`, exit 2 is explicitly propagated as an invalid invocation, and every other non-zero status appends `skipped (kernel-unresolvable)`. If the final append also fails, its non-zero status remains visible instead of being erased. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. The caller resolves a coherent installed-plugin bundle and passes its model-matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; the kernel validates both bundle containment and matrix structure without owning a provider dependency. An unreadable or invalid matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads through `record-attempt` as each lane settles; that one atomic call appends the lane outcome and exactly one `attempt_usage` row under the same lock. Pass the OpenRouter wrapper receipt when present, otherwise pass the exact Codex/Claude input files for deterministic byte measurement; when neither exists, the paired row explicitly records `attempt_unmeasured`. Do not also call a standalone translator with `--append-to` for that attempt, because doing both double-counts it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

If review setup creates any Docker/Compose resource, invoke exactly one planning interface:

If this review creates any Docker/Compose resource, load `${CLAUDE_SKILL_DIR}/references/review-docker-create.md` and follow it exactly.

## Fix Philosophy

All review agents and fix workflows must follow these principles:

1. **Smallest adequate repair** -- Recommend the clearest direct change that resolves the evidenced current failure within approved scope. A one-use handler or concrete implementation is valid when clear and tested.
2. **Relevant practices first** -- Apply framework conventions when they serve the current requirement or reachable risk; a preferred layer or abstraction is not a repair by itself.
3. **Replace, don't preserve** -- When old code is the problem, recommend replacing it. Don't wrap broken patterns in compatibility layers.
4. **No scope expansion** -- A required fix may touch only the approved behavior and the evidenced defect. Reject unrelated hardening, future-marketplace defenses, and new product scope during consolidation; do not retain them as P3 findings.

## Orchestration Phases

Execute these phases in order. Do not skip phases. The numbered majors are 1 through 8; several carry lettered sub-phases (1b, 2.5, 3.25, 3.5, 3.75, 4.5, 5.5, 7b, 7c) that run in sequence with their parent.

---

### Phase 1: Target Detection

Determine what files changed. Try these sources in order:

1. **If a PR number or URL was given:** `gh pr diff <number>`
2. **If on a feature branch:** `git diff main...HEAD --name-only`
3. **If uncommitted changes exist:** `git diff --name-only` + `git diff --cached --name-only`
4. **If a specific path was given:** use that path directly

Store the list of changed files and their extensions. If no changes detected, tell the user and stop.

Also get the full diff content for the agents:
```bash
git diff main...HEAD  # or appropriate diff command based on the target
```

---

### Phase 1b: Evidence Source Fallback

Reviewer threads and PR comments are frequently empty even when the work was reviewed -- the evidence lives elsewhere. **Absence of threads is never absence of findings.** An empty `gh pr view --comments` is not a clean bill.

When PR review threads and comments come back empty, or no PR exists, fall through these sources in order and use the first that yields evidence:

1. **Checked-in receipts** -- `plans/*/receipt.md` (evidence table, branch/worktree inventory), Auth Boundary Map receipts in the PR body or `docs/`, JSON and screenshot receipts under `.claude/ux-review/`.
2. **Merge-commit bodies** -- `git log --merges --format='%B' <base>..HEAD`. Decisions and trade-offs are recorded there when recorded nowhere else.
3. **Closed-issue references in the diff range** -- `git log <base>..HEAD --format=%B | grep -oE '#[0-9]+'`, then `gh issue view <n>` for each. A closed issue names the requirement the diff was meant to satisfy.
4. **Verification files** -- `tests/`, `tests/ux/`, `docs/runbooks/`, and any conformance-harness cases the diff added.

Record the source in the report header:

```text
**Evidence source:** PR threads | receipts | merge bodies | closed issues | verification files | none found
```

If every source is empty, say so explicitly and review the diff alone. That is a valid state -- but a *reported* one. A review that found no prior evidence and stays quiet about it is indistinguishable from a review that never looked.

---

### Phase 2: Project Type Detection

Detect the project type by checking for marker files in the project root:

| Check | Project Type |
|-------|-------------|
| `go.mod` exists | Go project |
| `docker-compose.yml` exists AND Go project | Go+Templ+Datastar |
| `craft/` directory exists OR `.ddev/` directory exists | Craft CMS |
| `package.json` exists AND `.css` files changed | CSS Framework |

A project can be multiple types (e.g., Go+Templ+Datastar with CSS).

If reviewing the depot itself, project type is "Plugin Marketplace (Markdown+JSON)".

---

### Phase 3: Agent Selection

Select which agents to launch based on mode, changed file extensions, and project type. Resolve each agent's path via the plugin cache (see conditional agents table below for the canonical resolver pattern). Diff size may inform existing budgets, but never widens the quick roster by itself.

**Coding-provider boundary:** Claude is not a coding implementation rail. Core code review, security, architecture, UI, and test review use policy-derived families regardless of legacy agent frontmatter. A native Claude family may run the read-only `second-perspective` or independent-family security sign-off only when the implementing family is different. Claude may also run clearly non-coding lanes such as voice/editorial review, research synthesis, or strategy.

#### Routing Policy for Mechanical Agents

For API candidates, "quality-per-price" means the explicit ordered role in
`routing-policy.json`, after family exclusions; `quality_rank` is only a
compatibility floor. Ordinary second perspective starts Qwen3.8 Max then Grok
4.6. Security starts Kimi K3 then Grok 4.6.

Read `plugins/pipeline/references/routing-policy.json` before selecting models **when it is present**. When dm-review is installed standalone, use the inline model table. Family means provider lineage: OpenAI/Codex, Anthropic/Claude, and each OpenRouter-served third party under its own vendor family; OpenRouter is a transport, not a family. The second-perspective reviewer model family MUST differ from the family that implemented the diff under review. For a mixed-family diff, treat every contributing family as implementing and select outside that set. The same family exclusion applies to the mandatory full-diff security sign-off.

Resolve both family-independent roles subscription-first: an eligible non-implementing family with live subscription headroom for both `five_hour` and `weekly` beats every API family, then use the applicable ordered role in `routing-policy.json` after removing implementing families. Ordinary second perspective uses `second-perspective`; security sign-off uses its dedicated implementer-aware route. Unknown subscription headroom is treated as at-threshold, never as available. Do not start a planned multi-chunk review whose projected subscription spend would cross the threshold mid-run. Apply `.dm/operator-profile.local.json` only after policy derivation: it may rank and remove derived candidates, never add one or override `neverOfferable`, disclosure/security controls, or family independence. No profile means policy defaults. This is the remove-only precedence defined by `plugins/pipeline/references/operator-profile-schema.json` (`properties.precedence`), not a separate override system.

Every `second-perspective` and independent-family security sign-off receipt records `implementer_family`, `reviewer_family`, and `resolution_reason`. For mixed implementation, `implementer_family` records `mixed(<sorted families>)`. A receipt with equal implementing and reviewing families is invalid and leaves the required lane incomplete.

**Before selecting agents, check external routing availability:**

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
  resolve_openrouter_bundle() {
    if [ -n "$OPENROUTER_ACTIVE_HOST" ]; then
      "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
        --minimum-version 1.15.0 --active-host "$OPENROUTER_ACTIVE_HOST" \
        --required-asset agents/workflow/openrouter-agent-runner.md \
        --required-asset agents/review/openrouter-bulk-analyst.md \
        --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
        --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
        --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
        --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
        --required-asset skills/openrouter-delegate/references/model-matrix.json \
        --required-asset skills/openrouter-delegate/references/prompt-templates.md
    else
      "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
        --minimum-version 1.15.0 \
        --required-asset agents/workflow/openrouter-agent-runner.md \
        --required-asset agents/review/openrouter-bulk-analyst.md \
        --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
        --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
        --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
        --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
        --required-asset skills/openrouter-delegate/references/model-matrix.json \
        --required-asset skills/openrouter-delegate/references/prompt-templates.md
    fi
  }
  BUNDLE_JSON=$(resolve_openrouter_bundle) || BUNDLE_JSON=""
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

When available, eligible mechanical, bulk, and supplementary security lanes
dispatch immediately. The runner materializes private outbound files, scans
them once, and passes those same files to the wrapper. A
missing/invalid key, unavailable bundle/provider, or automatic disclosure
decline records the reason and retries the lane on Codex without asking the
user. Broker presence, absence, readiness, or degradation is not consulted.

#### Quick Mode

Ordinary quick review always selects exactly these two core judgment lanes:

1. **pattern-recognition-specialist** -- `dm-review/*/agents/review/pattern-recognition-specialist.md`
2. **code-simplicity-reviewer** -- `dm-review/*/agents/review/code-simplicity-reviewer.md`

Add only applicable lanes using their existing triggers:

- **ui-standards-reviewer** when `.templ`, `.twig`, `.html`, or `.css` files changed.
- **go-build-verifier** when `.go` or `.templ` files changed and the project has `go.mod` + `docker-compose.yml`.
- **craft-reviewer** when `.twig` or `.php` files changed and the project has `craft/` or `.ddev/`.

Do not add `second-perspective`, security, architecture, documentation, or full-mode conditional lanes to an ordinary quick review. When a security-sensitive path from the escalation exception is present, quick mode escalates to the existing full mode instead of dispatching this roster.

Log the selected applicable lanes. Log an unavailable or skipped lane only when its trigger made it required; do not manufacture rows for every agent in the plugin.

#### Always-Run Agents (Full mode)

These 5 review criteria run as 6 logical lanes when OpenRouter is available:

1. **security-auditor-codex-signoff** -- compatibility lane ID for `dm-review/*/agents/review/security-auditor.md` -- **independent family, full diff, always required**
2. **security-auditor-openrouter** -- same criteria -- **Kimi K3, eligible sections only, selected only when OpenRouter is available**
3. **architecture-reviewer** -- `dm-review/*/agents/review/architecture-reviewer.md` -- **Codex**
4. **pattern-recognition-specialist** -- `dm-review/*/agents/review/pattern-recognition-specialist.md` -- **OpenRouter when available** (`routing-policy.json` model ladder)
5. **code-simplicity-reviewer** -- `dm-review/*/agents/review/code-simplicity-reviewer.md` -- **OpenRouter when available** (`routing-policy.json` model ladder)
6. **doc-sync-reviewer** -- `dm-review/*/agents/review/doc-sync-reviewer.md` -- **OpenRouter when available** (`routing-policy.json` model ladder)

#### Configurable Second Perspective

`DM_REVIEW_SECOND_PERSPECTIVE` fails OPEN: when it is unset, empty, unreadable, or any value other than exactly `0`, launch second-perspective. Only exactly `0` disables it, and a disabled lane must be receipted in Coverage Gaps. The legacy name `DM_REVIEW_CODEX_PERSPECTIVE` is still honoured for back-compat -- exactly `0` in EITHER variable disables the lane -- so an operator who had it switched off before the role was renamed does not get it silently switched back on.

When the lane is enabled, add **second-perspective** as a parallel read-only reviewer in full mode only. This is the default dual-perspective review lane at the integration boundary; it caught distinct blockers in real pipeline closeout runs. Independence is the property that caught those blockers, so this role is not tied to the orchestrating harness or a named provider.

Resolve the role by the subscription-first family rules above. When the implementer is OpenAI/Codex, select native Claude if both subscription windows have headroom; otherwise walk the ordered `second-perspective` role (`qwen/qwen3.8-max`, then `x-ai/grok-4.6`) after excluding every implementing family. Never resolve back to OpenAI/Codex for that diff. When another family implemented the diff, Codex is the preferred resolution when its subscription has headroom, followed by that same filtered ordered role.

Use `dm-review/*/agents/review/codex-perspective.md` as the compatibility-named default agent definition for the role. Dispatch it on the resolved family, normalize output to P1/P2/P3, and let the consolidator merge every finding as in-scope. The filename does not select the provider.

#### Conditional Agents (Full mode only)

Add these agents based on which file extensions appear in the changed files:

**Note on agent paths:** every path in the table below is depot-relative for readability, but the orchestrator MUST resolve selected assets through Workflow Kernel before dispatch -- pipeline runs in worktrees outside the depot where these paths do not exist. Build the fixed per-plugin indexed arrays below while selecting the roster: for every selected agent, strip the table's `<plugin>/*/` display prefix, set `AGENT_PLUGIN` and `AGENT_ASSET` from that row, and run the append `case` once. The dm-review array starts with the two workflow assets used later, so the required set is never empty. Resolve each non-empty plugin group once after the roster is final:

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
    openrouter) ;; # Its complete runner bundle was bound earlier in Phase 3.
    *) echo "SKIP: optional plugin has no declared resolution floor: $agent_plugin" ;;
  esac
}
# Run this call once for every selected roster row before resolving any bundle.
append_selected_asset "$AGENT_PLUGIN" "$AGENT_ASSET"

DM_REVIEW_BUNDLE_ROOT=""
ACCESSIBILITY_BUNDLE_ROOT=""
LIVE_WIRES_BUNDLE_ROOT=""
GHOSTWRITER_BUNDLE_ROOT=""
COUNCIL_BUNDLE_ROOT=""
for PLUGIN in dm-review accessibility-compliance live-wires ghostwriter council; do
  case "$PLUGIN" in
    dm-review)
      PLUGIN_MINIMUM_VERSION="1.62.0"
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

The indexed arrays are the final roster's resolution projection, not a second selection mechanism. `AGENT_ASSET` is always a path such as `agents/review/<agent-id>.md`. The five bundles in this loop are required dm-review dependencies, so failure to resolve any non-empty selected group fails closed; never remove one of their selected lanes or fall back to a repository-relative path. Every path for a resolved plugin is derived from its one simple root variable. The dm-review root therefore binds its selected agents, consolidator, and recorder coherently. OpenRouter remains outside this loop: Phase 3 preserves its separate optional availability check and Codex retry behavior.

| Condition | Agent | Cache-relative path components |
|-----------|-------|--------------------------------|
| `.templ`, `.twig`, or `.html` changed | **a11y-html-reviewer** | `accessibility-compliance/*/agents/review/a11y-html-reviewer.md` |
| `.css` changed | **a11y-css-reviewer** | `accessibility-compliance/*/agents/review/a11y-css-reviewer.md` |
| `.css` changed | **css-reviewer** | `live-wires/*/agents/review/css-reviewer.md` |
| `.templ`, `.js`, or `.ts` changed AND project is Go+Templ+Datastar | **a11y-dynamic-content-reviewer** | `accessibility-compliance/*/agents/review/a11y-dynamic-content-reviewer.md` |
| `.md` or `.txt` changed, OR user-facing text in templates | **voice-editor** | `ghostwriter/*/agents/review/voice-editor.md` |
| Any source file changed AND test infrastructure exists | **test-coverage-reviewer** -- **OpenRouter when available** (1800s) | `dm-review/*/agents/review/test-coverage-reviewer.md` |
| Paths contain `governance`, `proposal`, `voting`, `member`, `resolution`, or `bylaw` | **governance-domain** | `council/*/agents/review/governance-domain.md` |
| `.go` or `.templ` changed AND `go.mod` exists | **go-build-verifier** | `dm-review/*/agents/review/go-build-verifier.md` |
| `.twig` or `.php` changed AND (`craft/` or `.ddev/` exists) | **craft-reviewer** | `dm-review/*/agents/review/craft-reviewer.md` |
| `.sql` changed under a migrations directory (`migrations/` or `seeds/`) | **migration-validator** | `dm-review/*/agents/review/migration-validator.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **visual-browser-tester** | `dm-review/*/agents/review/visual-browser-tester.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **ux-quality-reviewer** | `dm-review/*/agents/review/ux-quality-reviewer.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **ui-standards-reviewer** | `dm-review/*/agents/review/ui-standards-reviewer.md` |
| `routing-policy.json` selects OpenRouter for bulk read, docs, mechanical checks, or large-context synthesis AND `OPENROUTER_AVAILABLE=true` | **openrouter-bulk-analyst** | `openrouter/*/agents/review/openrouter-bulk-analyst.md` |

#### Selective Lane Allowlist (internal loop input)

Build the normal roster first, exactly as the Phase 3 subsections above require. Call this completed roster the recomputed selected full set. Apply any selective allowlist only as a filter over that completed selection; `review_lane_allowlist` never participates in computing the roster.

`review_lane_allowlist` is an internal loop-to-review input passed only by `dm-review-loop`. It is not a user-facing flag, is not an environment variable, and cannot be set by a user. When it is absent, run the recomputed selected full set exactly as before and record `selective_input_absent`.

Consume `review_lane_allowlist` only when the recomputed selected full set exactly equals the caller's declared `selected_full_set`, with the same members, no more and no fewer, regardless of order; and the caller's `lanes` is a non-empty subset of that set containing only unique exact logical lane IDs. Duplicates, aliases, unknown IDs, and criterion-level IDs shared by more than one logical lane are invalid. In particular, `security-auditor-codex-signoff` and `security-auditor-openrouter` are distinct logical lanes that share one criterion, so bare `security-auditor` is a criterion-level ID and is invalid. Exact equality for `selected_full_set` is mandatory: it proves the caller and receiver agree on the full roster at this moment. If the diff changed between the caller's computation and Phase 3 recomputation, the sets differ and the receiver discards the input; never relax this equality check to a subset check.

For a full-mode allowlist that omits `security-auditor-codex-signoff`, also
require the internal input to carry all three exact fields:
`verification_basis: "affected_lane_repair"`,
`prior_full_review_complete: true`, and
`security_boundary_changed: false`. Only `dm-review-loop` produces this input.
These fields prove that the integration boundary already completed and that
the repair did not touch the bounded escalation set above. Missing, false, or
malformed proof discards the allowlist and runs the full roster.

Any validation failure discards the entire selective input and dispatches the unfiltered recomputed selected full set. Never drop invalid members and honor the remainder. Use only this closed reason set, applying the first matching reason in the order listed: `selective_input_absent` when no input was received; `selective_input_malformed` when the input is not an object with string-array `selected_full_set` and `lanes` members; `selected_full_set_mismatch` when the declared and recomputed full sets are unequal; `selective_lanes_empty` when `lanes` is empty; `selective_lanes_duplicated` when `lanes` contains duplicates; `selective_lanes_ambiguous_or_aliased` when `lanes` contains an alias or a criterion-level ID; `selective_lanes_not_subset` when `lanes` contains an unknown ID or a lane outside the recomputed selected full set; and `selective_lanes_omit_required_lane` when `lanes` omits a mandatory lane that the unfiltered review would require. The coverage receipt returns this exact reason, never a generic invalid-input reason.

The independent-family security sign-off, `security-auditor-codex-signoff`, is
mandatory for the initial full review, incomplete full-review recovery, and
security-boundary repairs. It may be omitted only by the proven affected-lane
repair case above. Otherwise, if the recomputed selected full set requires it
but `lanes` omits it, discard the entire allowlist, dispatch the unfiltered
roster, and report `selective_lanes_omit_required_lane`. Never silently drop a
required lane and never silently add it back to an otherwise honored allowlist.

When the input is honored, dispatch only the exact lanes in `lanes`. Every member of the recomputed selected full set outside `lanes` is a deliberate selective non-dispatch, not a failed lane, and must be identified that way in the coverage receipt. A selective affected-lane repair verification can support `CLEAN` only after an earlier complete full review, when no P1/P2/P3 findings remain and every required selected verification lane completes. It never substitutes for the initial full-review boundary.

#### Report Selection

After selecting agents, tell the user:

```
Launching X agents for [project type] review ([Full/Quick] mode):
- [agent-name-1]
- [agent-name-2]
- ...

Skipping Y agents:
- [agent-name] -- reason (e.g., "no .css files changed")
```

---

### Phase 3.25: Design Spec Discovery

If the change includes `.templ`, `.twig`, `.html`, or `.css`, load `${CLAUDE_SKILL_DIR}/references/design-spec-discovery.md` and inject any found spec as `## Design Spec Context`.

### Phase 3.5: Input Guardrails

Before dispatching agents, apply the input guardrails from `${CLAUDE_SKILL_DIR}/references/guardrails.md`:

1. **Diff size check:** Count diff lines. If >5000, truncate to file list + first 200 lines per file. Note truncation in each agent's prompt. If `openrouter-bulk-analyst` is active, it receives the full untruncated diff separately.
2. **Content boundary:** Codex lanes receive the complete review diff. Each
   OpenRouter lane independently runs the shared mechanical content boundary
   and transmits only its eligible file-diff sections. Path names alone never
   remove content from Codex review. A full disclosure decline returns the
   logical lane to Codex; a partial decline requires exact locally held-path
   completion before that lane is complete.
3. **Per-agent token check:** Estimate per-agent input: ~2K system prompt + (diff lines * ~4 tokens) + ~4K output headroom. If per-agent estimate exceeds ~80K tokens, drop the lowest-priority non-browser conditional agents per the degradation order in `${CLAUDE_SKILL_DIR}/references/guardrails.md`. Core agents and browser agents required by the verification profile are never dropped. If required browser input cannot fit safely, block with `human_help_required` and ask the user to narrow or restore the verification input; do not proceed without the lane.

If any agents were dropped or input was modified, report before proceeding:

```
Input guardrails applied:
- Diff truncated from 8,200 to 5,000 lines (200 lines/file cap)
- Stripped 2 sensitive files from non-security agents: .env, config/secrets.yml
- Blocked required browser lane: human_help_required (token budget; user input needed)
```

---

### Phase 3.75: Provider Routing Reference

Routing decisions come from `plugins/pipeline/references/routing-policy.json`, with inline notes above for readability. This section documents the technical details for Phase 4 dispatch.

**OpenRouter models + timeouts** (used in Phase 4 Branch A dispatch):

| Agent ID | Primary model slug | Fallback model slug | Timeout |
|---|---|---|---|
| `security-auditor-openrouter` | `moonshotai/kimi-k3` | `x-ai/grok-4.6` | 3600s |
| `pattern-recognition-specialist` | `deepseek/deepseek-v4-pro-0813` | `qwen/qwen3.8-max` | 1800s |
| `code-simplicity-reviewer` | `qwen/qwen3.8-max` | `deepseek/deepseek-v4-pro-0813` | 1800s |
| `doc-sync-reviewer` | `deepseek/deepseek-v4-flash-0731` | `openai/gpt-5.6-luna` | 1800s |
| `test-coverage-reviewer` | `deepseek/deepseek-v4-flash-0731` | `openai/gpt-5.6-luna` | 1800s |
| `openrouter-bulk-analyst` | `qwen/qwen3.8-max` | `deepseek/deepseek-v4-pro-0813` | 3600s; 7200s at or above 10K diff lines |

When `routing-policy.json` supplies `model` and `fallbackModel`, those full OpenRouter slugs override the inline table. The table is the standalone dm-review fallback. Both models are invoked through the OpenRouter wrapper and billed to the OpenRouter rail.

**Routing report** -- print before Phase 4:

```
Provider routing (OPENROUTER_AVAILABLE={true|false}, authorization={trusted-boundary|none}):
- N analyses -> OpenRouter (Kimi security only; DeepSeek pattern/docs/tests; Qwen simplicity/bulk/ordinary second perspective)
- N native coding agents -> Codex (architecture, visual/UI, unavailable-provider and sensitive-section coverage)
- 1 required security sign-off -> resolved independent family (full diff)
- 1 second perspective -> resolved independent family when enabled
- N non-coding agents -> Claude when explicitly selected (for example voice/editorial)
```

#### Automatic disclosure boundary

The configured key authorizes eligible development dispatch. Each runner
materializes its exact system/user bytes, scans those private files once, and
immediately invokes the wrapper. A credential/private-key
match, authenticated DSN, access/session token, or explicitly classified
private/regulated value declines automatically and returns that lane to Codex.
There is no approval prompt, broker probe, or sunset. The wrapper receipt
records a request-envelope digest without prompt or response content.

---

### Phase 4: Parallel Agent Launch

Launch every selected lane in one message. In **quick** mode, dispatch only the selected core/triggered lanes using Branch B (Codex) unless a named full-mode exception applies.

In **full** mode, load `${CLAUDE_SKILL_DIR}/references/full-lane-dispatch.md` and follow Branches A–D exactly. Bulk-analyst files are review criteria only; the generic runner is the single boundary, authorization, invocation, fallback, and provenance implementation. a Claude `Agent` call is not a valid Branch A launcher. Mixed diffs send only `--mode mechanical-review` remainders. On a non-Codex host, pipe reviewer prompts to `codex exec -s read-only -c service_tier=fast --skip-git-repo-check -`.

As each lane settles, record it with `record-attempt`. Supply `--openrouter-receipt` and `--request-envelope-sha256` for OpenRouter lanes, `--agent-definition` for Codex/Claude lanes, or omit both so the row records `attempt_unmeasured`.

### Phase 4.5: Lane Fallback

A failed, declined, or unavailable lane must be named. Load `${CLAUDE_SKILL_DIR}/references/lane-fallback.md` only when that happens.

There is no additional authorization or fallback rail. Ordinary in-policy OpenRouter/Codex routing remains unaffected. When this review is the pipeline's final full dm-review, “record the gap and continue” and the headless gap-and-continue default are unavailable.

Resolve the lane before its provider. For `security-auditor-codex-signoff`, all three signals instead continue only to another non-implementing family; do not complete the held paths on the implementing family. Tag independent fallback `[independent-family-fallback/{reviewer-family}/{agent-name}]`. Independent sign-off may try each policy-derived non-implementing family at most once.

Every machine-readable contribution decision and lane companion also records normalized `implementer_family`, `reviewer_family`, and `resolution_reason`.

### Phase 5: Consolidation

After all agents complete, synthesize their findings into the unified report.

#### Output guardrails (apply first)

Before merging findings, apply the output guardrails from `${CLAUDE_SKILL_DIR}/references/guardrails.md`:

1. **Structure check:** Verify each agent output contains severity classifications (P0/P1/P2/P3 or Critical/Serious/Moderate) or a no-findings indicator. Flag malformed outputs.
2. **Ghost file check:** Discard any finding referencing a file not in the changed files list.
3. **Findings cap:** If any agent returned >25 findings, truncate to top 25 by severity.
4. **Failure summary:** For agents that timed out, errored, or returned empty, record status in the Agent Summary table.

#### Consolidation steps

Read the consolidator from the dm-review root already bound for the selected required asset set:

```bash
CONSOLIDATOR_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-consolidator.md"
RECORDER_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-memory-recorder.md"
[ -f "$CONSOLIDATOR_PATH" ] || { echo "ERROR: bound dm-review consolidator missing" >&2; exit 1; }
```

Read from `$CONSOLIDATOR_PATH` and follow the instructions exactly:

1. **Collect** all findings from all agent outputs, including entries excluded
   from canonical counts by output guardrails, assigning each source finding
   an addressable ID and recording its literal
   lane/provider/model/agent, evidence, and `raw_ref`. Raw reviewer artifacts
   remain untouched and are never replaced by the summary.
2. **Assign stable identity** in the exact form
   `finding-v1:sha256(<normalized-key>)`, where the normalized key is lowercase
   POSIX path + smallest stable structural anchor (normalized line span only if
   no anchor exists) + normalized issue category + whitespace-collapsed
   root-cause invariant. Exclude reviewer/provider/model/severity/remediation/
   discovery order. Input reorder preserves IDs and decisions; severity
   disagreement changes the ledger, not identity.
3. **Classify and decide** using `agreement: unique|corroborated|disputed`
   independently from `finding_disposition: retained|merged|discarded`. Every
   source finding gets a rationale and a closed reason code. Preserve
   contradictions, source severities, selected severity, and evidence rationale;
   exact duplicates do not inflate counts and distinct root causes stay separate
   but receive sorted reciprocal cross-ID dispute links when their positions
   contradict. A linked root-cause position is disputed, never unique.
   Reproducible test/runtime evidence outranks direct HEAD evidence, diff/context
   evidence, standards-based reasoning, and reviewer consensus.
4. **Map severity** using the rules in `${CLAUDE_SKILL_DIR}/references/severity-mapping.md`
5. **Determine merge recommendation** using `${CLAUDE_SKILL_DIR}/references/output-format.md` §Merge Recommendation Logic. In summary:
   - Any P1 -> "BLOCKS MERGE"
   - Any P2 -> "APPROVE WITH FIXES"
   - Any P3 with no P1 -> "APPROVE WITH FIXES"
   - Zero findings -> "CLEAN"
6. **Generate the unified report** following the template in `${CLAUDE_SKILL_DIR}/references/output-format.md`, including the compact required `Synthesis Decisions` section and full raw agent reports.

Materialize the decisions, sealed raw-finding inventory, and literal lane
receipts described by `references/output-format.md` as
`synthesis-decisions.json`, `raw-finding-inventory.json`,
`review-lane-receipts.json`, and `raw-lane-outputs.json`. Then invoke the trusted launcher; this is the sole
producer of canonical contribution IDs, receipt sequences, and the durable
coverage receipt:

```bash
"$WORKFLOW_KERNEL" export-review-contributions \
  --request .claude/ux-review/workflow-kernel/request.json \
  --decisions .claude/ux-review/workflow-kernel/synthesis-decisions.json \
  --raw-findings .claude/ux-review/workflow-kernel/raw-finding-inventory.json \
  --lane-receipts .claude/ux-review/workflow-kernel/review-lane-receipts.json \
  --raw-lane-outputs .claude/ux-review/workflow-kernel/raw-lane-outputs.json \
  --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json \
  --state-dir .claude/ux-review/workflow-kernel \
  --output .claude/ux-review/workflow-kernel/authoritative-receipts.json
```

The command rejects credential-shaped content and credential-bearing URIs
before hashing or persistence, content-addresses all four canonical inputs and
every raw lane output under `contribution-inputs/`, and
fails closed unless the raw inventory, synthesis decisions, literal lane
provenance, finding counts, raw lane-output union, and lane evidence references
agree exactly. Exactly one receipt and raw output is required per requested
lane, including lanes with zero findings. Never hand-author
`canonical_finding_id`, `sequence`, `finding_contribution`, or contribution
coverage receipts. A zero-finding synthesis still runs the command with count
zero and all required lane receipts so missing producer coverage is observable.

Keep the consolidated report body provisional through the remaining phases.
Do not write `.claude/ux-review/report.md` or deliver the compact human handoff
yet: mandatory repository cleanup in Phase 8 supplies the report's final
cleanup truth. The finalization and delivery boundary follows Phase 8.

#### Coverage receipt and shadow observation

Emit an authoritative coverage receipt after consolidation with one row per selected lane and per required verification case. Each row names requested/attempted/implemented-by provider, fallback/reason, completed/degraded/unavailable status, finding count, and evidence reference. Required browser rows bind persona, scenario, concrete route, engine, viewport, authentication state, evaluation, attempt, and recovery receipt. Missing or failed required rows keep the review `REVIEW INCOMPLETE` or blocked; they are never omitted from a clean report.

The receipt also records whether `review_lane_allowlist` was received and whether its disposition was `APPLIED`, `DISCARDED`, or `ABSENT`. An absent input records `selective_input_absent`; a discarded input records the exact closed-set reason from Phase 3. It records the exact set of logical lanes actually `DISPATCHED` on this pass and the exact set in the recomputed selected full set that were deliberately `NOT_DISPATCHED` because an applied allowlist omitted them. The caller verifies the restriction against this receipt rather than assuming it was honored: because the receipt reports what was dispatched, a receiver that silently ignored, partially honored, or over-dispatched the allowlist is detectable rather than invisible. Deliberately not-dispatched lanes under an applied allowlist are distinct from missing or failed required rows and do not by themselves make the review `REVIEW INCOMPLETE`; a dispatched lane that does not complete still does.

Only after this receipt exists, run `observe-review` when the trusted runtime is available. The earlier `bind-prediction` command atomically seals the independent source, translated events, event digest, and RunSpec context as `review-shadow-prediction.json`, then appends exact binding evidence to the canonical lifecycle ledger while the run is still `planned`. The next lifecycle transition must be `run.started`; observation and direct comparison reject missing, post-start, reordered, or artifact-mismatched authority. Byte-identical prediction and authoritative sources are valid when this durable pre-start ordering proves independence. Observation requires the matching artifact and never creates or changes it. The source input and bound artifact remain until comparison; only an exact semantic match permits their post-match deletion. `.workflow-kernel/repository-scope.json` is repository-lifetime durable and never auto-deleted. Parity match alone never deletes terminal run state: retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches. Adapter failure or semantic parity gap is appended to the report without changing consolidation. At the terminal boundary, `compare` and `metrics` report `match`, `explained_host_difference`, `explained_host_economics_difference`, `missing_authoritative_evidence`, `unexpected_authoritative_transition`, `kernel_prediction_gap`, or `unsafe_to_promote`; economics differences are explicit non-matches and internal diagnostics such as `semantic_receipts_required` and `run_spec_receipt_context_mismatch` appear only in `differences`.

#### Verify-before-close gate

Before any stale, already-fixed, already fixed, or close disposition is applied to an existing finding, require code-evidence re-verification at HEAD. A single-pass assessment scan is not enough.

Acceptable evidence:

- `grep` or `rg` proving the cited vulnerable pattern is gone or the expected guard now exists.
- A focused test/build command that exercises the cited path.
- Direct file inspection at the current `HEAD` showing the finding no longer applies.

If evidence is missing or points the other way, keep the finding open and route
every retained severity through the normal fix flow. Record the command or file
evidence in the report when marking anything stale or already fixed.

**Airlift checkpoint (`dm-review-consolidation`):** Fire a tier-1 airlift checkpoint once the consolidated report exists so partially-complete review findings survive a usage cap, rate limit, or model switch. This is a guarded resolve-from-cache: it is tier-1 deterministic (pure local file + git work, NO model budget, no agent call, no network) and is skipped silently when airlift is absent (OPTIONAL dependency). On an early-warning trip (e.g. a budget threshold crossed mid-run), do not wait for the next phase boundary -- flush this checkpoint immediately so the consolidated findings are not lost.

```bash
ENGINE=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ENGINE=$(ls -t "$CACHE"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)
  [ -n "$ENGINE" ] && break
done
if [ -n "$ENGINE" ] && [ -x "$ENGINE" ]; then bash "$ENGINE" write --phase dm-review-consolidation; fi
```

The `[ -n "$ENGINE" ]` guard covers "airlift not installed"; the `[ -x "$ENGINE" ]` guard covers "resolved a path but not executable." Both guards sit within 3 lines of the `airlift-engine.sh` invocation.

---

### Phase 6: Issue Tracking

After consolidation, determine tracking method automatically:

**1. If `todos/` directory exists** in the project root -- use text file tracking automatically. Do NOT ask the user. Create todo files for every retained P1, P2, and P3 finding.

**2. If `todos/` does not exist** -- ask the user:

```
No todos/ directory found. How should I track these findings?
1. Create todos/ directory with text file tracking
2. GitHub Issues
```

Tracking may change location, but it never waives the finding or permits a
clean recommendation. Do not offer a skip or defer option.

**Text file tracking:**

Before creating new todo files, clean up stale completed files from previous sessions:

```bash
rm -- todos/*-done-*.md 2>/dev/null
```

Create `todos/` directory if it doesn't exist. For each retained finding, create a file following the template in `${CLAUDE_SKILL_DIR}/references/issue-tracking.md`:

```
todos/{id}-pending-{priority}-{slug}.md
```

Examples:
```
todos/001-pending-p1-sql-injection-in-search.md
todos/002-pending-p2-missing-csrf-protection.md
todos/003-pending-p3-heading-rhythm.md
```

After creating all files, summarize what was created:
```
Created N todo files in todos/:
- 001-pending-p1-... (description)
- 002-pending-p2-... (description)
- 003-pending-p3-... (description)

Resolve with: /dm-review-fix
```

**GitHub Issues:**

If tracking via GitHub Issues, load `${CLAUDE_SKILL_DIR}/references/review-github-tracking.md`.

### Phase 7: Optional Memory Enrichment (Full mode only)

Skip in Quick mode. Determine ai-memory availability from the callable-tool inventory or tool search, never
by invoking a memory tool as a probe. When callable, preserve the existing RAG lookup and ai-memory write behavior. Load `${CLAUDE_SKILL_DIR}/references/review-optional-enrichment.md` only when those tools are callable. If absent, omit Phase 7 and 7b silently. Callable-tool failures append `Memory capture: failed -- <safe reason>` without blocking.

### Phase 8: Repository Cleanup

Runs in **every mode** (quick and full), on every exit path -- including `REVIEW INCOMPLETE`, `BLOCKS MERGE`, and a stalled convergence loop. Read `${CLAUDE_SKILL_DIR}/references/repo-cleanup-contract.md`; it is authoritative.

dm-review creates no worktrees. Its obligations are narrower than pipeline's:

1. **Prune stale registrations.** `git worktree prune`, then confirm `git worktree list --porcelain` reports no `prunable` entries.
2. **Delete only branches this review created.** In practice that is the batch-cleanup branch from `references/issue-tracking.md`, and only once decision-table row 1 passes (`git merge-base --is-ancestor <branch> <target>` exits 0). Nothing else.
3. **Leave foreign refs alone.** Orphan `.worktrees/pipeline/**` paths and `pipeline/**` branches from an interrupted pipeline run are **not** dm-review's to delete. Report them under "Remaining after cleanup" with a follow-up command and move on. Deleting a ref you did not create is how a review loses someone's work.
4. **Assert a clean tree.** `git status --porcelain` empty, or the exact residue listed.
5. **Emit the inventory.** The `### Repository Cleanup` block in the report (see `references/output-format.md`).

dm-review may create Docker resources for a dev server or review harness. Clean only resources registered by this review after validation, consolidation, and browser evidence are authoritative. Atomically write the complete fresh authoritative dependent-node status proof before planning and again before every guarded execute. For node cleanup, invoke exactly:

If this review created Docker resources, load `${CLAUDE_SKILL_DIR}/references/review-docker-cleanup.md` and follow it exactly.

Never delete the feature branch under review. There is no condition under which a code review deletes the branch it was asked to review.

---

### Finalize Report and Deliver Handoff

Only after Phase 8 has completed, add its authoritative repository and Docker
cleanup results to the provisional unified report. Then write the complete report to `.claude/ux-review/report.md`.
This is the existing dm-review artifact flow, not a new report subsystem.

Deliver the compact human handoff after that write, following
`references/output-format.md`. Preserve the complete unified report and all
machine-readable companions in the established evidence flow. The compact
handoff links `.claude/ux-review/report.md` and names any blocked cleanup that
requires operator action. Do not dump the expanded report, provider tables,
agent transcripts, synthesis ledger, cleanup inventory, or raw reports directly
into visible chat by default.

---

## Reference Files

These files are loaded on demand during the review process:

- `${CLAUDE_SKILL_DIR}/references/severity-mapping.md` -- P1/P2/P3 mapping rules per agent
- `${CLAUDE_SKILL_DIR}/references/agent-registry.md` -- Complete agent catalog with trigger conditions
- `${CLAUDE_SKILL_DIR}/references/output-format.md` -- Unified report template
- `${CLAUDE_SKILL_DIR}/references/issue-tracking.md` -- Todo file template and GitHub Issue conventions
- `${CLAUDE_SKILL_DIR}/references/guardrails.md` -- Input/output validation rules, failure policies, deduplication precision
- `${CLAUDE_SKILL_DIR}/references/graceful-degradation.md` -- Failure classification, degradation priority, merge recommendation overrides
- `${CLAUDE_SKILL_DIR}/references/ai-slop-detector.md` -- 25-point AI output quality checklist (used by ux-quality-reviewer and ui-standards-reviewer)
- `${CLAUDE_SKILL_DIR}/references/ui-design-patterns.md` -- Practical UI patterns with Live Wires vocabulary
- `${CLAUDE_SKILL_DIR}/references/token-discovery.md` -- CSS token discovery protocol for review agents
- `${CLAUDE_SKILL_DIR}/references/repo-cleanup-contract.md` -- Worktree/branch registry, safe-to-delete decision table, feature-branch protection, inventory format (shared with pipeline)
- `${CLAUDE_SKILL_DIR}/references/datastar-pro.md` -- Datastar Pro attributes/actions, JS substitution table, bundle-presence rule, correctness traps

## Agent Definition Paths

See `${CLAUDE_SKILL_DIR}/references/agent-registry.md` for the complete agent catalog with trigger conditions, file matchers, and source plugins. Agent definition files are organized as:

- **dm-review agents:** `plugins/dm-review/agents/review/*.md`
- **Depot-native agents:** `plugins/{accessibility-compliance,live-wires,ghostwriter,council}/agents/review/*.md`
- **Workflow agents:** `plugins/dm-review/agents/workflow/*.md`

## Notes

- Agent definition files are read at runtime from the depot. If the exact path is not accessible (e.g., installed as a remote plugin), search for the file by name.
- The maximum number of parallel agents is 16 (full mode, all triggers hit). Ordinary quick mode always has 2 core lanes and adds only triggered UI/build/domain verification lanes.
- Agents default to `sonnet`. Agents that declare `model:` in their frontmatter use that model instead (e.g., go-build-verifier uses `haiku` for mechanical build checks).
- The consolidator and memory recorder run after all review agents complete -- they are not launched in parallel with the review agents.
