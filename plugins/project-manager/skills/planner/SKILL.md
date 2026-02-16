---
name: planner
description: Notion-integrated project planning, time tracking, and sprint management. Use at the start and end of every coding session, when working on assigned todos, when Travis asks for sprint planning help, or when logging time. Reads project config from memory/project-notion.md. Teaches Claude the Notion database schemas, read/write permissions, and session workflow conventions.
---

# Planner — Notion Workflow Integration

Travis plans work in Notion (Projects, Todos, Sprints, Time Tracking). This skill gives Claude the knowledge to participate in that workflow — reading context, tracking time, updating task status, and assisting with sprint planning.

**Philosophy:** Travis plans, Claude executes. Read freely, write carefully.

## Quick Reference

### Database IDs

Look up all database data source IDs from the `DM Notion Workspace` entity in ai-memory. The entity stores IDs for Projects, Todos, Time Tracking, Sprints, and Notes databases.

### Read/Write Permissions (CRITICAL)

| Action | Permission | When |
|--------|-----------|------|
| Query any database | ✅ Always | Anytime context is needed |
| Create time entry | ✅ Auto | Session start |
| Update time entry (Days, Entry) | ✅ Auto | Session end |
| Update todo → "In progress" | ✅ Auto | When starting an assigned todo |
| Update todo → "Done" | ✅ Auto | When finishing an assigned todo |
| Create new todo | ⚠️ Only when Travis asks | "Add a todo for X" |
| Update todo name/priority/sprint | ⚠️ Only when Travis asks | "Move this to Sprint 5" |
| Modify project properties | ❌ Never | Travis-only |
| Modify sprint properties | ❌ Never | Travis-only |


## Session Workflow

### At Session Start

1. **Read project config:** Check `memory/project-notion.md` for the Notion project URL and default role. If missing, ask Travis to set one up.

2. **Find active sprint:** Query Sprints DB for the sprint with Status = "In progress". Note the sprint name and date range.

3. **Load assigned todos:** Query Todos DB for todos linked to this project in the current sprint where Status is NOT "Done" or "Someday maybe". These are the candidates for this session.

4. **Create time entry:** Use the `time-tracker` agent or create directly:
   - Entry: "TBD" (updated at session end)
   - Days: 0.25 (default, updated at session end)
   - Date: today
   - Role: from project config
   - Link to Project and Sprint

5. **Read previous session:** Check `memory/sessions.md` for the last entry. Note what was done, what's pending, and anything learned.

6. **Brief Travis:** Share a concise summary: "Sprint 3 ends Feb 13. You have 4 open todos. Last session you worked on X. What should we focus on?"

### During Session

- When starting work on an assigned todo, update its Status to "In progress"
- When finishing a todo, update its Status to "Done"
- Track what you're doing — you'll need it for the time entry description

### At Session End

1. **Update time entry:** Set the Entry description (concise but specific) and Days worked:
   - 0.25 = ~2 hours
   - 0.50 = ~4 hours (half day)
   - 0.75 = ~6 hours
   - 1.00 = full day

2. **Update todo statuses:** Any todos that changed during the session

3. **Append to sessions.md:** Write a brief session summary (see Session Memory Convention below)


## Sprint Planning Support

Sprint planning happens **Monday mornings** in **Claude Desktop** (claude.ai), not in Claude Code. Sprints are biweekly.

When Travis asks for sprint planning help:

1. **Query all active projects:** Search Projects DB for Status = "In progress". Show project names and codes.

2. **Review current sprint:** What's done? What's still open? What rolled over from last sprint?

3. **Show open todos by project:** Query Todos DB for items with Status NOT in ("Done", "Someday maybe"), grouped by project. Include priority and blocking relationships.

4. **Suggest candidates for next sprint** based on:
   - Priority (High first)
   - Blocking relationships (unblock before blocked)
   - Sprint capacity (don't overfill — think in quarter-days)
   - Balance across projects (not all eggs in one basket)

5. **Travis decides.** Claude does not assign things to sprints. Present options, Travis picks.

### Sprint Cadence

- Biweekly sprints
- Sprint planning: Monday morning of sprint start
- Sprint review: last day of sprint (check what got done)
- Quarter planning: first sprint of each quarter

## Per-Project Config

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

This file is:
- Created once per project (manually or with Claude's help)
- NOT version-controlled (lives in Claude's memory directory)
- Instance-specific — when Assembly becomes a template, each co-op maps to a different Notion project


## Session Memory Convention

### `memory/sessions.md`

Append-only log. Claude writes a brief summary at the end of each session:

```markdown
## 2026-02-13 — [Brief description]

**Duration:** 0.25 days
**Sprint:** Sprint 3

**Done:**
- Bullet points of completed work

**Pending:**
- What's still in progress or deferred

**Learned:**
- Gotchas, discoveries, technical notes for next session
```

Keep entries concise. This is for Claude's continuity, not a detailed report. 5-10 lines max per entry.

## Relation Formatting (API Quirk)

When setting relations via Notion MCP `update-page`, use bare URL strings:

```
"Project": "https://www.notion.so/{page-id}"
```

Do NOT wrap in JSON arrays — the API rejects `["url"]` syntax.

When creating pages via `create-pages`, relations cannot be set inline. **Create the page first, then update with relations in a second call.**

## Reference Files

For detailed database schemas and API conventions:

| File | Contents |
|------|----------|
| `references/databases.md` | Full property schemas for all four databases |
| `references/conventions.md` | API quirks, error handling, formatting rules |

