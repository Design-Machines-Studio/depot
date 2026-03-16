# Content Scan -- Trend Research & Content Ideas

Research current events around labor, cooperatives, design, and the web industry. Cross-reference with DM strategy to generate content ideas and connect them to the weekly Buffer workflow.

## When to Run

Phase 7 of the sprint planning workflow. Run after Mail Scan.

## Tools Used

- `mcp__ai-memory__search_entities` -- current content priorities and strategy
- `mcp__ai-memory__get_entity` -- detailed strategy context
- Notion MCP tools -- query Content Development DB, create/update content items
- Web browsing (Claude Desktop only) -- current events research
- Companion skills:
  - `strategy` (design-machines) -- positioning, conversion funnel, target market
  - `social-media` (ghostwriter) -- platform strategy, format recommendations
  - `voice` (ghostwriter) -- writing direction and tone
  - `governance` (council) -- co-op and labor domain framing

## Content Development Database

Schema: see `databases.md` -- Content Development Database for full property reference, database IDs, status workflow, and content pillar descriptions.

## Procedure

### Step 1: Review DM Content Strategy

1. Load the strategy skill's context on positioning, target market, and content goals.
2. Search ai-memory for "content", "Buffer", "social media" to find current content priorities.
3. Key DM positioning pillars to align content with:
   - Democratizing the workplace via governance tools
   - Cooperative ownership as an alternative to extractive capitalism
   - Design and technology in service of democratic workplaces
   - The conversion funnel: designer uses Live Wires -> learns co-op content -> becomes Assembly client

### Step 2: Research Themes

Scan for current events and trends across DM's domain areas:

- **Labour and worker rights** -- wages, unionization, gig economy, layoffs, strikes
- **Cooperatives and alternative ownership** -- new co-ops, policy changes, success stories, co-op failures/lessons
- **Design and web industry** -- CSS developments, design tools, AI in design, web standards, agency trends
- **AI and labor** -- automation impact, job displacement, AI ethics, worker perspectives on AI
- **Co-op technology** -- governance tools, digital democracy, platform cooperatives, tech for social good

**In Claude Desktop:** Use web browsing to search for recent news, articles, and discussions.
**In Claude Code:** Rely on ai-memory for recent observations about these topics. Note that current events research is limited without web access.

> "Content research is more effective in Claude Desktop (web browsing available). Running with ai-memory context only."

### Step 3: Cross-Reference with Strategy

For each potential theme or news item:

1. Does it align with DM's positioning? (workplace democracy, cooperative ownership, design for good)
2. Does it serve the conversion funnel? (catches designers at craft level, or catches values-aligned people at co-op content level)
3. Is there a timely hook? (recent event, trending topic, upcoming date)
4. Does it connect to a content pillar? (Power & Democracy, Co-op Reality, etc.)
5. Which platform is it best suited for? (per social-media skill's guidance)

### Step 4: Generate Content Ideas

Produce 3-5 content ideas with full context:

```
### Content Ideas for Sprint [N]

**1. [Topic/Angle]**
- Pillar: [Power & Democracy / Co-op Reality / etc.]
- Platform: [LinkedIn / Instagram / Bluesky / Mastodon]
- Format: [Text post / Carousel / Thread / Reel / Quote card]
- Strategy connection: [Which DM product or positioning this serves]
- Timely hook: [Why now -- news event, trend, seasonal]
- Draft direction: [2-3 sentence pitch for the content]

**2. ...**
```

### Step 5: Check Existing Content Pipeline

Query the Content Development database for existing items that align with current themes:

1. Use Notion search or query to find items with Status = "Idea" or "Draft"
2. Check if any existing ideas are now timely (news hook emerged)
3. Flag items that should be prioritized this sprint

```
**Existing ideas now timely:**
- "[Title]" (Status: Idea, Pillar: [X]) -- now relevant because [reason]
- ...
```

### Step 6: Connect to Buffer Workflow

The weekly sprint typically includes a "Load up Buffer with social media posts" task. Content ideas from this phase should feed into that task.

Options:
1. **Add to Content Development DB** as new rows with Status = "Idea"
2. **Link to existing Buffer task** by adding content ideas as notes/comments
3. **Create dedicated content todos** for ideas that need research or writing time before they can be posted

Travis decides which approach for each idea.

## Output Summary

```
### Content Scan Summary

**Research context:** [Claude Desktop with web / Claude Code ai-memory only]
**Ideas generated:** N
**Existing ideas flagged:** N

[Ideas listed as in Step 4]

**Content pipeline status:**
- Ideas: X
- Drafts: X
- Ready: X
- Scheduled: X

**Action:** Add approved ideas to Content Development DB? Create content-specific todos?
```
