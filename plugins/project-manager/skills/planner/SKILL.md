---
name: planner
description: Notion-integrated project planning and sprint management. Use at the START of every coding session to check assigned todos. Use at the END of every session to mark completed tasks. Trigger when Travis asks about sprint status, wants to see what's on his plate, needs to create a new todo, asks for planning help, says "what should I work on," "create a task," "what's in this sprint," or any variation of checking project status or tracking work. Also trigger when Travis mentions sprints, todos, Notion tasks, project capacity, prioritization, userback, feedback, bugs, calendar, meetings, meeting prep, content ideas, sprint stats, sprint review, or velocity. Reads project config from memory/project-notion.md.
disable-model-invocation: true
allowed-tools:
  # Notion (claude.ai integration)
  - mcp__claude_ai_Notion__notion-search
  - mcp__claude_ai_Notion__notion-fetch
  - mcp__claude_ai_Notion__notion-create-pages
  - mcp__claude_ai_Notion__notion-update-page
  # Notion (plugin integration -- adds query-database-view)
  - mcp__plugin_Notion_notion__notion-search
  - mcp__plugin_Notion_notion__notion-fetch
  - mcp__plugin_Notion_notion__notion-create-pages
  - mcp__plugin_Notion_notion__notion-update-page
  - mcp__plugin_Notion_notion__notion-query-database-view
  - mcp__plugin_Notion_notion__notion-query-meeting-notes
  # ai-memory (read + write for sprint stats)
  - mcp__ai-memory__search_entities
  - mcp__ai-memory__get_entity
  - mcp__ai-memory__add_observation
  - mcp__ai-memory__add_entity
  # Userback (feedback triage)
  - mcp__Userback__list_projects
  - mcp__Userback__search_feedback_filter
  - mcp__Userback__search_feedback_semantic
  - mcp__Userback__get_feedback
  - mcp__Userback__get_feedback_logs
---

# Planner -- Notion Workflow Integration

## Current Git Context
!`git branch --show-current 2>/dev/null || echo "not a git repo"`
!`git log --oneline -3 2>/dev/null || echo "no recent commits"`

Travis plans work in Notion (Projects, Todos, Sprints). This skill gives Claude the knowledge to participate in that workflow -- reading context, updating task status, and assisting with sprint planning.

**Philosophy:** Travis plans, Claude executes. Read freely, write carefully.

## Quick Reference

### Database IDs

Look up all database data source IDs from the `DM Notion Workspace` entity in ai-memory. The entity stores IDs for Projects, Todos, Sprints, Notes, and Content Development databases.

### Read/Write Permissions (CRITICAL)

| Action | Permission | When |
|--------|-----------|------|
| Query any database | Always | Anytime context is needed |
| Update todo to "In progress" | Auto | When starting an assigned todo |
| Update todo to "Done" | Auto | When finishing an assigned todo |
| Create new todo | Only when Travis asks | "Add a todo for X" |
| Update todo name/priority/sprint | Only when Travis asks | "Move this to Sprint 5" |
| Modify project properties | Never | Travis-only |
| Modify sprint properties | Never | Travis-only |
| Update sprint status (Done/In progress) | After Travis confirms | During sprint commitment (Phase 9) |
| Write sprint stats to ai-memory | Auto | During sprint review (Phase 1) |
| Read Userback feedback | Always | During Userback triage (Phase 4) |


## Session Workflow

### At Session Start

1. **Read project config:** Check `memory/project-notion.md` for the Notion project URL and default role. If missing, ask Travis to set one up.

2. **Find active sprint:** Query Sprints DB for the sprint with Status = "In progress". Note the sprint name and date range.

3. **Load assigned todos:** Query Todos DB for todos linked to this project in the current sprint where Status is NOT "Done" or "Someday maybe". These are the candidates for this session.

4. **Read previous session:** Check `memory/sessions.md` for the last entry. Note what was done, what's pending, and anything learned.

5. **Brief Travis:** Share a concise summary: "Sprint 3 ends Feb 13. You have 4 open todos. Last session you worked on X. What should we focus on?"

### During Session

