---
name: scaffolding
description: Scaffold Claude Code project infrastructure — hooks, agents, settings.json, and CLAUDE.md — for any Design Machines project type. Use when setting up a new project, configuring Claude Code hooks, creating a CLAUDE.md routing document, adding commit-push reminders, setting up Docker safety gates, configuring session-start workflows, or standardizing .claude/ directory structure. Covers go-templ-datastar, go-library, css-framework, and craft-cms project types.
disable-model-invocation: true
argument-hint: "[project-type: go-templ-datastar|go-library|css-framework|craft-cms]"
---

# Project Scaffolding

Standardize Claude Code setup across all Design Machines projects. Generate `.claude/` infrastructure (hooks, agents, settings) and a routing-style `CLAUDE.md` from battle-tested templates.

## Quick Reference

### Project Types

| Type | Stack | Docker | Hooks | Agents |
|------|-------|--------|-------|--------|
| `go-templ-datastar` | Go + Templ + Datastar + Live Wires | Yes | all 5 + a11y-check | go-builder, css-reviewer, doc-sync, security-auditor, a11y-html-reviewer, a11y-css-reviewer, a11y-dynamic-content-reviewer |
| `go-library` | Go module (no frontend) | Optional | commit-push, pre-stop, post-edit | doc-sync |
| `css-framework` | CSS + npm build | No | commit-push, pre-stop, post-edit, a11y-check | css-reviewer, doc-sync, a11y-css-reviewer |
| `craft-cms` | Craft CMS + DDEV + Twig | DDEV | commit-push, pre-stop, post-edit, block-bare-craft, a11y-check | doc-sync, security-auditor, a11y-html-reviewer, a11y-css-reviewer |

### Hook Inventory

| Hook | Event | Matcher | Default | Purpose |
|------|-------|---------|---------|---------|
| `block-bare-go.sh` | PreToolUse | Bash | Go projects | Prevent Go/Templ outside Docker |
| `session-start-gate.sh` | PreToolUse | Edit\|Write | Opt-in | Block changes until planner workflow completes |
| `commit-push-reminder.sh` | PostToolUse | Edit\|Write | ALL | Nudge commits at 3+ files, push at 2+ commits |
| `post-edit-context.sh` | PostToolUse | Edit\|Write | ALL | Agent reminders based on file type |
| `a11y-check.sh` | PostToolUse | Edit\|Write | Frontend projects | A11y agent reminders after template/CSS/JS changes |
| `nats-safety.sh` | PostToolUse | Edit\|Write | `go-templ-datastar` | NATS config safety reminders after editing NATS-related files |
| `pre-stop-check.sh` | Stop | — | ALL | Uncommitted work check + agent compliance |

### Agent Inventory

| Agent | Applies to | Purpose |
|-------|-----------|---------|
| `go-builder.md` | Go projects | Docker-safe build, test, generate |
| `css-reviewer.md` | Live Wires projects | CSS compliance (layers, naming, tokens) |
| `doc-sync.md` | ALL projects | Documentation freshness after code changes |
| `security-auditor.md` | Backend projects | OWASP review + project-specific concerns |
| `a11y-html-reviewer.md` | Frontend projects | WCAG HTML/template compliance |
| `a11y-css-reviewer.md` | Frontend projects | WCAG visual accessibility (contrast, focus, motion) |
| `a11y-dynamic-content-reviewer.md` | Datastar projects | Live regions, focus management, keyboard |
| `nats-reviewer.md` | `go-templ-datastar` | NATS safety: DontListen, ScopedEventBus, subject naming, event ordering |
| `go-test-runner.md` | `go-templ-datastar`, `go-library` | Go test runner: race detection, coverage, missing test files |
| `migration-validator.md` | `go-templ-datastar`, `go-library` | Migration review: goose format, table prefixes, cross-fixture FK |

**Module Interface (go-templ-datastar):** Production Assembly projects use a Module interface for fixture registration. When scaffolding, the generated CLAUDE.md includes ScopedDB, ScopedNATS, Module interface, and federation sections. See the `project-configs.md` reference for the full CLAUDE.md template.

## Scaffold Workflow

When the user asks to scaffold a project, follow these steps:

### Step 1: Gather Requirements

