# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Depot (DM-013/WORKS) is Design Machines' Claude Code plugin marketplace -- a collection of knowledge-as-code plugins that give Claude specialized domain expertise. The repo is structured Markdown and JSON that Claude Code consumes as skills, agents, and reference material, with one sanctioned executable exception: the workflow-kernel plugin ships a stdlib-only Python 3.12 reference runtime (no build step, no third-party dependencies). Its test suite is a repository development artifact at the top-level `tests/` directory -- it never ships into user plugin caches -- and is run by `tools/validate-workflow-kernel.py` as part of `./tools/validate-composition.sh --all`. Everything else has no build system, test suite, or application code.

## Repository Structure

```
.claude-plugin/marketplace.json  -- Marketplace manifest (lists all plugins)
plugins/<name>/
  .claude-plugin/plugin.json     -- Plugin metadata and Agent Card capabilities
  skills/<skill-name>/
    SKILL.md                     -- Primary skill definition (loaded on skill invocation)
    references/                  -- Supporting reference docs (loaded on demand)
    *.md                         -- Additional skill pages (components, patterns, etc.)
  agents/<category>/
    <agent-name>.md              -- Agent definitions (review, workflow categories)
  commands/
    <command-name>.md            -- Slash command definitions (user-invocable actions)
description-evals/               -- Trigger evaluation datasets (query + should_trigger pairs)
tools/                           -- Eval runner and development utilities
docs/                            -- Design specs and architecture docs
```

## Plugin Anatomy

Each plugin under `plugins/` follows the same structure:

- **`.claude-plugin/plugin.json`** -- Required. Contains `name`, `description`, `version`, `author`, and `capabilities` (Agent Card metadata).
- **`skills/`** -- Each subdirectory is a skill. `SKILL.md` is the entry point; `references/` holds supplementary material that the skill can pull in.
- **`agents/`** -- Optional. Agent definitions organized by category (`review/`, `workflow/`). Each `.md` file defines a specialized agent.
- **`commands/`** -- Optional. Slash command definitions. Each `.md` file defines a command that can be invoked directly.

## Plugin Discovery (Agent Cards)

Each `plugin.json` serves as an **Agent Card** -- machine-readable metadata that makes plugin discovery reliable instead of vibes-based. Inspired by the A2A protocol's Agent Card concept, the `capabilities` object declares what each plugin can do:

```json
{
  "capabilities": {
    "skills": [{
      "id": "skill-folder-name",
      "name": "Human-readable name",
      "description": "One-line purpose",
      "triggers": ["natural user query fragments that should activate this skill"],
      "tags": ["searchable", "category", "tags"],
      "mcpDependencies": ["normalized-service-name"]
    }],
    "agents": [{
      "id": "agent-filename-without-md",
      "name": "Human-readable name",
      "category": "review|workflow",
      "description": "One-line purpose",
      "tags": ["searchable", "tags"]
    }],
    "commands": [{
      "id": "command-name",
      "name": "Human-readable name",
      "description": "One-line purpose",
      "argumentHint": "arg format if any"
    }]
  }
}
```

**Field conventions:**
- `triggers` are short query fragments a user would type, not restated descriptions. Skills with `description-evals/` JSON files use evaluated trigger queries; others use authored natural-language fragments.
- `mcpDependencies` uses normalized service names (`ai-memory`, `notion`, `userback`, `playwright`), not raw tool prefixes. Only present when the skill declares `allowed-tools` in its SKILL.md frontmatter.
- `argumentHint` is only present on commands that accept arguments.
- `skills`, `agents`, and `commands` arrays are always present in the `capabilities` object, even when empty.
- The marketplace manifest (`.claude-plugin/marketplace.json`) includes `capabilities_summary` for each plugin -- counts and curated tags for quick search without loading full capabilities:

```json
{
  "capabilities_summary": {
    "skills": 2,
    "agents": 1,
    "commands": 1,
    "tags": ["curated", "representative", "subset"]
  }
}
```

