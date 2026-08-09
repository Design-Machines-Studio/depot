---
name: dm-review
description: Full code review with all applicable agents including visual browser testing
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Full Code Review

Run a comprehensive code review using all applicable agents for the current project stack.

## Zero-Deferral Policy (default)

All dm-review commands default to zero-deferral: P1, P2, AND P3 findings MUST be fixed before the branch is considered ready to merge. P3s fix band-aid solutions and tech debt -- deferring them is how debt compounds silently. `/dm-review` surfaces findings; `/dm-review-fix` resolves them; `/dm-review-loop` automates fix-until-clean.

The merge recommendation reflects this policy:

- **Zero findings:** `CLEAN` -- safe to merge.
- **P3 only (no P1/P2):** `APPROVE WITH FIXES -- P3s mandatory under zero-deferral.` NOT clean. Run `/dm-review-fix` (or `/dm-review-loop`) to resolve before merging.
- **P2 present:** `APPROVE WITH FIXES`. Must fix.
- **P1 present:** `BLOCKS MERGE`. Must fix.

To explicitly opt out of zero-deferral for a specific run (rare -- e.g. a P3 genuinely belongs in a different branch), pass `--allow-defer-p3`. Each deferred P3 must carry a written justification and a tracking destination.

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Full** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. Output the unified review report with merge recommendation (per the zero-deferral policy above)

## Synthesis and Contribution Contract

Every raw reviewer finding keeps a durable `raw_ref`, source-scoped identity,
agent, provider, model, evidence, and severity. Consolidation derives stable
canonical finding IDs from the finding itself, never from display order or
provider preference. Agreement merges contributor IDs; disagreement is retained
in the synthesis decision ledger and changes the decision, not the finding's
identity. A summary never substitutes for missing raw evidence.

After consolidation, materialize `synthesis-decisions.json`, the sealed raw
finding inventory, literal required-lane receipts, and machine-readable raw
output for every requested lane using the review skill's
exact structured contracts. Then use only the trusted launcher command
`export-review-contributions` to append contribution receipts that attribute retained,
superseded, duplicate, resolved, and disagreement outcomes to the contributing
attempts. These receipts are observation-only economics evidence: they cannot
select a provider, change routing, invent a finding, waive coverage, or alter
the zero-deferral recommendation. Missing raw evidence or any required lane or
browser case remains a reported coverage gap, never an implicit clean result.
The exporter rejects credential-shaped content and credential-bearing URIs
before hashing or persistence, descriptor-safely seals every raw output, and
emits a durable coverage receipt even when the raw inventory is empty.

## OpenRouter Availability Resolution

Automated external lanes are never assumed available. The review skill RESOLVES
availability into exactly three outcomes, evaluated in this order and
fail-closed at every step:

1. **Broker probe reports `ready`** -- available, `authorization_mode: broker`.
   The independently installed Workflow Authority Broker owns run-bound
   authorization, credential custody, and transport. This is the target state
   and the only permanent one.
2. **Valid unexpired batch authorization for THIS run** -- available,
   `OPENROUTER_AUTHORIZATION_MODE=interim_operator_batch`, reason
   `interim_operator_batch`. This INTERIM mode is reachable only when the
   broker client is ABSENT from the host. Its intended entry is
   `payload-authorization.sh batch-approve`, which shows the operator the lane
   list, byte totals, and digest count on the controlling terminal at run start
   and waits for a typed confirmation.
   **No environment variable substitutes for the interactive confirmation.**
   **The batch artifact is procedural and unauthenticated** -- bare JSON with
   no signature and no user-presence binding, so nothing proves the
   confirmation ever happened and a same-user process can hand-write an
   equivalent file. The confirmation guards against accidental and automated
   entry by this tooling, not against same-user forgery; the out-of-process
   Workflow Authority Broker is what closes that gap, and it is the primary
   reason for the sunset. Only digests recorded in the batch file are accepted;
   the wrapper re-checks that membership over the bytes it actually transmits,
   and any other payload falls back to the per-payload interactive path or
   fails closed.
3. **Otherwise** -- unavailable. Coding agents run on Codex. An available API
   key, runner, policy, or caller environment variable is not automated
   dispatch authority. The reason is `broker_present_not_ready` when the broker
   client is installed but does not probe ready -- an unknown state fails
   closed instead of widening exposure -- and `host_authority_unavailable`
   otherwise.

