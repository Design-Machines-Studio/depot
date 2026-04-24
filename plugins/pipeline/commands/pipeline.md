---
name: pipeline
description: Full autonomous pipeline -- assess, research, plan, prompt, review, execute, deliver
argument-hint: "[feature idea or feedback]"
---

# Pipeline

Full autonomous feature development pipeline. Takes an idea and delivers a clean feature branch.

## Mode Selection

Before starting, assess the feature scope and select the appropriate mode:

**Simple mode** -- Use when the feature is small enough for a single context window:

- Touches fewer than 5 files
- One logical concern (not multiple subsystems)
- No dependency ordering needed (everything is sequential)
- Can be implemented and reviewed in one pass

In simple mode, skip Phases 4-5 (chunking and adversarial review). Instead:

1. Run Phases 1-3 (assess, research, plan) normally
2. Execute the plan as a single implementation pass (no manifest, no chunking)
3. Run `/dm-review-loop` on the result
4. Deliver

**Full mode** (default) -- Use for everything else. All phases execute in order.

**How to decide:** If the plan from Phase 3 has more than one logical step that could be parallelized or that touches separate file groups, use full mode. If it's a single coherent change, use simple mode. When in doubt, use full mode.

## Model-Adaptive Complexity

The pipeline's complexity should match the model's capabilities. Some harness components encode assumptions about model limitations that become stale as models improve.

**If running on Opus 4.6 (or newer):**

- Chunking is optional for medium-complexity features (5-10 files). Opus can sustain coherent multi-hour builds without explicit sprint decomposition. Consider simple mode more aggressively.
- The adversarial review (Phase 5) is still valuable -- self-evaluation remains unreliable regardless of model capability.
- dm-review-loop is still mandatory -- the separation of generator from evaluator is an architectural principle, not a model limitation.

**If running on Sonnet 4.6 (or earlier):**

- Always use full mode for features touching more than 3 files
- Chunking prevents context anxiety (Sonnet prematurely wraps up as context fills)
- Sprint contracts and explicit acceptance criteria are critical -- Sonnet benefits from concrete guardrails

**Periodically question whether each pipeline component is still necessary.** Every component encodes an assumption about model limitations. Test whether scaffolding remains needed as models improve.

## CRITICAL: No Shortcuts

You MUST execute every phase in order. You MUST NOT skip phases, combine phases, or take shortcuts. Specifically:

- You MUST NOT skip research because you think you have enough context
- You MUST NOT execute chunks yourself -- you MUST launch the execution-orchestrator agent
- You MUST NOT skip dm-review-loop after each chunk
- You MUST NOT skip the final full dm-review
- You MUST pause for user input at every marked pause point
- You MUST save all artifacts to disk (briefs, plans, prompts, manifest) -- not just hold them in context

If you are tempted to skip a phase, STOP and re-read this section.

## CRITICAL: Do Not Manually Replicate

When the user says "/pipeline" or asks to "run the pipeline" or "use the full pipeline process," you MUST invoke this skill. You MUST NOT manually replicate pipeline phases by hand — launching Explore agents, writing plans, implementing directly, and calling it "the pipeline."

The pipeline enforces gates, review loops, visual verification, memory capture, and sprint contracts that manual execution silently skips. "I already understand the code" is not a reason to bypass the pipeline — the pipeline exists precisely because self-confidence is unreliable.

**What happens when you bypass the pipeline:**

- Visual verification gets skipped entirely (documented in `docs/post-mortems/2026-04-07-pipeline-ui-refinement-postmortem.md`)
- Requirements get marked "done" without evidence (documented in `docs/post-mortems/2026-04-10-pipeline-visual-testing-postmortem.md`)
- The adversarial review never runs, so hallucinated APIs and missing edge cases ship
- dm-review-loop never runs, so the evaluator/generator separation is lost

If you catch yourself planning to "just do it quickly" without invoking the pipeline skill, you are about to repeat a documented failure. Stop and invoke the skill.

## Progress Ledger

Create this ledger with TodoWrite at the start. Update it as you complete each phase. This is your proof of compliance.

