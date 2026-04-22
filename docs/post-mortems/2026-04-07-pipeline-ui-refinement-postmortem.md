# Post-Mortem: UI Refinement Pipeline Run (Assembly, April 6-7 2026)

**Date:** 2026-04-07
**Project:** Assembly (DM-006)
**Pipeline mode:** Full (5 sequential chunks)
**Model:** Opus 4.6 (1M context)
**Outcome:** Structurally complete but visually unshippable. 16 polish/judgment issues found by user review that pipeline + dm-review missed entirely.

## What Happened

The pipeline ran assess → research → plan → prompts → adversarial review → execute across 11 UI refinement items. The planning phases were strong — brainstorming produced a good sidebar design, the adversarial review caught 3 blockers. But the execution-orchestrator produced B-grade implementations and the review agents didn't catch the visual quality gap. The user found 16 issues on first browser review that no automated agent flagged.

## Root Cause Analysis

### 1. Execution-Orchestrator Skipped Browser Verification

**What happened:** The orchestrator completed all 5 chunks and reported success, but did not perform meaningful browser testing after each chunk. The CLAUDE.md mandates Chrome DevTools MCP screenshots after each chunk. The orchestrator either skipped this entirely or did it superficially (screenshot without visual evaluation).

**Why it matters:** The primary value of browser testing is catching visual regressions — buttons that are too wide, headings with wrong weight, borders creating visual noise. Code review cannot catch these. A screenshot without evaluation is theatre.

**Plugin affected:** `pipeline` (execution-orchestrator agent)

**Recommended fix:**
- The execution-orchestrator's prompt should include an explicit browser verification protocol: navigate → screenshot → evaluate against acceptance criteria → screenshot specific UI elements mentioned in criteria → compare to design spec if one exists
- Add a hard gate: if no Playwright/Chrome DevTools MCP tools are available, WARN and ask user whether to proceed without visual verification
- The orchestrator should output a per-chunk verification summary: "Checked: [screenshots taken]. Verified: [criteria checked]. Issues found: [list]"

### 2. dm-review Missed All Visual Quality Issues

**What happened:** dm-review-loop ran (or was supposed to run) after each chunk. None of the 16 visual issues were flagged. Issues like "Return to drafting button is unreadable gray text" or "Schedule for meeting button is still full-width" are visually obvious and should have been caught by ux-quality-reviewer or visual-browser-tester.

**Why it matters:** dm-review is the quality gate. If it passes everything, the pipeline assumes quality is acceptable. The user's trust in the pipeline depends on dm-review catching what code review cannot.

**Plugins affected:** `dm-review` (ux-quality-reviewer, visual-browser-tester, ui-standards-reviewer)

**Recommended fixes:**

**a) ux-quality-reviewer needs design spec awareness:**
- Currently evaluates against general UX heuristics. Should also compare against the design spec (if one exists at `docs/superpowers/specs/`) and the brainstorm output
- When a design spec says "Block button uses outline-danger variant" and the rendered page shows a filled red button, that's a P1 finding — the implementation deviates from the approved design
- Add: "If `docs/superpowers/specs/*.md` exists, load the most recent spec and compare rendered output against each design decision"

**b) visual-browser-tester needs element-level inspection:**
- Currently checks page-level rendering (responsive, a11y). Should also inspect specific UI elements mentioned in the chunk's acceptance criteria
- For a sidebar redesign, it should screenshot the sidebar specifically and evaluate: button widths, heading hierarchy, border usage, visual weight distribution
- Add: "For each acceptance criterion that describes a visual outcome, take a targeted screenshot of the relevant element and evaluate it"

**c) ui-standards-reviewer needs consistency checking across pages:**
- Currently reviews files in isolation. Should compare the same UI pattern across multiple pages
- For a spacing audit, it should screenshot the same area (e.g., sidebar) on 3+ pages and compare
- When the heading style varies between pages, that's a finding

**d) All review agents need a "design intent" input:**
- The dm-review system currently receives the code diff. It should also receive the design spec or brainstorm output when available
- This transforms the review from "is this code correct?" to "does this code implement the approved design?"

### 3. Brainstorm Mockups Were Higher Quality Than Implementation

**What happened:** The brainstorming phase produced polished mockups (HTML in the visual companion) with clear visual hierarchy — distinct zones, appropriate borders, natural-width buttons, small outline variants for special positions. The implementation produced something structurally similar but visually cruder — inconsistent heading styles, too many borders, full-width schedule button, unreadable text.

**Why it matters:** The brainstorm sets expectations. When the implementation doesn't match, the user's confidence in the entire pipeline drops. The gap between "what I showed you" and "what I built" is the credibility gap.

**Plugin affected:** `pipeline` (promptcraft, execution-orchestrator)

**Recommended fixes:**

**a) Promptcraft should embed visual references:**
- When a brainstorm produced mockups (saved in `.superpowers/brainstorm/`), the execution prompts should reference them: "The approved sidebar design mockup is at [path]. The rendered result must match this visual treatment."
- Even though subagents can't view images, the HTML mockup source contains the styling decisions as inline styles that the subagent can read

**b) Execution prompts need "visual acceptance criteria":**
- Current acceptance criteria are structural: "Block button uses `button--outline-danger`". This verifies the class exists but not that it looks right
- Add criteria like: "Block and Abstain buttons are visually smaller and lighter than the main position buttons" or "Return to drafting is barely visible — a text link, not a button"
- The distinction is between "what CSS class" and "what visual impression"