Ask the user:
1. **Project type** — one of: `go-templ-datastar`, `go-library`, `css-framework`, `craft-cms`. If the project doesn't fit any of these, use a generic starter from `references/claude-md-templates/` (see "Generic CLAUDE.md Starters" below) and skip to Step 5.
2. **Project name** — used for display in CLAUDE.md (e.g., "Assembly", "Dashboard", "Live Wires")
3. **Enable session-start-gate?** — opt-in, only for projects using the planner workflow
4. **Any additional agents?** — project-specific agents beyond the defaults

### Step 2: Derive Configuration

Set these variables from the user's answers:

- `{{PROJECT_PREFIX}}` — lowercase directory name of the project (e.g., `assembly`, `dashboard`). Used in `/tmp/` marker files to avoid collisions between projects.
- `{{PROJECT_NAME}}` — display name (e.g., "Assembly", "Dashboard")
- `{{PROJECT_TYPE}}` — the selected type
- Determine which hooks and agents to include based on the project type table above

### Step 3: Generate Files

Read the reference files to get templates:
- **`${CLAUDE_SKILL_DIR}/references/hooks.md`** — hook script templates
- **`${CLAUDE_SKILL_DIR}/references/agents.md`** — agent definition templates
- **`${CLAUDE_SKILL_DIR}/references/project-configs.md`** — settings.json and CLAUDE.md templates

Create the following in the target project:

```
.claude/
  settings.json              ← from project-configs.md, based on project type
  hooks/
    block-bare-go.sh         ← Go projects only (from hooks.md)
    session-start-gate.sh    ← if opted in (from hooks.md)
    commit-push-reminder.sh  ← always (from hooks.md)
    post-edit-context.sh     ← always, customized per type (from hooks.md)
    a11y-check.sh            ← frontend projects (from hooks.md)
    pre-stop-check.sh        ← always (from hooks.md)
  agents/
    go-builder.md            ← Go projects only (from agents.md)
    css-reviewer.md          ← Live Wires projects (from agents.md)
    doc-sync.md              ← always (from agents.md)
    security-auditor.md      ← backend projects (from agents.md)
    a11y-html-reviewer.md    ← frontend projects (from agents.md)
    a11y-css-reviewer.md     ← frontend projects (from agents.md)
    a11y-dynamic-content-reviewer.md ← Datastar projects (from agents.md)
CLAUDE.md                    ← routing doc (from project-configs.md)
.pa11yci.json                ← frontend projects (from project-configs.md)
tests/
  a11y/
    pages.spec.js            ← frontend projects (from project-configs.md)
tasks/
  todo.md                    ← empty task file
  lessons.md                 ← empty lessons file
```

### Step 4: Finalize

1. Replace all `{{PROJECT_PREFIX}}` and `{{PROJECT_NAME}}` placeholders in generated files
2. For `post-edit-context.sh`: remove sections that don't apply to the project type (marked with comments)
3. For `pre-stop-check.sh`: set the `AGENTS` array to only include applicable agents
4. Run `chmod +x .claude/hooks/*.sh`
5. Print a summary of what was generated

### Step 5: User Customization Guidance

Tell the user:
- Review `CLAUDE.md` and fill in project-specific sections (architecture overview, build commands, directory structure)
- Review `settings.json` — add project-specific permissions to `settings.local.json` if needed
- Add any project-specific agents to `.claude/agents/`
- The `post-edit-context.sh` hook can be extended with project-specific file type → agent mappings

## Generic CLAUDE.md Starters

For projects that don't match one of the four project-type templates above, use a starter from `${CLAUDE_SKILL_DIR}/references/claude-md-templates/`. These files sit in a sub-directory (not flat under `references/`) to signal "choose one" and to reserve room for additional stack-generic starters (python, node, docs-site) without polluting the top-level reference namespace.

| Template | Use when |
|----------|----------|
| [${CLAUDE_SKILL_DIR}/references/claude-md-templates/minimal.md](${CLAUDE_SKILL_DIR}/references/claude-md-templates/minimal.md) | No DM-stack assumptions. Any project, any stack. |
| [${CLAUDE_SKILL_DIR}/references/claude-md-templates/dm-standard.md](${CLAUDE_SKILL_DIR}/references/claude-md-templates/dm-standard.md) | DM project that doesn't match one of the four project-type templates. |

