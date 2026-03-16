# Notion Database Schemas

Full property reference for project management databases. These are personal databases shared across all projects. Look up data source IDs from the `DM Notion Workspace` entity in ai-memory.

---

## Projects Database

**Data source ID:** Look up "Projects DB" in `DM Notion Workspace` ai-memory entity
**Title property:** `Name`

| Property | Type | Values / Notes |
|----------|------|---------------|
| Name | title | Project name |
| Status | status | Not started, In progress, No go, Done |
| Area | select | WORKS, COMPANY, FLOOR, PLATE, PRESS |
| Client | relation | → Clients DB |
| Team | person | Assigned people |
| Project code | text | e.g., DM-006/WORKS |
| Start Date | date | Project start |
| End Date | date | Project end |
| Todos | relation | → Todos DB |
| Notes | relation | → Notes DB |

---

## Todos Database

**Data source ID:** Look up "Todos DB" in `DM Notion Workspace` ai-memory entity
**Title property:** `Name`

| Property | Type | Values / Notes |
|----------|------|---------------|
| Name | title | Task name |
| Status | status | Someday maybe, Inbox, In progress, Waiting on, Blocked, Done |
| Priority | select | Low, Medium, High |
| Project | relation | → Projects DB |
| Sprint | relation | → Sprints DB (limit 1) |
| Person | person | Assigned to |
| Deadline | date | Due date |
| Blocked by | relation | → self (Todos DB) |
| Blocking | relation | → self (Todos DB) |
| Notes | relation | → Notes DB |

**Views:** This sprint (board), Quarter plan (board), Yearly plan (board), By project (board)

**Status workflow:** Inbox → In progress → Done (typical). Blocked/Waiting on for dependencies.

---

## Time Tracking Database

**Data source ID:** Look up "Time Tracking DB" in `DM Notion Workspace` ai-memory entity
**Title property:** `Entry`

| Property | Type | Values / Notes |
|----------|------|---------------|
| Entry | title | Description of work done |
| Days | number (float) | Quarter-day blocks: 0.25, 0.5, 0.75, 1.0 |
| Date | date | Date of work |
| Role | select | Project Management, Research, Strategy, Production |
| Project | relation | → Projects DB |
| Sprint | relation | → Sprints DB (limit 1) |


**Time entry conventions:**
- Entry descriptions should be concise but specific: "Built planner skill file structure" not "worked on stuff"
- Days should reflect actual effort, not elapsed time
- Role defaults to the value in `memory/project-notion.md` but can be overridden per entry
- Always link both Project and Sprint relations

---

## Sprints Database

**Data source ID:** Look up "Sprints DB" in `DM Notion Workspace` ai-memory entity
**Title property:** `Sprint`

| Property | Type | Values / Notes |
|----------|------|---------------|
| Sprint | title | e.g., "Sprint 4" |
| Status | status | Not started, In progress, Done |
| Dates | date (range) | Start and end dates |
| Quarter | select | Q1, Q2, Q3, Q4 |
| Year | select | 2025, 2026, etc. |
| Time Tracking | relation | → Time Tracking DB |
| Todos | relation | → Todos DB |

**Sprint conventions:**
- Biweekly cadence, Monday to Sunday (14 days)
- Only one sprint should be "In progress" at a time
- Planning happens Monday morning of sprint start, in Claude Desktop
- Review happens last day of sprint

---

## Content Development Database

**Database ID:** `313d8793-8808-80d6-8f95-d741bf62c08e`
**Data source:** `collection://313d8793-8808-80ac-aa16-000b113e478a`
**Title property:** `Title`

| Property | Type | Values / Notes |
|----------|------|---------------|
| Title | title | Content piece name |
| Status | status | Idea, Draft, Ready, Scheduled, Rejected, Published |
| Pillar | select | Power & Democracy, Co-op Reality, Lessons, System is Designed, What I'm Building, Influence Quotes, Making Things |
| Platforms | multi_select | LinkedIn, Instagram, Bluesky, Mastodon |
| Scheduled date | date (range) | Publication date |

**Status workflow:** Idea -> Draft -> Ready -> Scheduled -> Published. Rejected is a terminal state.

**Content pillars:**
- **Power & Democracy** -- workplace democracy, governance, voting, decision-making
- **Co-op Reality** -- real stories, challenges, and wins from cooperative work
- **Lessons** -- practical learnings from building, managing, and running projects
- **System is Designed** -- critiques of extractive systems, capitalism, labor exploitation
- **What I'm Building** -- behind-the-scenes on Assembly, Live Wires, DM products
- **Influence Quotes** -- quotes from thinkers who shape DM's worldview
- **Making Things** -- craft, design, CSS, web development
