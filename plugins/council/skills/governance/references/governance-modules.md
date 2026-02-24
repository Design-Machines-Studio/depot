# Co-op OS Governance Modules

> **Related sections:** → BC Act Requirements (`bc-cooperative-act.md`) → Discovery Framework (`discovery-framework.md`) → UX Testing (`ux-testing.md`)

## Module Architecture Overview

Co-op OS uses a tiered module architecture. Clients don't see "modules"—they get a bespoke system built from these building blocks.

**Positioning**: "Your [Co-op Name] OS"—not "an installation of Co-op OS"

---

## Tier Structure

### MVP Tier (Essential for Pilot)

| Module | Purpose | Core Features |
|--------|---------|---------------|
| **Members** | Who belongs | Profiles, classes, lifecycle, directory |
| **Governance (Basic)** | How decisions are made | Decisions, meetings, simple voting |
| **Records & Compliance** | Statutory requirements | Member register, director register, minutes |
| **Calendar** | Annual rhythm | AGM tracking, reminders, compliance dates |

### Core Tier (Standard Implementation)

| Module | Purpose | Core Features |
|--------|---------|---------------|
| **Equity** | Ownership tracking | Shares, ICAs, redemption, patronage |
| **Documentation** | Knowledge management | Policies, version control, SOPs |
| **Governance+** | Advanced decisions | Proposals, workflows, proxy management, COI |

### Advanced Tier (Full Implementation)

| Module | Purpose | Core Features |
|--------|---------|---------------|
| **Compensation** | Fair pay framework | Factor-based salary, ratios, transparency |
| **Real-time** | Live collaboration | Live voting, collaborative editing |
| **Integrations** | External connections | Financial systems, Slate, communication tools |

---

## Module Specifications

### Members Module (MVP)

**Purpose**: Track who belongs to the cooperative and their status.

#### Data Model

```
Member
├── profile (name, contact, bio, photo)
├── class (worker, community, investment shareholder)
├── status (candidate, active, withdrawn, terminated)
├── dates (application, probation_start, membership_effective, exit)
├── roles (member, director, officer, committee)
└── employment (if applicable: start_date, hours, wage)
```

#### Features

| Feature | Description | Statutory Basis |
|---------|-------------|-----------------|
| Member directory | Searchable list with contact info | — |
| Lifecycle tracking | Application → Candidacy → Active → Exit | Rules of Association |
| Class assignment | Worker, community, investment shareholder | s.48, Rules |
| Role management | Directors, officers, committee membership | s.72 |
| Residency tracking | Canadian/BC for director requirements | s.99 |
| Member count alert | Warning below 3 members | s.39 |

#### Workflows

1. **New member application**
   - Application submitted
   - Board review
   - Probationary period begins
   - Eligibility confirmed (hours, time, buy-in)
   - Board approval
   - Membership effective

2. **Withdrawal**
   - Written notice submitted
   - Share certificates surrendered
   - Redemption scheduled
   - Membership ceased

3. **Termination**
   - Grounds identified (Rule 17)
   - Meeting called (3/4 of directors)
   - Decision recorded
   - Appeal window
   - Share redemption scheduled

---

### Governance Module (MVP + Advanced)

**Purpose**: Track how decisions are made and recorded.

#### Core Concepts

```
Decision Chain
Proposal → Discussion → Vote/Consent → Resolution → Minutes
```

#### MVP Features

| Feature | Description |
|---------|-------------|
| Decision recording | Log decisions with rationale, votes, dissent |
| Meeting management | Schedule, agenda, attendance, minutes |
| Simple voting | Yes/no/abstain counting |
| Quorum calculation | Based on configured rules |
| Resolution archive | Searchable history of all decisions |

#### Advanced Features (Governance+)

| Feature | Description |
|---------|-------------|
| Proposal workflow | Draft → Review → Present → Decide |
| Ballot management | Named vs. anonymous, proxy assignment |
| Conflict of interest | Disclosure tracking, automatic abstention |
| Async voting | Time-boxed decisions between meetings |
| Consent resolutions | 100% written consent tracking |
| Modified consensus | Consent → Stand Aside → Block workflow |

#### Decision Types & Configuration

| Decision Type | Default Threshold | Override Source |
|---------------|-------------------|-----------------|
| Ordinary | 50% + 1 | — |
| Special | 66.67% (2/3) | Rules may specify 75% |
| Director removal | 75% (3/4 of all directors) | Act |
| Consent | 100% | — |

#### Meeting Types

| Type | Frequency | Governance Level |
|------|-----------|------------------|
| Operational | Weekly/bi-weekly | Team |
| Member meeting | Monthly | All members |
| Board meeting | Monthly+ | Directors |
| AGM | Annual | All members (required) |
| Special | As needed | Per trigger threshold |

---

### Equity Module (Core)

**Purpose**: Track member ownership, shares, and financial relationship.

#### Data Model

```
MemberEquity
├── membership_shares (count, value, paid)
├── investment_shares (if applicable: class, count, value)
├── internal_capital_account
│   ├── patronage_credits (retained)
│   ├── contributions (required buy-in)
│   ├── interest_credited
│   └── available_for_redemption
├── share_transactions (history)
└── patronage_allocations (history)
```

#### Features