Tags in `capabilities_summary` are a hand-picked subset, not a union of all skill/agent tags.

## Plugin Dependencies

Plugins that reference skills or agents from other plugins declare those relationships in `plugin.json`:

```json
{
  "pluginDependencies": {
    "ned": ">=1.4.0",
    "ghostwriter": ">=3.7.0"
  },
  "optionalPluginDependencies": {
    "council": ">=1.5.0"
  }
}
```

- `pluginDependencies` are hard requirements -- the plugin will not function without them.
- `optionalPluginDependencies` enrich behavior but the plugin works without them.
- Version constraints use semver `>=X.Y.Z` syntax. Set the floor to the version where the specific referenced capability (agent, skill) was present and stable.
- Most plugins are self-contained and need no dependencies field.

Validate with `./tools/check-dependencies.sh`. This checks package existence, version constraints, and that every declared capability (skill, agent, command) has a corresponding file on disk. Generate the dependency graph with `./tools/check-dependencies.sh --graph > docs/dependency-graph.md`.

## Marketplace Search

Every skill, agent, and command is indexed in `docs/search-index.md` -- a generated reference with three filterable tables plus a "Find by Need" section mapping common questions to the right plugin. Regenerate after editing plugin capabilities:

```shell
./tools/validate-composition.sh --generate-index
```

## Orchestration Patterns

Plugins compose through five patterns documented in `docs/orchestration-patterns.md`:

- **Companion Skill Loading** -- a command loads skills from other plugins at specific workflow phases (e.g. sprint-plan)
- **Multi-Agent Dispatch** -- a skill launches agents in parallel and consolidates results (e.g. dm-review)
- **Memory-Mediated Coordination** -- plugins write to ai-memory entities that other plugins read later (e.g. depot-metrics)
- **Pipeline Orchestration** -- a conductor plugin composes all three patterns into an autonomous multi-phase workflow with review-fix loops (e.g. pipeline)
- **API-Wrapper Model Delegation** -- a lightweight runner invokes an external model through the guarded OpenRouter wrapper, validates direct text output, and formats findings for the calling workflow

Workflow Kernel is the neutral mechanics leaf beneath pipeline and dm-review.
It owns deterministic run state, replay, receipts, verification evidence,
shadow comparison, and exact owned-resource cleanup. The consuming Markdown
workflows remain authoritative in v0.1.0; shadow is the default, and unavailable
runtime falls back to Markdown without deleting event history. See
`docs/workflow-kernel.md`.

## Composition Validation

Validate all cross-plugin references, dependencies, eval accuracy, and search index freshness in one command:

```shell
./tools/validate-composition.sh --all
```

Individual validators: `eval-descriptions.sh` (description accuracy), `check-dependencies.sh` (dependency resolution and the workflow-kernel leaf contract), `validate-workflow-kernel.py` (offline behavioral proof), `validate-composition.sh` (composition references), `validate-workflow-contracts.sh` (repository cleanup, Datastar-first, Baseplate evidence, and workflow-kernel integration anchors).

Before tagging or pushing a release, run the preflight. It is read-only and prints a release receipt:

```shell
./tools/check-release-preflight.sh
```

It verifies a clean tree, marketplace/plugin version sync, Codex shim freshness, that every plugin changed since its last tag has been bumped, and that `origin` is reachable and authenticated. **Never claim a release, tag, or push completed unless this passed.** It is not part of `--all` -- release hygiene is separate from composition validity.

## Plugin Versioning

When you modify a plugin's skills, agents, or references, **bump the version** in its `.claude-plugin/plugin.json` before committing. Follow semver:

- **Patch** (1.0.0 -> 1.0.1) -- reference fixes, typo corrections, description enrichment
- **Minor** (1.0.0 -> 1.1.0) -- new references, new agents, additional patterns, new skill content
- **Major** (1.0.0 -> 2.0.0) -- skill renamed/restructured, breaking changes to how the plugin works

