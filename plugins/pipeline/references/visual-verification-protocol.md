# Visual verification protocol

Loaded at orchestrator Step 3h only for a chunk with
`renderedSurface: required`. A `not_applicable` chunk never loads this file.

#### Step 1: Design Spec Discovery

Before taking screenshots, load `prototype-authority.md` when the chunk carries
a declared prototype counterpart. Its exact source and bounded parity map are
the primary baseline. Then check for additional local design specifications:

1. `plans/<feature-slug>/brainstorm.html` -- pipeline brainstorm output (read the `visualDecisions` island with `${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/extract-json-island.sh`)
2. `docs/superpowers/specs/*.md` -- formal design specs (use most recent)
3. `.superpowers/brainstorm/` -- brainstorm mockups (HTML files with inline styles)

If found, read the spec and extract visual decisions relevant to this chunk's files:

- Component variants (which classes, which visual treatment)
- Visual hierarchy (what should be prominent, what subdued)
- Spacing and layout choices (which tokens, which layout primitives)
- Specific visual treatments called out in the approved design

Store these as the **chunk's visual baseline** for evaluation in steps 4 and 5.

#### Step 2: Matched Page-Level Evidence

1. Use the exact host-selected or repository-declared target; never scan
   localhost, infer a port, or invent a start command.
2. Navigate the cases selected from this chunk's affected rendered files,
   routes, prototype parity, and acceptance criteria.
3. Take a full-page screenshot at each selected case viewport. Add at most one
   explicitly justified baseline case when needed for an adjacent regression.
4. Verify the page loads without errors (check `browser_console_messages` for errors)
5. For interactive elements (forms, buttons, modals), click/hover to verify they respond
6. If the project declares UX personas/tasks, execute every selected case from
   the verification profile at its declared engine and viewport. Supported
   dimensions do not create a full matrix. Do not fabricate personas or
   silently sample only two.

For a declared counterpart, navigate prototype and target at the same
meaningful routes, states, and viewports. Capture affected screenshots,
accessibility/DOM snapshots, targeted hierarchy, actual class lists, visible
copy/action order, and only the computed layout/spacing values needed to explain
a mismatch. Use T3 collaborative preview first in T3 Code. A target-only
screenshot, curl, or `looks close` is incomplete prototype evidence.

#### Step 3: Element-Level Screenshots

For each acceptance criterion in the chunk prompt that describes a **visual outcome** (not just a structural criterion like "uses class X"), take a targeted screenshot of the relevant element:

- If the criterion says "buttons are visually lighter" -> screenshot the button group
- If the criterion says "sidebar headings create clear hierarchy" -> screenshot the sidebar
- If the criterion says "card spacing is consistent" -> screenshot 2-3 adjacent cards

Use Playwright's element targeting (`browser_take_screenshot` with a CSS selector or coordinates) when possible. If element-level targeting is unavailable, take a cropped area screenshot or annotate which area of the full-page screenshot to evaluate.

#### Step 4: Visual Evaluation Against Spec

If a design spec was found in Step 1, compare each screenshot against the spec's visual decisions:

```text
Visual Spec Check:
- Spec: "Block button uses outline-danger variant, visually smaller than position buttons" -> MATCH / MISMATCH (actual: [describe what you see])
- Spec: "Sidebar headings use h4 with muted color, not competing with page heading" -> MATCH / MISMATCH (actual: [describe])
- Spec: "Natural-width buttons, not full-width" -> MATCH / MISMATCH (actual: [describe])
```

Classify prototype/spec deviations by observable impact per
`prototype-authority.md`; do not make every mismatch P1. Add every supported
P1/P2/P3 to the review fix queue.

#### Step 5: Visual Evaluation Against Acceptance Criteria

Even without a design spec, evaluate each **visual acceptance criterion** from the chunk prompt. These criteria describe the IMPRESSION, not the implementation:

- "Block and Abstain buttons are visually lighter than position buttons" -> requires visual judgment
- "Return to drafting is barely visible -- a text link, not a button" -> requires visual judgment
- "Sidebar zones are visually distinct without excessive borders" -> requires visual judgment

For each visual criterion, state: PASS (describe what you see and why it matches) or FAIL (describe the gap). Visual criterion failures are P2.

#### Step 5b: Visual Parity Diff (when applicable)

When the chunk's acceptance criteria include a parity requirement ("visually identical to," "match the existing," "same treatment as," "these should be the same component"), perform a computed style comparison:

1. **Identify elements:** Determine the reference element (the one being matched) and the target element (the one being changed). These may be on different pages.
2. **Navigate and extract:** For each element, navigate to its page and use `browser_evaluate` to run:
   ```javascript
   JSON.stringify((() => {
     const el = document.querySelector('[SELECTOR]');
     const s = getComputedStyle(el);
     return {
       fontFamily: s.fontFamily, fontSize: s.fontSize, fontWeight: s.fontWeight,
       lineHeight: s.lineHeight, letterSpacing: s.letterSpacing,
       color: s.color, backgroundColor: s.backgroundColor,
       border: s.border, borderRadius: s.borderRadius,
       padding: s.padding, margin: s.margin,
       display: s.display
     };
   })())
   ```
