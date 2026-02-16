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
desktop-skills/                  — Zipped skills for Claude Desktop (auto-generated)
```

## Plugin Anatomy

Each plugin under `plugins/` follows the same structure:

- **`.claude-plugin/plugin.json`** — Required. Contains `name`, `description`, `version`, and `author`.
- **`skills/`** — Each subdirectory is a skill. `SKILL.md` is the entry point; `references/` holds supplementary material that the skill can pull in.
- **`agents/`** — Optional. Agent definitions organized by category (`review/`, `workflow/`). Each `.md` file defines a specialized agent.

## The Eight Plugins

| Plugin | Purpose |
|---|---|
| **ned** | Personal knowledge graph (ai-memory MCP) and session recorder |
| **craft-developer** | Craft CMS 4/5 development patterns and query cookbook |
| **project-manager** | LT10 methodology, Notion-integrated planning, time tracking |
| **council** | Worker cooperative governance (BC Co-op Act) and decolonial content strategy |
| **design-machines** | DM business strategy, catalog, partnerships, revenue model |
| **assembly** | Go/Templ/Datastar governance app prototyping |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **ghostwriter** | Personal writing voice, editorial style engine, and voice editing |

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

## Desktop Skills Sync

Whenever you create or edit any file inside a plugin's `skills/` directory, you MUST also update the corresponding zip in `desktop-skills/`:

1. **Delete the old zip first**, then `cd` into the skill folder and zip from there so `SKILL.md` is at the zip root. Claude Desktop requires exactly one `SKILL.md` — nested paths or duplicate entries will fail.

   ```shell
   rm -f desktop-skills/memory.zip && cd plugins/ned/skills/memory && zip -r /absolute/path/to/desktop-skills/memory.zip .
   ```

2. The zip name matches the skill folder name, not the plugin name. So `plugins/project-manager/skills/lt10/` becomes `desktop-skills/lt10.zip`.
3. Always replace — `desktop-skills/` should contain the latest version of every affected skill.
4. After zipping, tell the user which skill zips were updated so they can install them in Claude Desktop.

If multiple skills are edited in one session, zip all of them.

## Conventions

- All content is Markdown. No code to compile, lint, or test.
- Skills use `SKILL.md` as the canonical filename for the primary skill definition. The `name:` field in its YAML frontmatter must match the skill folder name exactly.
- Reference files live in `references/` subdirectories and are named descriptively (e.g., `estimation.md`, `bc-cooperative-act.md`).
- Agent files are categorized by purpose: `review/` for code review agents, `workflow/` for automation agents.
- Plugin JSON is minimal — just `name`, `description`, `version`, and `author`.
- The marketplace manifest at `.claude-plugin/marketplace.json` must stay in sync with the actual plugin directories.
