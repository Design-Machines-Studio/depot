# Worked Examples

Detailed examples demonstrating LT10 methodology application.

---

## Example 1: Website Redesign Estimate

### Scenario

Client wants homepage redesign. You've worked with them before—slow feedback, multiple stakeholders who disagree.

### Step 1: 90th Percentile Ranges (from team conversations)

| Phase | Low | High | Notes |
|-------|-----|------|-------|
| Discovery | 1 day | 4 days | "If scope is clear... but remember last time" |
| Design concepts | 3 days | 8 days | "Depends how many directions they want" |
| Revisions | 1 day | 5 days | "Could be 1 round or 4, you know them" |
| Build support | 1 day | 3 days | "Clean handoff vs. edge cases" |
| **Total** | **6 days** | **20 days** | |

### Step 2: Score Red Flags

| Red Flag | Discovery | Design | Revisions | Build |
|----------|-----------|--------|-----------|-------|
| Slow feedback (historically weeks) | 2 | 3 | 5 | 3 |
| Multiple decision-makers | 4 | 4 | 5 | 2 |
| Direction changes likely | 3 | 4 | 4 | 3 |
| **Total** | **9/15** | **11/15** | **14/15** | **8/15** |
| **Percentage** | **60%** | **73%** | **93%** | **53%** |

### Step 3: Calculate Midpoints

```
Formula: ((High - Low) × RedFlag%) + Low = Midpoint

Discovery:  ((4-1) × 60%) + 1  = 2.8 days
Design:     ((8-3) × 73%) + 3  = 6.65 days
Revisions:  ((5-1) × 93%) + 1  = 4.72 days
Build:      ((3-1) × 53%) + 1  = 2.06 days
────────────────────────────────────────
Total Midpoint: 16.2 days ≈ 16 days
```

### Step 4: Convert to Billing Units

Remember: Estimate in days, bill in sprints.

```
Internal estimate: 16 days
Convert to weeks: 16 ÷ 5 = 3.2 weeks
Round to sprints: 2 sprints (with built-in buffer)
Sprint rate: $8,500/sprint
Total: 2 × $8,500 = $17,000
```

### Step 5: Present to Client

> "Based on the scope and what I know about how we've worked together, I'm estimating **2 sprints** ($17,000). 
>
> The range could be as tight as 1.5 sprints if feedback is fast and we nail the direction early, or stretch to 2.5 sprints if we hit complications.
>
> Here's why I'm budgeting the full 2 sprints: we've historically had slow feedback cycles, there are multiple stakeholders who need alignment, and this is a high-visibility page where direction changes are likely. The revision phase in particular has high risk.
>
> If we can commit to 48-72 hour feedback turnarounds, we'll likely come in under budget."

### What Goes in the Contract

- Scope: Homepage redesign (2 sprints)
- Investment: $17,000
- Additional sprints: $8,500 each if scope expands
- Change control: Direction changes or additional rounds quoted separately

### What You Track Internally

- 16 estimated days across specific tasks
- Actual days spent vs estimate
- Which phases ran over/under

---

## Example 2: Choosing a Methodology

### Scenario

Client wants a new e-commerce site. They have a fixed budget, a hard launch deadline (holiday season), but aren't sure exactly what features they need beyond "we need to sell products online."

### Assessment

