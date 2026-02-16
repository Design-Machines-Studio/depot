# Governance Terminology: Decolonial Alternatives

Detailed guidance for governance language in cooperative software, meeting facilitation, and organizational documents.

## The Core Shift: From Hierarchy to Circle

Corporate governance language embeds command-and-control assumptions: boards "direct," chairs "preside," officers "execute." Cooperative governance language should reflect collective decision-making, shared stewardship, and democratic participation.

The most successful alternative models — sociocracy, indigenous governance, horizontalidad — share a common pattern: circles instead of pyramids, facilitation instead of authority, consent instead of command.

---

## Term-by-Term Guide

### Stewardship Circle (not Board of Directors)

**Why it matters:** "Board of Directors" implies a group that directs others — a hierarchical relationship. "Stewardship Circle" implies a group that cares for something on behalf of the community — a service relationship.

**Legal requirement:** The BC Cooperative Association Act requires "directors." Legal documents must use this term. Internal operations can use any term.

**Implementation:**
- UI navigation: "Stewardship Circle"
- Meeting headers: "Stewardship Circle Meeting — February 2026"
- Legal documents: "Directors (referred to internally as the Stewardship Circle)"
- Bylaw bridge: "The Stewardship Circle shall serve as the Board of Directors as defined in the BC Cooperative Association Act"
- Member communication: "Your stewards met on Tuesday..."

**Sociocratic equivalent:** "Top Circle" — functions identically to a board but uses consent-based decision-making and double-linking.

### Facilitator / Convenor (not Chairman/Chairperson)

**Why it matters:** "Chair" implies authority over the meeting. "Facilitator" implies service to the group's process. The facilitator guides discussion; they don't control it.

**Legal requirement:** BC Act references "chairperson." Use in legal documents.

**Implementation:**
- UI label: "Facilitator" or "Convenor"
- Meeting context: "Today's facilitator is..."
- Legal documents: "Chairperson (Facilitator)"
- Role description: "Guides the group's process, ensures all voices are heard, manages time"
- Not: "Runs the meeting" or "presides over"

### Proposal (not Motion)

**Why it matters:** "Motion" is parliamentary procedure — formal, intimidating, associated with Robert's Rules. "Proposal" is accessible and action-oriented. Someone proposes something; others respond.

**Legal requirement:** BC Act uses "resolution" for formal decisions. "Proposal" describes the pre-decision stage.

**Implementation:**
- UI flow: Proposal → Discussion → Consent Decision
- Status labels: "Draft," "In Discussion," "Seeking Consent," "Decided," "Implemented"
- Member communication: "A new proposal has been shared for discussion"
- Not: "A motion has been tabled" (parliamentary jargon)

### Consent Decision / Working Agreement (not Resolution)

**Why it matters:** "Resolution" sounds final and bureaucratic. "Consent decision" describes what actually happens — the group consents to move forward. "Working agreement" emphasizes that decisions can be revisited.

**Legal requirement:** BC Act requires "ordinary resolutions" and "special resolutions" with specific voting thresholds. Use these terms in legal documents and compliance tracking.

**Implementation:**
- UI label: "Consent Decision"
- Types: "Consent Decision" (ordinary), "Major Consent Decision" (special/2/3 threshold)
- Bridge tooltip on "Major Consent Decision": "Requires 2/3 consent — the Act calls this a 'special resolution'"
- Meeting record: "The circle reached consent on..."
- Legal filing: "Special Resolution passed on [date]"

### Consent Round (not Vote)

**Why it matters:** Voting creates winners and losers. Consent rounds ask "can you live with this?" — a fundamentally different question than "do you agree?" Consent means no paramount objections, not unanimous enthusiasm.

**Implementation:**
- UI label: "Consent Round"
- Options: "Consent" / "Stand Aside" / "Block" (not Yes/No)
- "Stand Aside" tooltip: "I have concerns but won't prevent the group from moving forward"
- "Block" tooltip: "I believe this would harm the co-op and cannot support it proceeding"
- Fallback: If consent fails, Co-op OS can facilitate a supermajority vote as backup
- Legal tracking: Record the outcome as the legally required vote type

### Participation Threshold (not Quorum)

