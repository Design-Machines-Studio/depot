---
name: time-tracker
description: Create and update time tracking entries in Notion. Called by the main session at session start (create) and session end (update).
---

# Time Tracker Agent

A lightweight agent for creating and updating time tracking entries in Notion.

## Agent Config

- **Model:** claude-haiku-4-5-20241022
- **Purpose:** Create and update time entries. Single-purpose, fast, cheap.
- **Trigger:** Called by the main session at session start (create) and session end (update)

## Task: Create Time Entry

**Input from main session:**
- Project Notion URL
- Sprint Notion URL
- Date (today)
- Role (from project config)

**Steps:**
1. Create a page in Time Tracking DB (look up data source ID from `DM Notion Workspace` entity in ai-memory):
   - Entry: "Session in progress"
   - Days: 0.25
   - Date: {today}
   - Role: {role}
2. Update the created page to set relations:
   - Project: {project_url}
   - Sprint: {sprint_url}
3. Return the page URL to the main session

## Task: Update Time Entry

**Input from main session:**
- Time entry page ID or URL
- Entry description (what was done)
- Days worked (0.25 / 0.5 / 0.75 / 1.0)

**Steps:**
1. Update the time entry page:
   - Entry: {description}
   - Days: {days}

## Notes

- This agent does NOT query databases or make decisions — it receives specific instructions and executes
- The main session (Opus/Sonnet) handles all the reasoning about what to log
- If the agent fails, the main session should retry once, then log the failure in sessions.md and move on — don't block the coding session over a time entry
