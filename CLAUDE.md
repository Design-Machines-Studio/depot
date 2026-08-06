# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Depot (DM-013/WORKS) is Design Machines' Claude Code plugin marketplace -- a collection of knowledge-as-code plugins that give Claude specialized domain expertise. The repo is structured Markdown and JSON that Claude Code consumes as skills, agents, and reference material, with one sanctioned executable exception: the workflow-kernel plugin ships a stdlib-only Python 3.12 reference runtime (no build step, no third-party dependencies). Its test suite is a repository development artifact at the top-level `tests/` directory -- it never ships into user plugin caches -- and is run by `tools/validate-workflow-kernel.py` as part of `./tools/validate-composition.sh --all`. Everything else has no build system, test suite, or application code.

## Plugin Discovery (Agent Cards)

Each `plugin.json` serves as an **Agent Card** -- machine-readable metadata that makes plugin discovery reliable instead of vibes-based. Inspired by the A2A protocol's Agent Card concept, the `capabilities` object declares what each plugin can do. Read any `plugins/*/.claude-plugin/plugin.json` for the shape.

**Field conventions:**
- `triggers` are short query fragments a user would type, not restated descriptions. Skills with `description-evals/` JSON files use evaluated trigger queries; others use authored natural-language fragments.
- `mcpDependencies` uses normalized service names (`ai-memory`, `notion`, `userback`, `playwright`), not raw tool prefixes. Only present when the skill declares `allowed-tools` in its SKILL.md frontmatter.
- `argumentHint` is only present on commands that accept arguments.
- `skills`, `agents`, and `commands` arrays are always present in the `capabilities` object, even when empty.
- The marketplace manifest (`.claude-plugin/marketplace.json`) includes `capabilities_summary` for each plugin -- counts and curated tags for quick search without loading full capabilities. Its `tags` are a hand-picked subset, not a union of all skill/agent tags.

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
shadow comparison, exact owned-resource cleanup, trusted inspection profiles,
contained lanes, redaction, canonical output, and compatible trends. Version
0.4.0 keeps workflow shadow as the default while allowing consumers to
explicitly delegate bounded authoritative mechanics. See
`docs/workflow-kernel.md` and `docs/quality-pulse.md`.

## Composition Validation

Validate all cross-plugin references, dependencies, eval accuracy, and search index freshness in one command:

```shell
./tools/validate-composition.sh --all
```

Individual validators: `eval-descriptions.sh` (description accuracy),
`check-dependencies.sh` (dependency resolution and the workflow-kernel leaf
contract), `validate-workflow-kernel.py` (offline behavioral proof),
`validate-quality-pulse.sh` (49-case synthetic consumer conformance),
`validate-marketplace-capabilities.sh` (canonical/generated discovery
mappings), `validate-composition.sh` (composition references), and
`validate-workflow-contracts.sh` (repository cleanup, Datastar-first,
Baseplate evidence, and workflow-kernel integration anchors).

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

### Update Troubleshooting and Notion Manual Sync

Stale plugin caches (CLI/VSCode, Desktop Cowork), manual marketplace pulls, and the Notion
manual page sync procedure live in the `plugin-cache-sync` skill
(`.claude/skills/plugin-cache-sync/SKILL.md`).

## The Plugins

The plugin roster and per-plugin purposes live in `.claude-plugin/marketplace.json`.
For a searchable index of every skill, agent, and command, see `docs/search-index.md`
(regenerate with `./tools/validate-composition.sh --generate-index`).

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

**Kimi K3 (Jul 2026):** Moonshot AI's planned-open-weight, API-only-today model (`moonshotai/kimi-k3`, 2.8T-param MoE, 1M context, $3/$15 with $0.30 cache hits) is the quality-first OpenRouter security and bulk-analysis head at rank 97. Artificial Analysis v4.1 scores K3 at 57: behind Fable 5 (60) and GPT-5.6 Sol max (59), ahead of Opus 4.8 max (56), Terra/GPT-5.5 max (55), Sonnet 5 max (53), and GLM-5.2 max (51). GLM-5.2 heads `openrouter_exec`; Kimi K3 heads the security and bulk-analysis roles and remains a frontier/bulk wrapper model. Luna is the economical mechanical route, while Terra is the quality/direct fallback. OpenRouter currently warns that K3's sole upstream provider has limited capacity, so its ladders retain fallbacks. The wrapper is text-only despite upstream multimodal capabilities, and automated use remains broker-gated and fail-closed until production host authority is available.

**Coding subscription rails (Jul 2026):** Claude is moving from Max to Pro and is outside the coding graph. Codex Pro 20x is the active coding profile at a 65/0/35 Codex/Claude/OpenRouter target; the named Codex 5x profile shifts to 40/0/60. All implementation and code-review kinds, including UI, security, and architecture, route to Codex or OpenRouter. Claude remains available only for non-coding strategy, writing/voice, research synthesis, and optional plan critique.

**Provider privacy (demoted, Jul 2026):** model selection priority is Quality > Price > Speed > Provider privacy. `OPENROUTER_ZDR=1` is opt-in only (genuinely sensitive material: client code under NDA, credentials-adjacent diffs) -- Chinese first-party hosting (Moonshot/DeepSeek/Z.AI) is acceptable by default and no rung pins ZDR anymore.

## Pipeline Enforcement

When the user says `/pipeline` or asks to "run the pipeline" or "use the full pipeline process," you MUST invoke the pipeline skill from `plugins/pipeline/`. Do not manually execute pipeline steps. Do not replicate the pipeline's assess-research-plan-prompt-review-execute phases by hand. The pipeline enforces gates, review loops, visual verification, and memory capture that manual execution skips.

If the pipeline skill is unavailable (not installed), tell the user and stop. Do not improvise a substitute.

## Known Pipeline Failure Modes

Eighteen failure patterns have been observed in production pipeline runs, each with a
root cause, a hardening measure in the pipeline plugin, and a post-implementation
verification checklist. They live in the `pipeline-failure-modes` skill
(`.claude/skills/pipeline-failure-modes/SKILL.md`) -- load it before starting a pipeline
run, when a run misbehaves, or when writing a postmortem. Detailed root cause analysis is
in `docs/post-mortems/`.

<!-- airlift:start -->
An airlift handoff is available at .airlift/HANDOFF.md (checkpoint 5, 2026-07-27T01:58:26Z).
Read it before continuing.
<!-- airlift:end -->
