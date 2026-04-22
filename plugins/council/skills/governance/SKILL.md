---
name: governance
description: Worker cooperative governance expertise for BC Cooperative Association Act compliance, bylaw analysis, discovery processes, and Assembly system design. Use when working with cooperatives, analyzing bylaws, designing governance systems, conducting discovery for Assembly projects, interpreting voting thresholds, patronage allocation, member equity, compliance requirements, or any worker cooperative governance questions. While it specializes in BC, Canada (5-50 member worker co-ops), the decision-making models, red flags, discovery framework, and governance module architecture apply to cooperatives in any jurisdiction. Trigger this skill for ANY cooperative governance question — voting mechanics, quorum rules, AGM prep, member lifecycle, equity structures, consent-based decisions, board composition — even if the user doesn't mention BC specifically. Also trigger when discussing TACO, Solid State, or any Assembly pilot, when the user asks about co-op compliance deadlines, or when designing governance UI flows.
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
| **BC Act Requirements** | `${CLAUDE_SKILL_DIR}/references/bc-cooperative-act.md` | Statutory compliance questions |
| **Co-op OS Modules** | `${CLAUDE_SKILL_DIR}/references/governance-modules.md` | System design, feature planning |
| **Discovery Framework** | `${CLAUDE_SKILL_DIR}/references/discovery-framework.md` | New client onboarding |
| **Bylaw Analysis** | `${CLAUDE_SKILL_DIR}/references/bylaw-analysis.md` | Interpreting co-op rules |
| **Voting & Decisions** | `${CLAUDE_SKILL_DIR}/references/voting-decisions.md` | Decision types, thresholds |
| **Financial Governance** | `${CLAUDE_SKILL_DIR}/references/financial-governance.md` | Equity, patronage, ICAs |
| **Compliance Calendar** | `${CLAUDE_SKILL_DIR}/references/compliance-calendar.md` | Annual requirements |
| **Red Flags & Risks** | `${CLAUDE_SKILL_DIR}/references/red-flags.md` | Warning signs, common issues |
| **UX Testing** | `${CLAUDE_SKILL_DIR}/references/ux-testing.md` | Personas, test scenarios |

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
- **Audit**: Required unless s.109 exemption applies (registrar order needed; high burden for small co-ops)
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

## Systems Thinking for Governance Design

When designing or reviewing Assembly governance features, apply these lenses. The goal is to build governance structures that create healthy feedback loops — not just comply with the BC Act.

### Every Governance Feature Creates a Feedback Loop

Before building a feature, identify:

1. **What behavior does this reinforce?** A voting UI that shows live position distribution reinforces participation (people see their input matters). A voting UI that only shows a final tally reinforces passivity (people check the result, not the process).

2. **Is the loop reinforcing or balancing?** Reinforcing loops compound: participation → better decisions → trust → more participation. Balancing loops stabilize: complexity → member fatigue → low participation → poor decisions → more governance problems. Design for reinforcing loops. Watch for balancing loops that create governance debt.

3. **Where are the delays?** Senge: delays between action and consequence are where systems thinking falls apart. If a member submits a proposal and gets no feedback for two weeks, the delay kills the reinforcing loop. Assembly's real-time features (Datastar SSE, live positions, presence indicators) are delay-reduction tools.

### Archetype Risks in Governance Features

**Shifting the Burden:** Assembly handles something members should learn to do themselves. If the software auto-generates every resolution, members never develop governance literacy. The co-op becomes dependent on the tool instead of capable through the tool. **Design response:** Assembly should scaffold governance capacity, not replace it. Progressive disclosure: simple first, complexity available when members are ready.

**Fixes that Fail:** A feature solves an immediate governance pain but creates a new problem. Example: making voting frictionless might increase vote volume but decrease deliberation quality. **Design response:** Apply the design principle "comments are the democracy, vote is the conclusion." Don't optimize for vote throughput; optimize for decision quality.

**Success to the Successful:** Features that amplify existing power dynamics. If the loudest or most active members dominate because the UI rewards volume over equity, quieter members disengage. **Design response:** Show distribution not sums. Design for the quietest member, not the most active.

### The Kelly Test (from *Owning Our Future*)

Marjorie Kelly's core insight: **system structure is the source of system behavior.** The governance rules encoded in Assembly will determine how co-ops behave — not their stated values, not their bylaws on paper, but the actual feedback loops the software creates.

Ask: "If a co-op used Assembly exactly as designed, with no workarounds, would the resulting governance be healthy?" If the answer requires members to route around the tool (vote in Slack, discuss in DMs, track decisions in spreadsheets), the tool is failing.

### RAG Resources

Search the RAG for deeper material when designing governance features:

- `"feedback loops governance"` → Kelly on generative vs extractive design
- `"systems archetypes"` → Senge on Growth and Underinvestment, Shifting the Burden
- `"leverage points"` → Meadows' 12-point hierarchy for system intervention
- `"democratic workplace participation"` → Nightingale and Wolff on formal structure as prerequisite for real participation
- `"feedback thought social science"` → Weinberg on general systems thinking applied to organizations

---

## Governance → Production Architecture Mapping

How governance domain concepts map to Assembly's production backend (assembly-baseplate, DM-021).

### Voting Thresholds in Service Layer

Voting threshold calculations belong in the governance service, not in handlers or templates:

- **Ordinary resolution:** 50%+1 of votes cast
- **Special resolution:** ≥2/3 of votes cast
- **Director termination:** 3/4 of all directors (not just those present)
- **Consent resolution:** 100% written consent