Never commit plugin changes without also bumping the version.

### Version Sync: marketplace.json and plugin.json

**Both files must declare the same version.** Claude Desktop uses the version string to detect updates. Here's how the update pipeline works:

1. Claude Desktop clones the marketplace repo to `~/.claude/plugins/marketplaces/depot/`
2. On marketplace update, it does a `git pull` on that clone
3. It compares each plugin's version against the cached version at `~/.claude/plugins/cache/depot/<plugin>/<version>/`
4. If the version string hasn't changed, **no update is detected** -- even if the underlying files changed

Because our plugins use relative-path sources (`"source": "./plugins/assembly"`), the version can live in either `marketplace.json` or `plugin.json`. When both declare a version, **`plugin.json` wins silently** for resolution, but the marketplace entry version is what appears in cache paths and update detection UI.

**Rule: when you bump the version in `plugin.json`, also bump it in `.claude-plugin/marketplace.json`.** Run `./tools/validate-composition.sh --all` to catch any drift -- it includes a marketplace version sync check.

### Troubleshooting Update Failures

If Claude Desktop says plugins are "up to date" but versions look stale:

1. **Check the cached marketplace clone:** `cd ~/.claude/plugins/marketplaces/depot && git log --oneline -1` -- if it's behind `origin/main`, the auto-update `git pull` failed
2. **Manually pull:** `cd ~/.claude/plugins/marketplaces/depot && git pull origin main`
3. **Update individual plugins:** `claude plugin update <plugin-name>@depot`
4. **Check cache versions:** `ls ~/.claude/plugins/cache/depot/<plugin>/` shows which version directories exist

### CLI vs Desktop Cowork: Two Separate Plugin Systems

The CLI/VSCode and Desktop Cowork maintain **independent** plugin caches. Updating one does NOT update the other.

| System | Marketplace clone | Plugin cache |
|--------|------------------|--------------|
| CLI/VSCode | `~/.claude/plugins/marketplaces/depot/` | `~/.claude/plugins/cache/depot/` |
| Desktop Cowork | `~/Library/Application Support/Claude/local-agent-mode-sessions/<session>/<account>/cowork_plugins/marketplaces/depot/` | Same path but `/cache/depot/` |

To fix stale Desktop plugins, pull the Desktop's marketplace clone directly:

```shell
cd ~/Library/Application\ Support/Claude/local-agent-mode-sessions/*/*/cowork_plugins/marketplaces/depot && git pull origin main
```

Then restart Claude Desktop for it to detect the new versions.

## Notion Manual Sync

The depot has a manual page in Notion that documents all plugins, versions, and capabilities:
**Notion page ID:** `31ed8793880881749475c5c36dd252df`

When a plugin update changes any of the following, update the Notion manual page using the Notion MCP:
- Plugin version number
- New or removed skills, agents, or reference files
- Changes to key capabilities or ecosystem integration
- Plugin count or total file counts

To update, fetch the page with `notion-fetch`, then use `notion-update-page` with `update_content` to modify the relevant plugin section. Keep the format consistent with the existing entries.

## The Plugins

18 plugins | 38 domain-facing skills + 1 internal workflow-kernel skill + 33 generated Codex command-skill aliases | 38 agent cards | 33 commands

The generated search index counts every manifest-discovered surface, including
the internal kernel skill: 39 skills and 38 agents. The 38 count above preserves
the domain-facing skill inventory used by the release plan.

