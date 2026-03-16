# Meeting Prep -- Calendar Review & Participant Research

Scan Calendar.app for upcoming meetings, research participants using ai-memory and the strategy skill, generate meeting briefs, and create prep todos.

## When to Run

Phase 5 of the sprint planning workflow. Run after Userback Triage.

## Tools Used

- AppleScript via shell (`osascript`) for Calendar.app queries
- `mcp__ai-memory__search_entities` -- look up meeting participants
- `mcp__ai-memory__get_entity` -- get detailed person/company context
- Notion MCP tools -- create prep todos
- Companion skill: `strategy` (design-machines plugin) -- for pipeline and partnership context

## Requirements

**Requires shell access.** This phase works in Claude Code only. If running in Claude Desktop (no shell), skip this phase gracefully:

> "Calendar scan requires shell access (Calendar.app via AppleScript). Skipping this phase. You can run `/sprint-plan` in Claude Code to include calendar review, or manually share your upcoming meetings."

## Procedure

### Step 1: Query Calendar.app

Use AppleScript to get events for the next 14 days:

```applescript
tell application "Calendar"
    set now to current date
    set futureDate to now + 14 * days
    set eventList to {}
    repeat with cal in calendars
        try
            set calEvents to (every event of cal whose start date >= now and start date <= futureDate)
            repeat with evt in calEvents
                set evtStart to start date of evt
                set evtEnd to end date of evt
                set evtSummary to summary of evt
                set evtLocation to ""
                try
                    set evtLocation to location of evt
                end try
                set evtNotes to ""
                try
                    set evtNotes to description of evt
                end try
                -- Get attendees
                set attendeeList to {}
                try
                    repeat with att in attendees of evt
                        set end of attendeeList to (name of att) & " <" & (address of att) & ">"
                    end repeat
                end try
                set end of eventList to evtSummary & " ||| " & (evtStart as string) & " ||| " & (evtEnd as string) & " ||| " & (name of cal) & " ||| " & evtLocation & " ||| " & (attendeeList as string)
            end repeat
        end try
    end repeat
    return eventList
end tell
```

### Step 2: Filter for External Meetings

From the event list, identify meetings with external participants:
- Has attendees who are NOT Travis (travis@designmachines.ca or similar)
- Exclude personal calendar events (holidays, reminders, meal plans)
- Exclude recurring internal events (unless they have external attendees)
- Focus on: client calls, partner meetings, community calls, networking

Categories:
- **Client/prospect calls** -- related to DM pipeline
- **Partner meetings** -- related to partnerships ecosystem
- **Community/industry** -- co-op events, design industry
- **Personal/skip** -- medical, personal, not relevant to sprint planning

### Step 3: Research Participants

For each external meeting:

1. **Search ai-memory** for each attendee by name:
   - `search_entities("[person name]")`
   - If found: `get_entity("[person name]")` for full context
2. **Search for their company/organization:**
   - `search_entities("[company name]")`
   - Check for observations about the relationship, past interactions, pipeline status
3. **Check strategy context** (if relevant to DM business):
   - Load the strategy skill's pipeline and partnerships references
   - Is this person/company in the DM pipeline?
   - Are they a potential partner archetype (financial, governance, collaboration, design)?
4. **Check for recent Notion notes:**
   - Search Notion for notes mentioning this person or company
   - Look for previous meeting summaries

### Step 4: Generate Meeting Brief

For each external meeting, produce:

```
### [Meeting Name] -- [Date, Time]
**With:** [Person Name] ([Company/Org])
**Calendar:** [calendar name]

**Context:** [What ai-memory knows about this person and the relationship]
**Last interaction:** [Most recent ai-memory observation, if any]
**Strategic alignment:** [How this connects to DM goals -- pipeline stage, partner type, or N/A]
**Potential topics:**
- [Based on context, recent developments, and relationship history]
- [Any open questions or follow-ups from previous meetings]
**Prep needed:**
- [Specific items to prepare -- deck, demo, research, talking points]
```

### Step 5: Create Prep Todos

For meetings that require preparation:

1. Create a Notion todo:
   - Name: "Prep for [meeting name] with [person] -- [date]"
   - Status: "Inbox"
   - Priority: Medium (High if client/partner call)
   - Deadline: day before the meeting
2. Update with Project relation if the meeting is linked to a specific project.
3. Do NOT assign to a sprint yet -- that happens in Phase 8 (Sprint Loading).

### Step 6: Handle Unknown Participants

When an attendee is not found in ai-memory:

> "[Person Name] from [Meeting Title] is not in your knowledge graph. Would you like to:
> 1. Provide context so I can create an entity
> 2. Skip prep for this meeting
> 3. I'll do basic research based on the meeting title"

If Travis provides context, create a new ai-memory entity for the person.

## Output Summary

At the end of this phase, present:

```
### Calendar & Meeting Prep Summary
**Next 14 days:** X total events, Y external meetings identified

**Meetings requiring prep:**
1. [Meeting] with [Person] -- [Date] -- todo created
2. ...

**Meetings with no prep needed:**
- [Meeting] -- [reason: recurring, no external attendees, etc.]

**Unknown participants:**
- [Person] from [Meeting] -- needs context from Travis
```
