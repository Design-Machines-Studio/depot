# AGENTS.md

This file provides guidance to Codex when working with code in this repository.

## What This Is

Depot (DM-013/WORKS) is Design Machines' AI plugin marketplace — a collection of knowledge-as-code plugins that give AI coding assistants specialized domain expertise. There is no build system, test suite, or application code. The entire repo is structured Markdown and JSON consumed as skills, agents, and reference material.

**This marketplace was built for Claude Code.** Codex compatibility is provided via generated manifest shims. CLAUDE.md is the canonical reference for the full documentation — everything below covers only what differs for Codex.

## Dual-Platform Architecture

Claude Code is the primary consumer. Codex support is an adapter layer:

| Aspect | Claude (canonical) | Codex (generated) |
|--------|-------------------|-------------------|
| Root marketplace manifest | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| Per-plugin manifest | `plugins/<name>/.claude-plugin/plugin.json` | `plugins/<name>/.codex-plugin/plugin.json` |
| Plugin cache (runtime) | `~/.claude/plugins/cache/depot/` | `~/.codex/plugins/cache/depot/` |
| Project instructions | `CLAUDE.md` | `AGENTS.md` (this file) |

**All skill content, agent definitions, and reference material are shared.** Only the manifest layer differs.

## Repository Structure

```
.claude-plugin/marketplace.json     — Canonical marketplace manifest
.agents/plugins/marketplace.json    — Generated Codex marketplace manifest
plugins/<name>/
  .claude-plugin/plugin.json        — Canonical plugin metadata
  .codex-plugin/plugin.json         — Generated Codex plugin metadata
  skills/<skill-name>/
    SKILL.md                        — Primary skill definition
    references/                     — Supporting reference docs
  agents/<category>/
    <agent-name>.md                 — Agent definitions (review/, workflow/)
  commands/
    <command-name>.md               — Slash command definitions
description-evals/                  — Trigger evaluation datasets
tools/                              — Eval runner and development utilities
docs/                               — Design specs and architecture docs
```

## Codex Manifest Generation

Claude manifests are the source of truth. Never hand-edit Codex manifest files — they are generated:

```shell
./tools/generate-codex-manifests.py          # regenerate all Codex manifests
./tools/generate-codex-manifests.py --check  # verify generated files are current
```

## Runtime Cache Path Resolution

Plugins that resolve paths at runtime (deepseek, gemini, dm-review, pipeline) use a Claude-first/Codex-fallback loop:

```bash
WRAPPER_PATH=""
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER_PATH=$(ls -t "$CACHE_ROOT"/deepseek/*/skills/deepseek-delegate/references/deepseek-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER_PATH" ] && break
done
```

When editing cache lookups, always include both roots. Validate with:

```shell
./tools/validate-dual-compat.sh
```

## Validation

```shell
./tools/validate-composition.sh --all    # full validation (includes dual-compat check)
./tools/validate-dual-compat.sh          # Codex manifest sync + cache fallback check only
./tools/eval-descriptions.sh             # skill description trigger accuracy
./tools/check-dependencies.sh            # plugin dependency resolution
```

## Editing Rules

1. **Claude manifests are canonical.** Edit `.claude-plugin/plugin.json`, then run `./tools/generate-codex-manifests.py` to sync.
2. **Bump versions in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.** Codex manifests pick up the version automatically on regeneration.
3. **Skills, agents, commands, and references are shared.** Edit them once; both platforms consume the same files.
4. **Cache lookups need both roots.** Any new `~/.claude/plugins/cache/depot` reference must include the `~/.codex/plugins/cache/depot` fallback.
5. **Run `./tools/validate-composition.sh --all` before committing.** It catches manifest drift, stale Codex shims, missing cache fallbacks, and frontmatter corruption.

## Full Documentation

For plugin anatomy, Agent Card capabilities schema, dependency declarations, orchestration patterns, versioning rules, pipeline enforcement, known failure modes, and the post-implementation checklist, see CLAUDE.md. All of that applies identically to Codex — only the manifest paths differ as documented above.

## The Plugins

17 plugins | 36 skills | 41 agents | 31 commands

| Plugin | Purpose |
|---|---|
| **ned** | Personal knowledge graph (ai-memory MCP) and session recorder |
| **craft-developer** | Craft CMS 4/5 development patterns and query cookbook |
| **project-manager** | LT10 methodology, Notion-integrated sprint planning |
| **council** | Worker cooperative governance (BC Co-op Act) and decolonial content strategy |
| **design-machines** | DM business strategy, catalog, partnerships, revenue model, design system |
| **assembly** | Go/Templ/Datastar governance app development |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **ghostwriter** | Personal writing voice and editorial style engine |
| **design-practice** | Typography, layout, data visualization, and identity design philosophy |
| **project-scaffolder** | Project infrastructure scaffolding with hooks, agents, and CLAUDE.md templates |
| **accessibility-compliance** | WCAG 2.2 auditing and enforcement |
| **dm-review** | Code review orchestrator with parallel agents and visual browser testing |
| **the-local** | Self-hosted Matrix network — Element Web branding, Synapse config |
| **chef** | Science-driven cooking assistant with Mela integration |
| **pipeline** | Autonomous feature development pipeline with review-fix loops |
| **gemini** | Gemini CLI subagent for search grounding, 2M context diff analysis, code execution |
| **deepseek** | DeepSeek V4 API subagent for code review and bulk diff analysis |

## Conventions

- Almost all content is Markdown. No code to compile, lint, or test.
- Skills use `SKILL.md` as the canonical filename. The `name:` field in YAML frontmatter must match the skill folder name.
- Reference files live in `references/` subdirectories.
- Agent files are categorized: `review/` for code review agents, `workflow/` for automation agents.
- Plugin JSON requires `name`, `description`, `version`, `author`, and `capabilities`.