| Plugin | Purpose |
|---|---|
| **ned** | Personal knowledge graph (ai-memory MCP) and session recorder |
| **craft-developer** | Craft CMS 4/5 development patterns and query cookbook |
| **project-manager** | LT10 methodology, Notion-integrated sprint planning with Userback triage, Calendar.app meeting prep, Mail.app scanning, content ideation, and velocity tracking |
| **council** | Worker cooperative governance (BC Co-op Act) and decolonial content strategy |
| **design-machines** | DM business strategy, catalog, partnerships, revenue model, design system, audience research (positioning, pitch material, competitive landscape) |
| **assembly** | Go/Templ/Datastar governance app development with embedded NATS, SQLite, and production backend architecture |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **ghostwriter** | Personal writing voice, editorial style engine, and voice editing |
| **design-practice** | Typography, layout, data visualization, and identity design philosophy |
| **project-scaffolder** | Claude Code project infrastructure scaffolding with hooks, agents, and CLAUDE.md templates (project-type-specific plus generic/DM-standard starters) |
| **accessibility-compliance** | WCAG 2.2 auditing and enforcement for Live Wires, Templ+Datastar, and Craft CMS |
| **dm-review** | Code review orchestrator with parallel agents, visual browser testing, UX design review, visual design quality review, and Live Wires CSS compliance across all DM stacks |
| **the-local** | Self-hosted Matrix network (The Local) -- Element Web branding, Synapse config, server ops |
| **chef** | Science-driven cooking assistant with Mela integration, dietary analysis, meal planning, and Bali sourcing |
| **pipeline** | Autonomous feature development pipeline with assessment, research, prompt generation, adversarial review, worktree execution with review-fix loops, and `/pipeline-fix` fix-pass flavor for addressing numbered review findings |
| **workflow-kernel** | Neutral deterministic run state, event-ledger replay, recovery, shadow parity, verification, and exact owned-resource cleanup shared by pipeline and dm-review |
| **openrouter** | Unified external-model provider: Kimi K3 quality-first agentic execution, GLM-5.2/DeepSeek V4 mechanical review, bulk analysis, frontier cross-checks, and dm-review routing over one OpenAI-compatible endpoint and one credential. ZDR is opt-in. |
| **airlift** | Model- and harness-agnostic session-handoff capability. Writes a deterministic `.airlift/` bundle (HANDOFF.md, state.json, git-diff patch, RESUME_PROMPT.md) so a usage cap or rate limit becomes a non-event -- resume in any harness (Claude Code, Codex, DeepSeek, Kiro, OpenCode). Tier-1 deterministic checkpoint (no model budget) plus optional ccusage early-warning monitor; wired into pipeline and dm-review phase boundaries. |

## Description Evaluation

Every skill has a corresponding eval file in `description-evals/<plugin>-<skill>.json` containing test queries with expected trigger outcomes. The eval runner checks whether the SKILL.md `description:` field contains enough relevant vocabulary to match real user queries.

```shell
./tools/eval-descriptions.sh          # run all evals
./tools/eval-descriptions.sh -v       # verbose (show failures)
./tools/eval-descriptions.sh foo.json # run one eval
```

When editing a SKILL.md `description:` field, run the eval for that skill to confirm trigger accuracy holds. Skills must stay above 70% accuracy. See `tools/README.md` for details on the heuristic, pre-commit hooks, and adding new eval cases.

The eval covers only **trigger accuracy** (axis 1). Discipline skills -- those that enforce behavior under pressure (pipeline gates, zero-deferral, codify, council compliance) -- also need **compliance robustness** (axis 2): pressure-test them via the installed `superpowers:writing-skills` loop before shipping. Descriptions must state *triggers, not workflow steps* (SDO), or agents follow the summary instead of reading the skill. The full two-axis model, the SDO rule, and the cross-cutting compounding disciplines (`superpowers:systematic-debugging`, `superpowers:verification-before-completion`) are documented in `docs/skill-authoring.md`. The codify loop that turns each run's lessons into permanent encodings lives in the `ned:codify` skill and is wired into pipeline Step 5.2 and the dm-review memory recorder.

## Common Operations

Install the marketplace and plugins:
```shell
/plugin marketplace add Design-Machines-Studio/depot
/plugin install ned@depot
```

Validate a plugin:
```shell
claude plugin validate plugins/<name>
```

