# Scoping Framework

> **Related sections:** → Estimation (`estimation.md`) → Change Control (`change-control.md`) → Stakeholders (`stakeholders.md`)

## What Is Scope?

**As a noun (build the right thing):**
- Goals
- Size
- Complexity
- Functionality

**As a verb (build it the right way):**
- Processes
- Involvement
- Effort
- Acceptance criteria
- Constraints
- Assumptions
- Timelines
- Budgets

**Scope = "The pieces of the puzzle AND how you put those pieces together."**

---

## Product Scope vs Project Scope

| Type | Definition | Examples |
|------|------------|----------|
| **Product scope** | What you're building (features, deliverables) - the nucleus | Homepage, API, mobile app |
| **Project scope** | What it takes to build it (process, meetings, documentation) - the jelly | Kickoffs, reviews, QA rounds |

---

## Cone of Uncertainty

At beginning of project, you know the LEAST about all moving pieces. As you work through and understand audience/stakeholder needs, you gain more certainty.

**This is why discovery matters.** Promising too early = problems.

---

## Scoping Is a Team Sport

**Don't figure it out alone.** Your perception is just one piece of the whole.

"It takes the whole circle to complete the picture."

- People doing the work must scope it
- Rely on team and stakeholders to complete the pieces
- Ask questions - they are the lightswitch in a dark room

---

## Requirements Types

| Type | Focus | Tests |
|------|-------|-------|
| **Functional** | WHAT and WHY of product | Did we build the right thing? |
| **Non-functional** | HOW and HOW NOT (limits, parameters) | Did we build it the right way? |
| **Business** | WHY (org-wide goals) | Did we build the right thing? |

---

## Requirements Gathering

Start with nouns (deliverables) then list verbs (processes). Several verbs add up to a noun.

### Discovery Workshop Steps

1. List big items (card sort, sketching)
2. Break into smaller items (one person, one day achievable)
3. Include transition items (purchasing, reviews, approvals, onboarding)
4. Swap roles - have teams guess what teammates need to do
5. Prioritize together which features come first, last, or not at all

---

## Work Breakdown Structure (WBS)

Traditional method - 100% scope defined upfront.

**How to build:**
1. List all deliverables
2. Break into "work packages" (smallest bite-size pieces)
3. Stop when all parts add up to 100% of scope
4. Just nouns (deliverables), not verbs (actions)
5. Don't forget dependencies

**Best for:** Simple, repeatable projects (like identity design)
**Less good for:** Software projects that morph and change

---

## Backlog Approach (Agile)

Don't start with 100% scope upfront. Define, refine, add as you go.

| Type | Description |
|------|-------------|
| **Product backlog** | Things you'll likely tackle during product lifecycle - constantly prioritized and updated |
| **Sprint backlog** | Things you'll tackle in the explicit time chunk ahead - explicit commitment |

---

## Tasks, Subtasks, Milestones

### Task Format
```
As a [role], I will [action] so that [result]
```
Example: "As a designer, I will design the input form so dev can code it."

### User Story Format
```
As a [user], I want [action] so that [outcome]
```
Example: "As a patient, I want to view my records so I can track when I got sick."

### What Makes a Great Task

- Clear start and end
- Clear goal and outcome stated
- Can mark complete (observable criteria)
- One owner
- Completable in a day or two
- Descriptive enough to be understood by anyone

### Chores vs Tasks

**Chores:** Tasks providing value to team/product, not business value to external stakeholders (setting up environments, improving processes)

### Milestones

Date + deliverables list. Keep flexible with "anticipated milestones."

**Tip:** Don't tie invoices to milestones - if milestones slip, payments come late.

---

## What Gets Missed During Scoping

### Your Team Forgets

- Meetings and presentations
- Proper research/discovery time
- Travel time
- Bug fixing and testing
- Time for revisions
- Time for team communication

### Stakeholders Forget

- Copy, branded assets, translations
- Approvals and turnaround periods
- Board/exec/legal reviews (can be gargantuan)

---

## Acceptance Criteria Template

```
GIVEN [context/precondition]
WHEN [action/trigger]
THEN [expected outcome]
```

---

## Avoiding Scoping Pitfalls

### Test Assumptions

- "Can we know this to be true? How?"
- "Are we missing any pieces?"
- "What happens between X and Y?"
- "What surprises might we face?"

### Ask Stakeholders What They've Learned

"What's something you learned about this project/team that changed your approach?"

### Pre-Mortem ("What went wrong?" before you start)

"Pretend this project is finished. What went wrong and why? How did we fix it?"

