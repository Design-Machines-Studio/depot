# Project Configuration Templates

settings.json, CLAUDE.md, and starter files for each project type. Replace all `{{PLACEHOLDER}}` values before writing.

## Contents
- [settings.json Templates](#settingsjson-templates) (line 7)
  - go-templ-datastar (line 9), go-library (line 113), css-framework (line 148), craft-cms (line 183)
- [CLAUDE.md Templates](#claudemd-templates) (line 234)
  - go-templ-datastar (line 236), go-library (line 345), css-framework (line 405), craft-cms (line 477)
- [Starter Files](#starter-files) -- optional todo.md, lessons.md, sessions.md

---

## settings.json Templates

### go-templ-datastar (all hooks)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-bare-go.sh",
            "statusMessage": "Checking Docker safety..."
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-edit-context.sh"
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/commit-push-reminder.sh",
            "statusMessage": "Checking commit hygiene..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-stop-check.sh"
          }
        ]
      }
    ]
  }
}
```

### go-library (no Docker gate)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-edit-context.sh"
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/commit-push-reminder.sh",
            "statusMessage": "Checking commit hygiene..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-stop-check.sh"
          }
        ]
      }
    ]
  }
}
```

### css-framework (no Docker gate)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-edit-context.sh"
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/commit-push-reminder.sh",
            "statusMessage": "Checking commit hygiene..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-stop-check.sh"
          }
        ]
      }
    ]
  }
}
```

### craft-cms (DDEV gate instead of Docker gate)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-bare-craft.sh",
            "statusMessage": "Checking DDEV safety..."
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-edit-context.sh"
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/commit-push-reminder.sh",
            "statusMessage": "Checking commit hygiene..."
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-stop-check.sh"
          }
        ]
      }
    ]
  }
}
```

**Note:** `block-bare-craft.sh` is the hook template in `references/hooks.md`. It blocks bare `php craft` and `composer` commands, requiring `ddev craft` and `ddev composer` instead.

---

## CLAUDE.md Templates

For every rendered project, populate its root instructions with the verified
project code, established review domain, canonical serving repo folder, and
directly linked build/restart procedure. Design Machines codes such as
`DM-006/WORKS` map to `dm006.asmbly.app`; use the existing mapping, not a new
publication. Query the Project Codes catalog only if the code is unknown.
Record that ordinary review checks out the feature branch in that folder and
uses its existing domain and environment; a new harness needs a concrete test
requirement such as simultaneous Federation peers. Do not invent missing
bindings or make scaffolding change DNS, ports, data or service configuration.
For Assembly Baseplate/Fixtures, also declare the Assembly prototype as the
definitive HTML/Live Wires/component and Datastar interaction baseline, with
source comparison and matched browser save/reload proof. Link existing
prototype UX task/persona selection through dm-review’s `ui-case-selection.md`.
Include status commands and the safe detached exact-head alternative when the
feature branch is already checked out elsewhere; retain the maintained
instance. Carry these same instructions into the generated AGENTS.md; do not create a second registry.

### go-templ-datastar