```text
1. Save original prompt to plans/<slug>/original-prompt.md
1b. Phase 0: Creative routing check -- brainstorming invoked: yes/no
2. Phase 1: Assess -- save Assessment Brief to disk
3. Phase 1 GATE: Pause for user input
4. Phase 2: Research -- save Research Brief to disk
5. Phase 2 GATE: Pause for user input
6. Phase 3: Plan -- save plan to disk
7. Phase 3 GATE: Pause for user input
8. Phase 4: Generate prompts -- save manifest + prompts to disk
9. Phase 4 VERIFY: Requirements coverage check against original-prompt.md
10. Phase 5: Adversarial review -- iterate to APPROVED
11. Phase 5 GATE: Pause for user input (present prompts for approval)
12. Phase 6: Launch execution-orchestrator agent (NOT manual execution)
13. Phase 7: Deliver -- requirements cross-check against original-prompt.md
14. Phase 7 GATE: Present results and ask user for next step
```

Mark each item as you complete it. Do not mark a GATE as complete until AskUserQuestion has returned a response from the user. If you find yourself proceeding past a GATE without an AskUserQuestion response, you have violated the gate.

## Feature Input

<feature_input> #$ARGUMENTS </feature_input>

If the feature input above is empty, ask: "What feature or change do you want to build? Describe the idea, feedback, or iteration."

Do not proceed without a clear feature description.

## Original Prompt Preservation

**Immediately** save the user's original input (verbatim) to `plans/<feature-slug>/original-prompt.md`. This is the ground truth. Every subsequent phase MUST check back against this file.

**Slug validation:** the `<feature-slug>` MUST match `^[a-z0-9][a-z0-9-]{0,63}$`. If the derived slug contains `..`, `/`, spaces, uppercase, or exceeds 64 chars, regenerate it. Slug violations escape the `plans/` directory and are rejected.

### Re-read discipline (token budget)

`original-prompt.md` is read canonically ONCE in Phase 1 (Assessment). Phase 1 extracts a `Key Requirements` list and saves it into `plans/<feature-slug>/assessment.md`. After that, Phases 3, 4, and 7 reference the cached Key Requirements list from the assessment brief, NOT the full original-prompt.md.

**When to re-read original-prompt.md anyway:**

- The user provided feedback between phases (append to original-prompt.md as `## Iteration N Feedback`, then re-read).
- The cached Key Requirements summary appears incomplete or ambiguous (re-read to verify, then correct the summary).
- You are the execution-orchestrator preparing subagent context (orchestrator inlines from cache).

Defaulting to "re-read to refresh" in every phase burns tokens without adding information. Prefer the cache.

The file format:

```markdown
# Original Prompt

## User Input
[Exact user input, verbatim, including all bullet points, issues raised, and context]

## Date
[YYYY-MM-DD]

## Key Requirements Extracted
1. [Requirement 1]
2. [Requirement 2]
3. [Requirement N]
```

Mark ledger item 1 as complete. Proceed to Phase 0.

## Phase 0: Creative Routing Check

Before starting the pipeline phases, check whether the user's input involves creative or design work that would benefit from brainstorming.

### 0a. Structured Decision Scan (run FIRST)

Before the trigger-word scan, look for structured decision markers in the original prompt. These are signals that the user has already done some of the creative work upstream:

Grep the original prompt for lines matching (case-insensitive): `^(APPROVED|OPEN|BRAINSTORM):`

- **`APPROVED:` lines** -- the user has locked these decisions. Do NOT brainstorm them. Treat them as requirements for Phase 1 onward.
- **`OPEN:` or `BRAINSTORM:` lines** -- the user wants these specific items explored. Invoke `superpowers:brainstorming` scoped to ONLY these items. Pass the APPROVED list as context so the brainstorm does not re-open settled decisions.
- **Linked upstream documents** -- if the original prompt links to a file (e.g. `review-findings.md`, `post-mortem.md`, an approved design doc) that contains APPROVED-marked decisions, honor those markers. Do NOT re-brainstorm an approved decision just because the link is present.

If structured markers are present, log: `Phase 0: Scoped brainstorming -- N APPROVED decisions locked, M OPEN/BRAINSTORM items to explore.` Proceed with scoped brainstorming (only M items), then move to Phase 1.

If NO structured markers are present, fall through to the trigger-word scan (0b).

### 0b. Trigger-Word Scan (fallback when 0a found no markers)

