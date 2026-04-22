# 008 — P2 — Content quality and voice consistency pass

**Status:** pending
**Severity:** P2 (should fix before publishing the cornerstone blocks externally)
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agents:** ghostwriter:review:voice-editor, dm-review:review:code-simplicity-reviewer, dm-review:review:pattern-recognition-specialist, council:review:governance-domain

## Problem

The voice editor and pattern reviewer surfaced specific voice/structure improvements. None block merge, but several should be addressed before the cornerstone block files get used in real social posts.

## Findings (in fix-order priority)

### V-1 — "the data inverts the frame/pitch/inversion" drift across 6 files

The phrase appears in 6 cornerstone files in three slightly different formulations. Cornerstone material drift is the AI-tell pattern the avoid list calls out.

Standardize on **"the data inverts the frame"** (fewest syllables, most picturable). Update:
- `survival-reframe.md:21`
- `strategy/SKILL.md` (in the survival-reframe section)
- `survival-reframe-blocks.md` LinkedIn line 19
- `survival-reframe-blocks.md` Bluesky line 33
- `survival-reframe-blocks.md` Mastodon line 45
- `survival-reframe-blocks.md` Instagram slide 5

### V-2 — `survival-reframe-blocks.md:16` LinkedIn opener uses "at a 76% clip"

Sportscaster register, off-voice. Other 3 platform drafts in the same file say "76% of co-ops survive 5 years." Standardize.

### V-3 — Strategy SKILL.md survival-reframe paragraph too long

Hemingway-short fails — one paragraph stuffed with three statistics, three citations, two assertions, file pointer. Break into 4 short paragraphs.

### V-4 — Em-dash density flags

`developer-federation-pitch.md`: 18 em-dashes in 59 lines. `two-moats.md`: 11 in 56 lines. Several decorative — replace with periods. Specifically:
- `developer-federation-pitch.md:7` — em-dash → period
- `two-moats.md:36` pile-up sentence — break into fragments

### V-5 — `coop-pitch.md:11-17` Tuesday morning bullets uniform

Seven bullets, all start with verbs, all same length. This is the emotional climax of the doc. Vary the rhythm — mix in a fragment or two.

### V-6 — `voice/SKILL.md:322` "without restraint" off-key

Travis's voice rules are about restraint. Rewrite: "Use the 'Use freely' vocabulary as native, not as terms requiring translation."

### Structural

### S-1 — `audience/SKILL.md` description over-stuffed (1517 chars)

25 inline trigger phrases duplicated from plugin.json triggers array (16 entries). Trim description to ~80 words, trust plugin.json for trigger discovery. Re-run eval to confirm ≥70%.

### S-2 — `audience/full-research.md` duplicates ~70% of every sibling reference

515 lines, mostly redundant with language-card.md, developer-federation-pitch.md, coop-pitch.md, survival-reframe-citations.md. Trim to unique content (methodology notes, Day-in-the-Life sketches, confidence calls). Drops ~350 lines.

### S-3 — `strategy/SKILL.md` frontmatter still claims external-comms triggers

"positioning, marketing copy, go-to-market, client conversations" overlap with audience territory. Either trim from strategy description or scope to "as internal business decisions."

### S-4 — `plugin.json` declares `mcpDependencies: []` on audience entry

Convention is omit when no MCP deps. Remove the line.

### G — Glossary precision (from governance review)

- `plain-language-glossary.md` "Member in good standing" → fix dues language for worker co-ops
- `plain-language-glossary.md` "Internal capital account" → add liquidity caveat
- `plain-language-glossary.md` "Patronage allocation" → note bylaws-dependent measurement
- `plain-language-glossary.md` "Subchapter T" → add Canadian Income Tax Act parallel note

## Fix order

V-1 and V-3 first (highest visibility — will appear in any survival-reframe content). Then S-1 and S-2 (largest cleanup). Then V-2, V-4, V-5, V-6 (voice polish). Then S-3, S-4, G items (smaller corrections).

## Acceptance

- [ ] Grep "inverts the (pitch|inversion)" returns 0; "inverts the frame" appears in all 6 files
- [ ] No "at a 76% clip" in any cornerstone block
- [ ] Strategy SKILL.md survival-reframe section is ≤4 short paragraphs
- [ ] Em-dash count in developer-federation-pitch.md ≤10 (was 18)
- [ ] audience/SKILL.md description ≤500 chars; eval still ≥70%
- [ ] full-research.md trimmed to <250 lines (was 515)
- [ ] strategy/SKILL.md description trimmed of external-comms triggers
- [ ] plugin.json audience entry has no `mcpDependencies` line
- [ ] All 4 glossary precision items applied
