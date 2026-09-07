# Model and instruction optimization — 2026-09-07

Planning only. No plugin code, project instructions, personal configuration,
release tags, installations, or GitHub native items changed in this audit.

**Next Depot chunk: OR-EFFORT-01 — make OpenRouter effort requests and reports
agree with the request actually sent.**
[Complete execution prompt](prompts/or-effort-01-truthful-effort.md).
This is a small prerequisite for economical model tuning. It does not select
a new portfolio or redesign the harness. UI-READY-03 remains a reproduced,
prepared development blocker and follows this repair.

## Product constraints

Two trusted developers build internally authored Fixtures for self-installed
co-op intranets serving 5–50 people. Installations connect through federation;
each co-op owns its data and decides what to share. Preserve the current
single-binary, SQLite, embedded-NATS and server-rendered architecture unless a
measured requirement demands otherwise. These are constraints, not a request
to redesign existing production code.

Design Machines' strategy and the requested personal-memory context support
small, maintainable products, expressive editorial design, workplace democracy,
and scaling across independent co-ops. An internal development assistant does
not imply adding AI to the member-facing product. Older memory is context,
not authority over current source or the user's latest instructions. Personal
memory and Notion must remain optional for every other developer.

Reuse Live Wires primitives, tokens and livewires-templ components before
creating local equivalents. A reusable component belongs upstream when a real
consumer establishes the need; a consumer-specific adjustment belongs locally.
DRY means avoiding meaningful duplication, not extracting an interface for two
similar expressions. YAGNI does not excuse weak accessibility, broken upgrades,
missing authorization, unsafe backups, or slow pages.

Trusted developers and in-process Fixtures are not an adversarial plugin
marketplace. Members, uploaded data, network requests, federation peers,
credentials and update artifacts still have real trust boundaries. Require a
reachable failure, affected person, and smallest adequate repair. Keep every
retained P1/P2/P3 finding blocking; reject speculative findings instead of
expanding the product to satisfy them.

## Evidence and current state

Authenticated Depot main: `76267e0e10845e1f9ea4a5eb533b6ca9628b12be`.
No open Depot Issues or PRs at this refresh. Primary checkout remains
`bench/gpt-6-astra-screen`, head `6ab616fd5e3bd5c7f2e11ed44677413f0d8de759`,
with the existing modified CLAUDE.md, 169 deleted tracked todos, and nested
untracked benchmark checkout preserved. There are 26 registered worktrees,
including this planning branch. Historical clones/worktrees are evidence,
not 26 independent implementation owners.

| Area | Version/state | Verified problem or next decision |
|---|---|---|
| Pipeline | 1.66.1 | Assessment/prompt entrypoints still contain long procedural gates; browser completion inherits dm-review readiness |
| dm-review | 1.79.1 | Repository target discovery gap reproduced; full mode has five core lanes plus default second perspective and conditional lanes; root skill is 50,156 bytes |
| model-router | 0.6.1 | Policy maps effort but the OpenRouter invocation drops it; architect policy starts with Sol and does not include Astra |
| OpenRouter | 1.20.1 | Wrapper request omits reasoning effort and output limit; installed matrix dated August 27, native price evidence August 12 |
| Workflow Kernel | 0.19.1 | Reusable verification and observation contracts exist; no new ledger, broker, or service justified |
| project-manager | 1.13.0 | Coordinator already separates anonymous role requests and human model recommendations; keep that contract and shorten repeat refreshes |
| Assembly | 3.16.0 | 46,141-byte development skill mixes prototype examples, production guidance and historical roadmap instructions |
| release/sync | Relevant versions tagged; both caches matched source in prior refresh | Local/source/publication/cache/consumer proof remain separate; no new publication authorized |
| measurement | Existing receipts and terminal renderer | Requested effort is not proof of a transmitted setting; R1 comparable review-loop savings remain unproven |

Depot's current main has no required hosted validation check configured. Recent
PRs #120, #123, #125 and #126 expose Codesmith SKIPPED, not a passing hosted
composition gate. Prior local full composition and release preflight passed.
Do not turn this observation into a new CI platform project during this work.

