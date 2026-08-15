# Depot Efficiency Program -- Phase Index

## Active coordination (refreshed 2026-08-15)

Shared cross-repository projection: [Assembly Coordination, Project
1](https://github.com/orgs/Design-Machines-Studio/projects/1). GitHub Issues
and pull requests own live status, review, checks, dependencies, and
assignees. This file owns Depot's reusable tooling sequence and a compact
external handoff only; it does not duplicate Baseplate's production roadmap.

Depot trusted main is `40b6e00762b175158f16007f4105d71f846a0c5d`, the
merge commit for PR #69. Depot has no open pull requests or Issues. The current
priority order is:

1. **P1 -- no new Depot implementation.** The active efficiency sequence is
   complete. New routing, review, kernel, or harness work requires a measured
   current failure rather than another speculative layer.
2. **P2 -- finish the external Fixture release handoff.** Baseplate and Jig own
   that product work. Depot supplies the already-landed proportional workflow,
   release command, routing, and review support without duplicating their plan.
3. **Housekeeping is pull-based.** Expand the Agent Plugins canary or add another
   workflow abstraction only after a live consumer or failed run proves the need.

### Single next Depot action

**None.** Do not start another Depot execution chunk from this plan. The next
Assembly action is the already-owned Baseplate Fixture-release sequence under
[Issue #561](https://github.com/Design-Machines-Studio/assembly-baseplate/issues/561).
Its two live PRs overlap heavily, so resolve the superseded/conflicting PR #681
owner decision before treating draft PR #682 as review-ready.

R2 is closed **DONE / NO CODE**. Current `plan-verification` and
`run-verification` already put repository proof before model review, keep passing
raw output out of prompts, and provide bounded failure evidence for repair.
Each selected boundary now runs fresh and returns only bounded current-invocation
results. No measured workload justifies adding the authored caller-supplied
`mechanical_globs` policy, so the old untracked R2 prompts are historical inputs,
not executable work.

The historical harness-lessons phase had one reachable residual: caller-side
capture of the compact Pipeline run observation. PR #63 landed that repair at
`8637552`. Lane claims remain parked because current worktree isolation and
exact-head reuse leave no recurring collision; run budgets are solved/obsolete
under the existing planning limits and soft checkpoints; authorization friction
is solved/superseded by PRs #46 and #47. Codify recommendations remain
proposal-only.

### Ordered Depot queue

| Order | Work | State | Promotion evidence |
|---|---|---|---|
| 0 | PR 33 release closeout | **DONE** | three remote annotated tags peel to `48fc393`; PR 33's proven-merged refs/worktree removed |
| 1 | [#35](https://github.com/Design-Machines-Studio/depot/issues/35) / PR 37 proportional dm-review | **DONE** | merged at `372f2c9`; exact-head policy checks and release preflight passed; three release tags remain to cut |
| 2 | R2 pre-gates and evidence reuse | **DONE / NO CODE** | merged verification ordering, bounded receipts, and exact reuse cover the residual; no observed mechanical-glob class warrants another policy layer |
| 3 | [#39](https://github.com/Design-Machines-Studio/depot/issues/39) / PR 40 R3a Linux portability proof | **DONE** | production-tag build passed on NED; no service was installed |
| 4 | PR 44 production-root contract repair | **CLOSED / OBSOLETE** | closed unmerged; its lone unique commit touched only the retired Workflow Authority tree, and its local/remote branch and worktree were removed |
| 5 | Proportional scope, threat model, and review convergence | **DONE** | PR #52 exact head `f843d89` merged as `ed59991`; supported repairs converge proportionally |
| 6 | Clear Publish Preview operator output | **DONE** | PR #51 exact head `6da69ba` landed through `3c2a276`; the playbook returns explicit publication status |
| 7 | Clear human output for voice-check, dm-review, and Pipeline | **DONE** | PR #53 merged as `ecc8533`; three release tags and both installed harness caches are current |
| 8 | [#28](https://github.com/Design-Machines-Studio/depot/issues/28) / [PR #55](https://github.com/Design-Machines-Studio/depot/pull/55) runtime cache-resolution repair and cheap-path canary | **DONE** | exact head `d462e8f` merged as `5afc8de`; Depot now has no open Issues |
| 9 | [#54](https://github.com/Design-Machines-Studio/depot/issues/54) / PR #57 reusable Assembly planning-coordinator skill | **DONE** | merged at `844fc1b`; live Project 1 records the native issue Done |
| 10 | `/assembly-release` | **DONE** | PR #62 merged as `0e10409` |
| 11 | Minimal worker/advisor routing adjustment | HOLD / REASSESS | canary shows a concrete routing miss; otherwise current matrix stands |
| 12 | Baseplate verifier -> canonical Jig Fixture handoff | EXTERNAL / P2 | producer checks and consumer proof clear in their owning repositories; roadmap remains external |
| 13 | R4 rejected OpenRouter attempt evidence | **DONE** | PR #58 landed the evidenced residual at `9e5ee92` |
| 14 | R5 Agent Plugins interop canary | **DONE** | Issue #64 / PR #65 landed one generated `craft-developer` skills-discovery canary; live-client proof remains unavailable |
| 15 | Harness lane claims | PARK / EVIDENCE-GATED | a recurring concurrent-writer collision survives worktree isolation and exact-head reuse |
| 16 | Workflow Authority install, integration, and Darwin port | **REMOVED** | reintroduction requires a new owner decision backed by a demonstrated threat or operational need |
| 17 | Bounded OpenRouter worker context | **DONE** | PR #59 merged at `367f9d8` |
| 18 | Safe credential-reference handling | **DONE** | PR #60 merged at `730d2db` |
| 19 | Terminal-stream failure classification | **DONE** | PR #61 merged at `662fcd5` |
| 20 | Harness run budgets | **SOLVED / OBSOLETE** | existing 8/6 planning limits, scope freeze, exploration checkpoint, and long-run soft continuation cover the evidenced need |
| 21 | Caller-side Pipeline memory capture | **DONE** | PR #63 merged at `8637552` |
| 22 | Harness authorization friction | **SOLVED / SUPERSEDED** | PRs #46 and #47 removed per-call approval and Workflow Authority |
| 23 | Pipeline two-gate planning and project alignment | **DONE** | Issue #66 / PR #67 merged at `9a2d3cf` |
| 24 | Content-safe OpenRouter HTTP failure reasons | **DONE** | Issue #68 / PR #69 merged at `40b6e00`; `openrouter-v1.14.5` and both installed harness caches are current |

The Fixture-development handoff is now the active external P2 lane. No
additional Depot harness code is authorized absent fresh evidence. DONE, HOLD,
EXTERNAL, LATER, FUTURE, PARK, and PREPARED are not execution prompts.

### Cross-repository handoff

| Owner | Native item and exact state | Clearing event | Next actor / collision |
|---|---|---|---|
| Baseplate Fixture verifier | [PR #662](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/662) exact head `af2411a` merged as `9306074`; [Issue #659](https://github.com/Design-Machines-Studio/assembly-baseplate/issues/659) remains open in Review | trusted consumer proof closes the native issue | Baseplate and Jig owners act; no Depot collision. |
| Canonical Jig | [PR #11](https://github.com/Design-Machines-Studio/assembly-fixture-jig/pull/11) exact head `a37cfb4` merged as `2c27506`; [Issue #8](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/8) remains open in Review | trusted exact-head Baseplate conformance and consumer evidence close the native issue | Jig owner acts; no Depot collision. |
| Private Fixture releases | [PR #680](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/680) merged as `1087c40`; PR #681 remains open at `c0e7d0d`, conflicts with main, and substantially overlaps the landed outcome | owner confirms whether #681 has unique work, then closes or rebases it | Baseplate owner decision first; high collision with #682 across composer docs, code, tests, and task files. |
| Private Baseplate release assets | [PR #682](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/682) is draft and mergeable at `b4d172b`; all hosted checks are skipped | finish scope decisions, move out of draft, and obtain exact-head checks/review | Existing Baseplate session owns it; do not start a duplicate branch. |

Depot has no open pull requests or Issues. Project 1 remains the external
cross-repository projection; no duplicate Issue or free-form note is needed.

### Operating doctrine

- Assembly means small self-hosted Go applications for 4-50-person co-ops,
  maintained by a two-person team. YAGNI, pragmatic DRY, ergonomics, runtime
  performance, elapsed time, and token cost are design constraints.
- Kimi K3 is review-only, especially focused security. DeepSeek V4 Flash 0731
  leads bounded execution, Grok 4.5 handles harder escalation, and GLM-5.2 is
  the experimental last fallback. Native Fable 5 or Codex 5.6 provides one
  proportional supervisor checkpoint rather than duplicating the worker's implementation.
- A deliberately configured OpenRouter key is authorization on a trusted
  developer workstation. Do not add a second human-approval ceremony. Keep
  obvious-secret refusal automatic and use provider-side key limits for spend.
- Workflow Authority has been removed. Do not reintroduce a provider broker or
  make one a prerequisite for Pipeline or dm-review without a new owner decision
  backed by a demonstrated threat or operational need.
- R2 is closed rather than run as authored. The old R4 report proposal is
  retired in favor of the evidenced receipt-retention residual. R5's single
  skills-discovery canary is complete; any fleet rollout or MCP portability work
  waits for live-client evidence. Old prompts remain historical inputs until
  explicitly refreshed and marked NEXT.

The historical program below is retained as provenance. Its old `Next`,
`PENDING`, and entry-gate labels do not override the active queue above.
In particular, every broker go-live, broker-probe, FIDO, systemd, and Darwin
prompt below is superseded and must not be dispatched from this index.

Approved plan: `~/.claude/plans/mission-you-are-curious-neumann.md` (2026-08-07).
This file is the run-time index for orchestrators. Each phase directory carries
its own `manifest.json` + `prompts/`. Phases execute through `/pipeline-run`
(or resume, for R3.0) -- never by manual replication (failure mode 1).

Status 2026-08-07 (late): **R0 MERGED** (PR #17; landed stronger than planned --
transactional `emit-cost-summary` + mandatory `record-attempt`; first real
artifact measured 5/5 lanes, 365,216 tokens, $2.996, 100% OpenRouter with Codex
at cap; leftover: baseline copy to docs/cost-baselines/ folded into R1 chunk 01
step 0). **R3.0 MERGED** (PRs #18/#19: chunk 05 packaging + chunk 06 acceptance
harness, 1000-line env-gated integration suite, REQ-E2E-01..12). **R3 chunk 00
DONE** (PR #22): `OPENROUTER_AVAILABLE` now resolves three outcomes and permits
the sunset-bound interim batch only when the broker is absent. R3.1/R3.2 remain
PENDING strictly for broker-owned transport; gate = broker `status: ready` on
a supported host + an executed acceptance pass (`WORKFLOW_AUTHORITY_E2E=1`).
**Next: R1** (prompts refreshed against merged
state; versions now read-current-then-bump).

| Phase | Dir | Prompts | Entry gate | Exit gate |
|-------|-----|---------|-----------|-----------|
| R0 measurement backbone | `plans/r0-measurement-backbone/` | 3 (DONE) | none | >=3 real runs with per-lane cost tables; baselines committed to `docs/cost-baselines/` (1/3 runs done; baseline commit owed -> R1-01 step 0) |
| R1 review burn cuts | `plans/r1-review-burn-cuts/` | 6 | R0 merged (MET) | >=30% drop in review input-bytes on a real loop run, final full fan-out intact |
| P1 probe | scratchpad script, not a phase | 0 | R0 merged | survivor rate recorded; >=40% AND >=2 hunk-local lanes -> R2 reuse chunks live, else killed |
| R2 pre-gates (+ probe-gated reuse) | `plans/r2-pre-gates-evidence-reuse/` | 2 (+2 authored only if probe passes) | R0+R1 merged, probe verdict recorded | real-run bytes delta vs R0 baseline |
| R3 broker landing + routing | `plans/r3-broker-golive-routing/` | 3 (chunk 00 interim macOS operator-batch authorization DONE via PR #22; R3.0 Linux landing DONE via PRs #18/#19; chunks 01/02 parked) | chunk 01: broker `status: ready` on ANY supported host + executed E2E pass | interim: automated OpenRouter lanes on macOS under receipted batch authorization, sunset-bound. final: bulk lanes via broker, interim retired |
| R4 run report (+ gated kernel dispatch) | `plans/r4-run-report/` | 1 now (3 kernel prompts authored only if entry gate met) | report: none. kernel: >=5 runs show orchestration >=20% of residual spend | teammate diagnoses a failed run from the report alone |
| R5 Agent Plugins interop | `plans/r5-agent-plugins-interop/` | 1 | R1 merged | `--check` green in `--all` + preflight; one plugin passes vendored AP schemas |
| Rail-exhaustion ask-gate | `plans/rail-exhaustion-ask-gate/` | 1 | none (answers the 2026-08-08 zero-chunk BLOCKED incident; run at next Codex window, BEFORE the R1 rerun) | rail exhaustion pauses on human_gate with live per-operator rail status and receipted run-scoped authorization; headless default park; broker gate + final review + sensitive paths never overridable |

R3.0 resume steps (no new prompts -- finish the paid-for run):
1. In the Codex clone, merge `pipeline/macos-authority-broker/05-linux-packaging-admin`
   into `ai/workflow-authority-linux-m1` and record its completion receipt.
2. Execute the existing `plans/macos-authority-broker/prompts/06-linux-integration-acceptance.md`
   through the same run (`workflow-authority-linux-m1-20260803`), its gates unchanged.
3. Reconcile the feature branch with current main (main's kernel 0.8.0 content wins on overlap).
4. Full dm-review-loop (security class = full tier, zero-deferral), merge to main.
5. Clean the eight `04b-*`/`04c-*`/`04d-*`/`04e-*`/`04f-*` sub-worktrees + branches per
   the repo-cleanup contract with a Branch & Worktree Inventory.

Darwin broker milestone: AUTHORED at `plans/darwin-broker-milestone/`
(2 chunks, security class): 01 darwin platform layer + launchd packaging +
peer credentials; 02 darwin ops/validator/acceptance + AKIA-vector defang.
Retires interim mode on macOS once Travis performs the live install/enroll
per OPERATIONS.md darwin section. Run AFTER the chain-verification queue
completes (no file conflicts with it, but serialize merges). Sunset
2026-09-07; Linux hosts return ~2026-08-22.

Harness-lessons phase was historically AUTHORED at `plans/harness-lessons/`
(4 chunks). The 2026-08-15 reassessment makes that local plan provenance only:
lane claims are parked, run budgets are solved/obsolete, authorization friction
is solved/superseded, and PR #63 completed the caller-side memory-capture
residual. Codify auto-apply is rejected; recommendations remain proposal-only.

Kill switches introduced by this program (all fail OPEN to full coverage; every
receipt records active switches): `DM_REVIEW_LOOP_FULL_FANOUT`,
`DM_REVIEW_FULL_DIFF`, `PIPELINE_FULL_TIER_REVIEW`, `PIPELINE_NO_GATE_ONLY`,
`DM_REVIEW_NO_EVIDENCE_REUSE` (probe-gated chunk only).