```markdown
# CLAUDE.md

This file is the routing document for Claude Code. Critical rules live here; detailed reference lives in skills.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does, who it's for]. Built with Go (Templ + Chi), SQLite, Datastar, and the Live Wires CSS framework. Runs in Docker.

- **Local:** {{PROJECT_URL_LOCAL}}
- **Production:** {{PROJECT_URL_PROD}}

## Existing Development Site

- Project code: [verified project code]
- Review domain: [established project-code.asmbly.app mapping]
- Serving checkout: [verified absolute checkout and canonical remote]
- Source binding: [how status/build evidence identifies the served source]
- Status command: [existing exact command]
- Rebuild/restart: [existing exact command or directly linked runbook]

Use ordinary Git in the clean, available serving checkout to select the feature
branch, or its exact detached commit when that branch is already checked out
elsewhere. Preserve owned edits and fingerprint them for in-place review; name
unrelated dirty or concurrent ownership collisions. Rebuild before claiming the
new source is served. Keep the same domain, service, data and configuration.
Check incompatible migrations before maintenance; never reset shared data.
Leave the maintained instance available. Isolated browser environments need a
concrete test requirement; ordinary unit-test containers remain valid.

For Assembly counterparts, inspect exact prototype templates, rendered HTML,
Live Wires classes/components and Datastar save behavior before implementation.
Use existing prototype UX tasks/personas through dm-review's
`ui-case-selection.md`; compare paired interactions and reload/revisit evidence.

## Workflow Orchestration

### Workflow Selection
- Choose the lightest workflow that fits the task. For a small documentation, configuration, or bounded content edit, inspect the affected files, make the change, and run focused checks; plan mode and agents are optional.
- Use plan mode when a task is multi-step, architectural, cross-cutting, or higher risk and a written sequence clarifies the acceptance criteria.
- Keep focused agents available as tools. Use the go-builder, CSS, security, documentation, and accessibility agents when their checks apply; none is required after every edit.
- Update documentation when behavior, commands, configuration, file structure, or operating instructions change. Use doc-sync when the impact is non-obvious, not as a post-edit ritual.
- Record a lesson only when a finding is reusable beyond this task. Do not create routine lesson entries or a lessons store just to complete a workflow.
- Preserve repository-owned command restrictions and real checks for credentials, authentication/authorization, destructive or data-loss actions, release integrity, and applicable accessibility.
- When delegating, request only a role, required capabilities, and normalized effort (`low`, `medium`, `high`, or `max`). Keep concrete model and rail recommendations in operator context; see the [current model-router guidance](https://github.com/Design-Machines-Studio/depot/blob/main/plugins/model-router/skills/model-router/references/driver-worker-guidance.md).

### Focused Agents

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **go-builder** | Go/Templ compilation, testing, or generation when needed | Runs commands safely inside Docker |
| **css-reviewer** | CSS or HTML changes that need a Live Wires review | Checks cascade layers, naming, and tokens |
| **doc-sync** | Behavior, structure, configuration, or operating-instruction changes with unclear documentation impact | Checks relevant documentation |
| **security-auditor** | Auth, authorization, credentials, input, data handling, or destructive changes | Reviews real security boundaries |

Use the applicable accessibility reviewers for frontend changes. Agents are focused tools, not a required roster after every edit.

### Git Discipline
- Commit a coherent, verified change with a focused message; do not use file-count thresholds.
- Push when the branch is ready or sharing/recovery benefits from it; do not treat an ordinary source-branch push as publication.
- Use a feature branch or worktree when isolation, collaboration, or task risk warrants it.

### Work Notes
- Use `tasks/todo.md` only when a multi-step workboard or handoff is useful.
- Follow the repository's documented release checks for publication; publication is separate from ordinary source work.

## Critical Rules

### Docker-Only Go
**NEVER run Go commands directly on the host.** Always `docker compose exec app`. Enforced by `block-bare-go.sh` hook.

### Documentation Sync
When behavior or operating instructions change, update the relevant documentation. Use the `doc-sync` agent when the impact is non-obvious; it is not required after every code change.

### [ADD PROJECT-SPECIFIC RULES HERE]
<!-- e.g., naming conventions, module architecture rules, deployment constraints -->

## Architecture Overview

### Directory Structure
```
<!-- FILL IN: project directory tree -->
```

### [ADD ARCHITECTURE SECTIONS]
<!-- e.g., backend stack, frontend stack, database, deployment -->

### ScopedDB / ScopedNATS

Fixtures access the database exclusively through `ScopedDB` (table-prefix isolation) and NATS through `ScopedEventBus` (subject-prefix isolation). Never use raw `*sql.DB` or `nats.Conn` in fixture code.

### Module Interface

Fixtures implement the `Module` interface (`ID()`, `Name()`, `SetupRoutes()`, `Migrations()`), register via `init()`, and are included via blank imports. See `cmd/api/imports.go`.

### NATS Patterns

- Embedded NATS with `DontListen: true` (no external TCP)
- Subject hierarchy: `assembly.{scope}.{entity}.{event}`
- Events publish AFTER `db.WithTx()` commit, never inside transaction
- KV Watch for SSE real-time updates

### Federation

- HTTPS required for all federation endpoints in production
- Link tokens: 5-minute TTL, single-use nonce, audience validation
- `return_url` validated with exact host match

### Architecture Decision Records

Check `docs/adr/` for architectural decisions. Key ADRs:
- ADR-002: Production architecture philosophy
- ADR-003: SQLite + NATS dual-store
- ADR-004: Authorization pattern
- ADR-005: Install flow
- ADR-006: Member identity and federation
- ADR-007: NATS event patterns

## Build Commands

```bash
# Frontend
npm run dev           # Dev server
npm run build         # Production build

# Backend (always via Docker)
docker compose exec app templ generate
docker compose exec app go build -o bin/app ./cmd/api
docker compose restart app
docker compose exec app go test ./...

# Tests with race detection
docker compose exec app go test -race ./...

