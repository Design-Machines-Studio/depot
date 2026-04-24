# Design Machines Depot — Audience-Research Rollout

Claude Code: this prompt directs a full sweep of skill and plugin updates across the Design Machines depot, based on an audience research pass completed April 22, 2026. Work in this order. Stop and ask clarifying questions before creating any new file if scope is ambiguous — do not invent structure where the existing depot conventions answer the question.

## Voice and style (applies to everything you write here)

The depot is for Design Machines — Travis Gertz's Estonian company. DM's voice is Left-informed, pro-labor, anti-SaaS-pitch-deck. Every name and phrase you write must belong to at least one of three worlds: factories, labor, publishing. The naming test is literal: can this be pictured in a factory, union hall, or print shop? If no, rewrite.

Concrete voice rules:

- Complete sentences, plain English, Hemingway-short. No fragments used for drama.
- No em-dashes used decoratively. Legitimate em-dashes only (parenthetical or emphatic, sparingly).
- No corporate filler: no "unlock," "empower," "leverage," "synergy," "stakeholder" (in North American contexts), "users," "customers" (when referring to co-op members).
- Use movement-native language. A reference card appears in `/docs/audience-research-apr22.md` (see preflight). If you are unsure whether a term is native or tourist, consult that card first.

## Preflight (do this before any task)

1. Verify `/docs/audience-research-apr22.md` exists at the depot root. If it does not, stop and ask the user to save it from the earlier Claude conversation. Every task in this prompt depends on it as source of truth.
2. Read `/CLAUDE.md` and the depot README.
3. Skim `plugins/design-machines/skills/strategy/SKILL.md`, `plugins/ghostwriter/skills/voice/SKILL.md`, `plugins/ghostwriter/skills/social-media/SKILL.md`, `plugins/gemini/skills/gemini-delegate/SKILL.md`, and `plugins/council/skills/governance/SKILL.md` so you understand existing conventions before editing them.
4. Confirm your understanding with the user in one short message before beginning Task 1.

## Task 1 — Patch the gemini-delegate skill fallback chain

**Path:** `plugins/gemini/skills/gemini-delegate/`

**Problem:** The skill documents a `pro → flash → flash-lite → skip` rate-limit fallback chain, but the Gemini CLI does not auto-fall-back on HTTP 429. On April 22, 2026, Pro was rate-limited across 10 retries and never fell back to Flash — it just exited with an error. Manual rerun with `-m flash` succeeded in 23 seconds. The fallback chain is currently aspirational, not operational.

**Fix:** Write a bash wrapper function documented in `references/invocation-protocol.md` that catches 429 errors and retries with the next model in the chain. The wrapper should:

- Accept a prompt (via stdin or `-p`), a starting model, and a timeout.
- On exit code indicating 429 or on `err.log` matching "exhausted your capacity" / "quota" / "rate limit", retry with the next model in the chain.
- After flash-lite fails, exit gracefully with a clear message (not a silent skip — this is a real failure that Claude Code should surface to the user).
- Include the `export PATH="/opt/homebrew/bin:..."` line, since we discovered `nohup bash -c` doesn't inherit the login shell PATH on macOS.
- Use `gtimeout` (from coreutils), since macOS does not ship `timeout`. If `gtimeout` is not found, warn the user to `brew install coreutils` and exit.

**Deliverables:**

1. New file `references/gemini-wrapper.sh` containing the wrapper function. Include a comment block at top explaining what was broken and what this fixes.
2. Edit to `references/invocation-protocol.md` under a new "Fallback chain" subheading: document how to call the wrapper, replace aspirational language with the actual behavior, include the coreutils dependency.
3. Edit to `SKILL.md` to mention the wrapper exists and when to use it.

**Acceptance:** Wrapper handles 429 on pro → retries flash → retries flash-lite → exits with clear error. Documented in references. A co-worker reading the skill cold would understand the fallback is now real.

## Task 2 — Update design-machines/strategy skill

