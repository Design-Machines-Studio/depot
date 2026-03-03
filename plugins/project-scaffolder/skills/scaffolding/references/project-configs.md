# Project Configuration Templates

settings.json, CLAUDE.md, and starter files for each project type. Replace all `{{PLACEHOLDER}}` values before writing.

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
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-start-gate.sh",
            "statusMessage": "Checking session workflow..."
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

**Without session-start-gate** (remove the Edit|Write PreToolUse entry):

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

### go-library (no Docker gate, no session gate)

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

### css-framework (no Docker gate, no session gate)

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

**Note:** `block-bare-craft.sh` is a variant of `block-bare-go.sh` that blocks bare `php craft` and `composer` commands, requiring `ddev craft` and `ddev composer` instead. Create it by adapting the go hook pattern.

---

## CLAUDE.md Templates

### go-templ-datastar

```markdown
# CLAUDE.md

This file is the routing document for Claude Code. Critical rules live here; detailed reference lives in skills.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does, who it's for]. Built with Go (Templ + Chi), SQLite, Datastar, and the Live Wires CSS framework. Runs in Docker.

- **Local:** {{PROJECT_URL_LOCAL}}
- **Production:** {{PROJECT_URL_PROD}}

## Session Workflow (Planner Skill)

> Remove this section if not using session-start-gate.sh

At the **start of every session**, read the planner skill and follow its session start workflow.

**The `session-start-gate` hook BLOCKS all Edit/Write calls until this workflow completes.**

Planner skill: Invoke `/planner` (installed from the depot's project-manager plugin).

Key files:
- `memory/project-notion.md` — maps this repo to the Notion project
- `memory/sessions.md` — append-only session log

After completing: `touch /tmp/{{PROJECT_PREFIX}}-session-$(date +%Y-%m-%d)`

## Workflow Orchestration

### Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately

### Agent Delegation

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **go-builder** | Any Go/Templ compilation, testing, or generation | Runs commands safely inside Docker |
| **css-reviewer** | After any CSS or HTML template change | Enforces Live Wires compliance |
| **doc-sync** | After ANY code change | Checks documentation freshness |
| **security-auditor** | Before committing auth or data-handling code | Reviews for OWASP vulnerabilities |

### Self-Improvement Loop
- After ANY correction: update `tasks/lessons.md`
- Write rules that prevent the same mistake
- Review lessons at session start

### Git Discipline
- **Commit early and often.** Target 1-4 files per commit.
- **Push after every 2 commits.**
- **Feature branches** for work touching 3+ files.
- **The commit-push-reminder hook insists at 3+ files.** Obey immediately.

### Task Management
1. Plan first → `tasks/todo.md`
2. Track progress: mark items complete as you go
3. Capture lessons → `tasks/lessons.md`

## Critical Rules

### Docker-Only Go
**NEVER run Go commands directly on the host.** Always `docker compose exec app`. Enforced by `block-bare-go.sh` hook.

### Documentation Sync
After code changes, run the `doc-sync` agent. Checks CLAUDE.md, README.md, and related docs.

### [ADD PROJECT-SPECIFIC RULES HERE]
<!-- e.g., naming conventions, module architecture rules, deployment constraints -->

## Architecture Overview

### Directory Structure
```
<!-- FILL IN: project directory tree -->
```

### [ADD ARCHITECTURE SECTIONS]
<!-- e.g., backend stack, frontend stack, database, deployment -->

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

# Dev environment
docker compose up     # Start with hot reload
```

## Documentation Sync Checklist

After modifying code, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Any skill files (flag changes for depot, don't edit directly)
- [ ] API documentation
- [ ] Manual/docs pages
```

### go-library

```markdown
# CLAUDE.md

This file is the routing document for Claude Code.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does]. A Go module library.

## Workflow Orchestration

### Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps)

### Agent Delegation

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **doc-sync** | After ANY code change | Checks documentation freshness |

### Git Discipline
- Commit early and often. Target 1-4 files per commit.
- Push after every 2 commits.
- Feature branches for work touching 3+ files.

### Task Management
1. Plan first → `tasks/todo.md`
2. Track progress: mark items complete as you go
3. Capture lessons → `tasks/lessons.md`

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

After modifying code, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Go doc comments
- [ ] Examples in _test.go files
```

### css-framework

```markdown
# CLAUDE.md

This file is the routing document for Claude Code.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does]. A CSS framework/design system.

## Workflow Orchestration

### Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps)

### Agent Delegation

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **css-reviewer** | After any CSS change | Enforces naming conventions, layers, token usage |
| **doc-sync** | After ANY code change | Checks documentation freshness |

### Git Discipline
- Commit early and often. Target 1-4 files per commit.
- Push after every 2 commits.
- Feature branches for work touching 3+ files.

### Task Management
1. Plan first → `tasks/todo.md`
2. Track progress: mark items complete as you go
3. Capture lessons → `tasks/lessons.md`

## Critical Rules

### Cascade Layer Order
```css
@layer tokens, reset, base, layouts, components, utilities;
```

### Naming Conventions
- **Layout modifiers**: single-dash (`stack-compact`, `box-tight`)
- **Component modifiers**: double-dash (`button--accent`, `table--bordered`)

### Token-Based Spacing
All spacing derives from the foundational unit. Use tokens — never arbitrary pixel values.

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

After modifying code, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Documentation site pages
- [ ] Component examples
```

### craft-cms

```markdown
# CLAUDE.md

This file is the routing document for Claude Code.

## Project Identity

**{{PROJECT_NAME}}** is [DESCRIBE: what it does]. Built with Craft CMS 5, Twig templates, and DDEV.

- **Local:** {{PROJECT_URL_LOCAL}}
- **Production:** {{PROJECT_URL_PROD}}

## Workflow Orchestration

### Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps)

### Agent Delegation

| Agent | Trigger | What it does |
|-------|---------|-------------|
| **doc-sync** | After ANY code change | Checks documentation freshness |
| **security-auditor** | Before committing auth or data-handling code | Reviews for vulnerabilities |

### Git Discipline
- Commit early and often. Target 1-4 files per commit.
- Push after every 2 commits.
- Feature branches for work touching 3+ files.

### Task Management
1. Plan first → `tasks/todo.md`
2. Track progress: mark items complete as you go
3. Capture lessons → `tasks/lessons.md`

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

After modifying code, check if updates are needed in:
- [ ] CLAUDE.md (this file)
- [ ] README.md
- [ ] Template documentation
- [ ] Plugin/module documentation
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

### tasks/lessons.md

```markdown
# Lessons Learned

Patterns and corrections from development sessions. Review at session start.

## Conventions
<!-- Project conventions discovered during work -->

## Mistakes to Avoid
<!-- Errors and their corrections — write rules to prevent repeats -->

## Gotchas
<!-- Non-obvious behaviors, edge cases, workarounds -->
```

### memory/project-notion.md (for projects using the planner)

```markdown
# Notion Project Config

- **Project:** [Project Name](NOTION_PROJECT_URL)
- **Default Role:** Production
- **Notes:** [Context for time entries]
```

### memory/sessions.md (for projects using the planner)

```markdown
# Session Log

Append-only log for continuity between sessions.

<!-- Format:
## YYYY-MM-DD — Brief description
**Duration:** Days worked
**Sprint:** Sprint name
**Done:** Bullets
**Pending:** Bullets
**Learned:** Gotchas and notes
-->
```
