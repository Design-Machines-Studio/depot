# Depot Software Factory + Open-Model Stack

Date: 2026-08-06
Status: Proposal
Context: Adapt depot toward a code-first software factory (inspired by
disler/super-simple-software-factory, "SSSF") and pick an open-model stack for
when the Claude/Codex subscription rails are exhausted.

---

## 1. Model research snapshot (2026-08-06)

Verified against vendor posts, Artificial Analysis composites, and independent
benchmark trackers. Vendor-reported numbers are directional; run depot's own
eval sweep before promoting any rung.

| Model | Released | Weights | Context | Price (in/out per 1M) | Coding/agentic signal |
|---|---|---|---|---|---|
| Kimi K3 (`moonshotai/kimi-k3`) | 2026-07-16 | Open (2.8T MoE, MXFP4) | 1M | $3 / $15 ($0.30 cache) | Strongest open agentic model: AA agentic #4, FrontierSWE 81.2, Terminal-Bench 2.1 88.3. Verbose thinker — high output-token burn, slower than median. |
| GLM 5.2 (`z-ai/glm-5.2`) | 2026-06-13 | Open, MIT (~753B MoE) | 1M | ~$0.95 / $3.00 | SWE-Bench Pro 62.1; top of AA open-weights index at launch; specifically noted for stably sustaining long, messy agent trajectories. |
| DeepSeek V4 Pro (`deepseek/deepseek-v4-pro`) | 2026-04-24 | Open, MIT (1.6T/49B) | 1M | $0.435 / $0.87 ($0.0036 cache) | V4-Pro-Max 80.6% SWE-bench Verified — highest open-weights entry. |
| DeepSeek V4 Flash 0731 (`deepseek/deepseek-v4-flash`) | 2026-07-31 | Open, MIT (284B/13B) | 1M | ~$0.15 / $0.29 ($0.0028 cache) | Post-training upgrade: Terminal-Bench 2.1 82.7 (vendor), native Responses API + Codex-agent adaptation. Best $/task in the open field. |
| Qwen3.8-Max (`qwen/qwen3.8-max`) | 2026-08-03 | Open weights announced for ~next week (2.4T) | 1M | $2 / $6 | Qwen claims a new coding bar (NL2Repo 55.9 best-in-class); independent coverage still thin — trails Kimi K3 on FrontierSWE (-7.7) and MLS-Bench (-7.3). Watchlist, not a rung yet. |
| Qwen3.7 Flash (`qwen/qwen3.7-flash`) | 2026-07-27 | — | — | $0.03 / $0.13, ~206 tok/s | Ultra-cheap mechanical/bulk lane candidate. |
| Local (Bionic/LM Studio runtime) | — | Qwen3.6 35B-A3B, Gemma4 26B class | varies | $0 marginal | Viable for trivial mechanical lanes (rename, format, boilerplate) at zero marginal cost. |

Reference points from the closed side (subscription rails): GPT-5.6 Sol/Terra
(GA 2026-07-09), Claude Opus 5 (2026-07-24, ~half Fable 5 price), Gemini 3.6
Flash (2026-07-21). The open tier is now genuinely within striking distance:
K3's FrontierSWE 81.2 and V4-Pro-Max's 80.6% SWE-bench sit just under the
frontier rungs at 5–30x lower token cost.

### Orchestration-model recommendation (the actual question)

The orchestrator/host model needs reliable tool calling, long-horizon
coherence, and structured-output discipline more than peak coding brilliance.
Ranked for "Claude + Codex subs are exhausted, keep shipping":

1. **GLM 5.2 via Bionic Secure Cloud — default orchestrator.** Best balance:
   near-frontier agentic quality, MIT weights, 1M context, ~$0.95/$3, and
   Bionic's cloud is Zero Data Retention by default — a privacy upgrade over
   depot's current OpenRouter posture (where ZDR is opt-in). Its differentiator
   is exactly orchestrator duty: stable long-horizon trajectories.
2. **Kimi K3 — quality-first escalation, not the always-on host.** Strongest
   open agentic model, but $3/$15 plus heavy thinking-token burn makes it the
   planner/security-lens/cross-check rung (where depot already places it), not
   the default driver.
