---
name: governance
description: Worker cooperative governance expertise for BC Cooperative Association Act compliance, bylaw analysis, discovery processes, and Co-op OS system design. Use when working with cooperatives, analyzing bylaws, designing governance systems, conducting discovery for Co-op OS projects, interpreting voting thresholds, patronage allocation, member equity, compliance requirements, or any worker cooperative governance questions. Specializes in small worker cooperatives (5-50 members) in British Columbia, Canada. For values-aligned terminology and content strategy, also load the language skill in this plugin.
---

# Co-op Governance Skill

Comprehensive worker cooperative governance expertise for designing, testing, and implementing Co-op OS systems. Based on BC Cooperative Association Act requirements and real-world cooperative governance experience from Louder Than Ten Workers' Cooperative.

## Quick Reference: BC Cooperative Association Act Essentials

**Statute**: SBC 1999, c.28 | **Regulation**: B.C. Reg. 391/2000 (Model Rules in Schedule B)

### Core Statutory Requirements
| Requirement | Statutory Reference | Co-op OS Tracking |
|-------------|---------------------|-------------------|
| Minimum members | s.10(2) - at least 3; s.10(3) - 6-month grace | Member count alert |
| Director residency | s.72(1)(a) majority Canadian; s.72(1)(b) ≥1 BC | Director register |
| Board composition | s.72(1) ≥3 directors; s.72(3-4) max 1/5 non-member | Director roles |
| Annual report | s.126 - within 2 months after AGM | Compliance calendar |
| AGM timing | s.143 - first within 15 months of incorporation, then ≤15 months apart | Meeting scheduler |
| Director changes | s.127 - file within 14 days | Notification system |
| Financial statements | s.153(1)(b)(iv) - 10 days before AGM | Document distribution |
| Audit requirement | s.108 - required unless s.109 exemption applies | Financial tracking |

### Voting Thresholds (Memorize These)
| Resolution Type | Threshold | Common Uses |
|-----------------|-----------|-------------|
| Ordinary | 50% + 1 of votes cast | Budgets, elections, routine business |
| Special | ≥ 2/3 of votes cast | Bylaw amendments, name changes, dissolution |
| Director termination | 3/4 of all directors | Requires specific meeting |
| Consent resolution | 100% written consent | Substitute for meeting |

### Proxy Voting Restrictions (BC Act)
- **Distance requirement**: Member must live >80km from meeting location
- **Proxy holder**: Must be another member
- **Limit**: No member may hold >3 proxies
- **Most worker co-ops**: Prohibit proxy voting entirely, favor electronic participation

### Notice Requirements
| Notice Type | Minimum Days |
|-------------|--------------|
| Ordinary meeting | 7 days |
| Special resolution meeting | 14 days |
| AGM | 14 days |
| Financial statements before AGM | 10 days |

### Recommended Quorum by Size (Co-op OS Defaults)
| Co-op Size | Quorum Recommendation |
|------------|----------------------|
| 5-10 members | 50-75% |
| 11-25 members | 33-50% |
| 26-50 members | 25-33% |

**Warning**: If quorum not achieved, meeting adjourns 1 week → those present become quorum regardless of number.

---

## Domain Reference Guide

Load specific reference files based on needs:

| Topic | Reference File | When to Load |
|-------|----------------|--------------|
| **BC Act Requirements** | `references/bc-cooperative-act.md` | Statutory compliance questions |
| **Co-op OS Modules** | `references/governance-modules.md` | System design, feature planning |
| **Discovery Framework** | `references/discovery-framework.md` | New client onboarding |
| **Bylaw Analysis** | `references/bylaw-analysis.md` | Interpreting co-op rules |
| **Voting & Decisions** | `references/voting-decisions.md` | Decision types, thresholds |
| **Financial Governance** | `references/financial-governance.md` | Equity, patronage, ICAs |
| **Compliance Calendar** | `references/compliance-calendar.md` | Annual requirements |
| **Red Flags & Risks** | `references/red-flags.md` | Warning signs, common issues |
| **UX Testing** | `references/ux-testing.md` | Personas, test scenarios |

---

## Co-op OS Module Architecture

### Tier Structure (Progressive Implementation)

**MVP Tier** (Essential for pilot):
- Members module (profiles, classes, lifecycle)
- Governance module (basic decisions, meetings)
- Records & Compliance (statutory registers)
- Calendar & Reminders (annual rhythm)

