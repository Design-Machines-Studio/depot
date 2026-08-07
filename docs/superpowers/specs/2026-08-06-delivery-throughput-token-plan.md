# Delivery Throughput + Token Cost Plan (Cross-Project)

Date: 2026-08-06
Status: Proposal
Companion: [2026-08-06-software-factory-open-model-stack.md](2026-08-06-software-factory-open-model-stack.md)
Trigger: Weekly Claude/Codex subscription exhaustion within ~2 days of heavy
pipeline use; multi-hour token-heavy runs in assembly-baseplate slowing all
Design Machines delivery.

---

## 1. Where the tokens actually go (measured against the code)

Ranked sinks, with evidence from the current plugin sources:

1. **Review fan-out duplication.** Full `/dm-review` launches up to 16
   parallel agents (`plugins/dm-review/skills/review/SKILL.md`, "Notes"
   section), each carrying a 100-500-line agent definition plus the full diff
   plus stack guides. Pipeline execution then runs review gates *per chunk* and
   a *final full dm-review* over the merged result -- the same lines are
   reviewed by the same lanes multiple times per run. The review-tier policy
   (same file, "Review Tiers (token-economy policy)") already says "cheapest
   tier that fits"; execution does not fully honor it.
2. **Orchestration prose re-read every run.** The host model ingests
   `pipeline/SKILL.md` (~650 lines) + `pipeline-run/SKILL.md` (~235 lines) +
   `execution-orchestrator.md` (~2,270 lines) on every run, plus per-phase
   command files. That is ~3,100 lines of instructions re-processed at
   frontier-sub prices before any work happens -- and it is the host model,
   not code, executing the control flow.
3. **Model-generated planning artifacts.** `plan.html`, `research.html`,
   `assessment.html` with embedded JSON data islands are written by models
   (expensive output tokens) and re-read by later phases. Deterministic
   sections of these are code-generatable for free.
4. **Fix cycles fed with full context.** When a gate fails, the loop re-enters
   an agent with broad context instead of only the failing excerpt.
5. **Adversarial plan review on the subscription rails.** Phase 5 lenses
   default to Codex + OpenRouter; the Codex lens burns the same weekly budget
   that execution needs.
6. **Long wall-clock runs amplify all of the above.** Every hour a run sits
   open is an hour of session state, retries, and re-reads. OPS-01/TEST-01
   (CI/build/test speed) attack this correctly from the Baseplate side.

The subscription-exhaustion math: sinks 1, 2, and 5 hit the *weekly sub
budget* directly because they default to Codex/Claude rails. Sinks 3, 4, and 6
hit both budget and elapsed time.

---

## 2. Evaluation of the Baseplate production strategy

The `plans/production-backend-strategy` system is genuinely good -- the
dispatch rule, stable workstream IDs, and critical-path ordering
(`OPS-01 -> TEST-01 -> TOOL-01` as the shared delivery accelerator) are the
right calls. Three structural observations:

**a) TOOL-01 should not wait for the broker.** The sequence defers all of
TOOL-01 behind the host-authority broker, but TOOL-01's own scope lists four
work items with different dependencies:

- *Instrument elapsed time and token use by pipeline/review lane* -- needs no
  broker. The kernel event log and receipts already capture structure; this is
  a metrics rollup.
- *Remove redundant model work + safe evidence reuse + early exits* -- needs no
  broker. This is lane-selection and receipt-reuse policy in dm-review and the
  execution orchestrator.
- *Right-size adversarial/review passes* -- needs no broker. Routing policy.
- *Host-authority substrate* -- genuinely blocked on the broker.

Recommendation: split into **TOOL-01a** (instrumentation + redundancy removal
+ right-sizing; start immediately, highest leverage per the strategy's own
Priority 1) and **TOOL-01b** (broker/host-authority; remains deferred). Every
week TOOL-01a slips, every other chunk in the queue costs more -- the strategy
already says this path "reduces the cost of every later chunk," so let the
cheap 80% run now.

**b) TOOL-01 and the software-factory plan are the same substrate.** The
factory plan's Phase 1 (kernel enforce mode driving one pipeline class,
deterministic gates as code) *is* the "independent host-authority substrate"
done incrementally. Do not run them as competing efforts: TOOL-01b = factory
Phase 1-2 with Baseplate as the proving consumer. The quality-pulse prompt
(`depot-deterministic-quality-pulse-tooling.md`) already enforces the right
ownership split (dm-review owns pulse workflow, kernel owns neutral mechanics,
pipeline consumes without forking) -- the factory work inherits those
boundaries unchanged.

