# Plain-Language Glossary

A running translation table for cooperative governance terminology. The goal is plain-language defaults in member-facing surfaces (UI copy, onboarding flows, member statements, education materials) without eliminating legally required terminology where it is statutorily mandated.

## Why this exists

Most worker co-op governance terminology was written by lawyers in the 1970s and imported wholesale by software developers. The result: members are asked to consent to "patronage allocations subject to qualified written notice of allocation" when the plain-language version is "your share of this year's surplus." Assembly's product position is to ship plain-language defaults; bylaws and statutory filings keep the legal terms; everything members actually read uses the translations below.

This is a deliberate Design Machines product move. Per Chris Galloway (April 21, 2026 conversation): "Most of the language was lawyer-written and developer-imported. Co-ops inherit it without consent."

## When to use which column

| Surface | Column to use |
|---|---|
| Member-facing UI (Assembly) | Plain language |
| Onboarding flow | Plain language |
| Annual statements to members | Plain language (with legal term in parentheses where required) |
| Bylaws document | Legalese (statutory) |
| Statutory filings (BC Registries, CRA) | Legalese (statutory) |
| Tax filings | Legalese (statutory) |
| Member education / training material | Plain language with legal term taught alongside |

## Translation table

| Legalese | Plain language | Where the legal term is mandatory |
|---|---|---|
| Special resolution | Big decision requiring 2/3 of the votes cast (abstentions don't count against it) | Bylaws; meeting minutes for resolutions filed with BC Registries |
| Ordinary resolution | Decision requiring more than half of the votes cast | Bylaws; resolution texts |
| Patronage allocation / refund | Your share of the year's surplus, paid based on your work in the co-op (your bylaws define how, usually hours worked or wages earned), not on capital invested | Tax filings; BC Co-op Act § references. **Note: never use "patronage dividend"** (see `plugins/council/skills/decolonial-language/references/terminology-finance.md` for the rationale: dividends flow to investors based on capital; patronage refunds flow to member-owners based on contribution). |
| Quorum | The minimum number of members who need to show up for the meeting to count (a meeting can hit quorum and still fail a vote if not enough members vote yes) | Rules of Association — the BC Act does not prescribe quorum; the Model Rules default is 10% of members |
| Internal capital account (ICA) | Your ownership account in the co-op (tracks contributions you have made and your share of surplus allocated to you, paid out per the bylaws — usually on departure, sometimes on a schedule) | Annual financial statements; tax filings |
| Indivisible reserve | The shared kitty we can't pay out | Bylaws; financial statements |
| Consent resolution | Everyone signs off without a meeting | Bylaws (where defined as a permitted decision form) |
| Subchapter T | The co-op tax rules (US federal). BC co-ops follow the Canadian Income Tax Act and CRA guidance on patronage allocations; talk to a co-op-friendly accountant before quoting Subchapter T in a BC context. | Tax filings; legal advice contexts (US co-ops) |
| Patronage deduction (Canadian) | The CRA-recognized deduction the co-op takes for patronage allocations paid to members | Canadian co-op T2 corporate returns |
| Written notice of allocation | Paper record that ICA credit happened | Tax filings (specifically required by IRS Subchapter T for US co-ops) |
| AGM (Annual General Meeting) | Yearly all-members meeting | BC Co-op Act statutory filings; bylaws |
| Director | Board member | Bylaws; BC Registries director filings |
| Member in good standing | Member who has met their share contribution and any participation requirements in their co-op's bylaws | Bylaws |
| Proxy | A member voting on someone else's behalf with written permission | Bylaws (where proxy voting is permitted) |
| In-camera session | The part of the board meeting where minutes are sealed | Meeting minutes (where statutorily required to note in-camera time) |
| Block (sociocracy) | A "no, this would harm the co-op" with a required written reason | Bylaws (where consent decision-making is the model) |
| Stand-aside | "I won't block, but I want my disagreement on the record" | Meeting minutes |
| Bylaws review | Reading the rules together to make sure they still match how we work | Statutory contexts use "bylaws review" |
| Surplus available for distribution | The money the co-op has to share out this year | BC Co-op Act § references; financial statements (see `plugins/council/skills/decolonial-language/references/terminology-finance.md` for the surplus-vs-profit position) |
| Member capital | What members put in or built up; the co-op's funded equity (see `plugins/council/skills/decolonial-language/references/terminology-finance.md` for member-capital-vs-equity rationale) | Financial statements; bylaws |

## How to read this table

The plain-language column is what members see in Assembly UI, onboarding emails, and member statements. The legalese column is what appears in bylaws, statutory filings, tax returns, and any document where a regulator or auditor will read the words. Where a statutory document must use the legal term, the third column says so explicitly so writers know the escape valve is available.

When a plain-language version loses precision the legal term carried (for example, "quorum" carries the show-up-vs-vote distinction), the entry includes the clarifying clause inline rather than dropping the precision. Plain language is not the same thing as imprecise language.

## Cross-references

- `bc-cooperative-act.md` — when each legal term is statutorily required
- `bylaw-analysis.md` — patterns for spotting when legal terms drift from member understanding
- `voting-decisions.md` — sociocracy vs majority vs consent decision-making
- `plugins/council/skills/decolonial-language/references/terminology-finance.md` — finance-side terminology positions (patronage refunds, surpluses, member capital)
- `plugins/council/skills/decolonial-language/references/terminology-governance.md` — governance-side terminology positions
- `plugins/council/skills/decolonial-language/references/terminology-membership.md` — membership-side terminology positions
- `plugins/council/skills/decolonial-language/references/terminology-ux.md` — UI-copy guidance