**Core Tier** (Standard implementation):
- Equity module (shares, ICAs, redemption)
- Documentation (policies, version control)
- Advanced Governance (proposals, workflows)

**Advanced Tier** (Full implementation):
- Compensation (factor-based salary framework)
- Real-time features (live voting, collaboration)
- Integrations (financial systems, Slate)

### The "Journey Through a Year" Paradigm

Co-op governance is a rhythm, not a dashboard. Co-op OS guides members through:
- **Daily**: Pending proposals, action items
- **Weekly**: Meeting preparation, decision tracking
- **Monthly**: Member meetings, board meetings, operational reviews
- **Quarterly**: Financial reviews, compliance checks
- **Annually**: AGM, elections, audit, patronage allocation, annual report

---

## Discovery Process Overview

### Three Engagement Scenarios

**Scenario A: New Co-op (No existing systems)**
- Focus: Governance design from scratch
- Timeline: 4-6 weeks discovery
- Key activities: Founder interviews, governance design workshop, bylaw review

**Scenario B: Business Conversion (Some systems, needs new)**
- Focus: Migration + new governance layer
- Timeline: 6-8 weeks discovery
- Key activities: Current state audit, data migration planning, change management

**Scenario C: Existing Co-op (Systems in place, room for improvement)**
- Focus: Enhancement + consolidation
- Timeline: 4-6 weeks discovery
- Key activities: Pain point prioritization, system integration, training

