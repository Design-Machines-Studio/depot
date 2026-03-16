# Userback Triage -- Feedback Integration

Query user feedback from Userback during sprint planning, group it into actionable themes, cross-reference against project goals, and create Notion todos for approved work chunks.

## When to Run

Phase 4 of the sprint planning workflow. Run after Sprint Review/Rollover and Conversation Review.

## Tools Used

- `mcp__Userback__list_projects` -- discover Userback projects
- `mcp__Userback__search_feedback_filter` -- query feedback by date, status, project
- `mcp__Userback__search_feedback_semantic` -- cluster related feedback
- `mcp__Userback__get_feedback` -- get full details on a specific item
- `mcp__Userback__get_feedback_logs` -- check console/network logs attached to feedback
- `mcp__ai-memory__search_entities` -- look up project goals
- `mcp__ai-memory__get_entity` -- get detailed project context
- `mcp__ai-memory__add_observation` -- store Userback-to-Notion project mappings

## Procedure

### Step 1: Identify Userback Projects

Use `list_projects` to get all Userback projects. Match them to Notion projects by name or by checking ai-memory for stored mappings.

On first use, store the mapping as an ai-memory observation on the "DM Notion Workspace" entity:
```
Userback project "[name]" (ID: [id]) maps to Notion project "[project name]"
```

Currently active: Assembly (more projects may be added in future).

### Step 2: Query Recent Feedback

For each active Userback project:

Use `search_feedback_filter` to pull feedback from the last sprint period:
- Filter by date range (sprint start to sprint end)
- Focus on open/unresolved items
- Note severity, type (bug vs. feature request vs. general feedback)

### Step 3: Semantic Grouping

Do NOT create one todo per feedback item. Instead, group related items into themes.

Use `search_feedback_semantic` to identify clusters. Then manually group remaining items by:
- Feature area (e.g., "navigation", "member onboarding", "voting flow")
- Issue type (e.g., "mobile layout issues", "performance complaints")
- User intent (e.g., "wants better visibility into equity", "confused by terminology")

Each theme becomes a potential work chunk.

### Step 4: Cross-Reference with Project Goals

For each theme, check whether it aligns with current project direction:

1. Search ai-memory for the relevant project entity (e.g., "Assembly")
2. Look for observations about goals, priorities, current focus, roadmap
3. Ask:
   - Does this feedback align with what we're already planning?
   - Does it reveal something new we hadn't considered?
   - Does it contradict stated goals? (potential scope creep)
   - How severe is it? (blocking users vs. nice-to-have)

### Step 5: Present Triage Summary

Format for Travis:

```
### Userback Triage -- [Project Name]
**Period:** [sprint dates] | **Total items:** N

**Theme 1: [Description]** (X items, Y bugs / Z requests)
- Representative feedback: "[direct quote from user]"
- Aligns with: [project goal from ai-memory] / New concern / Contradicts [goal]
- Severity: High / Medium / Low
- Suggested action: Create todo / Defer to backlog / Already covered by [existing todo]
- Userback IDs: UB-123, UB-456, UB-789

**Theme 2: [Description]** (X items)
- ...

**No action needed:**
- [feedback item] -- already addressed in [sprint/todo]
- [feedback item] -- duplicate of Theme 1
```

### Step 6: Pushback Guidance

If feedback contradicts project direction, say so directly:

> "5 users want [feature X], but your stated goal for Assembly is [Y]. This might be scope creep -- the feedback suggests users want Assembly to be [something it isn't scoped to be]. Alternatively, it might indicate the goal needs revisiting. Your call."

Do not silently absorb feedback that conflicts with strategy. Flag the tension and let Travis decide.

### Step 7: Create Todos

Only after Travis confirms which themes to act on.

For each approved theme:
1. **Create the todo page:**
   - Name: actionable, verb-first ("Fix navigation flow for member onboarding")
   - Status: "Inbox"
   - Priority: based on theme severity and volume
2. **Update with relations** (second API call):
   - Project: linked to relevant Notion project
   - Sprint: do NOT assign yet -- that happens in Phase 8 (Sprint Loading)
3. **Todo description** should include:
   - Brief theme summary (1-2 sentences)
   - Userback item IDs for reference (e.g., "Related Userback: UB-123, UB-456, UB-789")
   - Do NOT paste full feedback text -- just IDs for traceability

## Permission Notes

- Reading Userback: always allowed
- Creating Notion todos: only after Travis explicitly approves themes
- Updating Userback item status: not done during triage (Travis handles Userback status separately)
