# Assembly development improvements — implementation plan

**Current plan, refreshed 2026-09-08.** This covers the entire instruction,
model, skill, harness, and workspace audit. It supersedes the sequence in the
[earlier alignment audit](https://github.com/Design-Machines-Studio/depot/blob/docs/depot-planning-20260907/plans/astra-alignment-20260908.md),
which remains the detailed source inventory. The routing update is the first
implemented part; the other project changes have not shipped.

**Next bounded development chunk: INSTRUCTIONS-01 — repair shared instruction
and workflow defaults in Depot.** Fix the generator before rolling its policy
into consumer repositories. The routing source is merged; publication and consumer proof remain separate;
PR #129 retains its own browser/Compose closeout owner. Neither the native price
refresh nor a model benchmark tournament is a prerequisite for instruction work.

## Execution prompts

Start with [INSTRUCTIONS-01](prompts/assembly-improvements/01-instructions-01.md).
The [fresh-session prompt pack](prompts/assembly-improvements/README.md) contains
complete prompts and installed-router model recommendations for each affected
project, shared skill pass, cost/harness task and optional maintenance operation.
Bring back each exact PR result before advancing dependent work.

## Current status and authority

Depot main is `386b98e26f493cc220047c981cd5c01b1513b24d` after merged PR #131.
Routing branch `feat/astra-driver-routing` was implemented and locally validated
at `0b3e84a65a1f85e8a7584f521f46540c102f9703` from main
`bda7cab9ddc97b1bf8746da05ce275584d281031`. PR #130 advances OpenRouter to
1.20.3; it must be retained when integrating this branch. Local source validation
on the earlier base is not a merged-main or consumer-proof claim.

| Audit gap | Current state | Owning chunk |
|---|---|---|
| Astra absent from routing | Merged source in PR #131; publication and complete install/consumer proof pending | MODEL-01 closeout |
| CLI still Luna/maximum | Superseded: current user config reads Astra/high, with 1,000,000/400,000 context overrides; the policy recommends low | CONFIG-01 |
| Blanket scaffolded chores and approvals | Pending | INSTRUCTIONS-01 |
| Baseplate root approximately 83 KB | Pending; exceeds the default project-instruction allowance | INSTRUCTIONS-02 |
| Prototype personal Notion and file-count gates | Pending | INSTRUCTIONS-03 |
| Floor retained P3 findings optional | Pending | INSTRUCTIONS-04 |
| Missing portable entrypoints in Jig/component library | Pending | INSTRUCTIONS-05 |
| Large or conflicting shared skills | Pending, one plugin per branch | SKILLS-01 onward |
| Native price evidence and paid-budget visibility | Pending; $50/month remains the operator ceiling, not a verified configured limit | COST-01 |
| Foreman transport, effort, compaction, progress ergonomics | Pending real Pi canary | HARNESS-01 |
| Old folders, worktrees, and proof snapshots | Inventory/reconciliation pending; nothing authorized for deletion by this plan | CLEANUP-01 |

Repository-specific findings below were inspected in the September 8 audit.
Refresh the owning repository, instructions, open PRs and worktrees at execution;
do not assume those snapshots are current permission to edit another session's
files. Demo's thin instructions had no demonstrated defect and need no rewrite.

## Results the whole program must achieve

- Two trusted developers can finish ordinary work without repeated planning,
  documentation-agent, lesson-update, or permission chores. Approval remains
  necessary at real destructive, credential, authorization and release boundaries.
- Instructions fit their harness's loading budget and point to existing topical
  references. Shared workflows work without Notion or personal memory systems.
- Assembly remains a self-installed, federated intranet for 5–50-person co-ops
  using internally developed trusted Fixtures. No speculative enterprise scale,
  hostile-Fixture infrastructure, approval platform, or additional service.
- Reuse Live Wires and existing components. Preserve prototype structure, copy,
  classes and meaningful states unless a divergence is deliberate. Keep
  accessibility, performance, upgrades, maintenance and actual security tests.
- Fix every retained P1/P2/P3 finding. Keep applicable review and rendered checks,
  reuse still-exact evidence, and stop review churn after convergence.
- Astra drives design and integration; bounded workers receive clear ownership
  and acceptance. Subscription capacity and economical OpenRouter offload are
  both useful. No worker inherits the driver model or maximum effort implicitly.
- Human reports are brief and plain, with the result and one next action.
  Estimates, unavailable measurements and failed lanes remain explicit.

## Execution sequence

Each numbered consumer row is a separate repository branch and PR. A skill pass
changes one owning plugin at a time. Prepare one complete execution prompt for
the selected chunk when requested; do not issue a bundle of competing prompts.

### MODEL-01 — finish the existing routing change

Owner: Depot. Source merged in PR #131; publication uses a fresh worktree at
the verified merged commit.


- model-router 0.7.0: native Astra first for `architect` and `builder-deep`,
  Sol fallback, existing Luna bounded workers and Terra specialist reviewers.
- Pipeline 1.67.0: demanding implementation defaults to medium; bounded workers
  may use high/max with settled requirements, file ownership, and acceptance.
  Existing lower mechanical defaults, legacy translations, review rosters,
  security effort, browser evidence, and retained P1/P2/P3 obligations remain.
- project-manager 1.14.0: medium architecture opinions; explicit task-based
  worker effort; separate critic effort and independence.
- Keep the closed role/effort schemas and existing adapters. No new service,
  model tier, budget ledger, provider, or context override mechanism.
- OpenRouter 1.20.2 and its August 27 catalog remain unchanged. Astra is native
  only; missing native price estimates are reported unavailable. Price refresh
  and long-input cost attribution are a separate bounded follow-up.

Acceptance: real dispatch fixtures select Astra at low/medium, retain Luna at
high/max, preserve quota fallback and explicit effort, and keep identities out
of participant surfaces. Verify generated manifests, dependency floors, routing,
recommendations, terminal receipts, and full composition. No paid sweep is needed.

PR #131 merged this source and retained PR #130. Before later authorized
delivery, inspect its exact source and retained findings, verify exact-head CI
or state its absence, trusted main, plugin tags, both harness caches and one
real consumer chunk. No merge, tag or installation refresh is authorized by the
current planning task. Existing PR #129 remains a separate browser-review lane.

### INSTRUCTIONS-01 — fix the shared generator first

Owner: Depot `project-scaffolder`, plus Depot's root workflow guidance.
Likely surfaces: scaffolding SKILL.md, `references/project-configs.md`, generated
instruction/hook templates, associated fixtures, AGENTS.md and CLAUDE.md.

Remove unconditional planning for three steps/files, documentation-agent runs
after every edit, lesson writes after every correction, and file-count-driven
commits. Replace these with task-based workflow selection and explicit authorized
completion. Keep real Docker, credential, authorization, destructive-action and
release protections. State the small trusted-team scope without copying an
entire company strategy into every generated file.

Acceptance: generated examples for the supported project types have concise,
portable instructions and no conflicting mandatory chores. A docs correction,
ordinary Go/Templ change and authorization change each select proportional work
and verification. Define a docs-only validation lane for Depot while retaining
full composition for plugin changes. Check generated artifacts and affected
fixtures; use full composition for the plugin update. Bump only the owning
plugin and regenerate its Codex metadata. No consumer product code changes.

### INSTRUCTIONS-02 through 05 — apply the policy in consumers

Start with Baseplate after the generator policy is reviewed and available.
Aim for roughly 8 KiB or less across root instruction entrypoints where practical;
verify the actual discovered instruction stack fits the harness allowance. This
is an editing target, not permission to remove necessary contracts or merely
raise Codex's default 32 KiB project-document allowance.

| Chunk / owner | Smallest change | Acceptance |
|---|---|---|
| INSTRUCTIONS-02 / assembly-baseplate | Shorten root AGENTS/CLAUDE; remove repeated chores; move detailed reference into existing topic docs | Both harnesses find the same authority; preserve Go/Docker runbooks, auth, migrations, testing and release requirements; ordinary work has one appropriate verification path |
| INSTRUCTIONS-03 / prototype Assembly | Remove mandatory personal Notion access and full Pipeline selected by file count | Work succeeds without personal systems; prototype remains UI authority; rendered desktop/mobile checks still apply to affected UI |
| INSTRUCTIONS-04 / Assembly Floor | Require fixing every retained P3; make personal design context optional | All retained findings are mandatory; preserve Floor's read-only observation boundary and Live Wires design authority |
| INSTRUCTIONS-05a / Fixture Jig | Add a thin portable AGENTS entrypoint to existing authoring authority | Codex and Claude find the same trusted-Fixture rules and documented author loop; do not duplicate a second guide |
| INSTRUCTIONS-05b / livewires-templ | Add a thin portable entrypoint | Preserve generated Templ output rules, attribute safety and component reuse |
| INSTRUCTIONS-05c / Governance | Consolidate only demonstrated instruction duplication | Preserve the current author loop, verification and release authority; avoid active product PRs |

For each: inspect the exact diff and effective instruction load; run focused
repository checks for changed instruction generators or hooks. Documentation
alone does not require an unrelated application test sweep. If an instruction
changes the development command path, exercise that path on a disposable target.
Do not update old worktrees, dependency caches or upstream checkouts by grep.

### SKILLS-01 onward — reduce loaded instructions without losing knowledge

Owner: Depot, one plugin per branch in this order:

1. Assembly development: separate prototype authority from production
   Go/Templ/Datastar work; move detailed implementation references out of the
   large entrypoint and preserve correct authoring/upgrade rules.
2. Pipeline: remove duplicated planning and review gates; retain approved scope,
   requirements, deterministic verification, cleanup and delivery contracts.
3. dm-review: consolidate repeated guidance, retain applicable lanes, all retained
   findings, repository-owned browser discovery and honest unavailable outcomes.
   Begin after the active #129 owner has finished its shared review surfaces.
4. Design Machines strategy/discovery: narrow the oversized trigger description
   and load task-specific references without losing company constraints.

Inspect coordinator and other relevant shared skills for conflicts as part of
those affected paths; change them only where a reproduced conflict requires it.
Do not rewrite unrelated domain knowledge merely because it is lengthy.

Acceptance per pass: focused trigger/contract fixtures, one ordinary consumer
example, and measured loaded context before/after. Report bytes or estimated
context as such, not measured model tokens. Preserve canonical Claude sources,
generated aliases/manifests, necessary dependency floors and full composition.
No new orchestration engine, state schema or general runbook parser.

### CONFIG-01 and COST-01 — local defaults and economical routing

CONFIG-01 is an operator-local check. The saved CLI setting now reads Astra/high;
do not claim Luna/max or overwrite a newer choice silently. The agreed default
recommendation remains Astra/low, medium for demanding work and selective high+
escalation. Keep current context overrides optional and local. Their catalog
cap and source-derived calculations are recorded in
[driver-worker guidance](../plugins/model-router/skills/model-router/references/driver-worker-guidance.md).
Do not propagate those overrides to workers, other models or providers.

COST-01 is a bounded Depot change to current native price evidence and its
existing reporting consumers. Refresh cited OpenAI prices and long-input tiers;
keep the OpenRouter catalog's independent evidence dates intact. Missing prices
stay unavailable until the existing summary can represent them truthfully.
Subscription usage is not API billing. Do not build a general pricing engine.

Use existing provider budget controls and receipts for the $50/month operator
ceiling. Verify what monthly spend/headroom the account actually exposes before
claiming enforcement. Prefer available subscription capacity and focused cheap
offload; avoid speculative paid sweeps. Record per-run measured spend, fallback
and unknown usage. Account settings belong to the operator, not tracked shared
routing policy. A missing monthly API does not justify a new budget service.

Acceptance: a native call, a bounded metered call and an unavailable measurement
are reported honestly; quota exhaustion falls back without repeated approvals.
Validate Luna High/Max with a small real implementation and required review,
comparing accepted outcome, retained defects, repairs, latency and measured usage.
One useful comparison is enough to inform the next choice; no blanket savings
or benchmark claim is justified by the calibration post.

### HARNESS-01 — prove the existing Pi path before extending it

Owner: Foreman for execution; Floor only for its existing observation UI.
Reacquire current source: the audit found Pi 0.84.4, fixed high thinking, disabled
compaction, an in-memory session and a fixed proof task. These are inspection
leads, not a claim that the current adapter is broken.

First run one bounded Astra canary through the actual pinned Pi adapter: tools,
request/response compatibility, selected effort, task progress, steering and
cancellation. Check the Astra tool endpoint before making compatibility claims.
Then replace only the fixed proof-task/effort assumptions that block current work
with one useful current work profile. Reuse existing Pi events, steer and abort;
keep Floor as the existing reader of progress. Evaluate compaction separately.

Acceptance: one real bounded task can be followed, steered, stopped and reported
through the current UI, with actual participant and measurement gaps visible.
OpenRouter continuation must respect its actual adapter capabilities. No new
broker, browser service, general workflow platform or invented transport layer.

### CLEANUP-01 — reconcile folders and worktrees safely

Owner: workspace maintenance across `/home/ned/ai` and `/home/ned/assembly`.
Inventory can run independently of instruction implementation. Deletion cannot.

Produce an exact keep/archive/remove/uncertain list tied to Git registration,
local and remote commits, merged PR state, dirty/untracked files, evidence and
current ownership. Preserve active and unique work, benchmark evidence, upstream
references and dependency caches. The earlier readable inventory found 61 AGENTS
and 49 CLAUDE files, including historical copies; protected proof directories
were unreadable. Treat that uncertainty honestly.

Prepare the concrete removal list for explicit authorization. At execution,
recheck every approved path before removing it; preserve unique files/commits and
confirm recovery evidence first. Do not infer permission from age or merged
branch names. Never stash, reset, clean, switch or discard the protected primary
checkout to make cleanup easier. No broad recursive deletion or remote-branch
cleanup is authorized by this plan.

Acceptance: intended worktrees still resolve, active repositories are intact,
unique work and evidence remain recoverable, and the receipt names exactly what
was removed, retained or blocked. Use existing Git/filesystem tools; no cleanup
service or new registry.

## Coordination and completion

Only active Issues/PRs that directly advance Assembly belong in Project 1. Keep
native repository ownership; do not create a parallel backlog or copy consumer
product roadmaps. Reuse the existing planning index and treat older untracked
plans as evidence leads, not competing execution authority.

R-series remains: R0 aggregate proof uncertain, R1 comparison measurement
blocked, R2 complete, R3 superseded, R4 complete, R5 source complete with live
client proof unavailable. HL01/02 and capture source work are complete; automatic
lesson application remains rejected. Retain those commitments alongside this
program without building speculative replacements.

Every plugin chunk records canonical version/marketplace, generated Codex
surfaces, necessary dependency floors/index/fixtures, local and exact-head
verification, then separately authorized trusted-main/tag/cache/consumer proof.
Root consumer instructions ship through their own PRs. Keep output brief, fix
retained findings, and preserve exact evidence instead of repeating whole reviews.

The program is complete only when targeted current repositories load coherent
instructions, shared plugin behavior is installed and consumer-proven, Pi's
current path is demonstrated, the paid budget is truthfully observable or its
limits stated, and approved cleanup has preserved recoverable work. A routing
merge alone does not complete the instruction or harness migration.

## Prior routing implementation evidence


The focused implementation passed `validate-composition.sh --all` on September
8. The affected router suite passed 141 assertions, the recommendation suite 24,
terminal reporting 37, and the OpenRouter noninteractive suite 41 tests. Generated
Codex manifests and command aliases, dependency floors/graph, and the search
index are current. One retained P2 from a bounded contract check was fixed: the
legacy installed-router fallback now requires 0.7.0, with fail-closed coverage.
The earlier reported five OpenRouter baseline failures did not reproduce here.

Initial validation exposed old dependency/version expectations and a candidate
count that needed updating; those were fixed. The final full run had no failures.
Its local log is `/tmp/astra-routing-evidence/composition-final.log`. Local proof
does not establish exact-head hosted CI, trusted-main, publication, installation,
or consumer delivery. That implementation turn changed no native Issue/PR or Project state; this
planning follow-up opens a PR for the implementation and complete rollout plan.

The read-only source recommendation resolves an attemptable native driver at
low effort with the existing native baseline as fallback. It does not dispatch
a model. Model performance, consumer execution, large-context latency/usage,
native API-equivalent pricing, and organization monthly-budget headroom remain
unmeasured here. User configuration and installed harnesses were not changed.

Model and cost report for the bounded contract check: role `review-fast`;
requested participant GPT-5.6 Luna, requested effort high; Codex native
collaboration rail; completed with one retained P2 subsequently fixed. Served
identity, effective effort, duration, tokens, and subscription charge were not
exposed by the collaboration tool. One subscription delegation; no observed
fallback. OpenRouter calls: 0; paid API spend: $0 because no paid API call ran.
The existing primary driver session is separate and its usage is unavailable.
This is not a fabricated model-router receipt or an independence claim.

SIMPLICITY-CHECK: three owning plugins, existing roles/adapters and effort
vocabulary; no new services, account controls, provider routes, context override
mechanisms, or unrelated plugin bumps.

NOT-COVERED: real worker-performance comparison, long-session context behavior,
native price refresh, monthly budget enforcement, consumer instruction rollout,
Pi compatibility, cleanup, release/tag/cache synchronization, and hosted CI.
Release preflight is not a delivery pass: installed caches intentionally retain
older versions, and its equal-version check also flags inherited dm-review 1.80.0
against the preserved merged-PR branch. Neither condition authorizes cache
refresh, an unrelated bump, or deletion of a worktree.

COMMANDS-RUN: authenticated main fetch and GitHub reads; fresh worktree creation;
selective Codex configuration/catalog reads; official documentation and matching
Codex source inspection; installed and source recommendation rendering;
`test-model-router.sh`, `test-assembly-coordinator-recommendation.sh`,
`test-terminal-model-report.sh`, `validate-provider-neutral-routing.sh`,
`validate-workflow-contracts.sh`, `validate-dm-review-codex-perspective.sh`,
`check-dependencies.sh`, both Codex generators/checks, index/graph regeneration,
`validate-composition.sh --all`, release preflight, local-link and diff checks.
