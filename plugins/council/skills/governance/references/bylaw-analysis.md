# Bylaw Analysis Guide

> **Related sections:** → BC Act Requirements (`bc-cooperative-act.md`) → Discovery Framework (`discovery-framework.md`) → Financial Governance (`financial-governance.md`)

## Overview

Bylaw analysis extracts configuration requirements for Co-op OS. The goal isn't to understand every rule—it's to identify what the system must enforce, track, and support.

**Key insight**: Bylaws tell you what's required. Actual practice tells you what's working.

---

## Document Hierarchy

**Order of precedence (highest to lowest):**

1. **BC Cooperative Association Act** — Cannot be overridden
2. **Memorandum of Association** — Foundational document
3. **Rules of Association (Bylaws)** — Governance framework
4. **Board Policies** — Operational guidelines
5. **Custom Practice** — How things actually work

**When bylaws conflict with the Act**: Act always wins. Document the conflict and recommend bylaw amendment.

---

## Complete Extraction Checklist

### Part 1: Membership Structure

| Requirement | Bylaw Reference | Co-op OS Config |
|-------------|-----------------|-----------------|
| Member classes defined | Part 2, Rule 12 | Member type definitions |
| Eligibility requirements | Rule 5-8 | Application form fields |
| Age requirement | Rule 8 | Validation rule |
| Probationary period length | Rule 12 | Candidacy workflow |
| Minimum share requirement | Rule 9 | Share assignment |
| Worker member hours threshold | Rule 12 | Eligibility calculation |
| Community member terms | Rule 12 | Alternate workflow |
| Membership fee/buy-in amount | Varies | Payment tracking |
| Vesting schedule | If specified | Equity module |
| Exit/withdrawal terms | Rule 14-15 | Withdrawal workflow |
| Expulsion process | Rule 17-18 | Termination workflow |
| Death/bankruptcy handling | Rule 16 | Automatic workflow trigger |
| Joint membership allowed? | Rule 20 | System restriction |

**Sample extraction (LT10 bylaws):**
```
Member Classes: 2 (Worker Members, Community Members)
Worker eligibility: 19+, 1 year employment, 1000 hours worked, 10,000 shares
Community eligibility: 19+ or org, terms agreement, 100 shares
Withdrawal: Written notice + share surrender
Termination grounds: Detrimental conduct, unpaid dues, breach, 2-year inactivity
Appeal: General meeting, simple majority confirms termination
```

---

### Part 2: Voting & Decisions

| Requirement | Bylaw Reference | Co-op OS Config |
|-------------|-----------------|-----------------|
| Voting rights by member class | Part 2, Part 8 | Permission system |
| Quorum - general meetings | Rule varies | Meeting validation |
| Quorum - board meetings | Rule varies | Meeting validation |
| Ordinary resolution threshold | Default 50%+1 | Decision type |
| Special resolution threshold | Default 2/3 | Decision type |
| Decisions requiring supermajority | List specific | Decision categorization |
| Decisions requiring unanimous consent | List specific | Decision categorization |
| Consensus definition | Rule 1 | Decision workflow |
| Proxy voting allowed? | Part 8 | Ballot configuration |
| Proxy restrictions | BC Act rules | Validation rules |
| Absentee/async voting rules | Rule varies | Async voting module |
| Tie-breaking method | Rule varies | Calculation rule |
| Chair's casting vote? | Rule varies | Tie-break config |

**Sample extraction (LT10 bylaws):**
```
Consensus defined: "Decision approved when no person entitled to vote opposes"
Ordinary resolution: 50%+1 of votes cast
Special resolution: 2/3 of votes cast
Director termination of membership: 3/4 of all directors
Proxy: BC Act restrictions apply (>80km, member holder, max 3)
```

---

### Part 3: Meetings & Governance Bodies

| Requirement | Bylaw Reference | Co-op OS Config |
|-------------|-----------------|-----------------|
| AGM timing requirements | Rule varies | Calendar module |
| First AGM deadline | 15 months from incorporation | Compliance alert |
| Subsequent AGM spacing | ≤15 months apart | Calendar validation |
| Special meeting trigger | % of members to call | Request workflow |
| Board composition requirements | Rule varies | Director tracking |
| Director term lengths | Rule varies | Term expiration |
| Officer roles required | Rule varies | Role definitions |
| Committee structure | Rule varies | Committee tracking |
| Notice period - ordinary | Rule varies | Notification lead time |
| Notice period - special | Rule varies | Notification lead time |
| Electronic meeting permitted? | Usually yes | Meeting type options |
| Adjourned meeting rules | Rule varies | Continuation workflow |

**Sample extraction (LT10 bylaws):**
```
Board: Minimum 3 directors, majority Canadian, ≥1 BC resident
Non-member directors: Allowed up to 20% if board ≥5, max 1 community member
Terms: Per election (specify in discovery)
Officers: Chair, Secretary, Treasurer (Secretary-Treasurer may combine)
Committee formation: By board resolution
Notice: 7 days ordinary, 14 days special/AGM
```

---

### Part 4: Financial & Patronage