**Path:** `plugins/design-machines/skills/strategy/SKILL.md` (and `references/` as needed)

The strategy skill currently captures positioning, product family, DM catalog, target market, partnerships, operating principles, brand language, go-to-market. The audience research adds six things this skill should reflect:

1. **The survival reframe.** Add a prominent subsection under "Target Market" or "Positioning." Worker co-ops outlast conventional businesses (76% UK 5-year survival vs ~42%; France 80–90% three-year vs 66%; Italy worker-buyouts 87% three-year vs 48%). Every DM pitch, talk, and propaganda piece should know this number. The framing: the business form that outlasts everyone else deserves infrastructure that does the same. Cite sources inline.

2. **The two moats.** The strategy skill currently frames DM's moat as purpose-built co-op governance. There are actually two integrated moats:
   - Moat 1: *integration across fixtures* — decisions, meetings, members, equity, compliance, documentation in one system. No competitor does all six.
   - Moat 2: *bylaws become operational, not aspirational* — the system enforces statutory requirements (2/3 quorum on special resolutions, AGM within 15 months of prior, director-change filing within 14 days, block requires mandatory comment, new-member approval follows each co-op's actual bylaws). Every other tool treats bylaws as reference docs.
   Candidate landing lines for marketing copy: *"Your bylaws stop being paperwork." · "The rules run the system." · "Governance you can't accidentally break."*

3. **Sectoral density, not scale.** Add to the operating principles or brand language section. This audience does not want "scale" in the VC sense. They want sectoral density (more co-ops per region, more co-op-to-co-op trade, more federation infrastructure). Native-movement distinction: *scale out* (replicate the model in many places) vs *scale up* (grow one org huge). Co-op developers use this fluently; most tech-sector people have never heard it.

4. **The channel-first strategy.** The current "Go-to-Market: The Trojan Horse" section should be updated. The primary audience is now *co-op developers, federations, and incubators* (sell to the orgs that make co-ops — they recommend to dozens of member co-ops). Secondary is existing worker co-ops. Live Wires and the designer-developer funnel is deprioritized for now per April 22 scoping conversation. Do not delete the Live Wires content; move it to a "secondary / long-term" subsection.

5. **Admin debt** as a named concept. Add under target-market pain points. Functions like technical debt but for governance: bylaws drift, equity spreadsheets only one person understands, decisions that get relitigated because nobody can find the last one. Sits inside DM's factory/labor/publishing triangle because debt is materialist.

6. **Decolonizing governance language** as a Design Machines move. Per Chris Galloway's April 21 feedback, most co-op governance terminology was written by lawyers in the 1970s and imported wholesale by developers. Assembly can ship opinionated plain-language defaults (e.g., "how we're splitting this year's surplus" instead of "patronage allocation subject to qualified written notice of allocation"). Document this as a deliberate DM product move, not just a feature choice.

**Deliverables:**

1. Edits to `SKILL.md` integrating all six points into existing structure. Do not append a new "Audience Research Apr 22" section — weave the findings into the voice and logic already there.
2. New reference file `references/survival-reframe.md` — standalone citable version of the survival statistics with sources, usable as material for blog posts, talks, and pitches.
3. New reference file `references/two-moats.md` — positioning doc for the integration + enforcement argument, with concrete BC Act examples.

**Acceptance:** An uninformed reader of the updated SKILL.md understands the channel-first strategy, the survival reframe, the two moats, and sectoral density without ever needing to consult the research doc. References are linkable and self-contained.

## Task 3 — Create design-machines/audience skill

**Path:** `plugins/design-machines/skills/audience/`

This is a new skill. It houses the April 22 research as canonical and gets triggered whenever a query touches audience, language, positioning voice for external communication, pitching, or competitive landscape.

**Structure:**

- `SKILL.md` — description + trigger conditions + what's in references.
- `references/full-research.md` — copy of `/docs/audience-research-apr22.md` (or a symlink if depot conventions allow).
- `references/language-card.md` — the Use Freely / Use Carefully / Avoid / Landing Phrases reference. Extract from the research doc.
- `references/developer-federation-pitch.md` — talking points for pitching co-op developers, federations, and incubators. Draw from sections 1, 2, 5, and 7 of the research. Include what they care about (pipeline economics, curriculum embedding, client retention, co-branded artifacts), what they fear (software that competes with their consulting revenue; extractive pricing that punishes adding member co-ops), and the anchor lines.
- `references/coop-pitch.md` — talking points for pitching an existing small worker co-op directly. Draw from sections 2, 3, 6, 8. Include the "Tuesday morning" frame, the admin-debt frame, and the two-moats argument.
- `references/survival-reframe-citations.md` — cite-ready version with URLs for UK Co-operatives UK report, France Scop data, Italy CECOP data.

**Skill description should trigger on:** audience questions, positioning decisions, pitch drafting, conference talk prep, external writing, competitive analysis, client conversations, federation outreach, USFWC / CWCF / DAWI / Cooperation Works! / Cooperatives Europe references, co-op developer conversations, Loomio comparisons, Decidim comparisons. Make the description pushy — Claude tends to undertrigger skills, so spell out casual trigger phrases and edge cases explicitly.

**Acceptance:** The skill loads when Trav says things like "help me draft a pitch," "what do I say to the federation staff," "how should I talk about this to Chris," "what's our positioning vs Loomio," without him having to invoke it by name.

## Task 4 — Update ghostwriter/voice skill

**Path:** `plugins/ghostwriter/skills/voice/`

The voice skill already defines platform-specific registers (LinkedIn, Mastodon, Bluesky, Instagram, essays, website). Add one new subsection explaining audience awareness.

**Add under a new heading "Audience awareness":**

> Design Machines writes primarily for three overlapping audiences: co-op developers and federation staff, existing worker co-op members, and the broader labor/solidarity-economy public. When drafting content, Claude should check which audience is primary for the piece and calibrate accordingly. The `design-machines/audience` skill has the detailed research. In practice:
>
> - Content for federation staff and co-op developers: pipeline, sector-density, curriculum, cross-developer solidarity framings. Assume familiarity with "technical assistance," "patronage," "ICAs," "the seven principles."
> - Content for co-op members: daily-experience framings (Tuesday morning test, admin debt, "ask Sarah"). Less movement jargon, more lived-experience language.
> - Content for the broader public: the survival reframe, workplace democracy as a proposition, AI-and-labor intersection. The door-opening content.
>
> If unsure which audience the piece is for, ask before drafting.

Also: update any existing "avoid" list in the voice skill to include the new additions from the language card: *scale up (as a virtue), compliance-as-code, best-in-class, enterprise-grade, unlock value, drive adoption, stakeholder (in NA contexts)*.

**Deliverables:**

1. Edit to `SKILL.md` with the new Audience Awareness section and the expanded avoid list.
2. If the voice skill has a landing-phrases reference, add: *bylaws become operational, not aspirational · the rules run the system · admin debt · scale out, not up · sectoral density*.

**Acceptance:** Next time Trav asks ghostwriter to draft a LinkedIn post, the drafting naturally reflects audience awareness.

## Task 5 — Update ghostwriter/social-media skill

**Path:** `plugins/ghostwriter/skills/social-media/`

This skill covers the platform register consolidation and content posting. Add three things:

1. **The survival reframe as a reusable content block.** Add a reference file `references/survival-reframe-blocks.md` with ready-to-adapt drafts in each platform register (LinkedIn long-form, Bluesky compressed, Mastodon with CW, Instagram carousel outline). Include the headline statistic and at least two reframes of it.

2. **The "bylaws become operational" post template.** Add to the same references folder or a new `references/enforcement-angle-blocks.md`. Include the concrete BC Act examples (quorum enforcement, AGM deadlines, block-with-mandatory-comment). Same platform-register treatment.

3. **The decolonizing-language post template.** `references/plain-language-blocks.md`. The pitch: governance terminology was written for lawyers in the 1970s; Assembly ships with plain-language defaults. Chris Galloway framing. Platform-register treatment.

These three are cornerstone content blocks the ghostwriter can pull from and adapt, not drop in verbatim. Write them in DM's voice; do not create SaaS-flavored templates.

**Acceptance:** When Trav says "help me write a LinkedIn post about why co-ops don't need to worry about surviving," ghostwriter can reach for the survival block and adapt, not start cold.

## Task 6 — Update council/governance skill

**Path:** `plugins/council/skills/governance/`

The governance skill is comprehensive on BC Cooperative Association Act mechanics, voting thresholds, bylaw analysis, discovery framework. Add one new reference for plain-language translation.

**New file:** `references/plain-language-glossary.md`

Contains a running table of legalese → plain language translations for governance terms. Seed it with entries drawn from the research and from the existing governance references. Examples of the pattern:

| Legalese | Plain language | When to use which |
|---|---|---|
| Special resolution | Big decision requiring 2/3 agreement | Plain in member-facing UI; legal in statutory docs |
| Patronage dividend | Your share of the year's surplus | Plain in member statements; legal in tax filings |
| Quorum | How many members need to show up to vote | Plain everywhere; legal in bylaws only |
| Internal capital account | The co-op's savings account in your name | Plain in onboarding; legal in annual financial statements |
| Indivisible reserve | The shared kitty we can't pay out | Plain internally; legal in bylaws |
| Consent resolution | Everyone signs off without a meeting | Plain everywhere |
| Subchapter T | The co-op tax rules | Plain in member education; legal in tax context |
| Written notice of allocation | Paper record that ICA credit happened | Plain in member statements; legal in tax filings |

Continue the pattern. Include a short note at top that the goal is plain-language defaults without eliminating legally required terminology. Bylaws and statutory filings need the legal terms; member-facing interfaces do not.

Also edit the governance `SKILL.md` to reference this new glossary and explain its purpose — Assembly's decolonizing-language product move relies on it.

**Acceptance:** When Assembly's UI copy needs writing, this glossary is the reference. When a co-op developer asks "how do I explain ICAs to a new member," this glossary has the answer.

## Task 7 — Update the depot `CLAUDE.md` (if one exists at depot root)

If `/CLAUDE.md` exists at the depot root and contains pointers to skills, add a line noting the new `design-machines/audience` skill and its purpose. Keep it short.

If no `/CLAUDE.md` exists at depot root, skip this task.

## Not in scope (do not do these in this session)

These four deliverables are mentioned in the research as next moves, but they are content, not infrastructure. Do not draft them in this session:

- The "Survival Reframe" cornerstone essay (500-word propaganda piece, likely /PRESS release DM-020)
- The plain-language governance glossary as a standalone public-facing product
- The "Why Assembly" one-pager for federation staff
- A separate `dm-sales` plugin (the audience skill covers this need for now; revisit if it gets crowded)

Leave those for later sessions where Trav is drafting content. This session is about making the skills and references able to support that drafting when it happens.

## Ground rules and self-check

Before you consider this work complete:

1. Every skill edit preserves existing structure. Do not refactor conventions that are working. If you see something that looks wrong but is not in scope, note it at the end of your work log and do not change it.
2. No SaaS language, no corporate filler, no tourist terms. Run the naming test on anything new you write.
3. All citations in `references/` are real and linkable. No invented URLs. If a source is behind a paywall or a listserv, note that plainly.
4. At the end of the session, produce a short work log listing every file created or modified, with one-line summaries. Trav uses these logs to review.
5. If any task feels ambiguous after reading the preflight, ask before proceeding. Do not guess scope.
6. The April 22 research doc is the source of truth for audience claims. Do not contradict it without flagging the contradiction and asking.

Begin with preflight. Confirm understanding. Then proceed through tasks in order.