**Scan the original prompt for explicit creative trigger words:** "brainstorm", "explore ideas", "superpowers", "concept", "rethink", "reimagine", "experiment", "try some things", "let's try"

**Also check the Key Requirements:** If any requirement involves NEW visual layout decisions, NEW page designs, or significant UI redesigns (not just adding a field to an existing form or fixing a bug in existing UI), this counts as creative work.

Routine template changes (adding a column, fixing a label, wiring an existing pattern) do NOT trigger brainstorming. The trigger is for work that requires design decisions about how something should look or behave -- not work that follows existing patterns.

**If ANY explicit trigger word is present OR the feature involves new design decisions:**

1. Invoke the `superpowers:brainstorming` skill BEFORE any pipeline phase
2. Pass the original prompt as context for the brainstorming session
3. Wait for the brainstorming process to complete (design doc written, user approved)
4. Save the brainstorming output to `plans/<feature-slug>/brainstorm.md`
5. Use both the original prompt AND the brainstorming spec as input to Phase 1

This is NOT optional. The brainstorming skill's hard gate ("Do NOT invoke any implementation skill until you have presented a design and the user has approved it") applies to the pipeline. The pipeline IS an implementation skill. "Having a reference pattern to copy" is NOT a reason to skip brainstorming -- the brainstorm explores whether that pattern is the right choice.

**If NO trigger words are present AND the feature is purely backend/logic:**

Skip to Phase 1. Log: "Phase 0: Creative routing check -- no creative triggers detected, skipping brainstorming."

Mark ledger item 1b as complete. Proceed to Phase 1.

## Phase 1: Assess Current State

Load the assess skill from `plugins/pipeline/skills/assess/SKILL.md`.

1. Determine the codebase area affected by the feature
2. Run the pre-plan assessment (code + UX in parallel)
3. Save the Assessment Brief to `plans/<feature-slug>/assessment.md`
4. Present key findings to the user

Mark ledger item 2 as complete.

**GATE (ledger item 3):** You MUST stop here and use AskUserQuestion to ask: "Assessment complete. Any corrections or context to add before I research?" Do NOT proceed by generating an answer to your own question. Do NOT combine this gate with Phase 2 work. The user's response is the gate -- without it, Phase 2 is blocked.

Mark item 3 when AskUserQuestion returns the user's response.

## Phase 2: Research

Load the research skill from `plugins/pipeline/skills/research/SKILL.md`.

You MUST run this phase even if you think you already have enough context. Research finds things you don't know you're missing.

1. Pass the feature description and Assessment Brief to the research orchestrator
2. Dispatch parallel research agents across all available sources (ai-memory, RAG, domain plugins, web, codebase)
3. Save the Research Brief to `plans/<feature-slug>/research.md`
4. Present the Research Brief summary to the user

**Verification:** The Research Brief file MUST exist on disk before proceeding. Run `ls plans/<feature-slug>/research.md` to confirm.

Mark ledger item 4 as complete.

**GATE (ledger item 5):** You MUST stop here and use AskUserQuestion to ask: "Research complete. Ready to plan, or want to adjust the scope?" Do NOT proceed by generating an answer to your own question. Do NOT combine this gate with Phase 3 work.

Mark item 5 when AskUserQuestion returns the user's response.

## Phase 3: Plan

Create the implementation plan. Two options:

**Option A:** If compound-engineering `/workflows:plan` is available, invoke it with the feature description, Assessment Brief, and Research Brief as context.

**Option B:** If not available, create the plan directly:

1. Use the cached Key Requirements from `plans/<feature-slug>/assessment.md` (re-read original-prompt.md only if the user gave feedback since Phase 1)
2. Break the feature into logical implementation steps
3. Identify file paths, patterns, and dependencies
4. Write acceptance criteria for each step
5. Save to `plans/<feature-slug>/plan.md`

**Verification:** The plan file MUST exist on disk before proceeding. Run `ls plans/<feature-slug>/plan.md` to confirm.

**Plan self-review (before presenting):** Re-read your own plan and check:

1. **Internal contradictions:** Do any two design decisions conflict? (e.g., "follow existing convention" in one section and "use a different approach" in another)
2. **API existence:** Does the plan propose using specific framework functions? Grep the dependency source to verify they exist in the installed version. Do NOT present a plan built on hallucinated APIs.
3. **Terminology consistency:** Does the plan use the same term for the same concept throughout?
4. **Build tool accuracy:** Do verification steps reference the actual commands from package.json / Makefile, not assumed tools?

If any check fails, fix the plan before presenting it.

Mark ledger item 6 as complete.

**GATE (ledger item 7):** You MUST stop here and use AskUserQuestion to ask: "Plan ready at `plans/<feature-slug>/plan.md`. Review it and let me know when to generate execution prompts." Do NOT proceed by generating an answer to your own question.

Mark item 7 when AskUserQuestion returns the user's response.

## Phase 4: Generate Execution Prompts

Load the promptcraft skill from `plugins/pipeline/skills/promptcraft/SKILL.md`.

1. Use the cached Key Requirements from `plans/<feature-slug>/assessment.md` (re-read original-prompt.md only if the user gave feedback since Phase 1)
2. Decompose the plan into chunks
3. Extract context for each chunk from the Assessment and Research Briefs
4. Perform overlap analysis
5. Generate self-contained execution prompts
6. Generate the manifest
7. Save to `plans/<feature-slug>/manifest.json` and `plans/<feature-slug>/prompts/`

**Verification:** Run `ls plans/<feature-slug>/manifest.json plans/<feature-slug>/prompts/` to confirm all files exist on disk.

Mark ledger item 8 as complete.

**Requirements coverage check (ledger item 9):** Read the cached Key Requirements from `plans/<feature-slug>/assessment.md`. For each requirement, verify at least one chunk's acceptance criteria covers it. Present the coverage map:

```
Requirements Coverage:
  1. [Requirement] -> chunk-XX (criterion #N)
  2. [Requirement] -> chunk-YY (criterion #M)
  3. [Requirement] -> NOT COVERED -- adding to chunk-ZZ
```

If any requirement is uncovered, fix it before proceeding. Mark item 9 when coverage is 100%.

Present the manifest summary: chunk count, parallel groups, overlap risk, requirements coverage.

## Phase 5: Adversarial Review + Sprint Contract Negotiation

Launch the plan-adversary agent from `plugins/pipeline/agents/workflow/plan-adversary.md`.

1. Pass the plan, prompts, manifest, AND `original-prompt.md`
2. The adversary reviews for feasibility, completeness, and DM standards
3. The adversary also produces **sprint contract addendums** -- additional acceptance criteria per chunk that the promptcraft may have missed (edge cases, error states, browser-verifiable criteria)
4. Merge the adversary's proposed criteria into the chunk prompts
5. If verdict is REVISE: apply revisions and re-submit (max 3 rounds)
6. If verdict is APPROVED: proceed

Mark ledger item 10 as complete.

**GATE (ledger item 11):** You MUST stop here and use AskUserQuestion to present the approved prompts: "Prompts reviewed and approved by adversary. Review the prompts in `plans/<feature-slug>/prompts/` and approve when ready to execute." Do NOT proceed by generating an answer to your own question.

Mark item 11 when AskUserQuestion returns the user's explicit approval.

## Phase 6: Execute

**Budget nudge (before pre-flight):** If the Progress Ledger shows more than 10 completed items AND the session has been running over 90 minutes of wall-clock time, pause and use AskUserQuestion: "Pipeline has been running a while. Continue with full scope (zero-deferral default), or break remaining work into a follow-up fix-pass run? Zero-deferral is the default; a split is the exception." This is a soft nudge, not a hard gate -- the default answer is "continue."

**Pre-flight check:**

1. Confirm bypass permissions mode is active
2. Confirm git working tree is clean (`git status --porcelain`)
3. Confirm on main branch with latest changes

**You MUST launch the execution-orchestrator agent.** You MUST NOT execute chunks yourself with general-purpose agents. The execution-orchestrator handles worktree isolation, input guardrails, Fix Philosophy injection, output validation, dm-review-loop after each chunk, merging, final full dm-review, and memory capture. If you skip it, all of those steps get skipped.

Launch the execution-orchestrator agent from `plugins/pipeline/agents/workflow/execution-orchestrator.md` with:

- The manifest path: `plans/<feature-slug>/manifest.json`
- The prompts directory: `plans/<feature-slug>/prompts/`
- The feature branch name from the manifest

