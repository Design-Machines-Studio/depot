# 005 — P1 — strategy/SKILL.md conflates quorum with passing threshold + misclassifies block-with-comment as statutory

**Status:** pending
**Severity:** P1 (blocks merge)
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agent:** council:review:governance-domain

## Problem

`plugins/design-machines/skills/strategy/SKILL.md:27` says:

> "Assembly enforces statutory requirements as defaults (**2/3 quorum on special resolutions**, AGM within 15 months of prior, director-change filing within 14 days, **block requires mandatory comment**, new-member approval follows each co-op's actual bylaws)"

Two errors in one sentence:

### Error 1 — 2/3 is the passing threshold, not quorum

Per `bc-cooperative-act.md:141`, the BC Act doesn't prescribe quorum — it's set in Rules of Association (Model Rules default: 10% of members). Quorum and threshold are two separate compliance gates.

Notably, the new plain-language glossary itself flags this exact confusion in the Quorum entry — and then strategy/SKILL.md commits the error in the same paragraph the glossary cross-references.

### Error 2 — "Block requires mandatory comment" is NOT statutory

It's a sociocracy / consent decision-making practice. The two-moats.md and enforcement-angle-blocks.md correctly contextualize this ("block in consent decision-making"). Strategy/SKILL.md drops the qualifier inside a "statutory requirements" list, which means anyone composing from this skill could assert "BC Act requires blocks to have a written reason." It does not.

## Fix

Replace line 27 of strategy/SKILL.md with:

```
Assembly enforces statutory requirements (e.g., the AGM 15-month rule, the 14-day director-change filing) and bylaw-or-process requirements (e.g., the 2/3-of-votes-cast special-resolution threshold encoded in your rules; blocks in consent decision-making require a written reason; quorum thresholds set per the Rules of Association; new-member approval per each co-op's bylaws).
```

This:
- Separates statutory from bylaw/process requirements
- Uses correct "votes cast" language (per todo 004)
- Correctly contextualizes block-with-comment as consent practice
- Names quorum as a separate gate per Rules of Association
- Preserves the moat-2 enforcement story

## Acceptance

- [ ] Strategy SKILL.md line 27 distinguishes statutory from bylaw/process requirements
- [ ] No mention of "quorum" in connection with the 2/3 threshold
- [ ] Block-with-comment correctly framed as consent decision-making, not BC Act
- [ ] Cross-reference to plain-language-glossary.md still works (no path drift)
