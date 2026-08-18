# Caller visual verification (Phase 7)

Loaded at `/pipeline` Phase 7 only when a full-mode chunk or the approved lean
plan carries `renderedSurface: required`. When every chunk is
`not_applicable`, record the rationale and never load this file.

### Caller Visual Verification (mandatory for rendered-surface features)

If any full-mode manifest chunk has `renderedSurface: required`, or the approved
lean plan includes a rendered surface, you MUST visually verify the rendered
output yourself. Do not trust an implementation worker's self-report for visual
quality. Full mode verifies per chunk; the caller verifies the whole.

If all full-mode chunks have `renderedSurface: not_applicable`, or the lean plan
records rendered verification as not applicable, record the rationale and skip
to the requirements cross-check.

1. **Discover the design spec.** Check these locations in order:
   - `plans/<feature-slug>/brainstorm.html` (read the `visualDecisions` island with `templates/extract-json-island.sh`)
   - `docs/superpowers/specs/*.md` (most recently modified)
   - `.superpowers/brainstorm/` (HTML mockups)
   - If none exist, use the original prompt's visual requirements as the baseline.

2. **Screenshot every affected page.** Navigate to each route that was touched by any chunk. Take a desktop (1440px) screenshot of each. If the design spec or original prompt mentions mobile, also take 375px screenshots.

3. **Compare to design spec.** For each visual decision in the design spec (or each visual requirement in the original prompt), evaluate the rendered page. State explicitly what you see.

4. **Present gaps to the user BEFORE claiming done.** Format:

```text
## Caller Visual Verification

Screenshots taken: [N pages at N breakpoints]
Design spec: [path or "none -- using original prompt requirements"]

### Gaps Found
- [page URL]: [description of gap] -- spec says [X], actual shows [Y]

### Verified
- [page URL]: [description of match]
```

If gaps are found, present them as part of the delivery. Do not present the branch as "ready" with undisclosed visual gaps.

**Evidence Requirement:** Every "Verified" item in the visual verification report MUST include concrete evidence:

- A screenshot path or inline screenshot reference
- A specific visual observation ("heading is h4 with muted color at 0.875rem" not just "heading looks correct")
- If a computed style matters (font-size, weight, color, background), the actual computed value from `getComputedStyle` via browser_evaluate

Assertions without evidence are findings, not verifications. "Verified: sidebar looks good" is NOT acceptable. "Verified: sidebar headings use 0.875rem / 400 weight / var(--color-muted) per getComputedStyle" IS acceptable.

If evidence is still unavailable after the required recovery ladder, emit blocked `human_help_required` with every attempt and exact missing case IDs, ask the user for help, and stop delivery. This is never a passing, skipped, or deferred verification.

