# 010 — P3 — Plugin metadata + marketplace convention polish

**Status:** pending
**Severity:** P3
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agents:** dm-review:review:pattern-recognition-specialist, dm-review:review:architecture-reviewer

## Findings

### P3-P1 — Audience triggers array at 16 entries vs 10-cap convention

Every other depot plugin caps `triggers` at 10 (live-wires, ghostwriter, council, assembly all stop at 10). The audience entry has 16. Five overlap with phrases already in the SKILL.md description (which is the actual matching surface).

**Fix:** Cull to ~10 highest-signal triggers — keep named entities (USFWC, CWCF, Decidim, Cooperation Works), in-house phrases ("survival reframe," "two moats," "admin debt," "sectoral density"), drop conversational phrasings the SKILL description already covers.

### P3-P2 — design-machines tags dropped "business" without justification

Pre-change tag set was `["strategy", "business", "pricing", "partnerships", "catalog", "revenue"]`. New set is `["strategy", "audience", "positioning", "pricing", "partnerships", "catalog", "revenue", "competitive-landscape"]` — `business` removed.

`business` is the only tag in either skill's `tags` array that didn't survive the curation, while `competitive-landscape` was added that doesn't appear in either skill's tags.

**Fix:** Either restore `business` (it's still in `strategy.tags`) or remove it from `strategy.tags` to match. The summary should be a defensible subset of actual skill tags.

### P3-A1 — Strategy↔audience coupling: strategy should delegate, not duplicate

Strategy SKILL.md now points at audience references AND restates the same findings (survival reframe, two moats, admin debt, channel-first GTM) that audience full-research.md contains. Bidirectional skill coupling complicates layering.

The clean layering: strategy depends on audience; audience does not depend on strategy. Strategy SKILL.md should *delegate* to audience for those sections rather than restating them. E.g., the survival-reframe section in strategy could be one sentence ("Worker co-ops outlast conventional businesses; see `audience/references/survival-reframe.md`") instead of a full paragraph.

**Fix:** Trim the survival-reframe and two-moats sections in strategy/SKILL.md to one-line pointers + key takeaway. Audience skill owns the depth; strategy skill owns the positioning that uses the depth.

## Acceptance

- [ ] design-machines plugin.json audience entry has ≤10 triggers
- [ ] marketplace.json design-machines `capabilities_summary.tags` is a defensible subset of skill tags
- [ ] Strategy SKILL.md survival-reframe and two-moats sections are pointers, not duplications