**c) The non-negotiables already point the right way.** "Keep reusable AI
workflow, review, lint, classification, receipt, and orchestration
capabilities in Depot plugins; Baseplate owns only profiles, thresholds,
fixtures, and integration receipts" is exactly the factory architecture. All
Depot-side changes below respect it.

---

## 3. The consolidated plan

Ordered by leverage-per-effort. Phases 0-2 are pure token/cost reduction with
no architecture risk; Phases 3-5 are the factory inversion.

### Phase 0 -- Instrument first (Depot, ~1 chunk, no broker)

You cannot right-size what you have not measured, and every later phase needs
these numbers to prove itself.

- Add a token/elapsed rollup to the workflow-kernel metrics module: per run,
  per phase, per review lane -- model, provider, input/output tokens, wall
  time, gate results. Data already exists in event logs and receipts; this is
  aggregation, stdlib-only, covered by the sanctioned kernel tests.
- Emit one `run-cost-summary.json` per pipeline/dm-review run alongside
  `authoritative-receipts.json`.
- Acceptance: one week of Baseplate runs produces a per-lane cost table that
  names the top three token sinks with real numbers, replacing the estimates
  in §1.

### Phase 1 -- Stop paying for redundant review (Depot, dm-review + pipeline)

- **Evidence reuse across chunks.** Lane receipts already record provider,
  status, and finding counts. Extend them with a content digest of the
  reviewed diff hunks; a lane whose exact hunks are unchanged from a clean
  prior receipt in the same run is `reused`, not re-run. Reused evidence is
  labeled, never silently promoted (mirrors the pulse contract's
  available/fallback distinction).
- **Deterministic pre-gates before agent lanes.** Run build/lint/typecheck/
  test as code first; if they fail, skip the paid review fan-out entirely and
  return the failure excerpt to the builder. Reviewing code that does not
  compile is pure waste.
- **Honor the review-tier policy in execution.** Per-chunk gates default to
  `dm-review-quick` with the existing lightweight classification (diff < 100
  lines -> 3 criteria); full review fires only for sensitive paths (already
  enumerated) and the final merge gate. The final full review reuses per-chunk
  receipts for unchanged hunks.
- **Early exits.** A chunk whose deterministic gates pass, diff is mechanical
  (config/docs/generated), and risk tier is low closes without agent review;
  recorded as `gate-only` in receipts.
- Acceptance: same-feature-class pipeline run shows >=40% review-token
  reduction against the Phase 0 baseline with zero change in merged-finding
  escape rate (track via post-merge fix prompts).

### Phase 2 -- Move bulk judgment off the subscription rails (Depot, routing)

- **Adversarial plan review (Phase 5) defaults to OpenRouter lenses** -- Kimi
  K3 primary, GLM 5.2 cross-check -- with the Codex lens reserved for
  high-risk-tier plans. Codex sign-off for security stays mandatory; plan
  critique does not need sub-budget.
- **Bulk/mechanical lanes default to DeepSeek V4 Flash 0731** (~$0.15/$0.29,
  agentic post-training, Codex-adapted) instead of climbing toward frontier
  rungs; `cheap_api` ladder reorders to `glm-5.2 -> deepseek-v4-flash ->
  deepseek-v4-pro -> ...` for mechanical work. Kimi K3 stays head of
  `frontier_api`/`bulk_api` where quality is the point.
- **Add the `bionic` host profile** to `harness-profile.json` (per the
  companion doc): GLM 5.2 as orchestrator, K3 escalation, V4 Flash executor,
  `local` role for LM Studio runtime models at $0. Bionic Secure Cloud is ZDR
  by default -- note it in the role comment.
- **When subs probe below headroom, descend the *whole* orchestration**, not
  just execution: airlift checkpoint -> resume in Bionic with GLM 5.2 driving
  (the harness-registry + guarded-continuation machinery already exists in
  airlift).
- Acceptance: a full pipeline feature completes with zero Codex/Claude sub
  tokens consumed on bulk lanes; weekly sub spend at equal throughput drops
  measurably in the Phase 0 rollup.

### Phase 3 -- Code owns the control flow (Depot, factory Phase 1)