Current consumer revisions inspected:

| Repository | GitHub main | Instruction disposition |
|---|---|---|
| assembly-baseplate | `2fd96359e1c9e239d0eef0ced80f046c08a24432` | 81,551-byte AGENTS.md, 9,973 words; consolidate first among consumer roots |
| assembly-fixture-jig | `50f0d47c275928953dcaa81ee15d68e05cf0a0ae` | No AGENTS.md; concise CLAUDE.md has correct trusted-Fixture scope and author loop; expose portably to Codex |
| assembly-governance | `d1f341dc051cdfd1bb4bbe55764dbb0d8f8ed32d` | 10,799-byte AGENTS.md; retain exact dev loop, move release-history detail into references |
| livewires-templ | `84e1e24c81784497b6fb7004e0ed7fa0d763b6ae` | No AGENTS.md; preserve generated-output, attribute safety, component and release rules from CLAUDE.md |
| assembly-floor | `561352882d2402ffb2b6889de101f31c22e0ef8b` | 11,213-byte AGENTS.md; keep read-only boundary, shorten command inventory; START-HERE is stale |
| foreman | `65b94dd03ad630de1bd4d0fed1f4615288672d37` | 712-byte AGENTS.md; clarify accepted proof now permits its implemented runtime; retain ownership constraints |
| assembly (prototype) | `6268ea42ff34f13652f0f06967f6a175dd6756b2` | Separate design authority, not retired; remove mandatory personal Notion gate and duplicate full workflows in its own branch |
| assembly-demo | `c7a54d5f2005edf0e7e4b5d10fdb4eb66286f200` | Thin 1,408-byte routing file; no demonstrated rewrite needed |

The filesystem audit discovered **87 AGENTS.md files, 42 unique contents**,
including historical worktrees, two Go module-cache copies and two harness
test snapshots. These are not 87 active projects and their aggregate size is
not the context cost of a session. Unique historical differences were compared
with current source. Full path/hash inventory is retained locally with audit
evidence; do not mass-edit old worktrees, module caches or test snapshots.

Other coverage: ai-memory repeats generic plan/agent/lesson ceremonies and a
universal pre-commit test gate; review applicability separately from its real
data-safety rules. deepseek-harness is an upstream reference checkout: its root,
package, docs, native, examples, scripts, website, vendor and note instructions
were compared as upstream-specific guidance. Do not import its architecture or
rewrite it as a Design Machines app. AIOStreams inspection, Gelato and the
new wiz-control checkout have no discovered AGENTS.md; no blanket scaffolding
is justified merely by their location under ~/ai. Duplicate Depot, Floor and
Baseplate clones retain their current work untouched.

## Findings that change the plan