| Feature | Description | Statutory Basis |
|---------|-------------|-----------------|
| Share register | All members' share holdings | s.48 |
| ICA tracking | Internal Capital Account balances | Rules |
| Patronage calculation | Based on configured method | Rules |
| Redemption workflow | Exit processing with solvency check | s.66 |
| Lien tracking | Outstanding debts against shares | s.56 |

#### Patronage Calculation Methods

| Method | Calculation | Best For |
|--------|-------------|----------|
| Hours worked | Surplus × (member_hours / total_hours) | Service co-ops |
| Wages earned | Surplus × (member_wages / total_wages) | Mixed-skill co-ops |
| Equal split | Surplus / member_count | Very small co-ops |
| Combined | Weighted formula | Professional services |

#### Solvency Check (Required)

Before any share redemption:
```
IF (assets - redemption_amount) < liabilities THEN
  BLOCK redemption
  ALERT: "Redemption would cause insolvency"
END
```

---

### Records & Compliance Module (MVP)

**Purpose**: Maintain statutory registers and compliance documentation.

#### Statutory Registers (Required)

| Register | Contents | Retention |
|----------|----------|-----------|
| Member register | Name, address, shares, dates | Permanent |
| Director register | Name, address, term, residency | Permanent |
| Meeting minutes | All general and board meetings | Permanent |
| Resolution register | All passed resolutions | Permanent |

#### Compliance Features

| Feature | Description |
|---------|-------------|
| Annual report generator | Pre-filled from member/director data |
| Director change alerts | 14-day filing reminder |
| Financial statement distribution | Track 10-day AGM requirement |
| Record retention policies | Automated alerts for 7-year documents |

---

### Calendar Module (MVP)

**Purpose**: Guide members through the annual governance rhythm.

#### The "Journey Through a Year"

| Period | Activities | Co-op OS Features |
|--------|------------|-------------------|
| **Daily** | Check pending proposals, action items | Dashboard, notifications |
| **Weekly** | Prepare for meetings, track time | Meeting prep, timesheet integration |
| **Monthly** | Member meetings, board meetings | Scheduling, agenda templates |
| **Quarterly** | Financial reviews, compliance checks | Reports, reminders |
| **Annually** | AGM, elections, audit, patronage | Annual workflow, document generation |

#### Key Date Tracking

| Date | Trigger | Alert |
|------|---------|-------|
| Fiscal year end | Start annual closeout | 30 days before |
| AGM deadline | Must hold within 15 months of previous AGM | 60 days before |
| Financial statements | 10 days before AGM | 14 days before |
| Annual report | 2 months after AGM | 30 days after AGM |
| Director terms | Track expirations | 60 days before |

---

### Documentation Module (Core)

**Purpose**: Manage policies, procedures, and institutional knowledge.

#### Document Types

| Type | Description | Versioning |
|------|-------------|------------|
| Policies | Board-approved guidelines | Full version control |
| SOPs | Standard operating procedures | Full version control |
| Templates | Meeting agendas, forms | Light versioning |
| Knowledge base | How-tos, FAQs | Wiki-style |

#### Features

| Feature | Description |
|---------|-------------|
| Version control | Track changes, who changed, when |
| Approval workflow | Draft → Review → Approve → Publish |
| Search | Full-text search across all documents |
| Access control | Member vs. board vs. public |

---

### Compensation Module (Advanced)

**Purpose**: Implement transparent, factor-based salary framework.

#### Salary Framework Factors

| Factor | Description | Weight Range |
|--------|-------------|--------------|
| Role/responsibility | Job complexity, decision authority | 1.0 - 1.5 |
| Experience/tenure | Years in field, years at co-op | 1.0 - 1.3 |
| Capacity | Hours per week | 0.4 - 1.0 |
| Location | Cost of living adjustment | 0.8 - 1.2 |

#### Ratio Constraints

| Constraint | Typical Range | Purpose |
|------------|---------------|---------|
| Max/min ratio | 2:1 to 5:1 | Compressed inequality |
| Role premium cap | 1.5x | Limit management premium |
| Tenure cap | 1.3x | Prevent seniority lock-in |

#### Formula Example

```
Base rate: $25/hour
× Role factor: 1.3 (lead)
× Experience factor: 1.15 (5 years)
× Capacity factor: 0.8 (4 days/week)
× Location factor: 1.0 (BC)
= $29.90/hour
```

---

## Module Dependencies

```
        Members (MVP)
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
Records  Calendar  Governance (MVP)
    │             │
    └──────┬──────┘
           ▼
    Documentation (Core)
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
Equity  Governance+ Compensation
    │              │
    └──────┬───────┘
           ▼
      Integrations
```

---

## Configuration by Client

Each module has configurable settings derived from bylaws:

| Setting Source | Configuration Type |
|----------------|-------------------|
| Rules of Association | Thresholds, quorum, terms |
| Board policies | Process details, workflows |
| Client preferences | UI, notifications, integrations |

---

## Implementation Approach

### Phase 1: MVP (Pilot)
Members + Basic Governance + Records + Calendar

See `docs/PILOT-SCOPE.md` in the Assembly repo for the detailed pilot checklist and acceptance criteria. The pilot ships Baseplate + Governance (Simple Mode) only.

### Phase 2: Core
Add Equity + Documentation + Governance+

### Phase 3: Advanced
Add Compensation + Real-time + Integrations

**Never deploy all at once.** Start simple, validate, expand. See `docs/DISTRIBUTION.md` for the phased distribution model.

---

*Reference v1.0 · February 2026*
*Part of Co-op OS Module Library*
