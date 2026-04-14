# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Depot (DM-013/WORKS) is Design Machines' Claude Code plugin marketplace — a collection of knowledge-as-code plugins that give Claude specialized domain expertise. There is no build system, test suite, or application code. The entire repo is structured Markdown and JSON that Claude Code consumes as skills, agents, and reference material.

## Repository Structure

```
.claude-plugin/marketplace.json  — Marketplace manifest (lists all plugins)
plugins/<name>/
  .claude-plugin/plugin.json     — Plugin metadata and Agent Card capabilities
  skills/<skill-name>/
    SKILL.md                     — Primary skill definition (loaded on skill invocation)
    references/                  — Supporting reference docs (loaded on demand)
    *.md                         — Additional skill pages (components, patterns, etc.)
  agents/<category>/
    <agent-name>.md              — Agent definitions (review, workflow categories)
  commands/
    <command-name>.md            — Slash command definitions (user-invocable actions)
description-evals/               — Trigger evaluation datasets (query + should_trigger pairs)
tools/                           — Eval runner and development utilities
docs/                            — Design specs and architecture docs
```

## Plugin Anatomy

Each plugin under `plugins/` follows the same structure:

- **`.claude-plugin/plugin.json`** — Required. Contains `name`, `description`, `version`, `author`, and `capabilities` (Agent Card metadata).
- **`skills/`** — Each subdirectory is a skill. `SKILL.md` is the entry point; `references/` holds supplementary material that the skill can pull in.
- **`agents/`** — Optional. Agent definitions organized by category (`review/`, `workflow/`). Each `.md` file defines a specialized agent.
- **`commands/`** — Optional. Slash command definitions. Each `.md` file defines a command that can be invoked directly.

## Plugin Discovery (Agent Cards)

Each `plugin.json` serves as an **Agent Card** — machine-readable metadata that makes plugin discovery reliable instead of vibes-based. Inspired by the A2A protocol's Agent Card concept, the `capabilities` object declares what each plugin can do:

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
- **CLI-Mediated Model Delegation** -- a Claude subagent invokes an external AI model via CLI, parses structured output, and formats findings for the calling workflow (e.g. gemini)

## Composition Validation

Validate all cross-plugin references, dependencies, eval accuracy, and search index freshness in one command:

```shell
./tools/validate-composition.sh --all
```

Individual validators: `eval-descriptions.sh` (description accuracy), `check-dependencies.sh` (dependency resolution), `validate-composition.sh` (composition references).

## Plugin Versioning

When you modify a plugin's skills, agents, or references, **bump the version** in its `.claude-plugin/plugin.json` before committing. Follow semver:

- **Patch** (1.0.0 → 1.0.1) — reference fixes, typo corrections, description enrichment
- **Minor** (1.0.0 → 1.1.0) — new references, new agents, additional patterns, new skill content
- **Major** (1.0.0 → 2.0.0) — skill renamed/restructured, breaking changes to how the plugin works

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

| Plugin | Purpose |
|---|---|
| **ned** | Personal knowledge graph (ai-memory MCP) and session recorder |
| **craft-developer** | Craft CMS 4/5 development patterns and query cookbook |
| **project-manager** | LT10 methodology, Notion-integrated sprint planning with Userback triage, Calendar.app meeting prep, Mail.app scanning, content ideation, and velocity tracking |
| **council** | Worker cooperative governance (BC Co-op Act) and decolonial content strategy |
| **design-machines** | DM business strategy, catalog, partnerships, revenue model, design system |
| **assembly** | Go/Templ/Datastar governance app development |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **ghostwriter** | Personal writing voice, editorial style engine, and voice editing |
| **design-practice** | Typography, layout, data visualization, and identity design philosophy |
| **project-scaffolder** | Claude Code project infrastructure scaffolding with hooks, agents, and CLAUDE.md |
| **accessibility-compliance** | WCAG 2.2 auditing and enforcement for Live Wires, Templ+Datastar, and Craft CMS |
| **dm-review** | Code review orchestrator with parallel agents, visual browser testing, UX design review, visual design quality review, and Live Wires CSS compliance across all DM stacks |
| **the-local** | Self-hosted Matrix network (The Local) -- Element Web branding, Synapse config, server ops |
| **chef** | Science-driven cooking assistant with Mela integration, dietary analysis, meal planning, and Bali sourcing |
| **pipeline** | Autonomous feature development pipeline with assessment, research, prompt generation, adversarial review, and worktree execution with review-fix loops |
| **gemini** | Gemini CLI subagent for Google search grounding, 2M token context diff analysis, and code execution sandbox |

## Description Evaluation

Every skill has a corresponding eval file in `description-evals/<plugin>-<skill>.json` containing test queries with expected trigger outcomes. The eval runner checks whether the SKILL.md `description:` field contains enough relevant vocabulary to match real user queries.

```shell
./tools/eval-descriptions.sh          # run all evals
./tools/eval-descriptions.sh -v       # verbose (show failures)
./tools/eval-descriptions.sh foo.json # run one eval
```

When editing a SKILL.md `description:` field, run the eval for that skill to confirm trigger accuracy holds. Skills must stay above 70% accuracy. See `tools/README.md` for details on the heuristic, pre-commit hooks, and adding new eval cases.

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

## Conventions

- All content is Markdown. No code to compile, lint, or test.
- Skills use `SKILL.md` as the canonical filename for the primary skill definition. The `name:` field in its YAML frontmatter must match the skill folder name exactly.
- Reference files live in `references/` subdirectories and are named descriptively (e.g., `estimation.md`, `bc-cooperative-act.md`).
- Agent files are categorized by purpose: `review/` for code review agents, `workflow/` for automation agents.
- Plugin JSON requires `name`, `description`, `version`, `author`, and `capabilities`. Optional fields include `keywords`, `repository`, and `author.url`.
- The marketplace manifest at `.claude-plugin/marketplace.json` must stay in sync with the actual plugin directories.

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

See `docs/post-mortems/` for detailed root cause analysis.

## Post-Implementation Checklist

After any pipeline run or manual feature implementation, verify:

- [ ] All affected pages render without console errors
- [ ] Screenshots taken at desktop (1440px) and mobile (375px) for every UI change
- [ ] Visual output compared to design spec or brainstorm mockup (if one exists)
- [ ] dm-review-loop run on the final branch (not just per-chunk quick reviews)
- [ ] Requirements cross-check with EVIDENCE type for each requirement (screenshot, build pass, computed style)
- [ ] No "visually identical" requirements left unverified (visual diff protocol applied)
- [ ] Session recorded to ai-memory
- [ ] Postmortem written if any failure patterns were observed

## Postmortems

Pipeline failure analysis documents live in `docs/post-mortems/`:

- `2026-04-07-pipeline-ui-refinement-postmortem.md` -- 6 failure modes from Assembly UI refinement run
- `2026-04-10-pipeline-visual-testing-postmortem.md` -- 7 failure modes from Assembly pipeline bypass and visual testing gaps

These postmortems inform the Known Pipeline Failure Modes section above and the hardening measures in the pipeline plugin.