3. **Compare:** For each property, compare the reference and target values. Log mismatches:
   ```text
   PARITY MISMATCH: font-weight -- reference: 400, target: 700
   PARITY MISMATCH: background-color -- reference: rgb(240,248,240), target: rgb(220,240,220)
   ```
4. **Severity:** Use proportional observable impact: P1 for blocked primary
   work, misleading authorization/governance consequences, inaccessible
   essential controls, or explicitly critical parity; P2 for meaningful
   structural/component/copy/placement/responsive/interaction drift; P3 for
   minor spacing, alignment, metadata, or presentation drift. Severity never
   permits deferral.
5. **Unavailable evaluation:** If `browser_evaluate` cannot run, preserve the failed attempt and run the same primary-quit, fresh-primary, different-browser recovery ladder. If still unavailable, emit blocked `human_help_required`, ask the user for help, and stop. Never skip or defer a required parity diff.

**Baseline comparison:** If `plans/<feature-slug>/baselines/` exists (created by the assess phase), also compare post-implementation screenshots against the baseline:

1. Take a new screenshot of the same route/viewport as each baseline file
2. Note visual differences between baseline and current state
3. Expected differences (the feature being built) are fine; unexpected regressions are P2 findings

#### Step 5c: Prototype source comparison (when applicable)

Re-read the affected prototype and target source after editing. Compare the
bounded parity map's semantic/wrapper hierarchy, significant components, exact
Live Wires class strings, literal copy/metadata, and action order. Record named
intentional divergences for functionality, authorization, accessibility,
public APIs, production data, and host/Fixture composition. A matching
screenshot cannot complete this step, just as matching source cannot complete
the browser step.

If the prototype render is temporarily unavailable after the recovery ladder,
preserve completed source work but return `human_help_required` for rendered
parity. Do not substitute target-only evidence or claim completion.

#### Step 6: Verification Receipt

After completing all checks, output this structured receipt:

```text
BROWSER_VERIFIED: [chunk-id] | screenshots: [N] | element_screenshots: [N] | spec_checks: [N passed]/[N total] | visual_criteria: [N passed]/[N total] | issues: [list or "none"]
```

Also retain the bounded screenshot/snapshot references and compact
DOM/class/copy/action, layout/computed-style, console, and accessibility
observations in this Pipeline run's ignored evidence root. Do not retain
cookies, credentials, private endpoints, browser storage, complete HTML, or
unbounded logs. Chunk evidence remains bound to its chunk commit. Only the
integrated-head capture described by `final-review-browser-evidence.md` may be
packaged and passed to the final dm-review; never choose a chunk artifact by
timestamp or latest-file guessing.

Classify every finding by observable impact under `prototype-authority.md`: P1
only for a blocked primary task, misleading authorization/governance
consequence, inaccessible essential control, or explicitly critical parity; P2
for meaningful structure, component, copy, placement, responsive, or
interaction failure; P3 for minor spacing, alignment, metadata, class, or
presentation drift. A page-load failure takes the severity supported by its
actual task impact. Add every retained P1/P2/P3 to the review fix queue and
reject taste-only preferences without an observable defect.

For required browser-tooling failure, first persist safe attempt evidence, then quit the primary browser process/engine session (closing a tab is insufficient), launch a fresh primary profile with a changed session identity and retry once, then recheck the target and try a genuinely different configured engine. If restart or alternate launch cannot be proved, record that explicitly. Exhaustion ends `human_help_required` with all attempts and exact missing case IDs; it is never skipped, approved, empty coverage, or curl-verified. Product/application assertion failures are terminal findings and do not trigger browser restart. Curl and reachability are diagnostics only and never satisfy `BROWSER_VERIFIED`.

Browser exhaustion is separate from deterministic-validation feedback. Its
authoritative blocked receipt has `stage: browser_recovery`, `status: blocked`,
`reason_code: human_help_required`, the ordered bounded attempt receipts, exact
`missing_case_ids`, a deterministic `human_intervention_id`, and
`human_intervention_reason: browser_evidence_unavailable`. Do not put browser
exhaustion into the deterministic-validation attempt ledger, and do not replace
this shape with `action: resume|replace`.

Derive the browser `human_intervention_id` from the run ID, node/chunk ID,
canonical sorted missing-case set, and stable terminal browser-attempt identity.
Never include a timestamp, receipt display order, or mutable attempt-list index
in that identifier.

Append the authoritative `BROWSER_VERIFIED` or blocked human-help receipt to the
cumulative ledger. Defer shadow observation until `all-chunks-complete`. A
recovered alternate-engine pass remains degraded recovery evidence, not
first-pass clean.

Mark `[chunk-id] 8. Run visual verification` complete only with complete required evidence. Otherwise mark it `blocked: human_help_required` and stop for user help; never mark it skipped or deferred.