1. **Standing instructions can exceed the loader budget.** Baseplate main's
   AGENTS.md is about 2.5 times Codex's default combined 32 KiB project-document
   allowance. This machine has no `project_doc_max_bytes` override. This is a
   documented truncation risk, not proof that this particular app session lost
   a particular line. Move detailed route maps, environment matrices, release
   history and implementation facts to existing topic documents. Merely raising
   the limit would retain the repeated context cost. [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
2. **Templates reproduce the overhead.** project-scaffolder's
   `references/project-configs.md:203–237` requires plan mode for every
   non-trivial task, doc-sync after any code change, lessons after any correction,
   and file-count-driven commits. Its hooks repeat these nudges. Baseplate has
   the same clauses. Its engineering-principles document already says to keep
   process proportionate. Repair the generator and then its real consumers.
3. **The local default spends maximum reasoning indiscriminately.**
   `~/.codex/config.toml` selects Luna with `model_reasoning_effort = "max"`;
   its OpenRouter profiles have no explicit effort override. This does not
   describe the current Astra planning session. Proposed local defaults are
   Terra/medium for general coding and explicit Astra/medium planners, with
   Luna/low for clear mechanical tasks. Confirm task quality with small canaries.
4. **OpenRouter effort reporting exceeds the evidence.**
   `role-dispatch.sh:563` computes effective effort, but both OpenRouter read
   and write invocations omit it. `openrouter-wrapper.sh:470–512` constructs
   messages/provider/stream settings without reasoning effort; router receipts
   nevertheless record effective effort. Fix the transport and report requested,
   transmitted and unavailable evidence honestly. No model-quality claim can
   substitute for this deterministic repair.
5. **Model discovery and billing need freshness, not another routing service.**
   The installed recommendation still projects Sol API-equivalent prices of
   $5/$30 per million tokens from August 12. Current official comparison lists
   $4/$20; the OpenRouter catalog can quote different rail prices. Subscription
   use is not a paid API charge. Qwen's undated alias is absent from the flat
   catalog but its endpoint lookup successfully resolves to `qwen3.8-max-0902`;
   absence from that list alone is not a routing failure. [Official comparison](https://developers.openai.com/api/docs/models/compare),
   [live provider catalog](https://openrouter.ai/api/v1/models).
6. **Skill discovery is noisy and entrypoints mix purposes.** The 79 local
   source/alias SKILL.md files contain roughly 31,671 description characters;
   this is an inventory total, not measured injected tokens. Strategy's
   description alone is 1,255 characters. Development contains both “prototype
   becomes the product” and the separate production implementation model, old
   internal Fixture paths, and a future builder-service phase. Live Wires says
   never create classes, then permits new components later. Make these scopes
   explicit; keep the useful examples in task-specific references.
7. **The anti-overengineering rules already exist.** dm-review's deployment
   context and current Jig instructions explicitly reject hostile-author and
   speculative enterprise machinery. Adding another long manifesto will not
   resolve conflicting templates or stale skill examples. Keep real checks,
   remove duplicated process, and compare actual review outcomes.

The linked [Astra skills article](https://x.com/pvncher/status/2095991462416490862)
was retrieved through a public mirror after direct X access failed. Its central
advice is concise discovery, conditional references, less procedural scaffolding,
and explicit completion boundaries. The installed OpenAI skill-creator guidance
and [official Astra guide](https://developers.openai.com/api/docs/guides/latest-model)
support the same direction. Shared instructions must still work for economical
workers and Claude; do not remove important invariants solely because Astra
can infer them.

## Model and budget operating plan

These are proposed defaults, not an adopted benchmark result. Concrete identities
belong in router policy and human recommendations, never participant prompts.

| Work | Proposed model / rail | Effort and escalation |
|---|---|---|
| Per-project planning and synthesis | GPT-6 Astra / Codex subscription | medium; high for ambiguous architecture, migrations, federation or release decisions; reserve max for an explicit hard problem |
| Routine implementation with judgment | GPT-5.6 Terra / Codex subscription | medium; escalate to Sol/high after a concrete capability gap |
| Difficult multi-file implementation or debugging | GPT-5.6 Sol / Codex subscription | high; do not use it for inventories and ordinary formatting |
| Clear mechanical edits and extraction | GPT-5.6 Luna / Codex, or DeepSeek V4 Flash 0731 / OpenRouter for usage relief | low where supported; verify produced changes deterministically |
| Bounded bulk context and independent analysis | DeepSeek Flash for extraction; approved Pro/Qwen/Grok candidates for substantive judgment / OpenRouter | choose through current router and evidence; one suitable independent lane, not every model |
| Security review | Current security-review role | only applicable real boundaries; Kimi is a candidate, not a mandatory additional reviewer |
| Rendered UI | Host-owned T3/browser automation plus applicable evidence analysis | exact desktop/mobile target, prototype parity, semantic/accessibility checks |

OpenAI's model guidance positions Terra for everyday work and Luna for focused,
repeatable tasks. Actual subscription consumption also depends on context,
reasoning, tools and caching; API token prices cannot predict a weekly reset.
Changing OpenAI models may reduce consumption but does not establish an
independent allowance pool. [Codex models](https://learn.chatgpt.com/docs/models),
[subscription pricing and limits](https://learn.chatgpt.com/docs/pricing).

The user's OpenRouter target is **US$50/month or lower**. Aim for $30 in normal
model charges and propose a provider-enforced $40 monthly limit to leave room
for reserve/fees within the overall target. Verify billing treatment before
claiming an all-in ceiling. Count every harness and key using that budget; a
$40 limit on each of several keys is not an aggregate $40 limit. Use existing
provider controls and current receipt reporting, not a new budget database.
No account/key setting was changed during planning.

Suggested allocation within $40: $20 routine offload, $10 harder independent
work, $10 interruption reserve. These are spending allowances, not targets to
use up. Proactively offload suitable tasks early in the week instead of waiting
for subscription exhaustion. Check authoritative remaining key usage at session
start; distinguish unavailable quota from zero quota. At the ceiling, use
available subscription work or checkpoint cleanly. Never silently raise the cap.
[OpenRouter key limits](https://openrouter.ai/docs/api_reference/limits).

The existing dispatcher selects native candidates first in most role lists;
an 8% exhaustion threshold is not weekly capacity planning. Adjust candidate
order for economical roles in a later bounded router change, retaining caller
requests of role/capabilities/effort only. A prompt-only OpenRouter participant
does not acquire repository tools merely by having a long context window.
Foreman supplies its own Pi tools; this requires a compatible session binding,
not pretending the one-shot wrapper is a Pi transport.

Some root Depot prose still calls OpenAI native-only, while the current wrapper
and invocation protocol permit `openai/*` on the API fallback rail and prohibit
`anthropic/*`. Reconcile that stale description against tested behavior. Prefer
non-OpenAI OpenRouter workers for economic relief where they prove suitable;
do not forbid useful paid OpenAI fallback based on the stale sentence.

## Bounded sequence and ownership

1. **OR-EFFORT-01 — Depot, model-router + OpenRouter.** Repair transmitted effort
   and truthful reporting. One branch; no portfolio, monthly-cap service, browser
   changes or new schema family. Local protocol proof, full composition, then
   approved release/cache work and a real bounded consumer call.
2. **UI-READY-03 — Depot, dm-review.** Complete the already prepared documented
   target discovery repair. Preserve “do not guess, but do look,” exact-head
   evidence, T3-first automation and owned cleanup. Jig owns the portable Fixture
   declaration. Use Governance as the real browser canary.
3. **MODEL-PORTFOLIO-01 — Depot, router + matrix; coordinator only if needed.**
   Admit Astra as the planning choice, refresh identities/prices, and make cheap
   offload proactive for appropriate roles. Keep the operator's provider cap
   outside tracked personal configuration. Run a few representative tasks,
   compare accepted result, repair time, subscription consumption when exposed,
   paid cost and duration. Do not run another enormous model tournament.
4. **INSTRUCTIONS-01 — Depot project-scaffolder, then consumer-owned branches.**
   Replace unconditional planning/doc-agent/lesson/file-count chores with a
   short task/risk rule. Baseplate is the first consumer: small root instructions,
   existing topical docs, one source of truth with thin harness adapters. Add
   portable Codex entrypoints for Jig and livewires-templ. Do not copy a personal
   ~/.codex configuration into shared repositories or sweep historical worktrees.
5. **SKILLS-01 — one owning plugin per bounded pass.** Start with Assembly's
   development entrypoint and prototype/production split. Then coordinator and
   strategy discovery, then Pipeline/review routing text, then applicable design
   descriptions. Keep deterministic contracts and meaningful negative tests;
   eliminate duplicate prose rather than inventing new references for every rule.
6. **FOREMAN-02 — Foreman, after its existing PR #5.** Replace smoke-test-specific
   task/path/verifier values with one real Assembly work profile. Use Pi's
   existing events for visible progress, operator steering and abort. Preserve
   Depot's routing ownership; no replacement harness, broker, daemon or Pi fork.
7. **FLOOR-02 — Floor, after Foreman emits live evidence.** Read the existing
   observation index and lifecycle evidence into current components. Floor stays
   read-only. Add persistent Pi resume only when a longer task demonstrates the
   need; reuse current handoff identity and verification evidence.

Confirmed safe parallel lanes: **None**. Baseplate instruction consolidation is
a potential later independent consumer lane: owner Baseplate, repository
assembly-baseplate, blocker instruction size and conflicting workflow rules.
Its dirty local checkout and frequently edited AGENTS/CLAUDE/docs surfaces need
an ownership check before dispatch. It must not change plugin code or release
policy. No second Depot implementation lane is recommended concurrently.

Foreman proof PR #4 is merged; main has a real Pi run. Existing PR #5 at
`24ae808d5cb4c090296493d507d5481f95989ab2` handles Kernel resolution/provenance;
do not duplicate it. Floor PR #4 is merged and issue #1 closed; current acceptance
records its three fixture viewports and real-run browser case passing. Its old
browser blocker must not be reopened. Foreman's proof still uses an in-memory
session, high thinking and fixed smoke-task inputs; Floor does not yet consume
Foreman's observation index. These are the useful implementation seams.

## Acceptance and reporting across the sequence

Use representative canaries: a narrow docs correction, an ordinary Go/Templ
change, a real authorization regression, an exact prototype desktop/mobile
surface, and a bounded OpenRouter context task. Reuse existing tests and retained
evidence. Measure loaded instruction bytes, wall time, retained defects, rework,
paid charges and available subscription measurements. Do not claim a percentage
cost reduction from file size alone. Keep R1's comparable review-loop proof
obligation; historical 36.1% context reduction was a different measurement.

For UI work, preserve prototype structure, copy, classes and meaningful states;
check keyboard/focus behavior, semantic names, contrast and narrow layouts, then
reuse exact browser evidence. Shared-component changes require a real consumer
render. Measure the affected request path and asset/query cost before adding
performance infrastructure; small co-ops still deserve fast software.

Skills should provide purpose, applicability, non-obvious constraints, completion
and relevant reference links. Root project instructions should identify the
product, trust/ownership boundaries, normal commands, design authority and
when deeper docs apply. An approximate 1,000–1,500-word root is a useful target,
not a new universal gate. Routine documentation work does not need a full
Pipeline, automatic agents or repeated adversarial review.

Planners answer with the next action, evidence that changes the decision, and
one complete execution prompt when needed. Use plain connected prose; keep
article/marketing voice out of technical coordination. Human recommendations
name model, rail, effort, why, cost, exactly one fallback and matrix date. After
work, report attempted/served participant, role, rail, effort, duration, outcome,
tokens, paid cost, subscription calls, fallbacks and missing measurements once.

The bulk comparison in this audit used DeepSeek V4 Flash 0731 through OpenRouter
(served by Wafer), 97.65 seconds, 150,780 input and 10,367 completion tokens,
provider-reported cost $0.01766975, no fallback and zero subscription calls for
that lane. Effort was provider default, not transmitted or measured. Its output
contained unsupported cross-repository conflicts and security suggestions;
those were rejected. This proves inexpensive bulk assistance works, not final
reviewer reliability. One native Astra subagent inspected Foreman/Floor; its
token usage, paid-equivalent cost and underlying subscription call count were
not exposed. The parent planning session has the same measurement gap.

Project items changed: **None**. Native Depot Issues/PRs created/closed: **None**.
R0/R1 source completion versus incomplete measurement, R2 completion, R3
supersession, R4 completion and R5 live-client blockage remain as classified in
the [phase index](depot-efficiency-program.md). Old factory-throughput, broker,
phase-triage and untracked planner kits remain superseded; speculative hardening
residuals remain uncertain. This plan does not revive them.

Planning repairs selected: this plan and the phase index. Consumer repairs to
schedule: Baseplate AGENTS/CLAUDE duplication, prototype personal workflow gate,
Foreman's accepted-proof framing, Floor START-HERE, and the missing Jig/component
Codex entrypoints. No mass rewrite is authorized by a stale label alone.

Planning validation: local links, fenced prompt, required execution fields and
provider-neutral participant text checked; `git diff --check` passed;
`./tools/validate-composition.sh --all` passed. This is planning/source validation,
not proof that any proposed model, instruction or harness change has shipped.