### Git Hooks

The depot tracks a pre-commit hook under `.githooks/pre-commit` that blocks commits introducing the canonical SKILL.md frontmatter corruption pattern (opening `---` intact but closing delimiter missing, or `## name:` heading appearing where YAML keys belong). The hook only runs when SKILL.md files are staged -- it never blocks unrelated commits.

Install once per local clone:

```shell
bash tools/install-hooks.sh
```

This sets `core.hooksPath = .githooks` and makes every script in `.githooks/` executable. After installation, every `git commit` automatically runs the corruption check on staged SKILL.md files. Recovery hint is included in the failure message (`git checkout HEAD -- <path>`).

Bypass for genuinely intentional changes:

```shell
git commit --no-verify
```

Use sparingly. The full validator (`bash tools/validate-composition.sh --all`) runs the same SKILL.md integrity check plus everything else and is the right pre-push gate.

## Conventions

- Almost all content is Markdown. The sanctioned exception is the stdlib-only
  workflow-kernel Python runtime and top-level `tests/`; verify it with
  `tools/validate-workflow-kernel.py` and the full composition validator.
- Skills use `SKILL.md` as the canonical filename for the primary skill definition. The `name:` field in its YAML frontmatter must match the skill folder name exactly.
- Reference files live in `references/` subdirectories and are named descriptively (e.g., `estimation.md`, `bc-cooperative-act.md`).
- Reference files are typically Markdown. Executable scripts (`.sh`) are permitted when a skill needs runtime tooling. Established pattern (see `plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh`): shebang line, top-of-file purpose/dependency/usage comments, executable bit set, POSIX-portable Bash 3.2+ for macOS compatibility, explicit non-zero handling, and a fixed `PATH` reset to prevent caller-controlled hijack of dependencies.
- Agent files are categorized by purpose: `review/` for code review agents, `workflow/` for automation agents.
- Plugin JSON requires `name`, `description`, `version`, `author`, and `capabilities`. Optional fields include `keywords`, `repository`, `author.url`, `pluginDependencies`, and `optionalPluginDependencies`.
- The marketplace manifest at `.claude-plugin/marketplace.json` must stay in sync with the actual plugin directories.
- **Artifact format (pipeline planning phase):** the four pipeline planning artifacts -- `brainstorm`, `assessment`, `research`, `plan` -- are emitted as self-contained **HTML carrying a JSON data island** (a `<script type="application/json" id="pipeline-data">` block). The HTML links the target project's compiled CSS; the island is what downstream agents read (via `extract-json-island.sh`) instead of grepping prose. Agent-only handoffs (`original-prompt.md`, `prompts/*.md`, `manifest.json`, crosscheck) stay **Markdown/JSON**. Terminal status reports (dm-review reports, pipeline receipts, delivery reports) stay **inline/markdown** -- HTML buys nothing for a one-shot status summary. Templates and the rationale live in `plugins/pipeline/skills/promptcraft/references/templates/` and `docs/html-artifacts.md`.

## Model & Effort Tuning

Claude model aliases remain in agent frontmatter for Claude Code compatibility and non-coding work. They are not coding routes: implementation, code review, security, and architecture execute on Codex or OpenRouter. See `docs/opus-4-8-tuning.md` for the compatibility and non-coding effort policy.

**Fable escalation (non-coding only):** Claude Fable 5 (`fable`) may be used for strategy, writing/voice, research synthesis, or optional plan critique when the current plan carries it. Never use Fable for implementation, code review, security, architecture, or the execution-orchestrator. Full rules are in `docs/opus-4-8-tuning.md`.