# Dev environment
docker compose up     # Start with hot reload
```

## Documentation Sync Checklist

When behavior or operating instructions change, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Any skill files (flag changes for depot, don't edit directly)
- [ ] API documentation
- [ ] Manual/docs pages

## Recommended Plugins

Install these plugins from the Design Machines depot for enhanced development:

| Plugin | Purpose |
|--------|---------|
| **superpowers** | TDD, debugging, verification workflows |
| **compound-engineering** | go-build-verifier, css-reviewer, security-sentinel agents |
| **context7** | Live documentation for Go, Templ, Datastar |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **hookify** | Create custom hooks for project-specific workflows |
| **claude-md-management** | Keep CLAUDE.md current as the project evolves |

## Serena Configuration

Create `.serena/project.yml` for semantic code intelligence:

```yaml
# {{PROJECT_NAME}} - Go/Templ/Datastar
ignored_paths:
  - node_modules
  - _dev
  - "*.min.js"
  - "*.min.css"
```

Add `.serena` to `.gitignore`. Register the project path in `~/.serena/serena_config.yml`.
```

### go-library

```markdown
# CLAUDE.md

This file is the routing document for Claude Code.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does]. A Go module library.

## Workflow Orchestration

### Workflow Selection
- Choose the lightest workflow that fits the task. For a small documentation, configuration, or bounded content edit, inspect the affected files, make the change, and run focused checks; plan mode and agents are optional.
- Use plan mode when a task is multi-step, architectural, cross-cutting, or higher risk and a written sequence clarifies the acceptance criteria.
- Keep focused agents available as tools. Use the go-builder and documentation agents when their checks apply; none is required after every edit.
- Update documentation when behavior, commands, configuration, file structure, or operating instructions change. Use doc-sync when the impact is non-obvious, not as a post-edit ritual.
- Record a lesson only when a finding is reusable beyond this task. Do not create routine lesson entries or a lessons store just to complete a workflow.
- Preserve repository-owned command restrictions and real checks for credentials, authentication/authorization, destructive or data-loss actions, release integrity, and applicable accessibility.
- When delegating, request only a role, required capabilities, and normalized effort (`low`, `medium`, `high`, or `max`). Keep concrete model and rail recommendations in operator context; see the [current model-router guidance](https://github.com/Design-Machines-Studio/depot/blob/main/plugins/model-router/skills/model-router/references/driver-worker-guidance.md).

### Focused Agents

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **doc-sync** | Behavior, structure, configuration, or operating-instruction changes with unclear documentation impact | Checks relevant documentation |

Use the go-builder for Go verification when the project provides a Docker workflow. Agents are focused tools, not a required roster after every edit.

### Git Discipline
- Commit a coherent, verified change with a focused message; do not use file-count thresholds.
- Push when the branch is ready or sharing/recovery benefits from it; do not treat an ordinary source-branch push as publication.
- Use a feature branch or worktree when isolation, collaboration, or task risk warrants it.

### Work Notes
- Use `tasks/todo.md` only when a multi-step workboard or handoff is useful.
- Follow the repository's documented release checks for publication; publication is separate from ordinary source work.

## Critical Rules

### [ADD PROJECT-SPECIFIC RULES HERE]

## Architecture Overview

### Directory Structure
```
<!-- FILL IN -->
```

## Build & Test Commands

```bash
go build ./...
go test ./...
go vet ./...
```

## Documentation Sync Checklist

When behavior or operating instructions change, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Go doc comments
- [ ] Examples in _test.go files

## Recommended Plugins

| Plugin | Purpose |
|--------|---------|
| **superpowers** | TDD, debugging, verification workflows |
| **context7** | Live documentation for Go standard library |
| **live-wires** | CSS framework (if project includes web UI) |
| **hookify** | Create custom hooks for project-specific workflows |
| **claude-md-management** | Keep CLAUDE.md current as the project evolves |

## Serena Configuration

Create `.serena/project.yml` for semantic code intelligence:

```yaml
# {{PROJECT_NAME}} - Go Library
ignored_paths:
  - _dev
  - vendor
```

Add `.serena` to `.gitignore`. Register the project path in `~/.serena/serena_config.yml`.
```

### css-framework