| Factor | What We Know | Points To |
|--------|--------------|-----------|
| Budget | Fixed ($50K) | Waterfall (need to control scope) |
| Timeline | Hard deadline (3 months) | Waterfall (can't iterate forever) |
| Requirements | Vague ("sell products") | Agile (need to discover) |
| Stakeholders | Single decision-maker, available weekly | Could go either way |
| Team | Experienced with e-commerce | Either (know the patterns) |

### Decision: Agifall (Hybrid)

**Why:**
- Use **Waterfall structure** for phases: Discovery → Design → Development → QA → Launch
- Use **Agile execution** within Development: 2-week sprints, prioritized backlog, daily standups
- **Fixed gates** between phases require client sign-off (protects scope)
- **Sprint flexibility** allows requirements to emerge during build

### How to Explain to Client

> "Given your fixed budget and deadline, we'll structure this in phases with clear milestones. Within each phase, we'll work in two-week sprints so you can see progress and we can adjust priorities based on what we learn. You'll have approval gates between phases so nothing moves forward until you're satisfied."

### What Goes in Contract

- Scope: E-commerce site (defined in discovery)
- Phases: Discovery (2 weeks) → Design (3 weeks) → Development (6 weeks) → QA (2 weeks)
- Investment: $50,000
- Gate approvals: Written sign-off required between phases
- Change control: Features added after Discovery quoted separately

---

## Example 3: Capacity Planning

### Scenario

You're a solo contractor with 3 potential projects:
- Project A: Homepage redesign (16 days over 6 weeks)
- Project B: Video production (8 days over 4 weeks)
- Project C: New client discovery (3 days over 2 weeks)

### Step 1: Calculate Available Capacity

```
Working days per week: 5
Productive hours per day: 6 (not 8!)
Days available for client work: 4 (reserve 1 for admin/business)
Weeks in period: 6

Total available: 4 days × 6 weeks = 24 client days
```

### Step 2: Map Project Demand

```
Project A: 16 days (must spread across 6 weeks = ~2.7 days/week)
Project B: 8 days (spread across 4 weeks = 2 days/week, but overlaps with A)
Project C: 3 days (in 2 weeks = 1.5 days/week)
```

### Step 3: Check for Conflicts

| Week | Project A | Project B | Project C | Total | Available | Status |
|------|-----------|-----------|-----------|-------|-----------|--------|
| 1 | 2.5 | 2 | - | 4.5 | 4 | ⚠️ Over |
| 2 | 2.5 | 2 | - | 4.5 | 4 | ⚠️ Over |
| 3 | 2.5 | 2 | 1.5 | 6 | 4 | 🔴 Way over |
| 4 | 2.5 | 2 | 1.5 | 6 | 4 | 🔴 Way over |
| 5 | 3 | - | - | 3 | 4 | ✅ OK |
| 6 | 3 | - | - | 3 | 4 | ✅ OK |

### Step 4: Make Decisions

**Options:**
1. **Defer Project C** to start week 5 (best option - stays within Think in Threes)
2. **Extend Project A timeline** to reduce weekly intensity
3. **Decline Project C** (if can't defer)
4. **Work overtime** (not recommended - unsustainable)

### Script for Deferring

> "I'd love to work on this, but I'm at capacity until week 5. Can we kick off then? If timing is critical, I can recommend another resource."

---

## Example 4: Handling Scope Creep

### Scenario

Mid-project, client emails: "Can you just add a contact form to the homepage? Should be quick."

### Assessment

1. **Is this in scope?** Check SOW - no contact form mentioned
2. **What's the real effort?** Form design, validation, backend processing, testing = 2-3 days
3. **What's the impact?** Current sprint is full, would push other items

### Response Script

> "Thanks for thinking ahead on this! The contact form isn't in our current scope, but I can definitely quote it as an addition.
>
> It would be approximately 2-3 days of work ($2,500-$3,750) covering design, development, and testing. 
>
> We have a couple options:
> 1. Add it to the current project, which would extend the timeline by about a week
> 2. Defer it to a quick phase two after launch
>
> Which would you prefer? Or if you'd like, we can swap it for something in the current scope that's lower priority."

### Key Points

- Acknowledged the request positively
- Quantified the actual effort (not "just")
- Provided options
- Offered to discuss trade-offs

---

## Example 5: Red Flag Scoring for Complex Project

### Scenario

New client, large website rebuild. Initial discovery reveals these red flags:

| Red Flag | Observed Behavior |
|----------|-------------------|
| Stakeholder disagreement | CEO and Marketing Director have different visions |
| Unclear requirements | "We want something modern" - no specifics |
| Aggressive timeline | "We need this in 6 weeks" (normally 12-week project) |
| Limited availability | POC is part-time, travels frequently |
| New technology | Requesting platform team hasn't used before |

### Step 1: Get 90th Percentile Ranges

| Phase | Low | High | Notes |
|-------|-----|------|-------|
| Discovery | 5 days | 15 days | Need extra for stakeholder alignment |
| Design | 10 days | 30 days | Multiple directions likely |
| Development | 20 days | 50 days | New platform, unknowns |
| QA | 5 days | 15 days | Standard testing |
| PM | 8 days | 20 days | High-touch stakeholders |
| **Total** | **48 days** | **130 days** | |

### Step 2: Score Red Flags by Section

| Red Flag | Discovery | Design | Dev | QA | PM |
|----------|-----------|--------|-----|-----|-----|
| Stakeholder disagreement (5) | 5 | 5 | 3 | 2 | 5 |
| Unclear requirements (4) | 4 | 5 | 4 | 3 | 3 |
| Aggressive timeline (3) | 2 | 3 | 4 | 4 | 3 |
| Limited availability (4) | 4 | 4 | 3 | 3 | 5 |
| New technology (5) | 2 | 2 | 5 | 4 | 3 |
| **Total** | 17/25 | 19/25 | 19/25 | 16/25 | 19/25 |
| **Percentage** | 68% | 76% | 76% | 64% | 76% |

### Step 3: Calculate Midpoints

```
Discovery:  ((15-5) × 68%) + 5   = 11.8 days
Design:     ((30-10) × 76%) + 10 = 25.2 days
Dev:        ((50-20) × 76%) + 20 = 42.8 days
QA:         ((15-5) × 64%) + 5   = 11.4 days
PM:         ((20-8) × 76%) + 8   = 17.1 days
─────────────────────────────────────────
Total Midpoint: 108.3 days ≈ 108 days
```

### Step 4: Convert and Present

```
108 days ÷ 5 days/week = 21.6 weeks
Round to: 11 two-week sprints
Sprint rate: $15,000/sprint
Total: $165,000
```

### Presentation to Client

> "Based on our discovery conversation, I'm estimating **11 sprints** (approximately 22 weeks) at $165,000.
>
> I know you mentioned 6 weeks, so I want to be transparent about why we're at 22 weeks:
>
> **High-risk factors we identified:**
> - Stakeholder alignment needed (CEO and Marketing have different visions)
> - Requirements still emerging ("modern" needs definition)
> - Platform we haven't used before (learning curve)
> - POC availability constraints (part-time, traveling)
>
> **Options to reduce timeline:**
> 1. **Reduce scope** - Phase 1 launches core pages only, Phase 2 adds the rest
> 2. **Increase resources** - Add team members (cost increases ~40%)
> 3. **Resolve alignment first** - 2-week strategy sprint before we estimate the build
>
> I'd recommend option 3. We can do a fixed $25,000 strategy sprint to align stakeholders and define requirements. After that, we can give you a much tighter estimate for the build."

---

## Example 6: Project Health Assessment

### Scenario

Week 4 of an 8-week project. Time for a health check.

### Metrics Gathered

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Time elapsed | 50% | 50% | ✅ |
| Budget spent | 50% | 65% | ⚠️ |
| Tasks complete | 50% | 35% | 🔴 |
| Stakeholder feedback | 2 rounds | 4 rounds | 🔴 |
| Team morale | High | Medium | ⚠️ |

### Analysis

- **Budget vs time:** Spending faster than planned (65% vs 50%)
- **Tasks vs time:** Behind on deliverables (35% vs 50%)
- **Feedback rounds:** Double what was planned (scope creep indicator)
- **Morale:** Declining (burnout risk)

### Diagnosis

**Root cause:** Excessive revision rounds are burning budget without advancing deliverables. Client adding requirements at each review.

### Action Plan

1. **Immediate:** Schedule call with client to discuss
2. **This week:** Document all scope additions since kickoff
3. **Present:** Show impact of additions on budget/timeline
4. **Propose:** Either trim scope or add budget
5. **Team:** Cancel Friday afternoon meetings, give breathing room

### Script for Client Call

> "I want to give you a mid-project check-in. We're at week 4 of 8, and I'm seeing some patterns I want to address.
>
> We've done 4 rounds of revisions so far—double what we planned. Each round has added new requirements that weren't in our original scope.
>
> The impact: We've used 65% of budget but completed only 35% of deliverables.
>
> To hit our launch date, we need to either:
> 1. Lock scope now and complete what's defined, or
> 2. Add $X and 2 weeks to accommodate the additions
>
> Which direction would you like to go?"

---

## Key Principles from These Examples

1. **Always show your math** - Stakeholders trust estimates backed by visible reasoning
2. **Red flags justify your position** - They're evidence, not excuses
3. **Offer options** - Never just say no; give alternatives
4. **Convert units appropriately** - Estimate in days, present in sprints
5. **Track actuals vs estimates** - Learn from every project
6. **Address issues early** - Week 4 is better than week 8
7. **Scripts prepare you** - Practice makes difficult conversations easier