**GPT-5.6 family (Jul 2026):** OpenAI's Sol/Terra/Luna tiers replace GPT-5.5 on the OpenAI rails. `gpt-5.6-sol` is rank 98 and leads OpenAI's paid and Codex-native ladders. Terra and GPT-5.5 tie at rank 94; Terra is attempted first on paid API rails because it costs half as much ($2.50/$15 versus $5/$30), while GPT-5.5 remains the older-CLI native fallback. Luna ties GLM-5.2 at rank 90 but stays at the **frontier tail, never on `cheap_api`**: its $1/$6 output price is about 2.1x GLM's live $2.86 rate, so price breaks the quality tie in GLM's favour. `cascade-dispatch.sh` emits the first floor-clearing model; the orchestrator's **Native Model Descent** (RC 64) walks later native models when a CLI rejects one. Sol leads `native_judgment` on the **codex** host only; see `docs/opus-4-8-tuning.md` for the host constraint. The Sol rail requires `codex-cli >= 0.144.x`, and `gpt-5.1-codex-mini` is unusable on a ChatGPT-sub account.

**Kimi K3 (Jul 2026):** Moonshot AI's planned-open-weight, API-only-today model (`moonshotai/kimi-k3`, 2.8T-param MoE, 1M context, $3/$15 with $0.30 cache hits) is the quality-first OpenRouter agentic head at rank 97. Artificial Analysis v4.1 scores K3 at 57: behind Fable 5 (60) and GPT-5.6 Sol max (59), ahead of Opus 4.8 max (56), Terra/GPT-5.5 max (55), Sonnet 5 max (53), and GLM-5.2 max (51). It leads `openrouter_exec` and sits second on `frontier_api`; GLM remains the mechanical review/bulk default. OpenRouter currently warns that K3's sole upstream provider has limited capacity, so its ladders retain fallbacks. The wrapper is text-only despite upstream multimodal capabilities.

**Coding subscription rails (Jul 2026):** Claude is moving from Max to Pro and is outside the coding graph. Codex Pro 20x is the active coding profile at a 65/0/35 Codex/Claude/OpenRouter target; the named Codex 5x profile shifts to 40/0/60. All implementation and code-review kinds, including UI, security, and architecture, route to Codex or OpenRouter. Claude remains available only for non-coding strategy, writing/voice, research synthesis, and optional plan critique.

**Provider privacy (demoted, Jul 2026):** model selection priority is Quality > Price > Speed > Provider privacy. `OPENROUTER_ZDR=1` is opt-in only (genuinely sensitive material: client code under NDA, credentials-adjacent diffs) -- Chinese first-party hosting (Moonshot/DeepSeek/Z.AI) is acceptable by default and no rung pins ZDR anymore.

## Pipeline Enforcement

When the user says `/pipeline` or asks to "run the pipeline" or "use the full pipeline process," you MUST invoke the pipeline skill from `plugins/pipeline/`. Do not manually execute pipeline steps. Do not replicate the pipeline's assess-research-plan-prompt-review-execute phases by hand. The pipeline enforces gates, review loops, visual verification, and memory capture that manual execution skips.

If the pipeline skill is unavailable (not installed), tell the user and stop. Do not improvise a substitute.

## Known Pipeline Failure Modes

These failure patterns have been observed in production pipeline runs. Each has a documented root cause and a corresponding hardening measure in the pipeline plugin.