```markdown
# CLAUDE.md

This file is the routing document for Claude Code.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does]. A CSS framework/design system.

## Workflow Orchestration

### Workflow Selection
- Choose the lightest workflow that fits the task. For a small documentation, configuration, or bounded content edit, inspect the affected files, make the change, and run focused checks; plan mode and agents are optional.
- Use plan mode when a task is multi-step, architectural, cross-cutting, or higher risk and a written sequence clarifies the acceptance criteria.
- Keep focused agents available as tools. Use the CSS, documentation, and accessibility agents when their checks apply; none is required after every edit.
- Update documentation when behavior, commands, configuration, file structure, or operating instructions change. Use doc-sync when the impact is non-obvious, not as a post-edit ritual.
- Record a lesson only when a finding is reusable beyond this task. Do not create routine lesson entries or a lessons store just to complete a workflow.
- Preserve repository-owned command restrictions and real checks for credentials, authentication/authorization, destructive or data-loss actions, release integrity, and applicable accessibility.
- When delegating, request only a role, required capabilities, and normalized effort (`low`, `medium`, `high`, or `max`). Keep concrete model and rail recommendations in operator context; see the [current model-router guidance](https://github.com/Design-Machines-Studio/depot/blob/main/plugins/model-router/skills/model-router/references/driver-worker-guidance.md).

### Focused Agents

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **css-reviewer** | CSS changes that need a Live Wires review | Enforces naming conventions, layers, and token usage |
| **doc-sync** | Behavior, structure, configuration, or operating-instruction changes with unclear documentation impact | Checks relevant documentation |

Use the accessibility reviewers when a frontend change affects semantics, visual accessibility, or dynamic interaction. Agents are focused tools, not a required roster after every edit.

### Git Discipline
- Commit a coherent, verified change with a focused message; do not use file-count thresholds.
- Push when the branch is ready or sharing/recovery benefits from it; do not treat an ordinary source-branch push as publication.
- Use a feature branch or worktree when isolation, collaboration, or task risk warrants it.

### Work Notes
- Use `tasks/todo.md` only when a multi-step workboard or handoff is useful.
- Follow the repository's documented release checks for publication; publication is separate from ordinary source work.

## Critical Rules

### Cascade Layer Order
```css
@layer tokens, reset, base, layouts, components, utilities;
```

### Naming Conventions
- **Layout modifiers**: single-dash (`stack-compact`, `box-tight`)
- **Component modifiers**: double-dash (`button--accent`, `table--bordered`)

### Token-Based Spacing
All spacing derives from the foundational unit. Use tokens -- never arbitrary pixel values.

### [ADD PROJECT-SPECIFIC RULES HERE]

## Architecture Overview

### Directory Structure
```
<!-- FILL IN: ITCSS layers, source structure -->
```

## Build Commands

```bash
npm run dev    # Dev server with HMR
npm run build  # Production build
```

## Documentation Sync Checklist

When behavior or operating instructions change, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Documentation site pages
- [ ] Component examples

## Recommended Plugins

| Plugin | Purpose |
|--------|---------|
| **superpowers** | TDD, debugging, verification workflows |
| **compound-engineering** | css-reviewer for automated compliance checking |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **figma** | Extract design tokens and specs from Figma |
| **frontend-design** | UI/UX implementation guidance |
| **hookify** | Create custom hooks for project-specific workflows |

## Serena Configuration

Create `.serena/project.yml` for semantic code intelligence:

```yaml
# {{PROJECT_NAME}} - CSS Framework
ignored_paths:
  - node_modules
  - _dev
  - bower_components
  - dist
```

Add `.serena` to `.gitignore`. Register the project path in `~/.serena/serena_config.yml`.
```

### craft-cms