**Why it matters:** "Quorum" is Latin parliamentary terminology that creates unnecessary formality. "Participation threshold" describes the concept directly — enough people need to be present for decisions to be valid.

**Legal requirement:** BC Act requires quorum. Use the term in legal documents.

**Implementation:**
- UI label: "Participation Threshold"
- Status indicator: "12 of 15 members present — threshold met ✓"
- Warning: "We need 3 more members to reach our participation threshold"
- Legal documents: "Quorum (Participation Threshold)"

### Community Agreements / Operating Agreement (not Bylaws)

**Why it matters:** "Bylaws" sound like rules imposed from above. "Community agreements" frames them as collectively created and owned.

**Legal requirement:** BC Act uses "rules" (not "bylaws" — that's actually a US term). Filed documents should reference "Rules of Association."

**Implementation:**
- UI navigation: "Our Agreements" or "Community Agreements"
- Document title: "Community Agreements of [Co-op Name] Workers' Cooperative"
- Legal filing: "Rules of Association"
- Bridge: "Our Community Agreements (filed as Rules of Association under the BC Act)"

### Steward / Coordinator (not Officer)

**Why it matters:** "Officer" implies rank and authority. "Steward" implies care and responsibility. "Coordinator" implies facilitation.

**Implementation:**
- Secretary → "Records Steward" or "Keeper of Records"
- Treasurer → "Financial Steward" or "Finance Coordinator"
- President → "Lead Facilitator" or "General Coordinator"
- Vice-President → "Alternate Facilitator" or "Support Coordinator"
- Legal documents: Use statutory officer titles with internal equivalences noted

### Meeting Record (not Minutes)

**Why it matters:** "Minutes" implies bureaucratic obligation. "Meeting record" or "decision record" emphasizes capturing what matters — what was decided and why.

**Implementation:**
- UI label: "Meeting Record" or "Decision Record"
- Template emphasis: Decisions made, actions assigned, reasoning captured
- De-emphasize: Attendance roll calls, procedural motions, parliamentary formatting
- Legal requirement: Records must exist and be accessible. Format is flexible.

---

## Governance Process Language

### Decision-Making Flow

**Instead of:** "The motion was moved by X, seconded by Y, and carried by majority vote."

**Use:** "X proposed [thing]. After discussion, the circle reached consent." Or: "X proposed [thing]. After discussion, the circle decided by [X] to [Y] consent, with [Z] standing aside."

### Meeting Flow

**Instead of:** "Call to order → Roll call → Approval of minutes → Old business → New business → Adjournment"

**Use:** "Opening → Check-in → Review previous decisions → Current proposals → New proposals → Closing"

Or even simpler: "Gather → Reflect → Decide → Plan → Close"

### Escalation Language

**Instead of:** "This matter has been escalated to the board."

**Use:** "This needs the stewardship circle's attention" or "We're bringing this to the wider group for guidance."

---

## The Dual-Document Pattern

For any formal governance document, maintain two versions:

**Internal version (cultural layer):**
- Uses all solidarity economy terminology
- Organized around member experience
- Written in accessible, direct language
- This is what members interact with daily

**Legal version (legal layer):**
- Uses BC Act terminology
- Meets all statutory filing requirements
- References internal document: "For member-facing version, see Community Agreements"
- This is what gets filed with BC Registry

Co-op OS should generate both from the same underlying data.

---

## Models That Have Done This Well

**Sociocracy** provides the most complete alternative governance vocabulary — circles, consent, facilitators, double-linking — all legally defensible and operationally proven. Sociocratic bylaws explicitly state board/circle equivalence.

**Loomio Cooperative** uses accessible decision language in their software: Proposals, Agree/Abstain/Disagree/Block. Their brand guidelines require non-gendered and non-violent language throughout.

**Mondragon** uses "Governing Council" (not board), "General Assembly" (not AGM), "Social Council" (worker welfare body), and "Management Council" (operational body). All legally recognized in Basque cooperative law.

**Haudenosaunee Confederacy** governance predates Western democracy by centuries: consensus circles, clan mothers, seven generations thinking. Don't appropriate the specific terms, but let the structural principles inform your design.
