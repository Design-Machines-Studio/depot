# Depot Efficiency Program -- Phase Index

## Active coordination (refreshed 2026-08-12)

Shared cross-repository projection: [Assembly Coordination, Project
1](https://github.com/orgs/Design-Machines-Studio/projects/1). GitHub Issues
and pull requests own live status, review, checks, dependencies, and
assignees. This file owns Depot's reusable tooling sequence and a compact
external handoff only; it does not duplicate Baseplate's production roadmap.

The current priority order is:

1. **P1 -- make OpenRouter useful without ceremony.** Replace R3's mandatory
   broker and repeated human approvals with a trusted-workstation path where a
   configured OpenRouter key authorizes non-interactive use. Retain automatic
   refusal of unmistakable credential/private-key payloads, cost receipts, and
   native Codex supervision. Workflow Authority and its broker architecture are
   removed; reintroduction requires a new owner decision backed by a
   demonstrated threat or operational need.
2. **P1 -- prove the cheaper path.** Run one bounded non-sensitive canary and
   compare elapsed time, tokens, cost, and actionable defects with the native
   fallback before expanding automated routing.
3. **P2 -- unlock Fixture development.** Apply the proven workflow to the
   existing Baseplate verifier -> canonical Jig chain as its external blockers
   clear. Depot does not own that product work.
4. **Other tooling is pull-based.** R4, R5, harness work, and new platform
   improvements remain evidence-gated rather than moving ahead of Fixture work.

### Single next Depot chunk

PRs 37-43 are merged. They made review proportional, refreshed model evidence,
made the Linux production build portable, repaired NED operation boundaries,
fixed direct-envelope handling, and removed Notion from development
coordination. Current trusted main is `981bf6c86cb1b4e70df9767786e9e5661eda0079`.

R2 is closed **DONE / NO CODE**. Current `plan-verification` and
`run-verification` already put repository proof before model review, keep passing
raw output out of prompts, and provide bounded failure evidence for repair.
Each selected boundary now runs fresh and returns only bounded current-invocation
results. No measured workload justifies adding the authored caller-supplied
`mechanical_globs` policy, so the old untracked R2 prompts are historical inputs,
not executable work.

The one immediate successor is **R3-simplify: non-interactive OpenRouter on a
trusted developer workstation**. `OPENROUTER_API_KEY` or the existing validated
key-file input is sufficient authorization. Direct `/openrouter`, eligible
dm-review lanes, and the bounded Pipeline adapter must not ask for exact-digest,
batch, FIDO, or broker approval. They keep the existing disclosure scan, output
boundary, model restrictions, timeouts, fallbacks, and content-free cost/usage
receipts. Missing credentials or an unavailable provider falls back to native
Codex without blocking the run.

This is a simplification of R3, not a new authorization framework. Reuse the
existing non-interactive `trusted-boundary` byte-scan path where it fits; do not
add another token, daemon, config service, approval artifact, or compatibility
layer merely to rename the decision. Provider-side per-key spending limits are
the preferred runaway-cost control.

### Ordered Depot queue

| Order | Work | State | Promotion evidence |
|---|---|---|---|
| 0 | PR 33 release closeout | **DONE** | three remote annotated tags peel to `48fc393`; PR 33's proven-merged refs/worktree removed |
| 1 | [#35](https://github.com/Design-Machines-Studio/depot/issues/35) / PR 37 proportional dm-review | **DONE** | merged at `372f2c9`; exact-head policy checks and release preflight passed; three release tags remain to cut |
| 2 | R2 pre-gates and evidence reuse | **DONE / NO CODE** | merged verification ordering, bounded receipts, and exact reuse cover the residual; no observed mechanical-glob class warrants another policy layer |
| 3 | [#39](https://github.com/Design-Machines-Studio/depot/issues/39) / PR 40 R3a Linux portability proof | **DONE** | production-tag build passed on NED; no service was installed |
| 4 | PR 44 production-root contract repair | **REVIEW / OPTIONAL** | exact-head review and owner merge decision; it does not block the new path and authorizes no broker continuation |
| 5 | R3-simplify non-interactive configured-key OpenRouter | **NEXT** | direct, dm-review, and one bounded Pipeline lane complete without human approval; automatic sensitive-payload refusal and receipts still pass |
| 6 | One real cheap-path canary | HOLD | R3-simplify merged and released; measured time/cost/quality receipt from a non-sensitive workload |
| 7 | Minimal worker/advisor routing adjustment | HOLD / REASSESS | canary shows a concrete routing miss; otherwise current matrix stands |
| 8 | Baseplate verifier -> canonical Jig Fixture handoff | EXTERNAL / P2 | producer checks and consumer proof clear in their owning repositories |
| 9 | R4 static run report | LATER / REWRITE | a current failed run supplies a diagnosis specimen |
| 10 | R5 Agent Plugins interop | PARK | a named client or distribution target exists |
| 11 | Harness lessons: budgets then memory/codify | HOLD / REWRITE | current run evidence justifies the exact change |
| 12 | Workflow Authority install, integration, and Darwin port | **REMOVED** | reintroduction requires a new owner decision backed by a demonstrated threat or operational need |

The Fixture-development handoff remains an external P2 lane and may advance in
parallel when its Baseplate/Jig dependency chain clears; it does not displace
the single `NEXT` Depot chunk.

Only `NEXT` authorizes a new Depot execution session. DONE, HOLD, EXTERNAL,
LATER, FUTURE, and PARK are not execution prompts.

### Cross-repository handoff

| Owner | Native item and exact state | Clearing event | Next actor / collision |
|---|---|---|---|
| Baseplate tooling | [PR 660](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/660) draft at `a126d7776000af2e12a6e7dabe5522b677d0e32f`; mergeable, all hosted checks skipped | exact-head CI and review become real, then merge | Existing PR owner/session. Safe in parallel with Depot because repositories differ. |
| Baseplate Fixture verifier | [PR 662](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/662) draft at `4eb88f5d85ac4727be6b00c5bc779ad5877901a9`; conflicting, all hosted checks skipped; addresses [#659](https://github.com/Design-Machines-Studio/assembly-baseplate/issues/659) | rebase after the owner-selected Baseplate order; candidate verifier accepts the real Jig; trusted publish succeeds | Baseplate acts next. High collision with PR 660 on nine files including `test.yml`, `Makefile`, `sequence.md`, `work-paths.html`, and `tasks/lessons.md`; do not advance both branches independently. |
| Canonical Jig | [PR 11](https://github.com/Design-Machines-Studio/assembly-fixture-jig/pull/11) draft at `ee27a7658d17af277a76daf1a5206915c8e1e50e`; mergeable; `declarations` passes; [#8](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/8) and [#10](https://github.com/Design-Machines-Studio/assembly-fixture-jig/issues/10) remain open | published Baseplate verifier, protected exact-head check, required consumer proof, and retained browser evidence | Jig acts after Baseplate. No Depot file collision; dependency blocks meaningful closeout. |

Project 1 carries the active Baseplate/Jig native items with appropriate P1/P2
and Tooling/Fixtures fields. Depot Issues #35 and #39 are `Done`. PR 44 remains
an ordinary review item until its owner merges or closes it, but it is not the
next shared-delivery item. Add the R3-simplify implementation PR to Project 1 as
P1 / Tooling when it exists; do not create a free-form note or repurpose
unrelated Depot Issues #25-#28.

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
- R2 is closed rather than run as authored; R4 waits for a real diagnostic
  specimen; R5 waits for a real consumer. Old prompts remain historical inputs
  until explicitly refreshed and marked NEXT.

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
