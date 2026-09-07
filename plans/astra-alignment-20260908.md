# Astra alignment — 2026-09-08

**Status: audited and planned; the system-wide migration has not shipped.**
The user now selects GPT-6 Astra as the main driver for planning and execution.
This supersedes the earlier plan's planner-only framing. It does not select
Astra for every worker or authorize a bulk rewrite of historical worktrees.

This remains the Depot planning session. No project instructions, plugin source,
local model settings, account limits, tags or installations were changed.

## Official guidance and applicability

The [current Astra guide](https://developers.openai.com/api/docs/guides/latest-model)
was read directly on September 8. Its migration advice supports resolving
conflicting instructions, clear completion/approval boundaries, deliberate
delegation, plain output and proportionate testing. Preserve effective effort
for the initial comparison; replace unsupported none/minimal with low. Optional
async, steering and cache features require a real harness consumer.

For direct Astra API tool use, verify Responses transport and remove unsupported
sampling fields. Do not impose that endpoint change on unrelated models or the
OpenRouter text-only wrapper. Check Pi's actual request adapter before claiming
compatibility. [Astra guide](https://developers.openai.com/api/docs/guides/latest-model).

The [model card](https://developers.openai.com/api/docs/models/gpt-6-astra)
supports low/medium/high/xhigh/max effort. Depot can retain its existing
low/medium/high/max request vocabulary; adding another orchestrator setting
requires a demonstrated consumer. API prices and subscription usage remain
separate measurements.

## Coverage and evidence

Authenticated current-main instructions were reacquired for nine Design Machines
repositories. The readable filesystem inventory found 61 AGENTS.md files with
34 unique contents and 49 CLAUDE.md files with 25 unique contents. These include
old worktrees and proof snapshots, not 110 independent projects. Protected old
proof directories were unreadable and are an explicit coverage gap; no permission
or filesystem changes were made to inspect them. Upstream reference checkouts,
module caches and historical evidence are not migration targets.

All 79 skill/command-alias entrypoints were inventoried. Shared generator,
routing, planning, development and review surfaces were inspected against the
previous detailed audit. Body size is context exposure when loaded, not measured
injected tokens. No blanket rewrite of cooking, domain knowledge or other
unrelated skills is justified by a model change.

| Owner / source at refresh | Finding | Required bounded change |
|---|---|---|
| Depot main `bda7cab9ddc97b1bf8746da05ce275584d281031` | model-router 0.6.2 policy and OpenRouter 1.20.2 matrix contain no Astra entry | Complete the existing portfolio chunk with Astra driver support and economical delegated roles |
| Local Codex configuration | Saved CLI default remains gpt-5.6-luna / max; no project_doc_max_bytes override | Align a later explicit local configuration change with the chosen driver; do not infer the active app session from this file |
| project-scaffolder 1.9.2 | Templates repeat mandatory plan mode, doc-sync after every code change, lesson updates after every correction and file-count-driven commits | Repair the generator before consumer rollout; update associated hook defaults where they reproduce the same friction |
| Baseplate `4fdff7e1be98bc57d5d1c27798b220b3d5890055` | AGENTS.md 82,738 bytes / 10,122 words; CLAUDE.md 42,576 bytes; both repeat generator chores | Short common instructions with thin harness entrypoints; move implementation reference to existing topical docs |
| Prototype Assembly `4f811431a970cd6b6ac82ed762a707ccc01b9887` | Mandatory personal Notion session gate, full Pipeline based on file count, repeated documentation chores | Remove personal prerequisites and use task/risk-based workflow selection in its own branch |
| Governance `4777a292bd4ea52b74bbbc0c82be1524ca0f0299` | 10,799-byte AGENTS, preserved author loop and verification rules | Targeted consolidation after generator policy; preserve concrete runtime and review authority |
| Jig `50f0d47c275928953dcaa81ee15d68e05cf0a0ae` | No AGENTS.md; 4,104-byte CLAUDE already states trusted first-party scope | Add a thin portable instruction entrypoint; retain the existing author loop |
| livewires-templ `84e1e24c81784497b6fb7004e0ed7fa0d763b6ae` | No AGENTS.md; CLAUDE contains real generated-output and attribute-safety contracts | Expose those rules portably without copying a second implementation guide |
| Floor `561352882d2402ffb2b6889de101f31c22e0ef8b` | CLAUDE already delegates to AGENTS; AGENTS makes P3 advisory and requests personal memory for design | Align retained P3 handling with the user's policy; make personal context optional; preserve read-only product boundary |
| Foreman `8234aeb73aa76b7f084572f3fcd52ca54acbffdc` | Pi 0.84.4, hardcoded high thinking, in-memory session and disabled compaction; operator experiment binding and fixed proof task | Test actual Astra tool transport, then one current work profile; use Pi's existing events/steer/abort before adding transport infrastructure |
| Demo `c7a54d5f2005edf0e7e4b5d10fdb4eb66286f200` | Thin 1,408-byte AGENTS, no discovered model-specific conflict | Preserve; no rewrite solely to mention Astra |
| Assembly development 3.16.0 | 46,141-byte entrypoint retains prototype/production mixture | Existing SKILLS-01 scope: separate task authority and shorten entrypoint |
| Pipeline 1.66.1 / dm-review 1.80.0 | Main workflow entrypoints are 47,828 / 51,096 bytes | Audit duplicated gates and instruction load, retain deterministic contracts and applicable detection |
| Strategy 1.5.1 / coordinator 1.13.0 | Strategy discovery description is 1,256 characters; coordinator already separates private routing from human recommendation | Narrow discovery, preserve company constraints; honor current driver without leaking model identity to participants |

Baseplate's root alone exceeds Codex's default combined 32 KiB project-document
limit. This is a loader risk, not proof that a particular app session truncated
specific instructions. Increasing the limit alone would retain repeated context
cost. [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

The inspected Codex copies of scaffolder, Assembly, strategy, coordinator,
model-router and OpenRouter match main. Both harnesses match Assembly,
coordinator, router and OpenRouter. Scaffolder and strategy are absent from the
Claude cache; absence does not authorize installing them or imply modified files.
Thus an all-project, both-harness rollout cannot be claimed.

## Adopted direction and remaining implementation

Astra is the operator-selected primary driver now. Keep economical workers for
bounded implementation, extraction and independent review, with the existing
provider-neutral role/capability/effort contract. Prefer available subscription
capacity where appropriate and planned paid offload when it saves meaningful
usage or provides useful independence. The OpenRouter target stays at $50/month
or less; do not treat proposed $30/$40 operating limits as applied account settings.

Treat normal trusted development as authorized when the task already permits it.
Prepare concrete work before any necessary final approval. Keep destructive
changes, data loss, credentials, authorization and release integrity fail-closed.
Approval exceptions must identify the exact governing instruction and actual
boundary. Do not generalize internally trusted Fixtures into hostile plugin authors.

Retain short human output, useful independent delegation and affected verification.
Remove repeated planning gates, automatic documentation-agent chores, automatic
lesson writes and file-count rules. Keep Live Wires/component reuse, accessibility,
prototype authority, upgrades and actual performance requirements. Fix every
retained P1/P2/P3 finding; dismiss unsupported findings explicitly.

Depot's own instructions also need proportionate treatment of planning-only
changes. Recent documentation pushes triggered release checks for an unchanged
plugin tree and repeated whole-repository validation. Keep release gates on
release/plugin changes; define a focused documentation lane instead of making
executors invent exceptions or new approval rituals. Do not weaken actual plugin
composition, generated-file, credential or release checks.

## Sequence and proof

The immediate Depot lane remains existing PR #129 closeout. At this refresh it
is draft/open at `07c4d5dd6a3efb0b52dc0c4df4bddd42346143dd`, mergeable, with
Codesmith skipped. Its body reports a successful exact-source Jig desktop/mobile
canary and owned cleanup, but required routed review was blocked before serving.
It reports five OpenRouter fixture failures reproduced on the unchanged base.
Those are reported evidence, not independently reverified claims in this audit.
No second writer should duplicate that branch.

After that blocker, retain the existing bounded sequence:

1. MODEL-PORTFOLIO-01: Astra driver support in router/matrix, current availability
   and price evidence, cost-aware offload. Preserve other worker roles and effort
   transport truth. No all-model benchmark tournament.
2. INSTRUCTIONS-01: scaffolder generator and Depot's own proportional workflow
   rules, then consumer-owned Baseplate/prototype/Jig/component rollouts.
3. SKILLS-01: one plugin per pass, starting with Assembly development authority;
   then discovery and repeated planning/review text where the audit proves friction.
4. Foreman: one real Astra tool/steering/receipt canary through the existing Pi
   binding, then current work-profile support and Floor's existing observation view.

Use a handful of real cases: a docs correction, ordinary Go/Templ change,
authorization regression, prototype desktop/mobile surface and metered context
job. Compare accepted outcome, retained defects, repair effort, elapsed time,
loaded context and measured charges. Change effort after preserving a baseline;
no maximum-effort default or lower-effort saving claim without evidence.

For each owning plugin: canonical version/marketplace, generated Codex surfaces,
necessary dependency floors/index/fixtures, exact-head validation, trusted-main
proof, approved tags, intended harness installations and a real consumer check.
Root consumer instructions ship through their own branches. Do not update
historical worktrees, upstream reference repositories or every model name by grep.

Project changes: None. This audit changes planning records only. The previous
system-wide audit remains historical evidence; this record updates the driver
choice and verifies that its rollout is still pending.

Validation: local links, required source records and `git diff --check` passed.
Plugin/tool/test trees still match main exactly. The September 7 full composition
result on that identical source remains prior evidence; no fresh application or
model canary was run for this documentation update. PR #129's reported fixture
failures remain an unresolved execution concern, not a claimed clean pass here.
The recorded release-preflight equal-version warning is unchanged; this is an
authorized planning-document push, with no release or installation action.
