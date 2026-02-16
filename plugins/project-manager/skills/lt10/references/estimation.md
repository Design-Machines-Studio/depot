# Estimation Framework

> **Related sections:** → Risk Management (`risk.md`) → Change Control (`change-control.md`) → Pricing (`pricing.md`) → Scoping (`scoping.md`)

## Core Estimation Principles

### 1. Ranges Are More Important Than Hitting a Single Number

This is foundational to LT10 estimation. Ranges give you:
- More wiggle room for unknowns
- More chances to try something new
- Flexibility to prioritize nice-to-haves instead of brutal triage
- Protection when scope shifts slightly

The less certain you are, the wider the range should be. A range you can hit 9/10 times is infinitely more valuable than a single number you'll miss.

### 2. Share Your Confidence Level With the Range

Don't just give a range—tell stakeholders how confident you are:
> "We're 50% confident we can deliver in 4 weeks, but we're 90% confident we can in 6 weeks."

This builds trust and helps stakeholders make informed decisions about risk.

### 3. Estimates Are Never Optimistic

Estimates seldom fall on the low end (remember the Planning Fallacy). Set expectations for the higher number first. Good salespeople mention the higher number first, then the lower number second.

### 4. The People Doing the Work MUST Estimate It

Not executives, not salespeople, not project managers alone. Why:
- Team can vet the scope
- Executives are naturally optimistic (their job)
- Best/brightest teammates underestimate badly
- Sales can only sell best guesses

### 5. Estimate vs Budget - Know the Difference

| Type | Example | Purpose |
|------|---------|---------|
| **Estimate** | $20,000–$25,000 | Range with wiggle room for planning |
| **Budget** | $24,350 | Fixed hard stop for accounting |

When uncertain about scope, share the estimate (range). Lock in a budget only when scope is firm.

**Estimates are NOT commitments.** Scopes change, technologies shift, people leave.

---

## Estimation Methods

### 1. Top-Down Estimation (ROM)

For early-stage budgeting and feasibility:
- Rough Order of Magnitude: 25-75% accuracy
- Based on similar past projects or industry benchmarks
- Used for proposals, roadmap planning, revenue forecasting
- **Reference class estimation:** Using past projects to predict future ones

### 2. Bottom-Up Estimation

For detailed project planning using 90th percentile technique.

---

## The 90th Percentile Estimation Technique

This is a **conversation technique** for pulling realistic estimates from the people doing the work. It's not a formula—it's a process of challenging assumptions until you find a range you'd bet money on.

**The goal:** Find a range (low to high) that the person is 90% confident they'd hit 9 times out of 10 if they did the task repeatedly.

### Example Conversation

```
PM: "How long to design the logo sketches?"
Designer: "A few hours?"
PM: "What's the least and most time it could take?"
Designer: "Half-day to a full day."
PM: "Are you 90% confident? Remember there are 10 sketches 
     and 110 stakeholders. What could make it take longer?"
Designer: "Oh... maybe up to three days then."
PM: "If I bet you $1000 you could finish in 3 days, would you take it?"
Designer: "Ha, no. I'd say seven days to be sure."
PM: "Any other steps we should include?"
Designer: "Add time for high-fidelity lockups too."
PM: "So 0.5 days low, 9 days high? 90% confident?"
Designer: "Yes."
```

### Key Insight

The 90th percentile gives you a confident LOW-HIGH range. This is your internal foundation—but it's NOT what you quote to clients. You use red flags to calculate a midpoint, then present that midpoint with the range and red flags as justification.

### Questions to Model 90th Percentile

- Can you describe the process of approaching this task?
- How often does this take longer than [their high number]?
- What happens if you adjust/change/remove/add [Y]?
- What could make that number higher?
- When do things get complicated? What adds to complexity?
- Looking back at similar work, what went wrong? Add those up—what did we miss?

---

## Three-Point (PERT) Estimation

A separate technique that weights optimistic, likely, and pessimistic estimates:

```
Expected = (Optimistic + 4×Most Likely + Pessimistic) / 6
Standard Deviation = (Pessimistic - Optimistic) / 6
```

The result gives you a **68% confidence midpoint** on a bell curve.

**Use PERT when:** You want a weighted "expected" value
**Use 90th percentile when:** You want a confident upper bound

### Double Blind Estimating

Two similar roles estimate same task secretly, reveal simultaneously. If >20% different, discuss and re-estimate until <20% range.

### Planning Poker

For team-based consensus on story points/effort. Use Fibonacci: 0, 0.5, 1, 2, 3, 5, 8, 13, 20, 40, 100

---

## The Red Flags System

Red flags are observable warning signs that indicate risks. They're not the risks themselves—they're clues that help you predict which risks will manifest and how severely.

### What Red Flags Look Like

- Actions, reactions, changes, responses
- Things that used to be one way and now they're another
- Subtle differences that alert you to problems

### Red Flag Categories

