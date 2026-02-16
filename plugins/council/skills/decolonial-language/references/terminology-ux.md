# UX & Interface Terminology: Decolonial Alternatives

Guidance for writing interface copy, notifications, labels, and microcopy in cooperative software. This applies to Co-op OS directly, but also informs Live Wires documentation and Design Machines communications.

## The Core Shift: From Extraction to Connection

UX vocabulary inherits from growth-hacking and surveillance capitalism: "users," "engagement," "retention," "conversion." These terms treat people as resources to be captured and optimized. Cooperative software should treat people as community members with agency.

---

## Interface Labels

### Navigation & Structure

| Conventional | → Use Instead | Rationale |
|-------------|---------------|-----------|
| Dashboard | **Overview** or **Pulse** | Less surveillance, more rhythm |
| Admin Panel | **Coordination Hub** or **Steward Tools** | Service, not control |
| Settings | **Preferences** or **Your Space** | Personal choice, not configuration |
| User Profile | **Your Profile** or **Member Profile** | Ownership and belonging |
| Notifications | **Updates** or **What's New** | Less interruption framing |
| Help Center | **Support** or **Learning** | Emphasizes growth |
| Reports | **Insights** or **How We're Doing** | Collective framing |

### Actions & Buttons

| Conventional | → Use Instead | Rationale |
|-------------|---------------|-----------|
| Submit | **Share** or **Propose** | Invitation, not subordination |
| Approve / Reject | **Consent** / **Raise Concern** | Sociocratic, non-binary |
| Delete | **Remove** or **Archive** | Less violent |
| Assign | **Invite** or **Ask** | Agency preserved |
| Manage Members | **Member Directory** or **Our People** | Care, not control |
| Run Report | **See Insights** | Less mechanical |
| Export Data | **Download** or **Save a Copy** | Plain language |

### Status Labels

| Conventional | → Use Instead | Rationale |
|-------------|---------------|-----------|
| Pending Approval | **Awaiting Consent** | Sociocratic process |
| Approved | **Consented** or **Agreed** | Collective action |
| Rejected | **Not Consented** or **Returned for Discussion** | Respectful, process-oriented |
| Overdue | **Needs Attention** | Less punitive |
| Expired | **Lapsed** or **Past Due** | Less final |
| Active | **Current** | Neutral |
| Inactive | **On Hold** or **Resting** | Less judgmental |
| Terminated | **Concluded** or **Completed** | Less violent |

---

## Notification & Message Tone

### Principles

1. **Speak as a peer, not an authority.** The software is a tool the cooperative owns, not a boss giving instructions.
2. **Frame actions as invitations, not obligations.** "Your growth conversation is coming up" not "Your performance review is overdue."
3. **Celebrate collective achievement.** "We reached consent on the budget proposal" not "Budget proposal approved."
4. **Be warm without being fake.** Authentic care, not corporate cheerfulness.

### Notification Patterns

**Meeting reminders:**
- ✗ "You are required to attend the Board Meeting on Thursday"
- ✓ "Stewardship Circle gathers Thursday at 3pm — your voice matters"

**Decision updates:**
- ✗ "Resolution #2026-04 has been passed by majority vote"
- ✓ "We've reached consent on the professional development fund proposal"

**Compliance reminders:**
- ✗ "URGENT: Annual report filing deadline approaching. Failure to comply may result in penalties."
- ✓ "Our annual report is due by March 15 — here's what we need to finish up"

**Financial updates:**
- ✗ "Q4 profit statement is available for review"
- ✓ "Our Q4 surplus report is ready — see how we did"

**Member lifecycle:**
- ✗ "New employee onboarded: Jane Smith"
- ✓ "Welcome Jane! She's starting her pathway to membership today"

**Contribution reminders:**
- ✗ "Payment overdue: Membership fee for February"
- ✓ "Friendly reminder: your February membership contribution is ready whenever you are"

---

## Empty States & Zero-Data Screens

Empty states are an opportunity to educate and invite rather than just display "No data found."

**Proposals page (empty):**
- ✗ "No proposals found."
- ✓ "No proposals yet — when someone has an idea for how we can improve, it'll show up here. Ready to start one?"

**Meeting records (empty):**
- ✗ "No meetings recorded."
- ✓ "Your meeting records will live here. After your first stewardship circle gathering, you'll see the decisions and actions captured."

**Member directory (one member):**
- ✗ "1 member found."
- ✓ "Just you so far! As more worker-owners join, you'll see your community grow here."

---

## Error Messages

Errors should be honest, helpful, and never blame the user.

- ✗ "Error: Invalid input"
- ✓ "That doesn't look quite right — could you check the date format?"

- ✗ "Access denied"
- ✓ "This area is for stewardship circle members — reach out to your facilitator if you need access"

- ✗ "Operation failed"
- ✓ "Something went wrong on our end — try again, and if it persists, let us know"

---

## Design & Development Process Language

When writing about the product itself (documentation, changelogs, internal communications), the same principles apply.

| Tech/Startup Term | → Use Instead | Notes |
|-------------------|---------------|-------|
| Users | **Members** or **People** | They own this tool |
| User stories | **Member needs** or **Scenarios** | |
| Pain points | **Challenges** or **Needs** | Less medicalized |
| Personas | **Portraits** or **Member profiles** | |
| Target audience | **Community** or **People we serve** | |
| Market | **Community** or **Sector** | |
| Stakeholders | **Participants** or **Community members** | |
| MVP | Fine as internal term | But frame externally as "first version" |
| Sprint | **Cycle** or **Iteration** | Less urgency-driven |
| Backlog | **Upcoming work** or **Ideas list** | Less industrial |
| Technical debt | **Deferred decisions** | More honest |
| Ship it | **Share it** or **Release** | Less aggressive |
| Deploy | **Publish** or **Go live** | Plain language |

---

## Configurable Terminology

Co-op OS should support cooperative-specific terminology configuration. Different communities may prefer different terms based on their cultural context.

**Configuration approach:**
- Provide sensible defaults (the terms recommended in this skill)
- Allow cooperatives to override any label
- Store overrides in cooperative's configuration
- Apply overrides across all interfaces and generated documents

**Example configuration:**
```
terminology:
  board: "Stewardship Circle"     # default
  chair: "Facilitator"            # default
  bylaws: "Community Agreements"  # default
  surplus: "Surplus"              # default
  meeting: "Gathering"            # cooperative override
  member: "Compañero"             # cooperative override (Spanish-speaking co-op)
```

This supports the pluriversal principle — multiple valid ways of naming the same concept, defined by each community for themselves.

---

## Accessibility Notes

Decolonial language must also be accessible language.

- **Plain language always wins.** If a decolonial alternative is harder to understand than the conventional term, the conventional term is better. The goal is clarity in service of democracy.
- **Define unfamiliar terms.** If using "consent round" instead of "vote," provide a brief definition on first encounter.
- **Translation considerations.** Some alternative terms may not translate well. "Stewardship Circle" works in English; test with multilingual cooperatives.
- **Screen reader friendliness.** Ensure alternative labels work well with assistive technology — avoid special characters or unusual punctuation in label text.
