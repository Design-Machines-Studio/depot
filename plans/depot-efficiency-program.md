# Depot Efficiency Program -- Phase Index

## Active coordination (refreshed 2026-08-12)

Shared cross-repository projection: [Assembly Coordination, Project
1](https://github.com/orgs/Design-Machines-Studio/projects/1). GitHub Issues
and pull requests own live status, review, checks, dependencies, and
assignees. This file owns Depot's reusable tooling sequence and a compact
external handoff only; it does not duplicate Baseplate's production roadmap.

The current priority order is:

1. **P1 -- shorten and cheapen development.** Finish PR 33 release closeout,
   then make dm-review proportional, install the accepted worker/advisor model
   policy, unlock one bounded audited cheap execution path, and prove it with a
   measured canary.
2. **P2 -- unlock Fixture development.** After the canary, apply the improved
   workflow to the existing Baseplate verifier -> canonical Jig chain. Depot
   does not own that product work.
3. **P3 -- wider platform improvement.** Linux/Darwin broker hardening,
   optional reporting, interop, and broad Baseplate quality work follow unless
   they become a demonstrated blocker.

### Single next Depot chunk

The PR 33 release-closeout prompt is currently executing in a separate clean
detached worktree at merge commit
`48fc3931281282844a13d988a2f21753f8c62b1c`. Its exact tags are
`assembly-v3.10.0`, `dm-review-v1.58.6`, and `pipeline-v1.45.0`.

After that receipt is checked, the one immediate successor is **00b-2:
proportional dm-review severity and convergence**. It makes P3 advisory,
removes unconditional duplicate simplification work, and right-sizes review
fan-out while retaining P1, applicable security, and required browser gates.
Do not start 00c or a paid OpenRouter implementation lane before 00b-2 lands.

### Ordered Depot queue

| Order | Work | State | Promotion evidence |
|---|---|---|---|
| 0 | PR 33 release closeout | **IN PROGRESS** | three remote annotated tags peel to `48fc393`; only PR 33's proven-merged refs/worktree removed |
| 1 | 00b-2 proportional dm-review | **NEXT** | release receipt checked; refreshed bounded prompt approved |
| 2 | 00c worker/advisor routing | HOLD | 00b-2 merged; executable routing matches the accepted 00a portfolio and effort policy |
| 3 | 00d bounded audited cheap execution | HOLD / REWRITE | 00c merged; one non-sensitive workload, direct receipt boundary, and one bounded native supervisor check |
| 4 | Cheap-path canary | HOLD | one real task measures elapsed time, token/cost, handholding, and defect escape |
| 5 | Fixture-development handoff | EXTERNAL | Baseplate verifier consumer proof and publication clear the canonical Jig path |
| 6 | Linux broker portability + production E2E | HOLD / REWRITE | cheap path proven; portable Go/libfido2 policy and non-skipped host acceptance |
| 7 | R3 broker transport integration | HOLD / REWRITE | ready probe plus executed acceptance; wire one broker-owned workload |
| 8 | R3 routing refresh | HOLD / REWRITE | accepted portfolio and direct/broker precedence re-anchored |
| 9 | Harness lessons: budgets then memory/codify | HOLD / REWRITE | current kernel/caller boundaries rechecked; no default lane claims without concurrent writers |
| 10 | R4 static run report | LATER / REWRITE | a current failed canary supplies a diagnosis specimen |
| 11 | Darwin broker | FUTURE / REPLAN | Linux proves production path; complete FIDO/runtime/IPC scope |
| 12 | R5 Agent Plugins interop | PARK | a named client or distribution target exists |

Only `IN PROGRESS` and `NEXT` rows authorize immediate coordination. HOLD,
EXTERNAL, LATER, FUTURE, and PARK are not execution prompts.

### Cross-repository handoff

| Owner | Native item and exact state | Clearing event | Next actor / collision |
|---|---|---|---|
| Baseplate tooling | [PR 660](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/660) draft at `95927c0dd6004d85ed7762f4349cd95149f6c92d`; mergeable, all hosted checks skipped | exact-head CI and review become real, then merge | Existing PR owner/session. Safe in parallel with Depot because repositories differ. |
| Baseplate Fixture verifier | [PR 662](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/662) draft at `4eb88f5d85ac4727be6b00c5bc779ad5877901a9`; conflicting, all hosted checks skipped; addresses [#659](https://github.com/Design-Machines-Studio/assembly-baseplate/issues/659) | rebase after the owner-selected Baseplate order; candidate verifier accepts the real Jig; trusted publish succeeds | Baseplate acts next. High collision with PR 660 on nine files including `test.yml`, `Makefile`, `sequence.md`, `work-paths.html`, and `tasks/lessons.md`; do not advance both branches independently. |
| Canonical Jig | [PR 11](https://github.com/Design-Machines-Studio/assembly-fixture-jig/pull/11) draft at `ee27a7658d17af277a76daf1a5206915c8e1e50e`; mergeable; `declarations` passes; [#8](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/8) and [#10](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/10) remain open | published Baseplate verifier, protected exact-head check, required consumer proof, and retained browser evidence | Jig acts after Baseplate. No Depot file collision; dependency blocks meaningful closeout. |

Project 1 already carries these Baseplate/Jig native items with appropriate
P1/P2 and Tooling/Fixtures fields. Depot has no native Issue for 00b-2; do not
create a free-form Project note or repurpose unrelated Depot Issues #25-#28.
Creating the execution Issue remains an owner decision.

### Operating doctrine

- Assembly means small self-hosted Go applications for 4-50-person co-ops,
  maintained by a two-person team. YAGNI, pragmatic DRY, ergonomics, runtime
  performance, elapsed time, and token cost are design constraints.
- Kimi K3 is review-only, especially focused security. GLM-5.2 has no default
  seat. DeepSeek V4 Flash refresh and Grok 4.5 remain bounded execution
  candidates. Native Fable 5 or Codex 5.6 provides one proportional supervisor
  checkpoint rather than duplicating the worker's implementation.
- No automated OpenRouter implementation runs before the audited 00d path.
  Broker completion is credential-custody hardening, not the cheap-development
  unlock gate.
- R2 is not run as authored; R4 waits for a real diagnostic specimen; R5 waits
  for a real consumer. Old prompts remain historical inputs until explicitly
  refreshed and marked NEXT.

The historical program below is retained as provenance. Its old `Next`,
`PENDING`, and entry-gate labels do not override the active queue above.

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
