# Scheduling & Capacity Planning

> **Related sections:** → Estimation (`estimation.md`) → Pricing (`pricing.md`) → Methodology (`methodology.md`)

## Why Schedules Matter

Schedules show you how healthy your company revenue is. Project drag = revenue loss.

### Cost of Delay Example

```
Day rate: $800/day/person
5 days late = $4,000 loss per person
20 days late = $16,000 loss per person
```

**Pro tip:** Aim for <10% project overages. One month project shouldn't drag more than 2 days.

---

## Scheduling Methods

| Method | Best For | Not Great For |
|--------|----------|---------------|
| **Calendars** | Milestones, few projects, booking meetings | Task-level duration, capacity tracking |
| **Gantt charts** | Long-range flexible timeline, phases, dependencies | Short campaigns, hardcore Agile |
| **Milestones** | Key checkpoints, handovers | Flexible iterative work |
| **Timeboxing** | Agile, focusing work, recurring tasks | Long-term planning, Waterfall |
| **Sprint/Iteration** | Complex projects, hybrid approaches | Running multiple projects |

---

## Gantt Chart Types

| Type | Use Case |
|------|----------|
| **Phase-based** | Discovery → Design → Development → QA → Launch |
| **Resource-based** | Design team, Developer team |
| **Task-based with dependencies** | Granular task tracking |
| **Sprint-based** | Sprint 1 → Sprint 2 → Sprint 3 |

---

## Timeboxing

Think in half-day chunks (AM/PM). Plan for 6-hour days (3 AM + 3 PM), not 8.

```
Mon AM | Mon PM | Tue AM | Tue PM | Wed AM | Wed PM | Thu AM | Thu PM | Fri AM | Fri PM
```

10 blocks per week for billable work. Reserve some blocks for overflow.

### Timeboxing Formula

```
2 blocks/day × 5 days = 10 blocks/week
Each block ≈ 3 hours (6-hour day, not 8)
1 block = 0.5 day = ~3 hours
2 blocks = 1 day = ~6 hours
```

### Benefits of Days vs Hours

- Easily divisible
- Half day fits nicely into blocks
- Buffer built in
- Easier to multiply/divide
- Better matches monthly revenue cycles

---

## Buffer Strategies (Build These In)

| Buffer Type | Purpose |
|-------------|---------|
| **Project planning/roadmapping** | Team can't implement while planning |
| **Learning/onboarding time** | New technology, stakeholder training |
| **Internal team reviews** | 1-2 days before external handover |
| **Stakeholder reviews** | First review takes longest; shorten subsequent rounds |
| **Quality Assurance** | Minimum 2 weeks at end; regular QA between handovers |
| **Holidays/PTO** | Check quarterly with staff; stagger roles so skills always available |
| **Illness/unexpected** | Flu season Oct-May; send sick people home |
| **Celebrations** | Don't schedule launches on birthdays/anniversaries |
| **Phase transitions** | 1-2 week buffer between launches and new starts |

**Default rule:** 10% buffer minimum at each major milestone

---

## Scheduling Considerations

### For Your Team

- What are they already working on? (3-6 month window)
- Anyone new needing onboarding?
- Remote teammates? Time zones?
- Need contractors?

### For External Stakeholders

- How many reviewers? (Each person adds days/weeks/months)
- Direct access to POC?
- Vacations, part-time schedules?
- Expect 5-10 hours/week from stakeholders

---

## Warning Signs (Project Drag)

- Tasks taking 20%+ longer than estimated
- Blocked items remaining blocked >48 hours
- Stakeholder reviews extending beyond scheduled time
- Team velocity declining sprint-over-sprint

---

## Adjusting Schedules

### Watch for Red Flags

- Contact goes silent
- New stakeholders appear
- Goals/vision change
- Hidden complexity discovered
- Change requests flood in

### When Adjusting, Ask

- What happened and how does this affect timeline?
- How much more time do we need?
- How will this affect budget?
- Who pays for this time?

**Brooks' Law:** Adding developers to a late project makes it later (onboarding time).

---

## Scheduling Don'ts

- Lock into firm deadlines (most are false unless public launch)
- Let non-implementers create schedules
- Think in hours when planning (use days)
- Schedule launches at end of week (no weekend work)
- Schedule multiple launches same week

---

## What Is Capacity Planning?

Determining how many staff and how much time on particular tasks/projects over a given period. A measure of **effort over time**.

**Utilization rate:** Amount of billable hours as percentage of total hours available.

**Warning:** Utilization historically was designed to measure enslaved people's output. Be mindful of how data is used. Humans are not units of work.

---

## Optimal Capacity