- Promote workflow-kernel from shadow to **enforce mode for the lean pipeline
  class** (smallest blast radius). Kernel drives the phase loop, gates,
  retries, and airlift checkpoints; the host model is invoked *inside* phases
  only.
- The ~3,100 lines of orchestration prose stop being re-read per run -- the
  kernel executes the control flow; skills remain as phase-level prompt
  material only.
- Model-generated planning artifacts split: deterministic sections (manifest,
  coverage matrices, receipts) are code-generated from schemas; models write
  only the genuinely judgment-bearing prose.
- Fix cycles receive only the failing gate excerpt plus the relevant diff
  slice, never full context.
- Acceptance: one Baseplate chunk (suggest a `CORE-02` item) ships
  kernel-driven end to end; per-run orchestration-token line in the rollup
  drops toward zero.

### Phase 4 -- Factory config + observability (Depot, factory Phases 2-3)

- `factory.config.json` per repo: phases -> roles -> gates -> risk tiers, as a
  kernel `*-schema.json` contract. Baseplate's version is a *profile* (paths,
  thresholds, commands) per the ownership non-negotiable.
- Static HTML swim-lane run report generated by stdlib Python from the event
  log -- phase lanes, model, cost, gates, compiled prompts. Replaces
  "ask the agent what happened."
- Acceptance: report renders for the Phase 3 run; a teammate can diagnose a
  failed run without spending a token.

### Phase 5 -- Fleet operations (cross-project)

- **Herdr** hosts long runs: persistent panes survive lid-close/network drops,
  blocked/working/idle state per agent, socket API so the kernel (or an
  orchestrator agent) can wait on genuine blockers instead of polling. Airlift
  remains the resume contract; Herdr removes half the reasons to need it.
- **Bionic** is the exhausted-subs cockpit (GLM 5.2 orchestration per
  companion doc) and the local-model runtime for mechanical lanes.
- **Pi / T3 Code / opencode** consume the existing `generic` host profile --
  validate once, no per-harness forks.
- Rollout to other projects (assembly, co-op health, fleet, governance):
  install depot plugins, check in a repo profile + factory config, inherit
  every improvement above. No project forks the tooling.

---

## 4. Baseplate-side alignment (already queued -- no new work invented)

- `OPS-01` (active): build/CI hygiene -- keep as-is; record before/after
  timings as its prompt requires; those numbers feed the Phase 0 baseline.
- `TEST-01` (next): test/CI acceleration -- unchanged; faster tests make the
  Phase 1 pre-gates cheap enough to run before every review fan-out.
- `TOOL-01` -> split into `TOOL-01a` (= Phases 0-2 above, start now) and
  `TOOL-01b` (= Phases 3-4, the broker/host-authority substrate). Suggest
  recording this split in `sequence.md` so the deferred label stops hiding the
  cheapest leverage in the strategy.
- Quality-pulse tooling prompt: proceed as written after Phases 0-1 land; its
  available/unavailable/fallback/skipped evidence semantics are the same ones
  Phase 1's receipt reuse must honor.

## 5. What success looks like in 4-6 weeks

- Weekly sub budgets survive a full week of normal pipeline use; exhaustion
  becomes a routing event (descend to Bionic/OpenRouter), not a work stoppage.
- Per-feature token cost and elapsed time published per run; the top sinks
  list is measured, not estimated.
- A pipeline run's token spend is dominated by *phase content* (plans, code,
  review findings), with orchestration, redundant review, and passing-gate
  noise at near zero.
- The same system runs unchanged across Baseplate, the Fixture repos, and
  Depot itself -- profiles differ, tooling does not.

## 6. Queued actions

- [ ] Phase 0: kernel metrics rollup + `run-cost-summary.json` (Depot).
- [ ] Record the `TOOL-01a`/`TOOL-01b` split in Baseplate `sequence.md`.
- [ ] Phase 1: receipt content digests + evidence reuse + deterministic
      pre-gates in dm-review/execution-orchestrator.
- [ ] Phase 2: routing-policy + model-cascade updates (V4 Flash mechanical
      default, OpenRouter-first adversarial lenses, `bionic` host profile);
      regenerate Codex shims; `./tools/validate-composition.sh --all`.
- [ ] Phase 3: kernel enforce mode on lean pipeline class; prove on a
      `CORE-02` chunk.
- [ ] Refresh `model-selection.md` snapshot (Qwen3.8-Max watchlist, V4 Flash
      0731 note) per companion doc.
