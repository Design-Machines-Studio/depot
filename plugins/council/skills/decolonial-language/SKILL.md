---
name: decolonial-language
description: Decolonial and anti-capitalist content strategy for cooperative software, governance documents, and member-facing communications. Use when naming UI elements, writing labels, seeding database values, drafting member communications, generating legal documents, or making any content decision in Co-op OS, Live Wires, or Design Machines. Provides terminology mappings between legal/regulatory language and values-aligned alternatives, plus a three-layer compliance architecture for maintaining legal validity while centering solidarity economy language.
---

# Decolonial Language Skill

Content strategy for cooperative software that centers relationships over extraction, stewardship over ownership, and collective wellbeing over individual accumulation. Built for Co-op OS but applicable across Design Machines projects.

## Core Principle

**Language shapes how members think about their own organization.** Colonial and capitalist terminology embeds assumptions about hierarchy, extraction, and individualism. We use solidarity economy language internally while generating legally compliant documents externally. The goal is not to reject legal frameworks but to prevent them from colonizing how cooperators understand their own democracy.

## The Three-Layer Architecture

Every piece of content in Co-op OS exists in one of three layers:

| Layer | Purpose | Language | Example |
|-------|---------|----------|---------|
| **Legal/Regulatory** | State compliance, filings, formal documents | Statutory terminology required by BC Cooperative Association Act | "Special Resolution," "Rules of Association," "Director" |
| **Bridge** | Glossaries, tooltips, dual-label interfaces | Both terms connected | "Stewardship Circle (Board of Directors)" |
| **Cultural/Internal** | Member-facing UI, onboarding, daily use | Solidarity economy language | "Stewardship Circle," "Consent Decision," "Surplus" |

**Default to the Cultural layer.** Use Legal layer only when generating documents for regulatory purposes. Use Bridge layer in contexts where members need to understand the legal equivalence.

### Implementation Pattern

```
UI Label:        "Surplus"
Tooltip:         "Net income remaining after expenses — your co-op's collective gain"
Legal document:  "Net Income" or "Surplus" (both legally recognized)
Bridge context:  "Surplus (Net Income)"
```

---

## Quick Reference: Terminology Mappings

### Financial Terms

| Legal/Capitalist | → Use Instead | Notes |
|------------------|---------------|-------|
| Profit / Loss | **Surplus / Deficit** | ICA Principle 3; IRS-recognized for co-ops |
| Shareholders | **Members** or **Worker-owners** | Universal cooperative standard |
| Dividends | **Patronage Refunds** or **Member Distributions** | IRS-recognized; based on patronage not capital |
| Capital | **Collective Funds** or **Member Capital** | "Capital as servant, not master" (ICA) |
| Equity (financial) | **Member Equity** or **Membership Shares** | Tied to membership, not tradeable |
| Assets | **Resources** or **Common Holdings** | Informal; use "Assets" in financial statements |
| Liabilities | **Obligations** or **Commitments** | Informal; use "Liabilities" in financial statements |
| Revenue | **Earnings** or **Receipts** | Standard alternatives |
| Net Income | **Net Margin** or **Surplus** | USDA cooperative terminology |
| ROI | **Community Benefit** or **Social Return** | Success = member/community wellbeing |
| Stakeholder | **Community Member** or **Participant** | Removes financial framing |
| Buy-in | **Membership Contribution** | Emphasizes joining community |
| Debt | **Mutual Obligations** | Relational framing |

### Governance Terms

| Legal/Corporate | → Use Instead | Notes |
|-----------------|---------------|-------|
| Board of Directors | **Stewardship Circle** or **Guidance Council** | Note legal equivalence in bylaws |
| Chairman/Chairperson | **Facilitator** or **Convenor** | Non-hierarchical; from sociocracy |
| CEO/Executive Director | **General Coordinator** or **Operations Lead** | Cooperative federations use these |
| Officer | **Steward** or **Coordinator** | Non-hierarchical role language |
| Bylaws | **Operating Agreement** or **Community Agreements** | BC Act uses "Rules of Association" |
| Resolution | **Consent Decision** or **Working Agreement** | Sociocratic framing |
| Motion | **Proposal** | More accessible, action-oriented |
| Vote | **Consent Round** or **Decision** | Sociocracy; emphasizes agreement over winning |
| Quorum | **Participation Threshold** | Functional description |
| Proxy | **Delegation** | Note legal limitations |
| Compliance | **Alignment** or **Accountability** | Values-based framing |
| Audit | **Review** or **Assessment** | Less punitive connotation |
| Fiduciary Duty | **Stewardship Responsibility** | Care framing over legal obligation |
| Minutes | **Meeting Record** or **Decision Record** | Emphasizes substance over formality |

