# Design Spec: Notion Workflow Integration

**Status:** Historical design; explicit personal/client planning only
**Plugin:** project-manager
**Date:** 2026-02-13

---

## Problem

Travis uses Notion for explicitly requested personal and client planning. Repository development coordination now lives in GitHub Issues, pull requests, and Assembly Coordination Project 1; ordinary coding sessions do not invoke this workflow.

## Goals

1. **Time tracking** -- Claude logs session time to Notion only when Travis explicitly requests it
2. **Sprint awareness** -- Claude knows what's in the current sprint across all projects
3. **Todo visibility** -- Claude can see assigned tasks and update their status when done
4. **Context continuity** -- Claude maintains robust internal memory across sessions without polluting Notion
5. **Minimal Notion writes** -- Claude reads freely but only writes time entries and status updates. Never creates todos unsolicited.

## Non-Goals

- Replacing Notion as the planning tool (Travis plans, Claude executes)
- Automating sprint planning (Claude assists, Travis decides)
- Syncing GitHub issues to Notion (Userback handles bug tracking)

---

## Architecture

### Three layers

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Plugin Skill (notion-workspace)            │
│  Universal Notion knowledge -- schemas, rules,        │
│  workflows. Lives in project-manager plugin.         │
│  Loaded by any project that installs the plugin.     │
├─────────────────────────────────────────────────────┤
│  Layer 2: Agent (time-tracker)                       │
│  Lightweight agent for creating/updating time        │
│  entries. Called only when explicitly requested.      │
├─────────────────────────────────────────────────────┤
│  Layer 3: Per-Project Memory                         │
│  Maps this codebase to a Notion project.             │
│  Stores Claude's session log for continuity.         │
│  Lives in Claude's memory directory, not in repo.    │
└─────────────────────────────────────────────────────┘
```

### Why memory files, not CLAUDE.md, for per-project config

CLAUDE.md is version-controlled and shared across all instances of a codebase. Assembly will become a template app -- each co-op gets the same repo but maps to a different Notion project. Memory files are per-machine, per-directory-path, making them the right place for instance-specific config.

---

## Database Reference

Travis's Notion workspace has four interconnected databases. These are **personal databases shared across all projects**, not project-specific.

### Projects Database

- **Data source ID:** Look up from `DM Notion Workspace` entity in ai-memory
- **Title property:** `Name`
- **Key properties:**

| Property | Type | Values/Notes |
|----------|------|-------------|
| Name | title | Project name |
| Status | status | Not started, In progress, No go, Done |
| Area | select | WORKS, COMPANY, FLOOR, PLATE, PRESS |
| Client | relation | -> Clients DB |
| Team | person | Assigned people |
| Project code | text | e.g., DM-006/WORKS |
| Start Date | date | Project start |
| End Date | date | Project end |
| Todos | relation | -> Todos DB |
| Notes | relation | -> Notes DB |

### Todos Database

- **Data source ID:** Look up from `DM Notion Workspace` entity in ai-memory
- **Title property:** `Name`
- **Key properties:**

| Property | Type | Values/Notes |
|----------|------|-------------|
| Name | title | Task name |
| Status | status | Someday maybe, Inbox, In progress, Waiting on, Blocked, Done |
| Priority | select | Low, Medium, High |
| Project | relation | -> Projects DB |
| Sprint | relation | -> Sprints DB (limit 1) |
| Person | person | Assigned to |
| Deadline | date | Due date |
| Blocked by | relation | -> self (Todos DB) |
| Blocking | relation | -> self (Todos DB) |
| Notes | relation | -> Notes DB |

**Views:** This sprint (board), Quarter plan (board), Yearly plan (board), By project (board)

### Time Tracking Database

- **Data source ID:** Look up from `DM Notion Workspace` entity in ai-memory
- **Title property:** `Entry`
- **Key properties:**

| Property | Type | Values/Notes |
|----------|------|-------------|
| Entry | title | Description of work done |
| Days | number (float) | Quarter-day blocks: 0.25 (~2hrs), 0.5 (~4hrs), 0.75 (~6hrs), 1.0 (full day) |
| Date | date | Date of work |
| Role | select | Project Management, Research, Strategy, Production |
| Project | relation | -> Projects DB |
| Sprint | relation | -> Sprints DB (limit 1) |

### Sprints Database

- **Data source ID:** Look up from `DM Notion Workspace` entity in ai-memory
- **Title property:** `Name`
- **Key properties:**

| Property | Type | Values/Notes |
|----------|------|-------------|
| Name | title | e.g., "Sprint 3" |
| Dates | date (range) | Start -> End |
| Quarter | relation | -> Quarters DB |
| Status | status | Not started, In progress, Done |
| Time entries | relation | -> Time Tracking DB |
| Todos | relation | -> Todos DB |

**Cadence:** Biweekly sprints.

---

## Relation Formatting

When setting relations via `notion-update-page`, use bare URL strings:

```
"Project": "https://www.notion.so/{page-id}"
```

Do NOT wrap in JSON arrays -- the API rejects `["url"]` syntax.

When creating pages via `notion-create-pages`, relations cannot be set inline. Create the page first, then update with relations in a second call.

---

## Deliverable 1: `notion-workspace` Skill

**Location:** `depot/plugins/project-manager/skills/notion-workspace/SKILL.md`

### Skill responsibilities

1. **Teach Claude the database schemas** -- property names, types, valid values
2. **Define read/write rules** -- what Claude can read, what it can write, and when
3. **Explicit planning workflow** -- what to do during a requested Notion planning session
4. **Sprint planning support** -- how to help Travis plan sprints
5. **Per-project config convention** -- how to find and use the project mapping

### Read/write rules (CRITICAL)

| Action | Permission | When |
|--------|-----------|------|
| Query any database | Always allowed | Anytime Claude needs context |
| Create time entry | Only when Travis asks | Explicit time-tracking request |
| Update time entry Days | Only when Travis asks | Explicit time-tracking request |
| Update todo status to "In progress" | Auto | When Claude starts working on an assigned todo |
| Update todo status to "Done" | Auto | When Claude finishes an assigned todo |
| Create new todo | Only when Travis explicitly asks | "Add a todo for X" |
| Update todo name/priority/sprint | Only when Travis explicitly asks | "Move this to Sprint 5" |
| Modify project properties | Never | Travis-only |
| Modify sprint properties | Never | Travis-only |

### Explicit Notion planning workflow

This workflow is not part of ordinary coding-session startup or shutdown. When Travis explicitly requests Notion planning:

**Start of planning:**
1. Read `memory/project-notion.md` to get project URL and default role
2. Query Sprints DB for the sprint with Status = "In progress"
3. Query Todos DB for todos assigned to this project in the current sprint
4. Read `memory/sessions.md` for context from previous planning sessions

**End of planning:**
1. Update any todo statuses that changed during the requested planning workflow
2. Append a planning summary to `memory/sessions.md` when useful

### Sprint planning support

When Travis asks for sprint planning help:
1. Query all active projects (Status = "In progress")
2. Query todos with Status not in ("Done", "Someday maybe") grouped by project
3. Show current sprint status (what's done, what's still open)
4. Suggest candidates for next sprint based on priority and blocking relationships
5. Travis decides -- Claude does not assign things to sprints

### Per-project config convention

Each project that uses this skill needs a memory file at:

```
memory/project-notion.md
```

Format:

```markdown
# Notion Project Config

