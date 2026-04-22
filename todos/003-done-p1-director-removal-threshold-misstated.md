# 003 — P1 — Director removal threshold misstated in two-moats.md

**Status:** pending
**Severity:** P1 (blocks merge)
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agent:** council:review:governance-domain

## Problem

`plugins/design-machines/skills/strategy/references/two-moats.md:26` says:

> "Director removal requires a 3/4 vote of members. Assembly knows this; the UI for the resolution refuses lower thresholds."

This is wrong under BC Cooperative Association Act s.82.

## Reality (verified against existing references)

- Per `plugins/council/skills/governance/references/voting-decisions.md:166`
- Per `plugins/council/skills/governance/references/bc-cooperative-act.md:112`

Director removal **by members** requires a special resolution — **2/3 of votes cast** by default (or 3/4 if rules specify, or 3/4 for housing co-ops).

The 3/4 threshold cited applies to **director-removal-by-other-directors** — 3/4 of all directors at a meeting called for that purpose. Different scenario.

## Why this is P1

The whole "moat 2 — bylaws become operational" pitch depends on the example demonstrating that Assembly enforces statutory thresholds correctly. Asserting the wrong threshold for the most consequential governance action a co-op can take destroys the moat-2 credibility with the rollout's primary audience (co-op developers).

Federation staff at USFWC, CWCF, DAWI will catch this in five seconds.

## Fix

Replace lines 25-30 of `two-moats.md` with:

```markdown
- **Director removal by members** requires a special resolution — 2/3 of votes cast by default (or 3/4 if your rules specify; 3/4 for housing co-ops).
- **Removal by fellow directors** requires 3/4 of all directors at a meeting called for that purpose.

Assembly enforces whichever threshold your bylaws encode.
```

## Acceptance

- [ ] two-moats.md director-removal example uses correct thresholds
- [ ] Cross-checked against voting-decisions.md and bc-cooperative-act.md
- [ ] Galloway-embarrassment test passes (would Chris Galloway nod or wince?)