- When starting work on an assigned todo, update its Status to "In progress"
- When finishing a todo, update its Status to "Done"
- Track what you're doing -- you'll summarize it in sessions.md at session end

### At Session End

1. **Update todo statuses:** Any todos that changed during the session

2. **Append to sessions.md:** Write a brief session summary (see Session Memory Convention below)


## Sprint Planning Workflow

Sprint planning is a comprehensive 9-phase process. Use the `/sprint-plan` command to run the full workflow, or trigger individual phases as needed.

**Cadence:** Biweekly sprints. Planning on Monday morning of sprint start. Review on last day of sprint. Quarter planning on first sprint of each quarter.

### Phase Overview

| Phase | What | Reference |
|-------|------|-----------|
| 1. Sprint Review | Close outgoing sprint, track completion stats | `sprint-stats.md` |
| 2. Sprint Rollover | Present incomplete tasks: keep, defer, or drop | `sprint-planning.md` |
| 3. Conversation Review | Mine ai-memory for decisions, next steps, backlog | `sprint-planning.md` |
| 4. Userback Triage | Query feedback, group themes, validate against goals | `userback-triage.md` |
| 5. Calendar & Meeting Prep | Scan Calendar.app for 2 weeks, research participants | `meeting-prep.md` |
| 6. Mail Scan | Search Mail.app for action items and follow-ups | `mail-scan.md` |
| 7. Content Scan | Research trends, generate ideas, connect to Buffer | `content-scan.md` |
| 8. Sprint Loading | Review todos, apply velocity-based capacity, suggest | `sprint-planning.md` |
| 9. Sprint Commitment | Assign chosen todos, create new ones, confirm load | `sprint-planning.md` |

Phases 5 and 6 require shell access (AppleScript for Calendar.app and Mail.app). Skip gracefully in Claude Desktop.

Travis confirms between phases. Any phase can be skipped on request.

### Companion Skills

Load these skills when reaching their relevant phases:

| Skill | Plugin | When to Load |
|-------|--------|--------------|
| strategy | design-machines | Phase 5: participant/company research, pipeline context |
| social-media | ghostwriter | Phase 7: platform strategy, format decisions |
| voice | ghostwriter | Phase 7: writing direction for content drafts |
| governance | council | Phase 7: co-op/labor framing for content ideas |
| ai-memory | ned | Phases 1, 3: sprint stats storage, conversation review |
| lt10 | project-manager | Phase 8: capacity rules, estimation principles |


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
- **Notes:** Any project-specific context
```

This file is:
- Created once per project (manually or with Claude's help)
- NOT version-controlled (lives in Claude's memory directory)
- Instance-specific -- when Assembly becomes a template, each co-op maps to a different Notion project


## Session Memory Convention

### `memory/sessions.md`

Append-only log. Claude writes a brief summary at the end of each session:

```markdown
## 2026-02-13 -- [Brief description]

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

Do NOT wrap in JSON arrays -- the API rejects `["url"]` syntax.

When creating pages via `create-pages`, relations cannot be set inline. **Create the page first, then update with relations in a second call.**

## Reference Files

| File | Contents |
|------|----------|
| `${CLAUDE_SKILL_DIR}/references/databases.md` | Property schemas for Projects, Todos, Sprints, Time Tracking, and Content Development databases |
| `${CLAUDE_SKILL_DIR}/references/conventions.md` | API quirks, error handling, formatting rules |
| `${CLAUDE_SKILL_DIR}/references/sprint-planning.md` | Full sprint planning workflow (phases 1-3, 8-9) |
| `${CLAUDE_SKILL_DIR}/references/sprint-stats.md` | Velocity tracking, rolling averages, capacity planning |
| `${CLAUDE_SKILL_DIR}/references/userback-triage.md` | Userback feedback query, grouping, triage, and todo creation |
| `${CLAUDE_SKILL_DIR}/references/meeting-prep.md` | Calendar.app review, participant research, meeting briefs |
| `${CLAUDE_SKILL_DIR}/references/mail-scan.md` | Mail.app search for action items and follow-ups |
| `${CLAUDE_SKILL_DIR}/references/content-scan.md` | Trend research, content ideation, Buffer workflow |