```markdown
# CLAUDE.md

This file is the routing document for Claude Code.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does]. Built with Craft CMS 5, Twig templates, and DDEV.

- **Local:** {{PROJECT_URL_LOCAL}}
- **Production:** {{PROJECT_URL_PROD}}

## Existing Development Site

- Project code: [verified project code]
- Review domain: [established project-code.asmbly.app mapping]
- Serving checkout: [verified absolute checkout and canonical remote]
- Source binding: [how status/build evidence identifies the served source]
- Status command: [existing exact command]
- Rebuild/restart: [existing exact command or directly linked runbook]

Use ordinary Git in the clean, available serving checkout to select the feature
branch, or its exact detached commit when that branch is already checked out
elsewhere. Preserve owned edits and fingerprint them for in-place review; name
unrelated dirty or concurrent ownership collisions. Rebuild before claiming the
new source is served. Keep the same domain, service, data and configuration.
Check incompatible migrations before maintenance; never reset shared data.
Leave the maintained instance available. Isolated browser environments need a
concrete test requirement; ordinary unit-test containers remain valid.

For Assembly counterparts, inspect exact prototype templates, rendered HTML,
Live Wires classes/components and Datastar save behavior before implementation.
Use existing prototype UX tasks/personas through dm-review's
`ui-case-selection.md`; compare paired interactions and reload/revisit evidence.

## Workflow Orchestration

### Workflow Selection
- Choose the lightest workflow that fits the task. For a small documentation, configuration, or bounded content edit, inspect the affected files, make the change, and run focused checks; plan mode and agents are optional.
- Use plan mode when a task is multi-step, architectural, cross-cutting, or higher risk and a written sequence clarifies the acceptance criteria.
- Keep focused agents available as tools. Use the documentation, security, and accessibility agents when their checks apply; none is required after every edit.
- Update documentation when behavior, commands, configuration, file structure, or operating instructions change. Use doc-sync when the impact is non-obvious, not as a post-edit ritual.
- Record a lesson only when a finding is reusable beyond this task. Do not create routine lesson entries or a lessons store just to complete a workflow.
- Preserve repository-owned DDEV restrictions and real checks for credentials, authentication/authorization, destructive or data-loss actions, release integrity, and applicable accessibility.
- When delegating, request only a role, required capabilities, and normalized effort (`low`, `medium`, `high`, or `max`). Keep concrete model and rail recommendations in operator context; see the [current model-router guidance](https://github.com/Design-Machines-Studio/depot/blob/main/plugins/model-router/skills/model-router/references/driver-worker-guidance.md).

### Focused Agents

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **doc-sync** | Behavior, structure, configuration, or operating-instruction changes with unclear documentation impact | Checks relevant documentation |
| **security-auditor** | Auth, authorization, credentials, input, data handling, or destructive changes | Reviews real security boundaries |

Use the accessibility reviewers when a frontend change affects semantics or visual accessibility. Agents are focused tools, not a required roster after every edit.

### Git Discipline
- Commit a coherent, verified change with a focused message; do not use file-count thresholds.
- Push when the branch is ready or sharing/recovery benefits from it; do not treat an ordinary source-branch push as publication.
- Use a feature branch or worktree when isolation, collaboration, or task risk warrants it.

### Work Notes
- Use `tasks/todo.md` only when a multi-step workboard or handoff is useful.
- Follow the repository's documented release checks for publication; publication is separate from ordinary source work.

## Critical Rules

### DDEV-Only Craft Commands
**NEVER run Craft or Composer commands directly.** Always use `ddev craft` and `ddev composer`.

### [ADD PROJECT-SPECIFIC RULES HERE]

## Architecture Overview

### Directory Structure
```
<!-- FILL IN -->
```

### Craft CMS Stack
- **CMS:** Craft 5
- **Templates:** Twig (in `templates/`)
- **Plugins:** [LIST PLUGINS]
- **Local dev:** DDEV

## Build Commands

```bash
# Craft commands (always via DDEV)
ddev craft migrate/all
ddev craft project-config/apply
ddev craft clear-caches/all
ddev composer install

# Frontend
npm run dev
npm run build
```

## Documentation Sync Checklist

When behavior or operating instructions change, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Template documentation
- [ ] Plugin/module documentation

## Recommended Plugins

| Plugin | Purpose |
|--------|---------|
| **superpowers** | TDD, debugging, verification workflows |
| **context7** | Live documentation for Craft CMS, Twig, Yii2 |
| **live-wires** | CSS framework with layout primitives and baseline rhythm |
| **figma** | Extract design specs when building templates |
| **hookify** | Create custom hooks for project-specific workflows |
| **claude-md-management** | Keep CLAUDE.md current as the project evolves |

## Serena Configuration

Create `.serena/project.yml` for semantic code intelligence:

```yaml
# {{PROJECT_NAME}} - Craft CMS
ignored_paths:
  - vendor
  - storage
  - .ddev
  - web/cpresources
  - node_modules
```

Add `.serena` to `.gitignore`. Register the project path in `~/.serena/serena_config.yml`.
```

---

## Starter Files

### tasks/todo.md

```markdown
# Tasks

## Current Sprint
<!-- Active tasks go here -->

## Backlog
<!-- Future tasks -->

## Done
<!-- Completed tasks (move here when done) -->
```

### Optional tasks/lessons.md

```markdown
# Lessons Learned

Optional notes for reusable project-specific patterns and corrections. Create this file only when the project benefits from keeping such findings between sessions; routine corrections do not belong here.

## Conventions
<!-- Project conventions discovered during work -->

## Mistakes to Avoid
<!-- Errors and their corrections -- write rules to prevent repeats -->

## Gotchas
<!-- Non-obvious behaviors, edge cases, workarounds -->
```

### memory/sessions.md

```markdown
# Session Log

Optional append-only repository-local log for continuity between sessions. It does not require an external planning service.

<!-- Format:
## YYYY-MM-DD -- Brief description
**Sprint:** Sprint name
**Done:** Bullets
**Pending:** Bullets
**Learned:** Gotchas and notes
-->
```
