# Risk Management

> **Related sections:** → Estimation (`estimation.md`) → Change Control (`change-control.md`) → Stakeholders (`stakeholders.md`)

## Red Flags vs Risks

| Term | Definition |
|------|------------|
| **Red flag** | Observable clue (action, reaction, change, response) that alerts you to possible risk |
| **Risk** | Probability-based guess about good or bad events that will impact your project |
| **Issue** | When a risk happens, it becomes an issue |

---

## Risk Analysis Process

1. **Identify:** What risks are you concerned about?
2. **Assess:** How serious and likely are they?
3. **Mitigate:** How will you deal with the most serious?
4. **Plan:** Build contingency for prevention

---

## Red Flag Categories

| Category | What to Watch |
|----------|---------------|
| **People** | Stakeholders, team, resources |
| **Relationships** | Alignment, communication, cooperation |
| **Schedules** | Availability, time off, project length |
| **Scope** | Features, complexity, scope creep |
| **Money** | Delayed payments, overages, budget changes |
| **Business** | Goals, revenue, long-term viability |

---

## Common Red Flags

### People Red Flags
- Stakeholders arguing about direction
- Point of contact goes silent
- New decision-makers appearing late
- Team members pulling all-nighters regularly
- Key person leaving mid-project

### Relationship Red Flags
- Trust breakdown between team and client
- Passive aggressive communication
- Avoiding difficult conversations
- Blame-shifting patterns emerging

### Schedule Red Flags
- Tasks taking 20%+ longer than estimated
- Blocked items remaining blocked >48 hours
- Stakeholder reviews extending beyond scheduled time
- Team velocity declining sprint-over-sprint

### Scope Red Flags
- "Can you just..." requests
- Salesperson estimates without team
- Requirements changing after each review
- Features being added without change control

### Money Red Flags
- Delayed payments
- Client questioning every line item
- Budget concerns raised after kickoff
- "We didn't expect this to cost so much"

### Business Red Flags
- Unclear or shifting business goals
- Key stakeholder departure
- Company restructuring mid-project
- Competing internal priorities

---

## Types of Risk Responses

### Negative Risk Responses

| Response | When to Use |
|----------|-------------|
| **Escalate** | Bring up chain, note it, monitor (no control) |
| **Avoid** | Do whatever it takes to eliminate |
| **Transfer** | Transfer to someone who can handle it |
| **Mitigate** | Decrease severity |
| **Accept** | Take what comes |

### Positive Risk Responses (Opportunities)

| Response | When to Use |
|----------|-------------|
| **Exploit** | Eliminate uncertainty, make it happen |
| **Enhance** | Increase odds of payoff |
| **Share** | Go halfsies with stakeholders |
| **Accept** | Take what comes |

---

## Risk Matrix (Qualitative Assessment)

|  | Unlikely | Likely |
|---|----------|--------|
| **Severe Impact** | MODERATE (Avoid/Mitigate) | EXTREME (Mitigate/Manage) |
| **Insignificant Impact** | MINOR (Accept/Monitor) | MAJOR (Mitigate/Monitor) |

**Visibility line:** If seeing red flags → risks are in top two quadrants (certain)

---

## Risk Response Priority

| Priority | Condition | Action |
|----------|-----------|--------|
| 1. **Extreme risks first** | Severe + Likely | Active mitigation and management |
| 2. **Major risks** | Likely but low impact | Mitigate probability, control impact |
| 3. **Moderate risks** | Unlikely but severe | Avoid if possible, mitigate impact |
| 4. **Minor risks** | Unlikely + low impact | Accept and monitor |

---

## Contingency Planning

### Tips

- Act immediately (waiting increases impact)
- Involve team in plan creation
- Inform stakeholders on review
- Schedule regular check-ins to re-evaluate
- Adjust plan as risks change

---

## The Cassandra Effect

You will predict problems and be ignored. Work to get buy-in on risk analysis—it's worth it.

---

## Vicious Risk Cycle

```
Red flag → Risk → More related risks → More red flags → Snowball effect
```

Best time to halt risk is BEFORE it happens.

---

## Situational Awareness

Practice mindfulness to spot red flags:
- Active listening
- Challenging limiting beliefs
- Beginner's mind (stay open)

Watch for:
- Behavior changes
- Attitude shifts
- Discrepancies
- Tension
- Inability to voice concerns

---

## Risk Categories (Detailed)

| Category | Examples |
|----------|----------|
| **Business risks** | Market changes, stakeholder availability, funding |
| **Technical risks** | New technology, integration complexity, performance |
| **Resource risks** | Team availability, skill gaps, turnover |
| **Schedule risks** | Dependencies, approvals, external delays |

---

## Risk Register Template

| Risk | Probability | Impact | Score | Mitigation | Owner | Status |
|------|-------------|--------|-------|------------|-------|--------|
| Key developer leaves | Medium | High | 6 | Cross-train team, document code | PM | Monitoring |
| Client feedback delayed | High | Medium | 6 | Pause clause, weekly reminders | PM | Active |
| Scope creep | High | High | 9 | Change control process, Mystery Voices clause | PM | Monitoring |

---

## Project Health Indicators

### Green Status ✅
- On schedule (±5%)
- Within budget (±10%)
- No critical risks
- Stakeholders aligned
- Clear communication

### Yellow Status ⚠️
- Minor schedule slips (5-15%)
- Budget concerns emerging
- Manageable risks active
- Some stakeholder concerns

### Red Status 🔴
- Major delays (>15%)
- Over budget (>15%)
- Critical risks realized
- Stakeholder conflicts
- Communication breakdown

---

## Key Project Calculations

### Time Used/Remaining

```
% time used = (days used / total days) × 100
% time remaining = 100 - % time used
```

### Effort Completed/Remaining

```
% complete = (tasks completed / total tasks) × 100
```

### Budget Used/Remaining

```
% budget used = (budget spent / total budget) × 100
```

**Combining metrics:** 50% through tasks but 75% through schedule = tracking behind. Catch drag early.

---

## Qualitative Health Metrics

### Project Health: Red/Yellow/Green

| Status | Meaning |
|--------|---------|
| **Red** | Off rails, needs major TLC |
| **Yellow** | Needs significant response |
| **Green** | On track |

### Team Happiness

- Periodic surveys/check-ins
- Regular peer reviews
- Niko Niko calendar
- Ask how project is going

---

## Warning About Metrics

Metrics dehumanize people into economic units. Optimizing for squeezing more from people's time leads to overwork, stress, dishonest timesheets, culture of fear.

**Use metrics as a tool, not a weapon.** Put human team ahead of blinking data points.

---

## Buffer Guidelines (Risk-Based)

| Situation | Buffer |
|-----------|--------|
| Minimum project buffer | 10-15% |
| High-risk projects | 20-30% |
| Unknown technology | +15% on technical tasks |
| New team members | +10% on their tasks |
| First-time client | +15% overall |

---

## See Also

- `estimation.md` - Red flags in estimation
- `change-control.md` - Managing changes from risks
- `stakeholders.md` - Stakeholder risk patterns
- `scheduling.md` - Buffer strategies
