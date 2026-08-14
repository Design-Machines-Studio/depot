# Depot Efficiency Program -- Phase Index

## Active coordination (refreshed 2026-08-14)

Shared cross-repository projection: [Assembly Coordination, Project
1](https://github.com/orgs/Design-Machines-Studio/projects/1). GitHub Issues
and pull requests own live status, review, checks, dependencies, and
assignees. This file owns Depot's reusable tooling sequence and a compact
external handoff only; it does not duplicate Baseplate's production roadmap.

The current priority order is:

1. **P1 -- preserve rejected OpenRouter attempt evidence.** PR #55 supplied
   the real R4 specimen: a paid provider response was rejected as
   `headerless-diff`, then its temporary wrapper receipt was deleted. Preserve
   the existing content-free receipt through Workflow Kernel `record-attempt`;
   do not create a separate report system.
2. **Close out the real cheap-path canary.** PR
   [#55](https://github.com/Design-Machines-Studio/depot/pull/55) merged the
   runtime resolver repair. Issue
   [#28](https://github.com/Design-Machines-Studio/depot/issues/28) remains open
   in `Review` for owner closeout; do not invent more implementation work.
3. **Assembly planning coordinator complete.**
   [#54](https://github.com/Design-Machines-Studio/depot/issues/54) and PR #57
   are complete on trusted main.
4. **Prepared P2 -- Assembly release-operations skill planning.** The
   [planning prompt](assembly-release-skill/prompts/00-plan-assembly-release.md)
   will decide the smallest reusable `/assembly-release` boundary from current
   Depot and Baseplate evidence. It follows the optimization initiative, does
   not delay live Baseplate or Fixture releases, and is not yet a Project item.
5. **Evidence-gated follow-ons.** Workflow Kernel changes, R5, new routing, and
   speculative harness/platform tooling stay parked until a current failure or
   measured workload proves the need. R2 remains done/no-code and R3 remains
   removed.
6. **P2 -- Fixture handoff remains external.** Baseplate and Jig own their
   verifier/product repair; Depot supplies proportional policy, not product code.

### Single next Depot chunk

Current trusted main for this chunk is
`5afc8defd0f3151bad52fa8036f012c8b936fda6`. PR #55's exact head
`d462e8f0c4e72eff07319289b9770b72d4e095e3` landed through that merge. The
host-aware Pipeline and dm-review bundle resolution repair, its Bash 3
compatibility repair, and required-bundle fail-closed correction are complete.

R2 is closed **DONE / NO CODE**. Current `plan-verification` and
`run-verification` already put repository proof before model review, keep passing
raw output out of prompts, and provide bounded failure evidence for repair.
Each selected boundary now runs fresh and returns only bounded current-invocation
results. No measured workload justifies adding the authored caller-supplied
`mechanical_globs` policy, so the old untracked R2 prompts are historical inputs,
not executable work.

Issue #54 is complete through PR #57. The immediate Depot successor is the
narrow R4 failure-observability residual above: retain an existing validated
wrapper receipt long enough to atomically record the paid rejected attempt.
Issue #28 still needs only owner review/closure against merged PR #55.

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
| 8 | [#28](https://github.com/Design-Machines-Studio/depot/issues/28) / [PR #55](https://github.com/Design-Machines-Studio/depot/pull/55) runtime cache-resolution repair and cheap-path canary | **MERGED / ISSUE REVIEW** | exact head `d462e8f` merged as `5afc8de`; owner closes #28 after confirming the merged outcome |
| 9 | [#54](https://github.com/Design-Machines-Studio/depot/issues/54) / PR #57 reusable Assembly planning-coordinator skill | **DONE** | merged at `844fc1b`; live Project 1 records the native issue Done |
| 10 | [Assembly release-operations skill planning](assembly-release-skill/prompts/00-plan-assembly-release.md) | **PREPARED / P2 / AFTER OPTIMIZATION** | live Depot/Baseplate inspection proves the smallest command boundary and produces one implementation prompt without delaying active releases |
| 11 | Minimal worker/advisor routing adjustment | HOLD / REASSESS | canary shows a concrete routing miss; otherwise current matrix stands |
| 12 | Baseplate verifier -> canonical Jig Fixture handoff | EXTERNAL / P2 | producer checks and consumer proof clear in their owning repositories; roadmap remains external |
| 13 | R4 rejected OpenRouter attempt evidence | **CURRENT / P1** | a provider-completed `headerless-diff` failure retains content-free usage/cost evidence through one `record-attempt` call; no standalone report |
| 14 | R5 Agent Plugins interop | PARK / EVIDENCE-GATED | a named client or distribution target exists |
| 15 | Workflow Kernel or speculative harness/platform changes | HOLD / EVIDENCE-GATED | a current reachable failure proves the smallest required change |
| 16 | Workflow Authority install, integration, and Darwin port | **REMOVED** | reintroduction requires a new owner decision backed by a demonstrated threat or operational need |

The Fixture-development handoff remains an external P2 lane and may advance in
parallel when its Baseplate/Jig dependency chain clears; it does not displace
the single `CURRENT` Depot chunk.

Only the R4 rejected-attempt-evidence residual authorizes the next Depot
execution session. The Assembly release prompt is prepared P2 planning work
after the optimization initiative. DONE, HOLD, EXTERNAL, LATER, FUTURE, PARK,
and PREPARED are not execution prompts.

### Cross-repository handoff

| Owner | Native item and exact state | Clearing event | Next actor / collision |
|---|---|---|---|
| Baseplate tooling | [PR 660](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/660) exact head `5a38dd1915ee83f4060b8d920e04ae15ae057e28` merged as `23609303ebd207add0cc2fad22add482db877ff4`; exact-head required checks passed | complete | No Depot collision. |
| Baseplate Fixture verifier | [PR 662](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/662) open, non-draft, mergeable at `af2411a3a3ea3d7d55315bd909d7817cf72bb413`; required test, security, composer-security, and docker-startup checks pass; addresses [#659](https://github.com/Design-Machines-Studio/assembly-baseplate/issues/659) | exact-head owner review/merge and trusted verifier publication | Baseplate acts next. Safe in parallel with Depot; PR 660 is merged, so its former file collision is gone. |
| Canonical Jig | [PR 11](https://github.com/Design-Machines-Studio/assembly-fixture-jig/pull/11) draft at `a1738fccc31f6738b546d36e0e7d949ae67ae0a6`; mergeable but unstable because `pull-request-checks` fails; [#8](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/8) and [#10](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/10) remain open | published Baseplate verifier, repaired exact-head check, required consumer proof, and retained browser evidence | Jig acts after Baseplate. No Depot file collision; dependency and red CI block closeout. |

Project 1 carries #28 as `Review / P1 / Tooling`, #54 as
`Done / P1 / Tooling`, and the active Baseplate/Jig native items with their
existing fields. This R4 residual will enter Project 1 as its native PR in
`Review / P1 / Tooling`; no duplicate Issue or free-form note is needed. Depot
Issues #35 and #39 are `Done`. No native Issue exists yet for the Assembly
release skill; its planner must inspect live Baseplate release state before
admitting one.

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
  retired in favor of the evidenced receipt-retention residual. R5 waits for a
  real consumer. Old prompts remain historical inputs until explicitly
  refreshed and marked NEXT.

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

Harness-lessons phase AUTHORED at `plans/harness-lessons/` (4 chunks): lane
claims, kernel run budgets, memory-capture fix + codify auto-apply, and the
audit-over-approval authorization relaxation (operator directive 2026-08-10).
Run after chain-verification lands; chunk 04 supersedes parts of R3 chunk 00.

Kill switches introduced by this program (all fail OPEN to full coverage; every
receipt records active switches): `DM_REVIEW_LOOP_FULL_FANOUT`,
`DM_REVIEW_FULL_DIFF`, `PIPELINE_FULL_TIER_REVIEW`, `PIPELINE_NO_GATE_ONLY`,
`DM_REVIEW_NO_EVIDENCE_REUSE` (probe-gated chunk only).
