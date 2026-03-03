---
name: voice-check
description: Check text against Travis Gertz's writing voice
argument-hint: "[paste text or provide file path]"
---

# Voice Check

Quick check of text against Travis Gertz's writing voice guidelines.

## Process

### 1. Get Text

- If a file path was provided, read the file
- If text was pasted inline, use that
- If neither, ask for the text to check

### 2. Load Voice Reference

Read the voice skill's kill list and style markers:
- `plugins/ghostwriter/skills/voice/SKILL.md` — vocabulary kills, rhythm patterns, register rules

### 3. Check Against Voice

Scan the text for:

**Kill Words (immediate flags):**
delve, tapestry, landscape (metaphorical), navigate (metaphorical), leverage (verb), foster, holistic, robust, multifaceted, resonate, unpack (ideas), circle back, double down, move the needle, synergy, ecosystem (non-literal), paradigm shift, game-changer, stakeholder, at its core, undeniably, it's worth noting, in today's [anything]

**AI Writing Patterns:**
- Em-dash clusters (more than 2 per paragraph)
- Tricolon crutches (three parallel items as a default rhythm)
- Mechanical transitions ("Furthermore," "Moreover," "Additionally,")
- Emotional flatness (every paragraph at the same register)
- Vocabulary uniformity (same word choices a human wouldn't repeat)

**Rhythm Issues:**
- No sentence variety (all medium-length)
- No fragment energy (Travis uses intentional fragments)
- No compound-complex sentences building through accumulation

**Register Match:**
- Detect the intended register (essay, LinkedIn, product copy, etc.)
- Check if the text matches that register's expected patterns

### 4. Report

```
Voice Check — [source]

Kill words found: X
AI patterns found: Y
Rhythm issues: Z

KILLS:
- Line N: "leverage" → try "use" or "exploit"
- Line N: "robust" → try "solid" or "tough"

AI PATTERNS:
- Para 2: Three consecutive "Additionally/Furthermore/Moreover" transitions
- Para 4: Em-dash cluster (4 in one paragraph)

RHYTHM:
- All sentences 15-25 words — needs variety (fragments + longer builds)
- No gear shifts between registers

REWRITES:
[Provide 2-3 rewritten passages that fix the identified issues]
```