1. **Pipeline bypass:** Claude skips the pipeline and manually implements features. The pipeline's gates, reviews, and visual checks are all skipped. Hardening: "Do Not Manually Replicate" section in `pipeline.md`.
2. **Silent MCP fallback:** The execution-orchestrator continues without browser verification when Playwright/Chrome DevTools MCP is unavailable. UI chunks ship without visual testing. Hardening: MCP pre-flight check in `execution-orchestrator.md`.
3. **Code-only adversarial review:** The plan-adversary reviews code patterns but not visual/rendered output. UI chunks pass review without visual acceptance criteria. Hardening: Visual Verification Readiness perspective in `plan-adversary.md`.
4. **Evidence-free assertions:** "Requirements covered" claims are assertions without screenshots, computed style comparisons, or other evidence. Hardening: Evidence requirement in `pipeline.md` Phase 7.
5. **Missing visual diff protocol:** When the user says "these should be visually identical," no protocol exists for getComputedStyle comparison. Hardening: Visual Parity Diff step in `execution-orchestrator.md`.
6. **dm-review-loop not invoked:** The caller never runs dm-review-loop on the final result, trusting the orchestrator's self-report. Hardening: Caller Visual Verification section in `pipeline.md` Phase 7.
7. **Prompt quality degradation:** Across large chunk sets, later prompts have less detail, fewer acceptance criteria, and weaker visual specifications. Hardening: Prompt Quality Parity Check in `promptcraft SKILL.md`.
8. **Silent browser-verification-skipped merge claims:** The orchestrator emits "ready to merge" when visual verification was skipped. Browser availability is a verification-evidence status, never an execution mode. Hardening: required browser-evidence status on every UI chunk receipt, browser-recovery escalation ladder (evidence capture -> primary restart -> alternate engine -> human help) in `execution-orchestrator.md`, forbidden-phrases list, and `BLOCKED PENDING CALLER VERIFICATION` merge recommendation; Caller Verification Checklist (screenshot + runtime eval + cardinality) in `pipeline.md` Phase 7.
9. **Multi-chunk rename atomicity:** Identifiers renamed across non-adjacent chunks produce a broken window under orchestrator parallelization. Hardening: Rename Atomicity Check in `plan-adversary.md`.
10. **Append-only revision residue:** Round N amendments coexist with superseded content. Hardening: Append-Only Purge Check + Final Audit + imperative verb discipline (`REPLACE`/`DELETE`/`INSERT`/`RENAME`) in `plan-adversary.md`.
11. **Dev-mode module loader desync:** New JS module ships without updating the dev-mode module map, loads 404 in browser. Hardening: Step 0c Module-Loader Pre-Flight in `execution-orchestrator.md`.
12. **P3 deferral drift:** P3-only returning CLEAN silently compounds tech debt. Hardening: zero-deferral policy as default in `dm-review/skills/review/references/severity-mapping.md` and command files; `--allow-defer-p3` opt-in requires written justification + tracking destination.
13. **Brittle line-number references:** Prompt references to `file:line` become stale as interstitial chunks edit files. Hardening: Phase 3e Stable Anchors Audit in `promptcraft SKILL.md` (prefer function/templ names over line numbers).
14. **Silent mid-execution ambiguity:** A subagent encounters a chunk prompt that admits multiple reasonable interpretations, picks one silently, and ships. The brainstorming skill catches pre-plan ambiguity and plan-adversary catches structural ambiguity, but neither covers implementation-time micro-decisions. Hardening (pipeline v1.10.0): Ambiguity Protocol block in `promptcraft/references/prompt-template.md`; Ambiguity Handling section in `execution-orchestrator.md` (autonomous-mode commit trailers `Chose:` / `Rejected:` + `ambiguity_resolved:` receipt flag); Ambiguity surfacing perspective in `plan-adversary.md` Sprint Contract Negotiation. Three-layer defence with "cheapest catch first" wording aligned across all three locations.
15. **External LLM provider failure without retry:** the OpenRouter runner fails and dm-review immediately classifies the agent as failed without a trusted fallback. Core agent coverage gaps go undetected. Hardening: Phase 4.5 retries coding lanes on Codex before applying failure policies; Claude is reserved for explicitly non-coding lanes.
16. **Orphan worktree and branch residue:** a run that fails, or that exits through a non-terminal gate answer ("Create PR", "Give feedback"), leaves `.worktrees/pipeline/**` paths and `pipeline/**` chunk branches behind. The next run collides on `git worktree add`, and `git branch -d` failures were swallowed by `2>/dev/null` so the receipt claimed refs were cleaned that still existed. Hardening (pipeline v1.26.0, dm-review v1.41.0): `plugins/dm-review/skills/review/references/repo-cleanup-contract.md` defines a ref registry, a safe-to-delete decision table, feature-branch protection (never deleted without `merge-base --is-ancestor` proof into `main`/`origin/main`), blocked-removal reporting, and a mandatory `## Branch & Worktree Inventory` receipt block. Wired into orchestrator Steps 0e/3b/3j/5b, all three pipeline commands, and dm-review Phase 8. Enforced by `tools/validate-workflow-contracts.sh`.
17. **Empty PR review threads read as "no findings":** formal review threads on Baseplate PRs are usually empty; the durable signal lives in checked-in receipts, merge-commit bodies, closed issues, and verification files. A reviewer that checks `gh pr view --comments` and stops concludes the work was unreviewed. Hardening (dm-review v1.41.0): Phase 1b Evidence Source Fallback in `plugins/dm-review/skills/review/SKILL.md` walks four evidence sources in order and reports which one was used; Phase 4.5 generalized from "external LLM failed" to "lane unavailable" (external runner, Codex CLI absent, evidence absent), and a skipped lane must appear in Coverage Gaps.
18. **Hand-rolled JS where Datastar suffices, and inert Pro attributes:** agents reach for `localStorage`, `matchMedia`, `ResizeObserver`, `scrollIntoView()`, `navigator.clipboard`, and `Intl.*` because Depot never documented Datastar Pro (Context7 has no entry; the repo is private). Worse, a Pro attribute whose plugin is missing from the vendored bundle is **inert** -- a silent no-op that reads as correct in review. Hardening (assembly v3.8.0, pipeline v1.26.0, dm-review v1.41.0): `plugins/assembly/skills/development/datastar-pro.md` is the self-contained reference (10 attributes, 3 actions, JS substitution table, bundle-presence rule, transcribed from the plugin sources at v1.0.2); promptcraft Phase 3o Datastar-First Gate; plan-adversary Datastar-first check; `Hand-Rolled JS Where Datastar Suffices` (P2) and `Inert Pro Attribute` (P1) findings in dm-review.

