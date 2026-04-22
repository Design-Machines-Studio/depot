# The Two Moats

Design Machines' competitive moat is two things working together, not one. Most competitive analyses focus on the first. The second is what makes the first defensible.

## Moat 1: Integration across fixtures

A worker co-op that runs on real governance has six fixtures: **decisions, meetings, members, equity, compliance, documentation**. Every other tool covers one or two.

- **Loomio.** Decisions only. You leave it for everything else.
- **Decidim.** Decisions and some participation. Too heavy for a 12-person co-op; built for cities.
- **Cobudget.** Budget allocation only. Narrow.
- **Sociocracy facilitators (Murmur, Consent.coop).** Meeting flow only. No persistence.
- **Notion / Slack / Monday.** Generic B2B. Treats members as users. No governance shape.
- **BoardEffect / Diligent Boards.** Corporate-board software. Inverts a worker co-op's power structure.
- **Carta / Ledgy.** Equity for investor-owned startups. Wrong model entirely. Cap tables and stock options, not patronage and internal capital accounts.

Assembly is the first tool to integrate all six fixtures into one system of record.

## Moat 2: Bylaws become operational, not aspirational

Every other governance tool treats bylaws as reference documents. Members are expected to read them; the system does not enforce them. Assembly inverts this. Bylaws are operational defaults the system enforces.

Concrete BC Cooperative Association Act examples:

- **Special resolutions** (bylaw amendments, sale of substantially all assets, dissolution) require **2/3 of votes cast** in favour (BC Co-op Act s.1 definition). Abstentions do not count against the threshold. Assembly enforces this automatically when the resolution type is set; members cannot accidentally pass a special resolution by simple majority.
- **Director removal by members** requires a special resolution: **2/3 of votes cast** by default (or 3/4 if your rules specify; 3/4 for housing co-ops). **Removal by fellow directors** requires 3/4 of all directors at a meeting called for that purpose. Assembly enforces whichever threshold your bylaws encode.
- **Annual General Meetings** must occur within **15 months of the prior AGM** (BC Co-op Act). Assembly tracks the prior AGM date and surfaces the deadline as a compliance event 90 days out, then 30, then 7. The statutory agenda generates automatically.
- **Director changes** must be filed with BC Registries within **14 days** of the change. Late filings carry fines up to $5,000 per incident. Assembly generates the filing draft automatically when a board change is recorded — turning a recurring fine risk into a non-event.
- **Block** (in consent decision-making, not BC Act) requires a written reason. Assembly enforces the reason field; you cannot register a block without it. Per Chris Galloway's April 21 feedback: "verify this is enforced in code." It is.
- **New member approvals** follow each co-op's actual bylaws. Some require a probationary period. Some require board approval. Some require an AGM vote. Assembly reads the bylaws config and enforces the right path; the same UI does not apply to every co-op.
- **Quorum thresholds** are encoded per meeting type (board vs general; ordinary vs special). Quorum is set in the Rules of Association — the BC Act does not prescribe it (the Model Rules default is 10% of members). The system blocks the meeting from passing decisions if quorum is not met.
- **Ordinary resolutions** require **more than half of votes cast** (50% + 1). Assembly knows the difference and shows the right threshold next to each proposal.

## Why moat 2 is what makes moat 1 defensible

A competitor could build the six fixtures without enforcement. The result would be Notion with a co-op skin. A system that documents the rules but does not run them. Members still drift. Bylaws still rot. Admin debt still compounds.

Integration without enforcement is a shallow moat. Anybody with budget can copy a feature list.

Enforcement is what turns the integrated system into governance infrastructure. Bylaws stop being paperwork. The rules run the system. You cannot accidentally break governance.

This is also why the Gemini-suggested phrase *compliance-as-code* is wrong for DM voice. Compliance-as-code sounds like a SaaS audit feature. *Operationalizing the bylaws* says what is actually happening: the document the co-op already wrote becomes the program the co-op already runs on.

## Landing phrases

For talks, propaganda, copy:

- "Your bylaws stop being paperwork."
- "The rules run the system."
- "Governance you can't accidentally break."
- "Operationalizing the bylaws, not just storing them."
- "Bylaws become operational, not aspirational."

## Why this lands inside DM voice

Picturable. A bylaw turning into a working part of the machine sits cleanly inside the factory/labor/publishing triangle. Assembly is the press; the bylaws are the typeset; the meeting is the print run. Nothing about this is metaphorical SaaS-talk. It is the actual mechanism.