### Membership Terms

| Corporate/Legal | → Use Instead | Notes |
|-----------------|---------------|-------|
| Employee | **Worker-owner** or **Cooperator** | Mondragon uses "cooperator" |
| Probationary Period | **Orientation Period** or **Pathway to Membership** | Less punitive |
| Termination | **Departure** or **Separation** | Neutral framing |
| Human Resources | **People & Culture** or **Member Support** | Relational framing |
| Performance Review | **Growth Conversation** or **Peer Reflection** | Development over judgment |
| Onboarding | **Welcome Journey** or **Orientation** | Emphasizes belonging |

### Interface/UX Language

| Extractive Framing | → Use Instead | Notes |
|--------------------|---------------|-------|
| User | **Member** or **Person** | They own this, they're not being used |
| User pain points | **Community needs** | |
| Target market | **Communities served** | |
| Impact metrics | **Relationships deepened** | |
| User acquisition | **Community growth** | |
| Conversion | **Participation** | |
| Engagement | **Connection** | |
| Retention | **Belonging** | |
| Dashboard | **Overview** or **Pulse** | Less surveillance, more rhythm |

---

## Decision Framework: When to Use Which Layer

**Use Cultural layer (default):**
- All member-facing UI labels, buttons, navigation
- Onboarding flows and welcome materials
- Internal meeting agendas and communications
- Member handbook and policies
- Notifications, reminders, status messages

**Use Bridge layer:**
- First encounter with a legal concept (tooltip or parenthetical)
- Glossary pages
- Training materials that prepare members for regulatory interactions
- AGM agendas (members see cultural terms with legal equivalences)

**Use Legal layer:**
- Annual reports filed with BC Registry
- Tax filings and financial statements for regulators
- Legal correspondence
- Formal bylaw/rules documents (though even here, consider bridge approach)
- Any document a regulator or court might read

**When in doubt:** Use cultural language and add a bridge tooltip. Members should never need to learn legal terminology to participate in their own democracy.

---

## Content Principles

### 1. Relational, Not Transactional
Frame everything in terms of relationships between people, not transactions between entities. "Member contributions" not "buy-in." "Community agreements" not "compliance requirements."

### 2. Active, Not Passive
Members do things together. "The circle decided" not "a resolution was passed." "Members agreed" not "the motion carried." Agency belongs to people, not procedures.

### 3. Accessible, Not Simplified
Use clear, direct language without dumbing down concepts. A "consent round" is not simpler than a "vote" — it's a different and more precise concept. Explain, don't reduce.

### 4. Pluriversal, Not Universal
Allow different cooperatives to use different terminology for the same concepts. Some may prefer indigenous terms from their own traditions. Co-op OS should support configurable terminology where possible.

### 5. Honest About the Tension
Don't pretend the legal framework doesn't exist. Name it: "The BC Act calls this a 'special resolution' — we call it a 'major consent decision' because that better describes what's actually happening: your whole community agreeing on something important."

### 6. Grounded in Practice
Terminology should emerge from what cooperators actually do, not from academic theory. If a term doesn't make immediate sense to a cleaning co-op member or an animation studio worker-owner, it needs more work.

---

## Reference Files

Load these for deeper context:

| File | When to Load |
|------|--------------|
| `references/terminology-finance.md` | Writing financial UI, reports, patronage flows |
| `references/terminology-governance.md` | Governance UI, meeting flows, decision tracking |
| `references/terminology-membership.md` | Member profiles, onboarding, lifecycle |
| `references/terminology-ux.md` | Interface copy, notifications, general UX writing |
| `references/frameworks.md` | Content strategy planning, philosophical grounding |
| `references/case-studies.md` | Precedent research, client conversations |

---

## Cross-References

- **governance skill** (in this plugin): Domain knowledge for BC Act requirements — this skill provides the language layer on top
- **assembly plugin**: Technical implementation — use this skill when naming components, writing labels, seeding data