The service validates thresholds and returns a pass/fail result. Handlers render the result. Templates never calculate thresholds.

```go
func (s *GovernanceService) CheckVoteResult(ctx context.Context, proposalID string) (VoteResult, error) {
    // Count votes, apply threshold based on decision type
    // Return: passed bool, votesFor, votesAgainst, threshold, quorumMet
}
```

### Quorum Calculation in Meeting Service

Quorum logic lives in the meeting service. Takes current member count and the co-op's quorum rule (from `coop_settings`), returns whether quorum is met.

Quorum must be checked before allowing any vote to proceed. If quorum is lost mid-meeting (members leave), votes taken after that point are invalid.

### Resolution Numbering in Transactions

Resolution numbers must be generated inside a `db.WithTx()` transaction to prevent duplicates under concurrent access:

```go
err := s.db.WithTx(ctx, func(tx *sql.Tx) error {
    // Get next number inside transaction
    var nextNum int
    tx.QueryRow("SELECT COALESCE(MAX(number), 0) + 1 FROM gov_resolutions WHERE fiscal_year = ?", year).Scan(&nextNum)
    // Insert resolution with that number
    _, err := tx.Exec("INSERT INTO gov_resolutions (number, ...) VALUES (?, ...)", nextNum, ...)
    return err
})
```

### BC Act Fields → Database Columns

Statutory requirements map to specific database columns and validation rules:

| BC Act Requirement | Database Column | Validation |
|---|---|---|
| ≥3 directors (s.72) | `member_roles WHERE role='director'` | Count ≥ 3 |
| Majority Canadian directors | `members.country` via role join | Count check |
| ≥1 BC resident director | `members.province` via role join | Exists check |
| AGM within 15 months | `gov_meetings WHERE type='agm'` | Date interval check |
| Financial statements 10 days pre-AGM | `doc_documents WHERE type='financial'` | Date comparison |
| Annual report within 2 months post-AGM | `doc_documents WHERE type='annual_report'` | Date comparison |

### Audit Trail → NATS AUDIT Stream

Every governance action publishes to the NATS `AUDIT` stream (90-day retention):

- Vote cast → `assembly.audit.action` (type: `vote.cast`)
- Resolution passed → `assembly.audit.action` (type: `resolution.passed`)
- Meeting called → `assembly.audit.action` (type: `meeting.called`)
- Member status change → `assembly.audit.action` (type: `member.status_changed`)
- Proposal status change → `assembly.audit.action` (type: `proposal.status_changed`)

The NATS event envelope includes `actor_id`, `entity_id`, `timestamp`, and a `data` payload with the specific change details. This creates the statutory audit trail required by the BC Cooperative Association Act.

### Decision Types as Seed Data

Decision types (ordinary, special, consent, director-termination) are seed data loaded via goose migrations, not hardcoded enums in Go code. This allows co-ops to:

- Add custom decision types via the admin UI (future)
- Configure thresholds per decision type
- Meet jurisdiction-specific requirements without code changes

```sql
-- seeds/001_decision_types.sql
INSERT INTO gov_decision_types (id, name, threshold_type, threshold_value) VALUES
    ('ordinary', 'Ordinary Resolution', 'majority', 0.50),
    ('special', 'Special Resolution', 'supermajority', 0.6667),
    ('consent', 'Consent Resolution', 'unanimous', 1.00),
    ('director_termination', 'Director Termination', 'supermajority', 0.75);
```

---

## Plain-Language Glossary

The translation table at `${CLAUDE_SKILL_DIR}/references/plain-language-glossary.md` documents legalese-to-plain-language pairs for cooperative governance terminology. Assembly's decolonizing-language product move depends on this glossary: bylaws and statutory filings keep the legal terms; everything members actually read uses the plain-language defaults. When writing UI copy, onboarding flows, or member-facing documentation, consult the glossary first.

The glossary is the source of truth that backs Assembly's UI copy, member statements, and education material. It cross-references the existing `decolonial-language` skill so that positions taken there (patronage refunds not dividends, surpluses not profits, member capital not equity) appear consistently across both skills. Per Chris Galloway (April 21, 2026): governance terminology was overwhelmingly written by lawyers in the 1970s and absorbed wholesale by software developers; co-ops inherit a dialect that does not sound like them. The glossary is how Assembly stops that inheritance from showing up in member-facing surfaces.

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

## Companion Skills

| Skill | Plugin | When to Load |
|-------|--------|--------------|
| **decolonial-language** | council | Values-aligned terminology for UI labels, member communications, and content decisions |
| **development** | assembly | Technical implementation — Docker-based Go development, Templ templates, Datastar reactivity |
| **strategy** | design-machines | Business context, pricing, partnerships, pipeline status |

## Cross-References

- **decolonial-language skill** (in this plugin): For values-aligned terminology, content strategy, and the three-layer architecture (legal → bridge → cultural) for member-facing communications. Use when naming UI elements, writing labels, or drafting member documents.
- **assembly plugin**: Technical implementation — Docker-based Go development, Templ templates, Datastar reactivity.
- **Assembly repo distribution docs**: `docs/DISTRIBUTION.md` (phased distribution — pilot → self-updating → platform), `docs/PILOT-SCOPE.md` (first client scope — governance Simple Mode, no proposals/async/proxy), `docs/UPDATE-FLOW.md` (update/rollback sequence).