| Metric | Reality |
|--------|---------|
| Traditional optimal | 70-80% (28-32 productive hrs/week) |
| Reality | People do 5-6 hours of "real work" per day |
| **Your team's capacity** | **6 hours/day, not 8** |
| Build for | 25-30 billable hours/week, not 40 |

---

## Why Capacity Planning Matters

- Plan accurate team schedules across projects
- Determine when to book next project
- Monitor actual vs estimated time
- Forecast future project needs
- Use historical data for better estimates
- Push back on requests with real data

---

## Capacity Planning Impacts

- Prevents project lag from overbooked team members
- Provides accurate view of timeline factors
- Predicts when stakeholders need to be more active
- Protects team members' time
- Flags dangerous budget burn rates
- Plans for contractor needs in advance

---

## Think in Threes

**Goal:** Never work on more than 3 projects at any given time.

### Benefits

- Reduces plate-spinning
- Allows focus
- Easier allocation and forecasting

**Your ultimate goal:** Reduce simultaneous projects, break big into smaller, increase overall value, focus team's time, prioritize deadlines over hourly tracking.

---

## Building Buffer by Default

Reserve blocks for:
- Planning and check-ins
- Updates and reviews
- Fun/learning
- Focused productive work
- Flexible time (meetings, internal projects)

**Example:** Reserve Fridays for internal planning, learning, and org improvement.

---

## Capacity Formula

```
Team member capacity = Time booked per [period] / Working time in [period]
```

**Example:** Harley works 2 days/week on Project A, available 5 days/week:
- 2/5 = 40% capacity on this project
- 60% available for other projects

---

## Don't Book at 100%

Creates impossible targets. Team cups overflow, can't accommodate changes. Aim for 5-6 billable hours/day maximum.

---

## When to Plan Capacity

### At Project Start

- Names and roles with rough availability
- Time per role per week/sprint
- Compare against schedule and milestones

### During Project

- Adjust for actual vs estimated
- Team satisfaction with pace
- Future capacity changes (illness, holidays, new hires)
- Schedule changes and emergencies

### After Project

- Did you allocate enough time?
- Did you meet deadlines?
- What would you do differently?

---

## Capacity Planning Considerations

### Before Starting

- Team time off/vacation entered?
- Holidays coming up?
- Flu season? (With COVID, perpetually)
- Staffing changes?

### From Stakeholders

- Major company holidays
- Stakeholder vacations
- Other launches/events mid-project

### During Planning

- Does project length cover expenses?
- Team dedicated or shared?
- Other PMs plotting capacity? Sync up!
- How many other projects active/pipeline?
- Non-billable time on this project?
- Contractors needed?
- High-touch or low-touch stakeholders?

---

## Managing Personal Capacity

### Your Calendar is Sacred

- Build time for ramp-ups and big meetings
- Don't feel bad saying no
- Remember 40% time lost to task switching
- Turn off alerts and disturbances
- Track your own capacity

### Know Your Limits

- How many hats are you wearing?
- Different project types with different priorities?
- Historic project data—where do you get bogged down?
- Calculate your minimum project setup requirements

---

## Resourcing & Team Selection

### What is Resourcing?

Selecting who or what's needed to work on projects. Resources include humans, equipment, materials, facilities, and funding.

**Golden rule:** Never forget you're working with flesh and blood humans who have families, fears, failures, dreams, and quirks. Treat people well and don't take them for granted.

### Securing the Right People

1. Cross-check skills required against talent available
2. Assess availability for upcoming projects
3. Reach out and involve in project handover meeting

### Questions Before Booking Someone

- Do they have the skills? (Check past work)
- How many projects are they currently on?
- Do their projects drag?
- Full-time or part-time? Can they commit?
- Are they reliable with deadlines?
- Employees or contractors?
- Do they look tired? Need a change of pace?
- Are they excited about the project?
- Do they work well with others?

---

## Employees vs Contractors

| Factor | Employees | Contractors |
|--------|-----------|-------------|
| Cost | Generally less long-term | Higher hourly, but no benefits |
| Availability | Consistent | Fill shorter gaps |
| Investment | Company culture | Less connected |
| Risk | Company carries | Contractor carries |
| Onboarding | More investment | Need solid system |

### When to Bring in Contractors

- No one available for weeks on larger project
- Team lacks required skills
- Looking to expand capacity but can't commit to hiring
- Have solid onboarding process
- Great leadership to direct them

### When to Hire Employees

- Hit capacity with consistent work
- 3-6 months of work in pipeline
- Looking to specialize or grow expertise
- Need to smooth out capacity issues

---

## See Also

- `estimation.md` - Creating time estimates
- `pricing.md` - Converting time to billing
- `methodology.md` - Sprint and iteration planning
- `worked-examples.md` - Capacity planning walkthrough