3. **DeepSeek V4 Flash 0731 — budget-floor orchestrator and default executor.**
   At ~$0.15/$0.29 with the 0731 agentic post-training and Codex adaptation,
   this is the "keep the factory running all week for the price of a lunch"
   rung. Orchestration quality is a notch below GLM 5.2; execution $/task is
   unbeatable.
4. **Local models via Bionic — free tier for mechanical lanes.** Qwen3.6 35B
   class models handle formatting, boilerplate, and simple transforms at $0.
   Do not let them plan or review.
5. **Qwen3.8-Max — bake off when weights land (~2026-08-10).** If the open
   weights reproduce the hosted numbers, it could displace GLM 5.2 as the
   value orchestrator. Revisit this document then.

Suggested stack when subs are dry: **GLM 5.2 orchestrates (Bionic) → DeepSeek
V4 Flash executes → Kimi K3 plans/reviews the risky 10% → local models absorb
mechanical lanes.** Estimated blended cost: well under $1/hour of factory
runtime versus ~$15–50/hour equivalent on frontier API pricing.

---

## 2. Evaluation: depot vs the SSSF principles

SSSF's three design principles, scored against depot as it exists today.

### Observable — strong foundation, one gap

Already have: workflow-kernel's append-only validated event log with replay,
receipts with authentication, metrics module, quality-pulse profiles, airlift
checkpoint bundles, per-chunk `authoritative-receipts.json`. This is *deeper*
than SSSF's observability (they have a swim-lane UI; depot has cryptographic
-grade receipt discipline).

Gap: **no human-glanceable run view.** Kernel events are machine-first. SSSF's
swim-lane UI is the one thing worth stealing outright — but build it as *code*
(stdlib Python: event log → static HTML report with per-phase cost, model,
duration, gate results), not as an agent-summarized artifact.

### Customizable — strong, differently shaped

Already have: `model-cascade.json` + `harness-profile.json` (the only file
with host-specific knowledge — exactly SSSF's "agent config" insight, arrived
at independently), routing-policy.json, workflow-classes.json, per-plugin
skills as lazy-loaded context.

Gap: SSSF keeps the **core four (context, model, prompt, tools) per phase in
one YAML data file**. Depot's equivalents are split: models in cascade JSON
(good), but prompts and tool grants live inside skill/command Markdown prose,
so retargeting a phase means editing prose. A per-run factory config (data,
not prose) is the missing piece.

### Reusable — strong

18 plugins installable across repos, airlift for cross-harness resume,
project-scaffolder for greenfield installs, dual Claude/Codex manifest
generation. Depot is ahead of SSSF here (SSSF's `/install` copies templates;
depot has versioned plugin distribution with dependency checks).

### Agents + code — the real inversion still ahead

This is SSSF's core thesis: *code proposes the control flow, agents propose
content, code disposes.* Depot has all the machinery but the control flow is
still host-model-driven: the pipeline skill is ~650 lines of Markdown that the
host model interprets and executes phase by phase. The workflow-kernel runs in
**shadow mode by default** — it observes and validates but does not drive.

That inversion is the factory move: `python3 -m workflow_kernel run
<workflow-class>` should own the phase loop, call harness CLIs per phase
config, run deterministic gates as code, and only spend tokens where judgment
is required. Every phase boundary, gate, retry, and checkpoint that is
currently executed by an expensive model reading instructions becomes free,
instant, deterministic code.

### What NOT to copy from SSSF

- SSSF runs agents on the main branch; depot's worktree isolation per chunk is
  strictly better. Keep it.
- SSSF's typed JSON handoffs between phases: depot already has the canonical
  `*-schema.json` contracts in workflow-kernel. Reuse those; don't invent a
  second envelope format.
- SSSF is single-harness (Pi only). Depot's harness-profile abstraction is the
  right layer — extend it, don't bypass it.

---

## 3. Factory plan (phased)

### Phase 1 — Invert control for one workflow class (foundation)

- Promote workflow-kernel from shadow to **enforce mode for one pipeline
  class** (suggest: the lean-mode pipeline, smallest blast radius).