Copy the chosen template to the target project's `CLAUDE.md` and edit in place. No `{{PLACEHOLDER}}` substitution required — these starters ship with concrete content, unlike the project-type templates in `project-configs.md` which do use placeholder substitution. `minimal.md`'s header comment is a license-mandated attribution block; retain it verbatim when the template is redistributed. `dm-standard.md`'s header is informational and may be stripped by the consumer.

## Parameterization Convention

All templates use double-brace placeholders:

| Placeholder | Replaced with | Example |
|-------------|---------------|---------|
| `{{PROJECT_PREFIX}}` | Lowercase project directory name | `assembly` |
| `{{PROJECT_NAME}}` | Display name | `Assembly` |
| `{{PROJECT_TYPE}}` | Project type key | `go-templ-datastar` |
| `{{PROJECT_URL_LOCAL}}` | Local development URL | `http://dm006.asmbly.site` |
| `{{PROJECT_URL_PROD}}` | Production URL | `https://dm006.asmbly.app` |

Replace all placeholders before writing files. Remove any remaining placeholder lines that don't apply.

## DM-Review Integration

The `dm-review` depot plugin provides a full code review orchestrator that launches up to 15 parallel agents across accessibility, security, architecture, CSS, voice, and governance domains. It detects project type automatically from marker files (`go.mod`, `craft/`, `.ddev/`, `package.json`) and selects applicable agents — no per-project configuration needed.

For projects with the depot installed, run `/dm-review` for a full review or `/dm-review quick` for core agents only.

## Hook Design Principles

These principles are baked into every hook template:

1. **Portable paths** — use `$CLAUDE_PROJECT_DIR`, never hardcoded absolute paths
2. **jq for JSON parsing** — hooks receive JSON via stdin; use `jq` to extract fields
3. **Exit codes** — `0` = allow, `2` = block (for PreToolUse hooks)
4. **PostToolUse JSON** — return `{"systemMessage": "..."}` for nudges
5. **Defensive scripting** — handle missing git, missing files, unset variables gracefully
6. **Marker files in /tmp** — use `{{PROJECT_PREFIX}}` in marker names to avoid collisions
7. **HEAD-keyed markers** — nudges that should reset after commits use `git rev-parse --short HEAD` in the marker name
8. **Security** — use `printf '%s\n'` instead of `echo` to prevent flag injection; quote all variable expansions

## Ecosystem Integration

Official and third-party Claude Code plugins that complement this skill:

| Plugin | Tool | When to Use |
|--------|------|-------------|
| **hookify** | `/hookify` | Create custom hooks beyond scaffold templates |
| **claude-md-management** | `/revise-claude-md` | Ongoing CLAUDE.md maintenance after scaffolding |
| **plugin-dev** | `/create-plugin` | Develop project-specific plugins |
| **superpowers** | `/plan` | Architecture planning before scaffolding |

## Reference Files

| File | Contains |
|------|----------|
| [${CLAUDE_SKILL_DIR}/references/hooks.md](${CLAUDE_SKILL_DIR}/references/hooks.md) | All 5 hook script templates with full source and customization notes |
| [${CLAUDE_SKILL_DIR}/references/agents.md](${CLAUDE_SKILL_DIR}/references/agents.md) | Agent definition templates (go-builder, css-reviewer, doc-sync, security-auditor) |
| [${CLAUDE_SKILL_DIR}/references/project-configs.md](${CLAUDE_SKILL_DIR}/references/project-configs.md) | settings.json templates, CLAUDE.md routing doc templates, tasks file starters — organized by project type |
| [${CLAUDE_SKILL_DIR}/references/claude-md-templates/minimal.md](${CLAUDE_SKILL_DIR}/references/claude-md-templates/minimal.md) | Drop-in CLAUDE.md starter for any stack — Karpathy's four principles, verbatim, with MIT attribution |
| [${CLAUDE_SKILL_DIR}/references/claude-md-templates/dm-standard.md](${CLAUDE_SKILL_DIR}/references/claude-md-templates/dm-standard.md) | Drop-in CLAUDE.md starter for DM projects that don't match a project-type template — paraphrased principles plus DM conventions |
