# The Two Moats

Design Machines' competitive moat is two things working together, not one. Most competitive analyses focus on the first. The second is what makes the first defensible.

## Moat 1 — Integration across fixtures

A worker co-op that runs on real governance has six fixtures: **decisions, meetings, members, equity, compliance, documentation**. Every other tool covers one or two:

- **Loomio** — decisions only. You leave it for everything else.
- **Decidim** — decisions and some participation. Too heavy for a 12-person co-op; built for cities.
- **Cobudget** — budget allocation only. Narrow.
- **Sociocracy facilitators (Murmur, Consent.coop)** — meeting flow only. No persistence.
- **Notion / Slack / Monday** — generic B2B; treats members as users; no governance shape.
- **BoardEffect / Diligent Boards** — corporate-board software. Inverts a worker co-op's power structure.
- **Carta / Ledgy** — equity for investor-owned startups. Wrong model entirely. Cap tables and stock options, not patronage and internal capital accounts.

Assembly is the first tool to integrate all six fixtures into one system of record.

## Moat 2 — Bylaws become operational, not aspirational

Every other governance tool treats bylaws as reference documents. Members are expected to read them; the system does not enforce them. Assembly inverts this. Bylaws are operational defaults the system enforces.

Concrete BC Cooperative Association Act examples:

- **Special resolutions** (bylaw amendments, sale of substantially all assets, dissolution) require **2/3 of members voting** in favour. Assembly enforces this threshold automatically when the resolution type is set; members cannot accidentally pass a special resolution by simple majority.
- **Director removal** requires a **3/4 vote** of members. Assembly knows this; the UI for the resolution refuses lower thresholds.
- **Annual General Meetings** must occur within **15 months of the prior AGM** (BC Co-op Act). Assembly tracks the prior AGM date and surfaces the deadline as a compliance event 90 days out, then 30, then 7. The statutory agenda generates automatically.
- **Director changes** must be filed with BC Registries within **14 days** of the change. Assembly generates the filing draft automatically when a board change is recorded; the deadline shows in compliance.
- **Block** (in consent decision-making) requires a written reason. Assembly enforces the reason field; you cannot register a block without it. Per Chris Galloway's April 21 feedback: "verify this is enforced in code." It is.
- **New member approvals** follow each co-op's actual bylaws. Some require a probationary period. Some require board approval. Some require an AGM vote. Assembly reads the bylaws config and enforces the right path; the same UI does not apply to every co-op.
- **Quorum thresholds** are encoded per meeting type (board vs general; ordinary vs special). The system blocks the meeting from passing decisions if quorum is not met.
- **Ordinary resolutions** require **50% + 1**. Assembly knows the difference and shows the right threshold next to each proposal.

## Why moat 2 is what makes moat 1 defensible

A competitor could build the six fixtures without enforcement. The result would be Notion with a co-op skin — a system that documents the rules but does not run them. Members still drift. Bylaws still rot. Admin debt still compounds.

Integration without enforcement is a shallow moat. Anybody with budget can copy a feature list.

Enforcement is what turns the integrated system into governance infrastructure. Bylaws stop being paperwork. The rules run the system. You cannot accidentally break governance.

This is also why the Gemini-suggested phrase *compliance-as-code* is wrong for DM voice. Compliance-as-code sounds like a SaaS audit feature. *Operationalizing the bylaws* says what is actually happening: the document the co-op already wrote becomes the program the co-op already runs on.

## Landing phrases

For talks, propaganda, copy:

- "Your bylaws stop being paperwork."
- "The rules run the system."
- "Governance you can't accidentally break."
- "Operationalizing the bylaws — not just storing them."
- "Bylaws become operational, not aspirational."

## Why this lands inside DM voice

Picturable. A bylaw turning into a working part of the machine sits cleanly inside the factory/labor/publishing triangle. Assembly is the press; the bylaws are the typeset; the meeting is the print run. Nothing about this is metaphorical SaaS-talk. It is the actual mechanism.
