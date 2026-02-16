---
name: recorder
description: Captures conversation sessions into structured summaries, pushes observations to ai-memory entities, and creates Notion notes. Use when Travis says "capture this session", "log this", "save this conversation", "capture this", or any variation requesting session documentation. Also use when a long strategic conversation naturally concludes and significant decisions were made.
---

# Session Capture

Protocol for capturing conversation sessions into persistent storage across two systems: the ai-memory knowledge graph and Notion notes database.

## When to Trigger

**Explicit triggers:** "capture this session", "log this", "save this conversation", "capture this", "document what we decided", "save our decisions"

**Implicit triggers:** End of a long conversation where significant decisions, strategy shifts, or new information emerged. Claude should offer: "Want me to capture this session?"

## The Capture Protocol

When triggered, execute these three phases in order.

### Phase 1: Analyze the Conversation

Review the full conversation and extract:

1. **Session title** — A descriptive name (e.g., "Assembly Architecture Naming Session", "Pilot Prep Call Notes")
2. **Key decisions** — Things that were decided or agreed upon. Be specific. "Renamed Co-op OS to Assembly" not "discussed naming."
3. **New information** — Facts, data, or context that emerged. People mentioned, dates confirmed, prices quoted.
4. **Todos** — Concrete next-step tasks that emerged. These are actionable items, not vague intentions. Each todo needs: a clear name, a suggested Notion project to link it to (if identifiable), and optionally a priority (Low/Medium/High). Default status is "Inbox" unless context suggests otherwise.
5. **Open questions** — Things raised but not resolved.
6. **Entities affected** — Which ai-memory entities need new observations. Think about: people, projects, companies, products, events.

Present this analysis to Travis for review before proceeding. Format it as a concise summary he can scan and approve or adjust. **For todos specifically**, list them with suggested project links so Travis can confirm, adjust, or remove before creation.

### Phase 2: Push to AI Memory

For each affected entity, add observations using the `add_observation` MCP tool.

**Observation writing rules:**
- Start with a date reference: "As of Feb 2026:" or "Decided in Feb 2026 session:"
- Be factual and specific, not vague
- One observation per distinct fact or decision
- Keep under 300 characters when possible (hard limit: 500)
- Don't duplicate existing observations — check the entity first with `get_entity`

**If an entity doesn't exist yet**, create it with `add_entity` before adding observations. Include entity_type (Person, Project, Company, Product, Event, etc.).

**If relationships changed**, add them with `add_relationship`.

**Example observations:**
- Good: "Decided in Feb 2026: Assembly Baseplate will use Go + Datastar + SQLite stack"
- Good: "As of Feb 2026: Pilot meeting scheduled for Feb 23, 2026"
- Bad: "Discussed some technical stuff about Assembly"
- Bad: "Travis is thinking about maybe changing something"

### Phase 3: Create Todos in Notion

For each confirmed todo, create a page in the Todos database.

**Notion target:**
- Look up the Todos DB data source ID from the `DM Notion Workspace` entity in ai-memory.
- Use `Notion:notion-create-pages` tool

**Property mapping:**

| Property | How to set |
|----------|-----------|
| Name | Todo title — clear, actionable (e.g., "Update session-capture skill with todo extraction") |
| Status | "Inbox" by default. Use "In progress" only if Travis explicitly said he's starting it now. |
| Priority | "Medium" by default. Use "High" if urgent/blocking, "Low" if someday/nice-to-have. |
| Project | Link to the relevant project page URL. Look up project URLs from the `DM Notion Workspace` entity in ai-memory. |

If the todo doesn't clearly belong to a project, skip the Project link. If a new project is needed, note it but don't create one without Travis confirming.

**Todo writing rules:**
- Start with a verb: "Update...", "Research...", "Schedule...", "Draft...", "Build..."
- Be specific enough to act on without re-reading the session
- One todo per distinct action — don't combine multiple steps
- If a todo has a deadline mentioned in conversation, set the Deadline property

### Phase 4: Create Notion Note

Create a page in the Notes database with the session summary.

**Notion target:**
- Look up the Notes DB data source ID from the `DM Notion Workspace` entity in ai-memory.
- Use `Notion:notion-create-pages` tool

**Property mapping:**

| Property | How to set |
|----------|-----------|
| Name | Session title (e.g., "Session: Assembly Architecture Naming") |
| Type | "Document" |
| Tags | Match to available options: "Design Machines", "Work", "Brainstorming", "Writing", "AI Prompts" — pick what fits |
| Topics | Match to available options: "Design", "Development", "AI", "Capitalism", "Employment", "Craft" — pick what fits |

**Page content structure (Notion markdown):**

```
## Summary
[2-3 sentence overview of what the session covered and accomplished]

## Decisions
- [Decision 1]
- [Decision 2]

## New Information
- [Fact or context that emerged]

## Todos Created
- [ ] [Todo 1] → [Project name if linked]
- [ ] [Todo 2] → [Project name if linked]

## Open Questions
- [Unresolved question]

## Entities Updated
[List of ai-memory entities that received new observations, as a simple list]

---
*Captured from Claude session · [Date]*
```

## Handling Edge Cases

**Short conversations with few decisions:** Still capture, but keep it minimal. A 3-line Notion note is fine. Skip ai-memory updates if nothing entity-worthy emerged.

**Multiple topics covered:** Use a compound title: "Session: Live Wires Beta Feedback + Pilot Planning"

**Sensitive financial info:** Include in ai-memory observations (it's private) but be judicious about what goes in Notion if the workspace has other viewers.

**Conversations across multiple chat sessions:** If Travis says "capture the last few sessions" or references work done in previous chats, use the conversation_search or recent_chats tools to pull context, then capture holistically.

**Travis disagrees with analysis:** Adjust before pushing. Never push to ai-memory or Notion without approval on the summary.

## Quick Capture Mode

If Travis says "quick capture" or "just log the highlights", skip the review step and push directly with a shorter summary. Use best judgment on what's significant. Still create both ai-memory observations and Notion note, just leaner.

## After Capture

Confirm what was saved:
- Number of ai-memory observations added (and to which entities)
- Number of todos created in Notion (and which projects they're linked to)
- Link to the Notion note page created
- Any entities that were created new

Keep it brief. Don't over-explain what you just did.