### Don't Ignore Complexity (Bikeshedding)

Tendency to scope easy things thoroughly while rushing complex things. Break nuclear-plant-sized projects into phases.

### Create Scope Takeout Menu

If team creates similar deliverables repeatedly, create reusable scope menu with price ranges.

---

## Scope Protection Clauses

### Pause Clause

> "If any deliverable, approval, payment, or sign-off is more than [5] business days late, we'll put the project on hold and restart based on our availability."

### Mystery Voices Clause

> "All stakeholders who want a say must be present from kickoff. If new voices are added, we'll re-evaluate scope and provide estimate for additional time/budget."

### Mimic Clause

> "If any deliverable is delayed, all future dates will be extended by the same length. If launch date is non-negotiable, increased fee applies."

---

## Scope Creep Management

### What Is Scope Creep?

Surprise changes to scope that have you doing more work for the same time/money.

### Why It Happens

- Expectations, goals, and outcomes become misaligned
- Boundaries disappear
- Stakeholders discover what they want during the project
- Teams don't manage changes properly

### Who Pays?

| Cause | Who Pays |
|-------|----------|
| Your team caused it | You eat the cost |
| Client/miscommunication | They pay for additional work |
| Internal teams | Delays and low trust |

### Impact of Unmanaged Scope Creep

- Goals and outcomes change
- Stakeholder relationships suffer
- Timeline and budget stretch
- People lose faith in successful launch
- Teams get stressed, people may quit
- More projects come in to close revenue gaps
- Cycle repeats

---

## Four Types of Scope Creep

### 1. Business Scope Creep

Stakeholders change their mind, understanding, roles, process, or priorities. Also happens when you fix the problem before understanding it.

**Warning signs:** New stakeholder voices, shifting goals, assumption-based work
**Fix:** Document everything, check alignment regularly, use Mystery Voices clause

### 2. Effort Creep

Wheels spinning in mud. No matter how much effort, you can't get closer to finish line. Can spend 80% of budget on last 20% of scope.

**Warning signs:** High priority items becoming high effort, anxiety rising, people cutting corners
**Causes:** Skills shortage, optimism about work involved, shifting priorities
**Fix:** Call for help, have tough conversations, admit you need more time/budget

### 3. Hope Creep

Lying to yourself/team/clients that you can meet deadlines when you can't. "Nobody wants to let anyone down, so everyone lets everyone down."

**Warning signs:** Silence, vigorous nods, responses don't match behavior, high stress with "everything's fine"
**Fix:** Quit lying, build trust, create open learning environment

### 4. Feature Creep (Gold Plating)

Adding unnecessary features even when nobody requested them. Desire for perfectionism or overwhelming need to please.

**Warning signs:** Hand-illustrating when stock would do, overengineering simple requests
**Fix:** You have full control - can say no, delay, or charge more

---

## Triage Framework

| Action | When |
|--------|------|
| **Dismiss** | Not aligned with project goals |
| **Downgrade** | High effort, low impact → backlog or dismiss |
| **Defer** | High effort, high impact → future phase (unless central to functionality) |
| **Prioritize** | Low effort, high impact → do now (highest value, least disruption) |

---

## Scope Creep Scripts

**When a new request comes in:**
> "Got it. Let me check with the team on how this impacts our timeline and budget. I'll get back to you by [date]."

**When you need to say no:**
> "This is a great idea for the future. Let's add it to the backlog for phase two so we can stay focused on our current goals."

**When scope is clearly expanding:**
> "This would add [X days/dollars] to the project. Do you want me to quote it as an addition, or should we swap it for something in the current scope?"

**When someone says "Can you just...":**
> "There's no such thing as 'just' in project work. Let me estimate what this actually involves and get back to you."

**When hope creep is happening:**
> "I'm concerned we're not being realistic about the timeline. Can we look at what's actually left and adjust expectations now rather than miss the deadline?"

**When a stakeholder goes silent after feedback:**
> "I noticed you haven't responded to the designs. Is everything okay? If there are concerns, I'd rather hear them now so we can address them."

---

## Tips for Managing Change

- Make bullet list of what you've already provided in scope
- Take time to get thoughts straight - you don't need an answer on the spot
- You're only responsible for your half of any relationship
- You can't make people do what they don't want - but can provide guidance
- If you don't catch something immediately, there's usually still time to undo damage

---

## See Also

- `change-control.md` - Processing change requests
- `estimation.md` - Estimating scope
- `stakeholders.md` - Alignment and communication
- `scripts.md` - More communication scripts