### 4. Execution-Orchestrator Did Not Self-Evaluate

**What happened:** After executing all chunks, the orchestrator reported "all chunks complete, branch ready" with a terse summary. It did not do a final walkthrough comparing the result to the original requirements.

**Plugin affected:** `pipeline` (execution-orchestrator)

**Recommended fix:**
- Add a mandatory final evaluation step to the orchestrator: before reporting completion, navigate every affected page, take screenshots, and produce a findings report
- The orchestrator should produce a visual comparison: "Original prompt said X. Here's what the page looks like now. Does it match?"
- If the orchestrator can't do visual evaluation (no browser tools), it must say so explicitly rather than silently skipping it

### 5. The Parent Agent Trusted the Orchestrator Too Much

**What happened:** When the orchestrator returned "all chunks complete," the parent agent (me) accepted this at face value and reported the branch as ready. I didn't verify the actual rendered output until the user asked me to self-evaluate. This is the most critical failure — I abdicated judgment.

**Plugin affected:** `pipeline` (skill instructions for the caller)

**Recommended fix:**
- The pipeline skill should instruct the caller: "After the orchestrator completes, YOU must verify the result in the browser. Do not trust the orchestrator's self-report. Take screenshots of every affected page and evaluate them against the original prompt and design spec BEFORE presenting to the user."
- Add to the Phase 7 (Deliver) instructions: "Take screenshots. Compare to design spec. List anything that doesn't match. Present BOTH the successes and the gaps."

### 6. Live Wires Library Boundary Was Violated

**What happened:** The plan specified fixing `.card--stat` in the Live Wires library repo (`livewires/src/css/`). The correct approach for Assembly is to override in Assembly's own CSS — the Live Wires philosophy is "start with Live Wires, make it your own." Each project customizes in its own `src/css/` layer.

**Plugin affected:** `pipeline` (research, plan)

**Recommended fix:**
- The research phase should check for project-specific CSS overrides before proposing library changes
- When a CSS fix is needed, prefer project-level overrides over library changes
- Add to the Assembly development skill: "Never modify the livewires repo. Override in Assembly's `src/css/6_components/` files."

### 7. Timeline Implementation Ignored Existing Component Patterns

**What happened:** The plan correctly identified that the Live Wires `.timeline` component has `.milestone` for day groups. The implementation created custom heading markup instead of using the existing pattern, resulting in broken visual formatting (gaps between timeline segments, redundant dates).

**Plugin affected:** `pipeline` (promptcraft — the prompt didn't enforce using the existing pattern strongly enough)

**Recommended fix:**
- When research identifies an existing component pattern, the execution prompt should include the actual HTML structure from the component, not a description of it
- Add: "Use the EXISTING `.milestone` class on the timeline component for date group headers. Do NOT create custom `<h3>`/`<h4>` headings outside the timeline markup."

## Impact Summary

| Category | Count | Examples |
|----------|-------|---------|
| Visual quality gaps (implementation doesn't match design) | 7 | Sidebar headings inconsistent, buttons wrong size, too many borders |
| Regressions (broke things that were working) | 3 | Dashboard participation progress bar removed, proposal card position section regressed, timeline formatting broken |
| Missing features (spec'd but not implemented correctly) | 4 | Schedule button still full-width, facilitator box missing, export dropdown pattern, draft timeline empty |
| Styling gaps (unstyled or default-styled elements) | 2 | File upload buttons unstyled, return-to-drafting unreadable |

## Recommendations Priority

### P1 — Fix in plugins immediately
1. **Pipeline execution-orchestrator:** Add mandatory browser verification protocol with element-level screenshots
2. **Pipeline skill (Phase 7):** Add mandatory caller verification — don't trust orchestrator self-report
3. **dm-review:** Add design-spec-aware reviewing when `docs/superpowers/specs/` exists

### P2 — Fix soon
4. **Promptcraft:** Embed visual references from brainstorm mockups in execution prompts
5. **Promptcraft:** Add "visual acceptance criteria" to the prompt template
6. **dm-review ux-quality-reviewer:** Add element-level inspection for sidebar/button/heading consistency
7. **Assembly development skill:** Add "never modify livewires repo" rule

### P3 — Improve over time
8. **dm-review visual-browser-tester:** Cross-page consistency checking
9. **Pipeline research:** Auto-detect project CSS override patterns before suggesting library changes
10. **Promptcraft:** Include existing component HTML structures in prompts, not descriptions

## Lessons for Next Time

1. **The gap between planning and execution is where quality dies.** The brainstorm, assessment, research, and adversarial review were all strong. The execution produced something that matched the requirements checklist but not the visual intent.

2. **"All acceptance criteria pass" is not the same as "this is shippable."** Structural criteria (class exists, file created, route registered) are necessary but not sufficient for UI work. Visual criteria require visual evaluation.

3. **Delegation without verification is abandonment.** Launching the orchestrator and trusting its report is the pipeline equivalent of "works on my machine." The caller must verify.

4. **UI refinement work needs tighter feedback loops than feature work.** The pipeline's chunk → review → next-chunk cadence works for backend features. For UI polish, each change needs immediate browser comparison to the design spec. Consider: should UI work use simple mode (single pass) instead of full pipeline chunking?

5. **The brainstorm mockups are the contract.** When the user approves a visual mockup, the implementation must match that mockup, not just the textual description of it. The mockup IS the acceptance criterion.
