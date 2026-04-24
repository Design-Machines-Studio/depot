# Ops Dashboard Setup

One-time setup instructions for the Agent Activity Log database and Ops Dashboard page in Notion. Run these steps in a session with Notion MCP tools available.

## Step 1: Create the Agent Activity Log Database

Use `notion-create-database` to create a new database in the DM workspace with these properties:

| Property | Type | Configuration |
|----------|------|--------------|
| Entry | title | (default title property) |
| Type | select | Options: Pipeline Run, Code Review, Sprint Close |
| Status | select | Options: Clean, Needs Attention, Blocked |
| Date | date | |
| Project | relation | -> Projects DB |
| Sprint | relation | -> Sprints DB |
| Findings | number | |
| P1 Count | number | |
| Chunks | number | |
| Agents | number | |
| Merge Rec | select | Options: CLEAN, APPROVE WITH FIXES, BLOCKS MERGE, N/A |
| Branch | rich_text | |

## Step 2: Store the Database ID

After creation, store the database ID in ai-memory:

```
search_entities("DM Notion Workspace")
add_observation("DM Notion Workspace", "Agent Activity Log DB: <database-id>")
save()
```

## Step 3: Create the Ops Dashboard Page

Create a Notion page called "Ops Dashboard" in the DM workspace. Add five linked database views of the Agent Activity Log:

1. **Ops Timeline** -- Table view, all types, sorted by Date descending. Show: Entry, Type, Status, Date, Project, Findings, Merge Rec
2. **Pipeline Runs** -- Table view, filter Type = "Pipeline Run". Show: Entry, Status, Date, Project, Chunks, Findings, Merge Rec, Branch
3. **Review Quality** -- Table view, filter Type = "Code Review". Show: Entry, Status, Date, Project, Agents, Findings, P1 Count, Merge Rec
4. **By Sprint** -- Board view, grouped by Sprint relation. Show all Types
5. **Health Board** -- Board view, grouped by Status. Filter: Date within last 30 days

## Step 4: Verify

Run `/dm-review` on any project. After completion, check that a "Code Review" row appears in the Agent Activity Log with the correct findings count and merge recommendation.

## Write Points

Three plugin workflows write to this database:

- **dm-review** Phase 7c -- after every full code review
- **pipeline** Phase 7 Deliver -- after every pipeline run
- **sprint-plan** Phase 1 Sprint Review -- after every sprint close

All writes are optional. If Notion MCP is unavailable, writes are skipped silently and ai-memory remains the primary record.