Wait for the orchestrator to complete. Mark ledger item 12 as complete.

## Phase 7: Deliver

Present the execution summary from the orchestrator.

### Orchestrator Blind Spots (read before starting Phase 7)

The execution-orchestrator verifies per-chunk, but `curl` + `grep` + HTML regex CANNOT observe:

- **JS runtime state** -- whether `window.assemblyPopup` actually attached, whether an event listener bound, whether a module imported.
- **Visual cardinality** -- whether a button appears "exactly once" vs duplicated via a second code path that independently satisfies the same DOM assertion.
- **Layout regressions** -- whether a neighboring card got pushed off-screen by your margin change.
- **Duplicate elements** -- an AC saying "Post comment button is present" passes when there are two Post comment buttons as long as at least one is there.

If the orchestrator ran in `executionMode: curl_fallback`, assume ALL of the above were unverified. The caller (you) must verify them in Phase 7.

### Ambiguity Protocol Check (pipeline v1.10.0+)

The three-layer ambiguity defence added in v1.10.0 leaves an audit trail. Inspect each chunk's commit and receipt:

- **Commit trailers** -- each chunk commit may contain two trailers: `Chose: <interpretation>` and `Rejected: <alt-1>; <alt-2>`. Extract with `git log <featureBranch> --format=%B | git interpret-trailers --parse --only-trailers` or grep. Trailers are emitted only when a subagent had to pick between defensible interpretations in autonomous mode.
- **Receipt flag** -- chunk receipts may include `ambiguity_resolved: true` with a one-line summary. Cross-check against the commit trailers.
- **If trailers or the flag are present,** review the chosen path. If the chosen interpretation conflicts with what the user actually wanted, this is a Phase 7 gap -- fix inline on the feature branch, then re-run `/dm-review-quick` on the affected chunk.
- **If neither signal is present,** either the chunks were unambiguous OR the subagents silently picked. The plan-adversary's Sprint Contract Negotiation should have caught the latter at Phase 5; if you suspect it didn't, sample one or two chunks' rendered output against the original prompt before approving merge.

### Caller Verification Checklist (mandatory when ANY UI/Integration chunk was executed, OR executionMode was `curl_fallback`)

Complete ALL THREE checks. Record evidence in the delivery report.

- [ ] **(1) Screenshot at minimum one viewport.** Desktop 1440px is mandatory. Also capture mobile 375px if the original prompt mentions responsive behavior, mobile, narrow viewport, or touch interaction. Save to `plans/<feature-slug>/screenshots/phase7-*.png`.
- [ ] **(2) One runtime state eval per new JS module.** For each chunk that added a JS module, run `browser_evaluate` with a snippet like `typeof window.<globalName>` or `typeof document.querySelector('<selector>').dataset.<attr>` to confirm the module attached at runtime. curl confirms the file responds; `browser_evaluate` confirms it actually ran. Record the snippet and its result.
- [ ] **(3) Cardinality check per AC containing quantity language.** For every acceptance criterion containing "exactly N", "no duplicate", "only one", "should replace", or "instead of", run a `browser_evaluate` that counts matching elements: e.g. `document.querySelectorAll('button[type=submit]').length`. An AC that says "Post comment should REPLACE the old button" passes only when count is 1, not 2.

Any check that cannot be completed (no browser tools, dev server down) MUST be recorded as `FAILED -- no browser tools` in the delivery report, and the merge recommendation MUST escalate to `BLOCKED PENDING CALLER VERIFICATION`. Do NOT deliver as "ready" without these evidence items.

### Caller Visual Verification (mandatory for UI features)

If ANY chunk in the manifest was classified as UI or Integration, you MUST visually verify the rendered output yourself. Do not trust the orchestrator's self-report for visual quality. The orchestrator verifies per-chunk; you verify the whole.

If all chunks were Logic-only, skip to the requirements cross-check.

1. **Discover the design spec.** Check these locations in order:
   - `plans/<feature-slug>/brainstorm.md`
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

If you cannot provide evidence (no browser tools), you MUST state: "Visual verification incomplete -- no browser tools available. The following requirements could not be visually verified: [list]." This is NOT a passing verification.

