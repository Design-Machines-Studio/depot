# 004 — P1 — Special resolution threshold described inconsistently and imprecisely

**Status:** pending
**Severity:** P1 (blocks merge)
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agent:** council:review:governance-domain

## Problem

The BC Co-op Act s.1 defines special resolution as **"≥ 2/3 of votes cast"** — confirmed in `bc-cooperative-act.md:56` and `voting-decisions.md:28`.

The rollout uses three different incorrect formulations across files:

- `two-moats.md:25` — "2/3 of members voting in favour"
- `plain-language-blocks.md:16` — "two-thirds of the room"
- `plain-language-glossary.md:27` — "Big decision requiring 2/3 agreement"

## Why this matters

The distinction matters in plausible scenarios. With 30 members present, 18 yes / 6 no / 6 abstain:
- Under "2/3 of votes cast": 18/24 = 75% → passes
- Under "2/3 of the room": 18/30 = 60% → fails

Two different answers from two different framings of the same threshold. A co-op configuring Assembly using the wrong framing would either reject valid resolutions or pass invalid ones.

Worse: the new glossary's whole pitch is "preserve precision when plain-language loses it." Getting the threshold's denominator wrong on the glossary page that promises precision is the failure mode the page warns against.

## Fix

- `two-moats.md:25` → "2/3 of votes cast"
- `plain-language-glossary.md:27` → "Big decision requiring 2/3 of the votes cast (abstentions don't count against it)"
- `plain-language-blocks.md:16` → "two-thirds of the votes cast"

The "abstentions don't count against it" clarifying clause matches the precision-preserving pattern the glossary's Quorum entry already uses.

## Acceptance

- [ ] All 3 files use "votes cast" denominator
- [ ] Glossary entry adds the abstention-clarifying clause
- [ ] Grep `2/3 of (members voting|the room|agreement)` returns 0 across the rollout files
- [ ] Cross-check with existing council references — terminology consistent
