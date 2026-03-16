# Sprint Planning Workflow

Master reference for the `/sprint-plan` command. This workflow runs at the start of each new sprint (Monday mornings, biweekly). Each phase is described below or cross-referenced to its dedicated file.

Travis plans, Claude executes. Present findings and suggestions -- Travis decides.

## Phase Overview

1. Sprint Review -- close outgoing sprint, track stats
2. Sprint Rollover -- present incomplete tasks for keep/defer/drop
3. Conversation Review -- mine ai-memory for decisions and next steps
4. Userback Triage -- query feedback, group themes, validate goals (see `userback-triage.md`)
5. Calendar & Meeting Prep -- scan 2 weeks, research participants (see `meeting-prep.md`)
6. Mail Scan -- search Mail.app for action items (see `mail-scan.md`)
7. Content Scan -- research trends, generate content ideas (see `content-scan.md`)
8. Sprint Loading -- review open todos, apply capacity, suggest candidates
9. Sprint Commitment -- assign chosen todos, confirm load

---

## Phase 1: Sprint Review

Close the outgoing sprint and capture stats.

1. Query the Sprints DB for the sprint with Status = "In progress". Note its name and date range.
2. Query the Todos DB for all todos linked to this sprint where Person includes Travis.
3. Categorize each todo:
   - **Done** -- Status = "Done"
   - **Still open** -- Status is "In progress", "Inbox", or "Waiting on"
   - **Blocked** -- Status = "Blocked"
4. Calculate completion rate: done / total Travis-assigned.
5. Store stats in ai-memory (see `sprint-stats.md` for format and procedure).
6. Present summary to Travis:

```
### Sprint Review -- [Sprint Name]
**Period:** [start] to [end]
**Completed:** X / Y tasks (Z%)
**Still open:** [list with status]
**Blocked:** [list with blocker info]
```

---

## Phase 2: Sprint Rollover

Handle incomplete tasks from the outgoing sprint.

1. Take the "Still open" and "Blocked" lists from Phase 1.
2. For each incomplete task, present three options:
   - **Keep** -- carry into the new sprint (default for high-priority items)
   - **Defer** -- move back to Inbox or Someday maybe for future consideration
   - **Drop** -- remove from sprint without completing (rare -- only if no longer relevant)
3. Present as a table:

```
### Sprint Rollover
| Task | Priority | Status | Suggestion |
|------|----------|--------|------------|
| [name] | High | In progress | Keep (was actively worked on) |
| [name] | Low | Inbox | Defer (not started, low priority) |
```

4. Travis decides on each. Update todo statuses and sprint relations accordingly.

---

## Phase 3: Conversation Review

Review ai-memory for recent decisions, next steps, and backlog items from the previous sprint period.

1. Use `search_entities` with queries related to recent work:
   - Search for recent date prefixes matching the sprint period (e.g., "Mar 2026", "Feb 2026")
   - Search for key project names (Assembly, Live Wires, Design Machines, etc.)
   - Search for "decided", "session", "next step", "todo", "backlog"
2. Use `get_entity` to drill into entities with relevant observations.
3. Extract and categorize findings:
   - **Decisions made** -- things that were settled and should inform this sprint's work
   - **Actionable next steps** -- items mentioned as follow-ups that may not have become Notion todos yet
   - **Backlog items** -- ideas or future work raised but not urgent
   - **Open questions** -- unresolved items that need Travis's input
4. Cross-reference with existing Notion todos to avoid duplicates.
5. Present findings grouped by project:

```
### Conversation Review -- [Sprint Period]

**Assembly:**
- Decided: [decision and date]
- Next step: [action item] -- suggest creating todo? Y/N
- Backlog: [future consideration]

**Design Machines:**
- ...
```

6. Travis decides which items become new todos for the upcoming sprint.

---

## Phase 8: Sprint Loading

The core planning step. Review all available work and suggest what to load into the new sprint.

1. **Query active projects:** Search Projects DB for Status = "In progress". List project names and codes.
2. **Gather open todos:** Query Todos DB for items where Status is NOT "Done" or "Someday maybe", grouped by project. Include priority and blocking relationships.
3. **Include rollover items** from Phase 2 (those marked "Keep").
4. **Include new items** from Phases 3-7 (conversation review, Userback, calendar, mail, content).
5. **Apply capacity planning:**
   - Check sprint stats rolling average from ai-memory (see `sprint-stats.md`)
   - Count meeting days from Phase 5 calendar scan
   - Apply LT10 rules: 6-hour productive days, 70-80% utilization, max 3 active projects
   - Calculate available capacity: `(sprint days - meeting days) * utilization * avg tasks/day`
6. **Suggest candidates** based on:
   - Priority (High first)
   - Blocking relationships (unblock before blocked)
   - Sprint capacity (don't overfill)
   - Balance across projects (distribute load, don't stack one project)
   - Deadlines (approaching deadlines first)
7. Present as a grouped list:

```
### Sprint Loading -- [New Sprint Name]

**Capacity:** Rolling avg is X tasks/sprint. Y meeting days this sprint. Suggested load: Z tasks.

**High Priority:**
- [task] (Project) -- [reason for inclusion]
- ...

**Medium Priority:**
- ...

**Candidates if capacity allows:**
- ...

**Deferred (over capacity):**
- ...
```

8. **Travis decides.** Claude does not assign things to sprints. Present options, Travis picks.

---

## Phase 9: Sprint Commitment

After Travis selects tasks for the sprint:

1. **Update sprint relations:** For each chosen todo, update its Sprint relation to link to the new sprint.
   - Create the new sprint page first if it doesn't exist (ask Travis for dates)
   - Use bare URL format for relations: `"Sprint": "https://www.notion.so/{sprint-page-id}"`
   - Remember: relations must be set via update, not create
2. **Create new todos** for items that emerged from Phases 3-7:
   - Create the page first (Name, Status = "Inbox", Priority)
   - Then update with relations (Project, Sprint) in a second call
3. **Confirm final load:**

```
### Sprint Commitment -- [Sprint Name]
**Period:** [start] to [end]
**Total tasks:** X
**By project:** Project A (N), Project B (N), ...
**Capacity check:** X tasks vs. Y rolling average -- [OK / Over / Under]
```

4. Mark the outgoing sprint as Status = "Done" (only after Travis confirms).
5. Mark the new sprint as Status = "In progress" (only after Travis confirms).

Note: Sprint property modifications are Travis-only per permission rules. Ask Travis to confirm before making these changes.