See `docs/post-mortems/` for detailed root cause analysis.

## Post-Implementation Checklist

After any pipeline run or manual feature implementation, verify:

- [ ] All affected pages render without console errors
- [ ] Screenshots taken at desktop (1440px) and mobile (375px) for every UI change
- [ ] Visual output compared to design spec or brainstorm mockup (if one exists)
- [ ] dm-review-loop run on the final branch (not just per-chunk quick reviews)
- [ ] Zero pending P3 findings OR explicit `--allow-defer-p3` with justification + tracking ID for each (zero-deferral default)
- [ ] Requirements cross-check with EVIDENCE type for each requirement (screenshot, build pass, computed style)
- [ ] No "visually identical" requirements left unverified (visual diff protocol applied)
- [ ] If any UI chunk receipt carries a browser-evidence status other than verified (browser unavailable, alternate engine, or human-help escalation), the 3-item Caller Verification Checklist is complete with attached evidence
- [ ] Repository cleanup phase ran; receipt carries a `## Branch & Worktree Inventory` with every created ref dispositioned, every kept/blocked ref carrying a follow-up command, and a clean `git status --porcelain`
- [ ] Feature branch preserved unless `git merge-base --is-ancestor <branch> origin/main` proves it landed
- [ ] UI work uses Datastar/Datastar Pro attributes rather than hand-rolled JS; every Pro attribute has a recorded bundle-presence check
- [ ] Session recorded to ai-memory
- [ ] Postmortem written if any failure patterns were observed

## Postmortems

Pipeline failure analysis documents live in `docs/post-mortems/`:

- `2026-04-07-pipeline-ui-refinement-postmortem.md` -- 6 failure modes from Assembly UI refinement run
- `2026-04-10-pipeline-visual-testing-postmortem.md` -- 7 failure modes from Assembly pipeline bypass and visual testing gaps

These postmortems inform the Known Pipeline Failure Modes section above and the hardening measures in the pipeline plugin.