### Standard Discovery Deliverables
1. Stakeholder Map (roles, alignment, concerns)
2. Governance Requirements Extract (from bylaws)
3. Current State Documentation
4. Risk Assessment (red flags identified)
5. Scope Document (what we're building)
6. Success Metrics (how we'll measure)

---

## Bylaw Analysis Checklist

### Critical Configuration Requirements to Extract

**Membership Structure**:
- [ ] Member classes defined
- [ ] Eligibility requirements
- [ ] Probationary period length
- [ ] Membership fee/buy-in amount
- [ ] Vesting schedule (if any)
- [ ] Exit/withdrawal terms
- [ ] Expulsion process

**Voting & Decisions**:
- [ ] Voting rights by member class
- [ ] Quorum requirements (general meetings)
- [ ] Quorum requirements (board meetings)
- [ ] Simple majority threshold
- [ ] Supermajority threshold and triggers
- [ ] Decisions requiring supermajority (list)
- [ ] Decisions requiring unanimous consent (list)
- [ ] Proxy voting rules
- [ ] Absentee/async voting rules

**Meetings & Governance Bodies**:
- [ ] AGM timing requirements
- [ ] Special meeting trigger (% of members to call)
- [ ] Board composition requirements
- [ ] Board term lengths
- [ ] Officer roles required
- [ ] Committee structure
- [ ] Notice periods for meetings

**Financial & Patronage**:
- [ ] Fiscal year end date
- [ ] Patronage calculation method
- [ ] Patronage distribution timeline
- [ ] Internal Capital Account rules
- [ ] Interest on member equity
- [ ] Reserve fund requirements
- [ ] Audit requirements

### Bylaw vs. Act Conflicts Resolution
**Order of precedence**: Act > Rules > Policies > Custom

When bylaws conflict with the BC Act:
1. Act always wins—bylaws cannot override statutory requirements
2. Document the conflict in discovery findings
3. Advise bylaw amendment to avoid confusion
4. Configure Co-op OS to enforce Act requirements
5. Flag for legal review if significant conflicts exist

---

## Red Flags Quick Reference

### Discovery Red Flags
| Flag | Severity | Mitigation |
|------|----------|------------|
| Stakeholders argue about direction | High | Alignment workshop before build |
| Point of contact goes silent | High | Escalation protocol needed |
| No budget clarity | High | Clarify before scoping |
| "Everyone decides everything" | Medium | Governance design needed |
| One founder dominates | Medium | Document power dynamics |
| Vague decision-making process | Medium | Design clear workflows |
| No one can articulate 90-day plan | Medium | Discovery needs more depth |

### Compliance Red Flags
| Issue | BC Act Requirement | Risk |
|-------|-------------------|------|
| Fewer than 3 members for >6 months | s.39 | Directors personally liable for debts |
| No BC resident director | s.99 | Filing may be rejected |
| Majority non-Canadian directors | s.99 | Non-compliance with Act |
| AGM not held within 15 months | s.143 | Court-ordered meeting |
| Annual report late | s.126 | $50/day fine, dissolution risk |
| Director changes not filed | s.125 | Up to $5,000 fine |

### Governance Health Red Flags
- Meeting minutes inconsistent or missing
- Members can't explain decision process
- Governance "owned" by one burned-out person
- Different members describe different processes
- System technically tracks governance but never referenced
- No clear distinction between governance and operations

---

## Decision-Making Models

### Model Comparison
| Model | How It Works | Best For |
|-------|--------------|----------|
| **Simple Majority** | 50%+1 passes | Routine decisions, quick choices |
| **Modified Consensus** | Try consensus, fall back to 75-80% supermajority | Most worker co-ops (recommended default) |
| **Sociocracy** | Consent-based ("safe enough to try?"), nested circles | Mature co-ops, complex governance |
| **Pure Consensus** | 100% agreement required | Very small groups, high-trust environments |

### Modified Consensus Process (Recommended)
1. Proposal presented
2. Questions for clarification
3. Discussion/amendment
4. Response options: **Consent** / **Stand Aside** / **Block**
5. If blocked: Further discussion or fall back to supermajority vote
6. If vote: 75-80% passes

### Decision Categorization for Co-op OS
| Category | Who Decides | Threshold | Examples |
|----------|-------------|-----------|----------|
| Operational | Manager/Team | N/A | Day-to-day work |
| Policy | Board | Ordinary | Budgets, work policies |
| Structural | Membership | Special | Bylaws, dissolution |
| Member Status | Board/Membership | Per bylaws | Admission, termination |

---

## Financial Governance Essentials

### Internal Capital Accounts (ICAs)
**What they track**:
- Member's patronage credits (retained)
- Interest paid on capital (if any)
- Required member contributions
- Available for redemption on exit

**Why they matter**:
- Fair entry/exit for members
- Clear ownership accounting
- Enables patronage-based allocation
- Supports solvency calculations

### Patronage Allocation Methods
| Method | Basis | Common In |
|--------|-------|-----------|
| Hours worked | Time contribution | Service co-ops |
| Wages earned | Economic contribution | Mixed-skill co-ops |
| Equal split | Per member | Very small co-ops |
| Combined | Hours + Performance | Professional services |

### BC Act Financial Requirements
- **Solvency test before share redemption**: Assets > Liabilities
- **Reserve fund**: Not mandated but strongly recommended
- **Audit**: Required for all worker co-ops (no small co-op exemption)
- **Financial statements to members**: 10 days before AGM

---

## Co-op OS Design Principles

### Core Philosophy
"Make governance feel like a rhythm, not homework."

### UX Principles
1. **Two audience design**: Worker-members need simplicity; compliance-savvy members need precision
2. **Progressive disclosure**: Show complexity only when needed
3. **Contextual education**: Learn through use, not upfront training
4. **Inhabited interfaces**: Living rhythm, not archived snapshots

### What Makes Co-op OS Different
| Generic Tools | Co-op OS |
|---------------|----------|
| Forcing co-op shapes into generic project tools | Purpose-built for cooperative governance |
| Enterprise solutions priced for large co-ops | Accessible to small co-ops ($5K-50K) |
| Install and figure it out | Consultation + training + bespoke system |
| Compliance-feeling bureaucratic interfaces | Designed to feel good, simple, expressive |
| Static request-response | Real-time collaboration, live voting |

---

## Cross-Reference Guide

| Topic | Related Sections |
|-------|------------------|
| Voting thresholds | → Bylaw Analysis, → Decision Models, → BC Act |
| Member equity | → Financial Governance, → ICAs, → Patronage |
| Compliance | → BC Act Requirements, → Compliance Calendar, → Red Flags |
| Discovery | → Three Scenarios, → Deliverables, → Red Flags |
| System design | → Module Architecture, → Journey Paradigm, → UX Principles |

---

## Cross-References

- **decolonial-language skill** (in this plugin): For values-aligned terminology, content strategy, and the three-layer architecture (legal → bridge → cultural) for member-facing communications. Use when naming UI elements, writing labels, or drafting member documents.
- **assembly plugin**: Technical implementation — Docker-based Go development, Templ templates, Datastar reactivity.
- **Assembly repo distribution docs**: `docs/DISTRIBUTION.md` (phased distribution — pilot → self-updating → platform), `docs/PILOT-SCOPE.md` (first client scope — governance Simple Mode, no proposals/async/proxy), `docs/UPDATE-FLOW.md` (update/rollback sequence).