- **Project:** [Project Name](https://www.notion.so/{page-id})
- **Default Role:** Production
- **Notes:** Any project-specific context for time entry descriptions
```

This file is created once per project, manually or with Claude's help.

### Reference files

- `references/databases.md` -- Full database schemas (the tables from above)
- `references/conventions.md` -- Relation formatting, API quirks, error handling

---

## Deliverable 2: `time-tracker` Agent

**Location:** `depot/plugins/project-manager/agents/workflow/time-tracker.md`

### Agent behavior

**Trigger:** Use only when Travis explicitly asks to log time.

**Model:** haiku (fast, lightweight)

**Inputs:**
- Reads `memory/project-notion.md` for project URL and role
- Reads current sprint from Sprints DB
- Takes a description and duration from the calling session

**Actions:**
1. Creates a time entry in the Time Tracking DB
2. Links it to the correct Project and Sprint
3. Returns the entry URL for reference

**Agent structure:**

```markdown
---
name: time-tracker
description: Logs time entries to Notion when Travis explicitly asks. Reads
  project config from memory/project-notion.md.
---

You are a time tracking agent. You create and update time entries in Travis's
Notion Time Tracking database.

## Steps

1. Read `memory/project-notion.md` for the project URL and default role
2. If no config exists, ask the user to set one up
3. Query the Sprints database for the sprint with Status = "In progress"
4. Create or update the time entry with the provided details
5. Link the entry to the project and current sprint

## Database details
[Include Time Tracking schema from databases.md]

## Rules
- Days are quarter-day blocks: 0.25, 0.5, 0.75, 1.0
- Default role comes from project config, but can be overridden
- Entry descriptions should be concise but specific
- Always link to both Project and Sprint
```

---

## Deliverable 3: Session Memory Convention

**Not a plugin file** -- this is a convention documented in the skill.

### `memory/sessions.md`

Append-only log. Claude writes a brief summary at the end of each session:

```markdown
## 2026-02-13 -- Workflow planning

**Duration:** 0.25 days
**Sprint:** Sprint 3

**Done:**
- Explored Notion database schemas
- Set up time tracking integration
- Designed project-manager plugin additions

**Pending:**
- Implement notion-workspace skill in depot
- Create time-tracker agent
- Set up per-project configs for other projects

**Learned:**
- Notion relations must be set via update, not create
- Use bare URL strings for relation values, not JSON arrays
```

### `memory/project-notion.md`

Created once per project. Example for Assembly:

```markdown
# Notion Project Config

- **Project:** [Assembly Alpha](https://www.notion.so/{project-page-id})
- **Default Role:** Production
- **Notes:** Co-op governance prototype. Project code DM-006/WORKS.
```

---

## Implementation Plan

### Phase 1: Skill + Agent (do first)
1. Create `depot/plugins/project-manager/skills/notion-workspace/SKILL.md`
2. Create `depot/plugins/project-manager/skills/notion-workspace/references/databases.md`
3. Create `depot/plugins/project-manager/skills/notion-workspace/references/conventions.md`
4. Create `depot/plugins/project-manager/agents/workflow/time-tracker.md`
5. Update `depot/plugins/project-manager/.claude-plugin/plugin.json` description

### Phase 2: Per-project setup
6. Create `memory/project-notion.md` for Assembly
7. Create `memory/sessions.md` for Assembly (initial entry)
8. Retire `tasks/todo.md` as planning document (keep as archive)
9. Update Assembly's `memory/MEMORY.md` to reference the new convention

### Phase 3: Roll out to other projects
10. Install project-manager plugin in other project repos
11. Create `memory/project-notion.md` for each project
12. Test time tracking and sprint awareness across projects

---

## Open Questions

1. **Sprint planning as a skill or workflow?** Could be a `/lt10:sprint-plan` command that queries across projects. Needs design.
2. **Session start/end automation?** Currently manual ("log my time"). Could eventually be triggered by hooks.
3. **Multi-person future?** When Travis adds collaborators, the Person field on todos and time entries becomes important. Current design assumes solo.
4. **Userback integration?** Bug tracking flows through Userback -> GitHub/Notion. Does Claude need to interact with Userback, or is it purely Travis's tool?
