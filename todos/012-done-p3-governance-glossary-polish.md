# 012 — P3 — Governance glossary polish + two-moats fines surfacing

**Status:** pending
**Severity:** P3
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agent:** council:review:governance-domain

## Findings

### P3-G1 — Subchapter T entry should note Canadian Income Tax Act parallel

`plugins/council/skills/governance/references/plain-language-glossary.md` lists Subchapter T (US/IRS) without noting that BC co-ops live under the Canadian Income Tax Act and CRA's treatment of patronage allocations. Listing Subchapter T without the parallel implies IRS rules apply to BC co-ops.

**Fix:** Either modify the entry:

> Subchapter T — The co-op tax rules (US federal). BC co-ops follow the Canadian Income Tax Act and CRA guidance on patronage allocations; talk to a co-op-friendly accountant before quoting Subchapter T in a BC context.

Or add a sibling row for the Canadian patronage deduction.

### P3-G2 — two-moats.md director-fine context worth surfacing

`two-moats.md:28` says "Director changes must be filed with BC Registries within 14 days" — correct, but `bc-cooperative-act.md:190` also notes the consequence (up to $5,000 fine). For a federation TA pitch, this is a $5K-per-incident risk that sharpens the moat-2 argument.

**Fix:** Add the fine context after the existing 14-day note:

> Director changes must be filed with BC Registries within 14 days. Late filings incur fines up to $5,000 per incident under the BC Co-op Act. Assembly generates the filing draft automatically when a board change is recorded — turning a recurring fine risk into a non-event.

## Acceptance

- [ ] Subchapter T entry notes Canadian parallel
- [ ] two-moats.md director-change example includes the $5K fine context