**Requirements cross-check (ledger item 13):** Use the cached Key Requirements from `plans/<feature-slug>/assessment.md`. (At this phase, re-read original-prompt.md is justified ONLY if the user has layered feedback on during execution -- otherwise the cache is authoritative.) Verify every Key Requirement was addressed in the final branch. Each entry requires an evidence type:

```text
Requirements Cross-Check:
  1. [Requirement] -> Addressed in [commit/file] -- Evidence: [screenshot/build pass/computed style/test pass]
  2. [Requirement] -> Addressed in [commit/file] -- Evidence: [type]
  3. [Requirement] -> NOT ADDRESSED -- [reason]
```

Entries marked "Addressed" without an evidence type are treated as NOT ADDRESSED. If any requirement was missed, report it explicitly: "The following requirements from your original prompt were not addressed: [list]."

**Ops Dashboard write:** After the requirements cross-check, write a structured row to the Agent Activity Log database in Notion:

1. Look up "Agent Activity Log DB" ID from the `DM Notion Workspace` ai-memory entity
2. If the ID is not found, skip silently (database not yet created)
3. Create a page in the Agent Activity Log database using `notion-create-pages`:
   - **Entry:** "Pipeline: <feature-slug>"
   - **Type:** "Pipeline Run"
   - **Status:** "Clean" if final review was clean, "Needs Attention" if findings remain, "Blocked" if pipeline failed
   - **Date:** Today's date
   - **Findings:** Total findings from the orchestrator's final review
   - **P1 Count:** P1 findings from the final review
   - **Chunks:** Number of chunks executed
   - **Merge Rec:** Merge recommendation from the final review (CLEAN / APPROVE WITH FIXES / BLOCKS MERGE)
   - **Branch:** Feature branch name
4. Update the created page with `notion-update-page` to set relations:
   - **Project:** Link to the project's Notion page (from `memory/project-notion.md` if available)
   - **Sprint:** Link to the current "In progress" sprint (query Sprints DB)
5. If any Notion MCP call fails, skip silently -- ai-memory (captured by the orchestrator) is the primary record

Mark item 13 as complete.

**GATE (ledger item 14):** Use AskUserQuestion to ask: "Feature branch `<branch>` is ready. Review it with `git log main..<branch>`. Want to create a PR, give feedback for another iteration, or done?"

**If feedback given:** Append the new feedback to `original-prompt.md` as a new section (`## Iteration N Feedback`), extract new requirements, and re-enter at Phase 3 or Phase 4. This ensures feedback accumulates rather than replacing context.

## Self-Audit

Before delivering to the user, verify your own compliance by answering these questions honestly:

0. If the feature involved creative/UI work, did I run the brainstorming skill first (or the scoped brainstorm from Phase 0a)?
1. Did I save the original prompt to disk?
2. Did I run the full assessment (not just skim the code)?
3. Did I run the full research phase (not skip it)?
4. Did I pause for user input at every GATE?
5. Did I generate prompts and manifest to disk (not just in context)?
6. Did I check requirements coverage against the cached Key Requirements?
7. Did I run the adversarial review (max 4 rounds)?
8. Did I launch the actual execution-orchestrator agent (not run chunks manually)?
9. Did the orchestrator run dm-review-loop after each chunk?
10. Did the orchestrator run a final full dm-review?
11. Did the orchestrator record the session to ai-memory?
12. **Curl-fallback audit:** If the orchestrator ran in `executionMode: curl_fallback`, did I complete the 3-item Caller Verification Checklist (screenshot, runtime eval, cardinality) with attached evidence? If the answer is "no" for any item, this self-audit FAILS LOUDLY -- I must not deliver until every check has evidence or the merge recommendation is set to `BLOCKED PENDING CALLER VERIFICATION`. "I ran curl and grep" is NOT visual verification.
13. **Runtime state audit:** For every new JS module added in this feature, did I verify it attached at runtime via `browser_evaluate` (typeof check, global presence, listener binding)? curl confirms the file exists; `browser_evaluate` confirms it runs.
14. If the feature involved UI work beyond curl_fallback mode, did I (the caller) visually verify the rendered output in the browser, rather than trusting the orchestrator's self-report?

If the answer to any question is "no," go back and do it. Do not deliver with skipped steps.