| Category | Examples |
|----------|----------|
| **People** | Stakeholder alignment, team dynamics, availability |
| **Relationships** | Communication, cooperation, trust |
| **Schedules** | Time off, availability, project length |
| **Scope** | Features, complexity, creep patterns |
| **Money** | Payment delays, budget changes, overages |
| **Business** | Goals, viability, organizational health |

### Example Red Flags

- Stakeholders arguing about project direction
- Salesperson estimates without involving team
- Point of contact goes silent after seeing designs
- Developers regularly pulling all-nighters
- Designer using unfamiliar tool without onboarding
- "Can you just..." requests
- New decision-makers appearing late

### Why Red Flags Matter for Estimates

Red flags allow you to **narrow your estimates** because you can predict how risks will manifest in specific roles and tasks. They give you physical evidence to justify where on the bell curve your estimate will land.

---

## The Full LT10 Estimation System

**This is the complete process for creating defensible, evidence-based estimates:**

### Step 1: Get 90th Percentile Ranges

Use the conversation technique to get LOW and HIGH estimates for each project section that the team is 90% confident they'd hit 9/10 times.

```
Design:      Low: 30 days    High: 70 days
Content:     Low: 5 days     High: 10 days
Development: Low: 40 days    High: 80 days
PM:          Low: 15 days    High: 30 days
─────────────────────────────────────────
Total:       Low: 90 days    High: 190 days
```

### Step 2: Score Red Flags by Impact

For each red flag, score its impact on each project section (1-5 scale):

| Red Flag | Design | Content | Dev | PM |
|----------|--------|---------|-----|-----|
| Stakeholders arguing about direction | 4 | 2 | 3 | 1 |
| POC goes silent after designs | 2 | 1 | 4 | 5 |
| New technology, no onboarding | 4 | 4 | 4 | 5 |

### Step 3: Calculate Red Flag Percentage

For each section, add up actual points and divide by maximum possible:

```
Max possible = (# of red flags) × 5 points each

Design:  4+2+4 = 10/15 = 67%
Content: 2+1+4 = 7/15  = 47%
Dev:     3+4+4 = 11/15 = 73%
PM:      1+5+5 = 11/15 = 73%
```

### Step 4: Calculate the Midpoint

Use red flag percentages to find where on the bell curve each section lands:

```
Formula: ((High - Low) × RedFlag%) + Low = Midpoint

Design:  ((70-30) × 67%) + 30 = 56.8 days
Content: ((10-5) × 47%) + 5   = 7.35 days
Dev:     ((80-40) × 73%) + 40 = 69.2 days
PM:      ((30-15) × 73%) + 15 = 25.95 days
─────────────────────────────────────────
Total Midpoint: 159.3 days
```

### Step 5: Present to Client

Share the **midpoint** (~68% confidence) as your target estimate, with the full range and red flags visible:

> "We're estimating **159 days** for this project. The range could be as low as 120 days if things go smoothly, or as high as 190 days if we hit complications. Here's why we're landing toward the higher end: [list red flags]."

---

## What to Present vs. Keep Internal

| Audience | What to Share |
|----------|---------------|
| **Client** | Midpoint (~68% confidence) with red flags justifying position on range |
| **Internal** | Full 90th percentile range (low to high) |
| **Contract** | Midpoint as target, high end as "not to exceed" with change control |

**Key insight:** The 90th percentile high is your "if everything goes wrong" ceiling. You don't quote that—you quote the midpoint, supported by visible red flags that explain why you're where you are on the curve.

---

## Buffer Guidelines

| Situation | Buffer |
|-----------|--------|
| **Minimum project buffer** | 10-15% |
| **High-risk projects** | 20-30% |
| **Unknown technology** | +15% on technical tasks |
| **New team members** | +10% on their tasks |

---

## Estimation Pitfalls (Avoid These)

- Just doubling the budget (no science behind it)
- Estimating in hours (slip away like sand)
- Leaving out PM, admin, or buffer tasks
- Estimating in silos without the team
- **Refusing to provide ranges** - single numbers create false precision
- **Selling a fixed bid, one-line budget** - invites scope disputes
- Not estimating at all
- Not re-estimating when scope changes

---

## Human Biases in Estimation

| Bias | Impact |
|------|--------|
| **Planning Fallacy** | Think you'll do it faster this time (you won't) |
| **Parkinson's Law** | Work expands to fill time allotted |
| **Confirmation Bias** | Seek data that validates your beliefs |
| **Murphy's Law** | Anything that can go wrong will |

---

## Estimating Tips

- **Estimate in days, not hours** - more accurate, less micromanagement
- **Bill round numbers** - easier for stakeholders to say yes
- **Modular estimates** - group similar work types together
- **Sell packages + additions** - core package, extras by sprint
- **Avoid line items** - clients will cut and question individual items
- **15-30% of budget for PM time** - don't forget yourself
- **Get to MVP first** - break scope into phases, easier to digest and adjust

---

## See Also

- `worked-examples.md` - Complete estimation walkthrough examples
- `pricing.md` - Converting estimates to billing
- `risk.md` - Risk assessment and red flag details
- `scoping.md` - Scope definition before estimation