Interim mode is FORBIDDEN when a broker probe on the host reports `ready`; the
batch path refuses with `broker available; interim mode retired on this host`.
It is likewise WITHHELD when the broker client is installed but does not probe
ready. Probes are parsed with `jq -e '.status == "ready"'`, never a substring
match.
It also carries a hard calendar backstop, `program_sunset` (2026-09-07), after
which batch files fail validation and extending the program requires a reviewed
commit that re-issues the sunset in the schema. The darwin broker milestone is
scheduled inside that window.

Every lane receipt produced in interim mode carries
`authorization_mode: interim_operator_batch` plus the batch file digest, and
the review report's coverage section states that interim operator-batch
authorization was active for the run.

## Shadow Workflow Kernel Lifecycle

The review skill, selected lanes, findings, coverage receipt, merge recommendation, and repository-cleanup report remain authoritative. Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per run, following the single fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md` (launcher discovery snippet, repo-vs-cache trust boundaries, semver compatibility, and symlink/scope fail-closed rules all live there; do not restate them here).

Materialize the validated review request at `.claude/ux-review/workflow-kernel/request.json` and the cumulative ordered redacted authoritative receipt array at `.claude/ux-review/workflow-kernel/authoritative-receipts.json`. Initialize this run under `.workflow-kernel/runs/<run-id>`; the kernel derives the nearest real Git repository from the state directory and binds its canonical `.workflow-kernel` root to an immutable random scope ID plus repository/root device and inode. No caller-selected lease root is accepted, and symlink, cross-repository, scope-metadata, or run-directory mismatches fail closed. Produce independent prediction receipts before corresponding authoritative actions and seal them first:

```text
"$WORKFLOW_KERNEL" bind-prediction --type review --request .claude/ux-review/workflow-kernel/request.json --prediction-receipts .claude/ux-review/workflow-kernel/independent-prediction-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

After the authoritative consolidated review and coverage receipt exist, run exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

After terminal cleanup receipts are appended, run exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --matrix trusted-openrouter-bundle --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; [ "$s" -eq 2 ] || [ "$s" -eq 6 ]; } || printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be gated on the status (`|| { s=$?; [ "$s" -eq 2 ] || [ "$s" -eq 6 ]; } || printf ...`), because a bare `||` fires on every non-zero exit: after an exit 6 whose receipt line was already written it appends a second, contradicting skip line, and after an exit 2 it blames a launcher that demonstrably ran. Gated, the fallback covers only what no process inside the kernel can report -- the launcher itself failing to run. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. Pass `--matrix trusted-openrouter-bundle` so subscription-rail attempt usage receives a visibly imputed API-equivalent cost; an unreadable matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads: after each lane attempt, translate that attempt's OpenRouter wrapper receipt with `openrouter-usage`, or that lane's Codex/Claude input files with `lane-input-bytes`, passing `--append-to <authoritative-receipts.json> --run-id <id> --occurred-at <ISO-8601> --authoritative-receipt <path>` so the translator wraps the payload as an `attempt_usage` receipt and appends it under an exclusive lock in one validated step. Emit a row for every attempt including failed ones -- an attempt missing from the receipt stream is indistinguishable from one that never ran, and its spend disappears with it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

Inline Python source is forbidden. `bind-prediction` atomically seals the pre-action source, translated events, event digest, and request context and appends its exact authority to the canonical lifecycle ledger before `run.started`. Observation and direct comparison require that ordered binding plus the matching artifact and never create or mutate either. Byte-identical predicted and authoritative receipts are valid only with this durable pre-start authority. Keep the source input, request, authoritative receipts, `review-shadow-observation.json`, and `review-shadow-prediction.json` through comparison. Delete the prediction source and bound artifact only after semantic `match`. Missing independent prediction evidence fails closed and preserves the review result. A parity gap cannot convert `CLEAN`, `APPROVE WITH FIXES`, `BLOCKS MERGE`, or `REVIEW INCOMPLETE`; it is proposal-only evidence. Never auto-delete `.workflow-kernel/repository-scope.json`. Parity match alone never deletes terminal run state; retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches.

When a review request has no explicit `workflowClass`, translate it as `feature` with `workflow_class_defaulted=true`; never infer it from findings, diff kinds, or severity. Preserve requested/attempted/implemented-by/fallback/reason evidence for every provider lane.
