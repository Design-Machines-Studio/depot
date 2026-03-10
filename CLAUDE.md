# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Depot (DM-013/WORKS) is Design Machines' Claude Code plugin marketplace — a collection of knowledge-as-code plugins that give Claude specialized domain expertise. There is no build system, test suite, or application code. The entire repo is structured Markdown and JSON that Claude Code consumes as skills, agents, and reference material.

## Repository Structure

```
.claude-plugin/marketplace.json  — Marketplace manifest (lists all plugins)
plugins/<name>/
  .claude-plugin/plugin.json     — Plugin metadata (name, description, version)
  skills/<skill-name>/
    SKILL.md                     — Primary skill definition (loaded on skill invocation)
    references/                  — Supporting reference docs (loaded on demand)
    *.md                         — Additional skill pages (components, patterns, etc.)
  agents/<category>/
    <agent-name>.md              — Agent definitions (review, workflow categories)
docs/                            — Design specs and architecture docs
```

## Plugin Anatomy

Each plugin under `plugins/` follows the same structure:

- **`.claude-plugin/plugin.json`** — Required. Contains `name`, `description`, `version`, and `author`.
- **`skills/`** — Each subdirectory is a skill. `SKILL.md` is the entry point; `references/` holds supplementary material that the skill can pull in.
- **`agents/`** — Optional. Agent definitions organized by category (`review/`, `workflow/`). Each `.md` file defines a specialized agent.
- **`commands/`** — Optional. Slash command definitions. Each `.md` file defines a command that can be invoked directly.

## Plugin Versioning

When you modify a plugin's skills, agents, or references, **bump the version** in its `.claude-plugin/plugin.json` before committing. Follow semver:

- **Patch** (1.0.0 → 1.0.1) — reference fixes, typo corrections, description enrichment
- **Minor** (1.0.0 → 1.1.0) — new references, new agents, additional patterns, new skill content
- **Major** (1.0.0 → 2.0.0) — skill renamed/restructured, breaking changes to how the plugin works

Never commit plugin changes without also bumping the version.

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
| **project-manager** | LT10 methodology, Notion-integrated planning, and sprint management |
| **council** | Worker cooperative governance (BC Co-op Act) and decolonial content strategy |
| **design-machines** | DM business strategy, catalog, partnerships, revenue model |
| **assembly** | Go/Templ/Datastar governance app development |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **ghostwriter** | Personal writing voice, editorial style engine, and voice editing |
| **design-practice** | Typography, layout, data visualization, and identity design philosophy |
| **project-scaffolder** | Claude Code project infrastructure scaffolding with hooks, agents, and CLAUDE.md |
| **accessibility-compliance** | WCAG 2.2 auditing and enforcement for Live Wires, Templ+Datastar, and Craft CMS |
| **dm-review** | Code review orchestrator with parallel agents and visual browser testing across all DM stacks |
| **the-local** | Self-hosted Matrix network (The Local) -- Element Web branding, Synapse config, server ops |

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
- Plugin JSON requires `name`, `description`, `version`, and `author`. Optional fields include `keywords`, `repository`, and `author.url`.
- The marketplace manifest at `.claude-plugin/marketplace.json` must stay in sync with the actual plugin directories.