| Requirement | Bylaw Reference | Co-op OS Config |
|-------------|-----------------|-----------------|
| Fiscal year end date | Rule varies | Calendar configuration |
| Share value | Memorandum | Equity tracking |
| Patronage calculation method | Rule varies | Patronage formula |
| Patronage distribution timeline | Rule varies | Calendar/notifications |
| Deferred bonus treatment | Rule 1 definition | Patronage type |
| Internal Capital Account rules | Rule varies | ICA module |
| Interest on member equity | Rule varies | ICA calculations |
| Reserve fund requirements | Rule varies | Financial tracking |
| Surplus allocation sequence | Rule varies | Distribution workflow |
| Audit requirements | BC Act | Compliance tracking |
| Financial statements distribution | 10 days before AGM | Notification rule |
| Borrowing powers | Part 4 | (Usually board tracked) |
| Lien on shares | s.56 automatic | Equity module |

**Sample extraction (LT10 bylaws):**
```
Share structure: Membership shares ($1 par) + Investment shares (optional)
Worker member buy-in: 10,000 shares ($10,000)
Community member buy-in: 100 shares ($100)
Deferred bonus: "Distribution of income from employment calculated and treated as patronage return"
Redemption: Subject to solvency test
```

---

### Part 5: Records & Compliance

| Requirement | Bylaw Reference | Co-op OS Config |
|-------------|-----------------|-----------------|
| Required records to maintain | Part 27 | Records module |
| Record retention periods | BC Act | Retention policies |
| Member access to records | Rule varies | Permission system |
| Register of members | Required | Member register |
| Register of directors | Required | Director register |
| Minutes retention | Permanent | Minutes archive |
| Annual report deadline | 2 months after AGM | Compliance calendar |
| Director change filing | 14 days | Alert trigger |

---

## Red Flags in Document Review

### Missing or Vague

| Issue | Problem | Action |
|-------|---------|--------|
| No patronage calculation specified | Can't configure equity module | Needs resolution before build |
| "As determined by the board" for critical items | Who decides what? | Clarify in discovery |
| Missing quorum specification | Model Rules default (10%) may apply | Confirm intended quorum |
| No withdrawal process | Legal gap | Advise bylaw amendment |
| Vague membership eligibility | Disputes likely | Clarify criteria |

### Conflicts with BC Act

| Bylaw Says | Act Says | Resolution |
|------------|----------|------------|
| Proxy voting unrestricted | Must be >80km, member, max 3 | Act wins, flag for amendment |
| Non-member directors unlimited | Max 20% | Act wins, flag for amendment |
| No director residency mention | Majority Canadian, ≥1 BC | Must track regardless |
| Audit waived | Mandatory for worker co-ops | Cannot waive, inform client |

### Unusual Complexity

| Complexity | Concern | Approach |
|------------|---------|----------|
| 5+ member classes | System complexity | Simplify if possible |
| Complex patronage formula | Calculation errors | Document clearly, test thoroughly |
| Nested committee structure | Governance confusion | Map clearly |
| Multiple voting thresholds | User confusion | Clear UI labeling |

---

## Configuration Impact Matrix

| Bylaw Requirement | Co-op OS Module | Configuration Setting |
|-------------------|-----------------|----------------------|
| Member classes | Members | Member type definitions |
| Probationary period | Members | Candidacy workflow, timeline |
| Voting thresholds | Governance | Decision type settings |
| Quorum requirements | Governance | Meeting validation rules |
| Board terms | Members | Role expiration tracking |
| Patronage method | Equity | Calculation formula |
| Fiscal year | System | Calendar configuration |
| AGM timing | Governance | Annual calendar, reminders |
| Notice periods | Governance | Notification lead times |
| Share values | Equity | Share register config |

---

## Worked Example: LT10 Bylaws

### Key Configurations Extracted

**Membership Module:**
- Two classes: Worker, Community
- Worker eligibility: 19+, 1 year, 1000 hours, 10,000 shares
- Community eligibility: 19+ or org, 100 shares
- Withdrawal: Written notice + share surrender
- Termination: 4 grounds, 3/4 director vote, appeal to general meeting

**Governance Module:**
- Consensus definition: No opposition = passed
- Ordinary: 50%+1
- Special: 2/3
- Director termination: 3/4 of all directors
- Proxy: BC Act restrictions (>80km, member, max 3)
- Meetings: Board determined frequency, electronic permitted

**Equity Module:**
- Membership shares: $1 par value
- Worker buy-in: 10,000 shares
- Community buy-in: 100 shares
- Deferred bonus = patronage return treatment
- Redemption: Solvency test required

**Records Module:**
- Standard BC Act requirements
- Access governed by Act
- Retention governed by Act

---

## Analysis Workflow

### Step 1: First Read (30 min)
- Skim entire document
- Note structure (how many parts, what topics)
- Flag anything unusual

### Step 2: Systematic Extraction (2-3 hours)
- Work through checklist above
- Note exact rule numbers
- Flag gaps and conflicts

### Step 3: Conflict Resolution (30 min)
- Compare against BC Act requirements
- Document any conflicts
- Note Act provisions that override

### Step 4: Configuration Document (1 hour)
- Translate extractions to system settings
- Group by module
- Note any decisions needed

### Total Time: 4-6 hours for comprehensive analysis

---

*Reference v1.0 · February 2026*
*Part of Co-op OS Discovery Framework*
