# Ops Dashboard Setup

One-time setup instructions for the Agent Activity Log database and Ops Dashboard page in Notion. This dashboard is used by explicitly invoked personal sprint planning; Pipeline and dm-review do not write development activity here. Run these steps in a session with Notion MCP tools available.

## Step 1: Create the Agent Activity Log Database

Use `notion-create-database` to create a new database in the DM workspace with these properties:

| Property | Type | Configuration |
|----------|------|--------------|
| Entry | title | (default title property) |
| Type | select | Option: Sprint Close |
| Status | select | Options: Clean, Needs Attention, Blocked |
| Date | date | |
| Sprint | relation | -> Sprints DB |
| Findings | number | |

## Step 2: Store the Database ID

After creation, store the database ID in ai-memory:

```
search_entities("DM Notion Workspace")
add_observation("DM Notion Workspace", "Agent Activity Log DB: <database-id>")
save()
```

## Step 3: Create the Ops Dashboard Page

Create a Notion page called "Ops Dashboard" in the DM workspace. Add three linked database views of the Agent Activity Log:

1. **Sprint Close Timeline** -- Table view, sorted by Date descending. Show: Entry, Status, Date, Sprint, Findings
2. **By Sprint** -- Board view, grouped by Sprint relation
3. **Health Board** -- Board view, grouped by Status. Filter: Date within last 30 days

## Step 4: Verify

Run the Sprint Review phase of `/sprint-plan`. After completion, check that a "Sprint Close" row appears in the Agent Activity Log with the correct completion data.

## Write Points

One explicitly invoked workflow writes to this database:

- **sprint-plan** Phase 1 Sprint Review -- after a sprint close

All writes are optional. If Notion MCP is unavailable, writes are skipped silently and ai-memory remains the primary record.