- Kernel drives: phase loop, gate execution, retry-with-failure-context,
  airlift checkpoint at each boundary (contract already exists in
  `plugins/pipeline/references/airlift-checkpoint.md`).
- **Deterministic gate runner**: tests, lint, typecheck, build run as code.
  Passing output never enters an agent's context — only failures do, and only
  the failing excerpt. This is the single biggest token saver available.
- Exit criteria: one full feature shipped with the kernel driving, host model
  only invoked inside phases; token spend per phase recorded in the event log
  and compared against the same feature class run Markdown-driven.

### Phase 2 — Factory config as data

- New per-repo `factory.config.json` (or YAML): phases, role per phase
  (`frontier_api` / `cheap_api` / `bulk_api` / `local`), gate commands, risk
  tier, timeout. Roles resolve through the existing
  `model-cascade.json` → `harness-profile.json` chain — no new source of truth
  for models.
- Add a **`bionic` host profile** to `harness-profile.json`: Secure Cloud
  slugs (GLM 5.2, Kimi K3, DeepSeek V4 Pro/Flash) plus a `local` role kind for
  LM Studio runtime models. Keep Bionic's ZDR property documented in the role
  comment — it changes the privacy calculus versus OpenRouter rungs.
- Phase prompts become template files with variables (SSSF's
  instructions/variables/workflow/report format), referenced by the config —
  not embedded in skill prose.

### Phase 3 — Observability report (code, not agent)

- Stdlib Python generator in workflow-kernel: event log + receipts → static
  HTML swim-lane report (phase lanes, model used, cost, gate results, compiled
  prompts, handoff envelopes). No JS build, no dependencies — consistent with
  the kernel's stdlib-only rule.
- This replaces "ask the agent what happened" with "open the report" — another
  token sink eliminated.

### Phase 4 — Fleet operations

- **Herdr** as the persistence/multiplexing layer: persistent agent panes,
  blocked/working/idle state, socket API agents can drive, SSH reattach. It
  detects 19 agent CLIs including Claude Code, Codex, and Pi — factory phases
  run in Herdr panes so lid-closing and network drops stop killing runs
  (airlift already handles the resume side).
- **Bionic** as the open-model cockpit and the exhausted-subs environment.
- **Pi / T3 Code / opencode** map to the existing `generic` host profile —
  no depot changes needed beyond validating the profile against them.
- Team use: factory config + cascade files are checked in, so teammates get
  identical routing; Bionic seats or shared OpenRouter keys slot into the same
  roles.

### Token-reduction tactics (bake into every phase)

- Never feed passing gates to agents (Phase 1 gate runner enforces this).
- Diff-scoped review: dm-review already fans out specialists; gate the
  expensive lanes (security-auditor, architecture) behind risk tier and diff
  size, run them on Kimi K3/GLM 5.2 instead of frontier subs.
- Cache-aware prompting: DeepSeek cache reads are ~$0.003/M — stable system
  prompts and phase templates pay off measurably at factory scale.
- Local-first mechanical lanes: format, rename, boilerplate, snapshot updates
  go to $0 local models in Bionic.
- Escalation, not default: frontier subs (when available) and Kimi K3 are
  pulled in by gate failure or risk tier, never by default.

---

## 4. Actions queued by this document

- [ ] Refresh `plugins/openrouter/.../model-selection.md` snapshot: add
      `qwen/qwen3.8-max` to the watchlist (not a rung), note V4 Flash 0731's
      agentic post-training upgrade, add `qwen/qwen3.7-flash` as ultra-cheap
      bulk candidate. Re-pull live pricing via MCP receipt per the file's
      15-minute freshness rule before paid runs.
- [ ] Prototype Phase 1 on the lean pipeline class.
- [ ] Draft `factory.config.json` schema as a kernel `*-schema.json` contract.
- [ ] Add `bionic` host profile to `harness-profile.json` (edit
      `.claude-plugin` sources, regenerate Codex shims, run
      `./tools/validate-composition.sh --all`).
- [ ] Re-evaluate Qwen3.8-Max when open weights land (~2026-08-10).
