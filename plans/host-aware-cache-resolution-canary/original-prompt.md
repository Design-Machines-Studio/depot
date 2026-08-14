# Original Prompt

## User Input

You are executing the single current Depot P1 chunk: Issue #28 as a measured
cheap-path canary.

Repository:
https://github.com/Design-Machines-Studio/depot

Current trusted origin/main at preparation time:
a1094889b0461579a744d2ba159a41c6e394d081

Do not modify, stash, reset, rebase, or clean the dirty primary checkout at
/home/ned/ai/depot. Fetch and prune origin, inspect all current worktrees, then
create or reuse one clean worktree at:

/home/ned/ai/depot-cache-resolution-canary

Branch:

fix/host-aware-cache-resolution

Base it on current origin/main. If origin/main has advanced, adapt to the new
trusted state rather than forcing the prepared commit.

Read completely:

- AGENTS.md and every directly referenced instruction
- CLAUDE.md
- Issue #28
- the active section of plans/depot-efficiency-program.md
- workflow-kernel runtime-resolution.md
- the current OpenRouter model-selection and Pipeline routing-policy references
- relevant validators and existing bundle-resolution tests

Refresh PR, Issue, and Assembly Coordination Project state before changing
anything. Move Issue #28 from Next to In progress once the branch/worktree is
active. Project field updates are authorized; closing or substantially rewriting
the Issue is not.

## Objective

Remove the remaining reachable path by which Pipeline or dm-review can silently
select stale assets merely because the Claude cache is searched before the
Codex cache.

The release-preflight Codex cache check already exists and passed during the
latest release. Do not rebuild, expand, or duplicate it.

Prefer the existing Workflow Kernel `resolve-plugin-bundle` or
`resolve-plugin-asset` behavior:

- highest compatible semantic version wins across both caches;
- active host breaks equal-version ties;
- required assets are selected from one coherent plugin root;
- missing optional plugins remain a graceful skip.

Do not create another resolver framework, generic abstraction, background
service, broker, authorization mechanism, or cache synchronization daemon.

Start by proving the affected runtime path is still reachable. Concentrate on
the active Pipeline and dm-review paths. Do not sweep historical prompts or
unrelated optional plugins merely to make the diff comprehensive.

If no reachable stale-selection path remains, stop without manufacturing code.
Provide exact evidence and recommend how Issue #28 should be resolved.

## Canary execution

Use the literal installed `/pipeline` workflow for one bounded implementation
chunk. This prompt approves only that one-chunk scope.

Required manifest posture:

- one config/mechanical-logic chunk;
- expected executor: OpenRouter’s configured `openrouter_exec` route;
- expected worker head: `deepseek/deepseek-v4-flash-0731`;
- native Codex 5.6 is the supervisor;
- low uncertainty and low consequence;
- `renderedSurface: not_applicable`;
- no browser work;
- quick/focused verification;
- `noMergeOnCompletion: true`.

Before the paid call, obtain the required fresh OpenRouter price/availability
receipt through the installed read-only control plane. Do not update the model
matrix or routing policy in this chunk.

Do not force a provider if executable policy rejects the route. Record that as
a canary result. Do not invoke Kimi, GLM, a full dm-review, or repeated
adversarial review.

Allow one cheap-model implementation attempt. Native Codex then inspects every
changed line, tests it, removes unnecessary complexity, and makes at most one
bounded repair pass. Codex must not redo the task automatically: record what it
accepted, rejected, or rewrote from the worker.

## Scope boundaries

Do not change:

- Workflow Authority or any broker code;
- routing-policy.json, model-cascade.json, or model-matrix.json;
- Issue #54 or the planning-coordinator skill;
- plans/depot-efficiency-program.md;
- unrelated plugin surfaces;
- product or Fixture repositories.

Do not modify Workflow Kernel runtime code unless a focused failing test proves
the existing resolver itself is defective. Reusing it is the expected solution.

Bump only plugins whose shipped behavior changes. Treat this as a patch fix
unless the actual public contract proves otherwise. Regenerate derived Codex
manifests and command aliases where required.

## Acceptance

Prove with mutation-sensitive fixtures that:

1. A stale Claude cache cannot beat a newer compatible Codex cache.
2. A stale Codex cache cannot beat a newer compatible Claude cache.
3. Equal versions prefer the active harness.
4. Required assets come from one coherent root.
5. Missing optional dependencies still skip gracefully.
6. Active Pipeline/dm-review consumers cannot regress to the old first-root
   lookup without a validator failing.
7. No unrelated resolver framework or cache-sync machinery was added.

Run focused affected tests, then:

- ./tools/generate-codex-manifests.py --check
- ./tools/generate-codex-command-skills.py --check
- ./tools/validate-dual-compat.sh
- ./tools/validate-workflow-contracts.sh
- ./tools/validate-openrouter-resolution.sh
- ./tools/validate-composition.sh --all
- git diff --check

Do not run release preflight, tag, merge, or synchronize installed caches. The
planning coordinator handles release work after merge.

## Measurement

Preserve the Pipeline attempt and cost receipts. Record compactly:

- requested and served model;
- matrix snapshot and live price observation;
- input/output tokens and billed cost when reported;
- elapsed worker and total elapsed time;
- accepted, rejected, and rewritten worker hunks;
- retries or fallback;
- validation outcome;
- one recommendation: keep, narrow, or reject this cheap execution route.

Copy a valid generated run-cost summary into the existing
docs/cost-baselines/ convention. Never hand-author missing usage. If measurement
is unavailable or incomparable, label the canary inconclusive and do not change
routing policy.

## Delivery

Commit intentionally, push the branch, and open a ready-for-review PR linked to
Issue #28. Put the compact canary result in the PR body. Move #28 to Review once
the PR is ready.

Do not merge it.

Finish with an outcome-first handoff under roughly 250 words containing:

- exact PR head and URL;
- what changed;
- verification result;
- worker-versus-supervisor disposition;
- measured time/token/cost result;
- any coverage gap;
- one recommended next action.

## Date

2026-08-14

## Iteration 1 Feedback

Resume Issue #28 from the approved assessment.

Coordinator correction: the OpenRouter MCP is optional and is not required for
ordinary paid Pipeline execution. The prior requirement for a fresh MCP
price/availability receipt is withdrawn.

Do not register or authenticate another MCP. Proceed using:

- the reviewed checked-in routing policy and model-matrix snapshot;
- the configured-key OpenRouter execution path;
- the direct wrapper and Pipeline receipts as authoritative evidence for the
  actual call;
- reported usage and billed cost when available.

Do not claim the checked-in price or availability is live telemetry. Record
`live_catalog: unavailable, not required for normal execution`. If billed cost
is unavailable, record it as unavailable rather than blocking or estimating it
by hand.

Continue the single bounded Issue #28 canary exactly as scoped. Do not change
routing policy or the model matrix. Preserve the assessment and proceed through
the existing Pipeline gate.

## Iteration 2 Feedback

bug
