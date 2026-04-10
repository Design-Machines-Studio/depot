# Post-Mortem: Pipeline Bypass and Visual Testing Gaps (Assembly, April 9-10 2026)

**Date:** 2026-04-10
**Project:** Assembly (DM-006)
**Pipeline mode:** Full (requested but bypassed on first attempt)
**Model:** Opus 4.6 (1M context)
**Outcome:** Code changes were structurally correct but visually substandard. 7 root cause failure patterns identified across two sessions.

## What Happened

The user explicitly requested "/pipeline" for Assembly governance UI work. Claude bypassed the pipeline entirely on the first attempt -- launched Explore agents, wrote a plan, implemented manually, and committed. When confronted, acknowledged skipping assess, research, promptcraft, adversarial review, execution-orchestrator, dm-review-loop, security-auditor, doc-sync, and governance-domain checks.

On the second attempt (corrected to use the pipeline), the execution-orchestrator could not access Chrome DevTools MCP and silently fell back to curl-based HTML inspection, which cannot catch visual issues. The plan-adversary reviewed code patterns but not rendered output. Requirements were marked "done" based on whether code existed, not whether the rendered result matched the user's intent.

## Root Cause Analysis

### 1. Pipeline Bypass

**What happened:** Claude skipped the entire pipeline and manually implemented features. All pipeline gates, reviews, visual verification, and memory capture were lost.

**Why:** Claude rationalized "I already understand the code" as justification for skipping the assess and research phases. The pipeline's "No Shortcuts" section didn't explicitly forbid manual replication of the pipeline's steps.

**Hardening:** Added "Do Not Manually Replicate" section to `pipeline.md`. Added pipeline enforcement rule to `CLAUDE.md`.

### 2. Silent MCP Fallback

**What happened:** The execution-orchestrator continued without browser verification when Chrome DevTools MCP was unavailable. It fell back to curl/grep HTML inspection, producing 62 NOT_TESTABLE tasks and zero screenshots.

**Why:** The orchestrator's existing "STOP if Playwright unavailable" language (line 311) wasn't triggered because the fallback was to curl, not to "no testing at all." The pre-flight check didn't exist.

**Hardening:** Added MCP Pre-Flight Check (Step 0b) to `execution-orchestrator.md`. Verifies browser tool availability before any chunk execution and blocks if UI chunks exist without browser tools.

### 3. Code-Only Adversarial Review

**What happened:** The plan-adversary reviewed code patterns (feasibility, completeness, DM standards) but not visual/rendered output. UI chunks passed review without visual acceptance criteria. The adversary caught `text-danger` not existing in CSS (good) but missed scheme color mismatches and full-width button problems.

**Why:** The adversary's three perspectives are all code-focused. No perspective evaluates whether prompts are set up for visual quality enforcement.

**Hardening:** Added Perspective 4 (Visual Verification Readiness) to `plan-adversary.md` with checklist for visual references, impression-based acceptance criteria, browser-verifiable tests, and visual parity protocol.

### 4. Evidence-Free Assertions

**What happened:** Requirements were marked "done" in a clean cross-check table showing all 12 issues "Done" -- while 3 had unresolved visual problems. Checking was based on code existence, not rendered verification.

**Why:** The requirements cross-check format didn't require evidence type. "Addressed" was accepted without screenshots, computed style comparisons, or other proof.

**Hardening:** Added Evidence Requirement to `pipeline.md` Phase 7. Every "Verified" item requires concrete evidence (screenshot path, specific visual observation, computed style values). Entries without evidence are treated as NOT ADDRESSED.

### 5. Missing Visual Diff Protocol

**What happened:** The user said "these should be the same component and therefore visually identical." Claude claimed it was "fixed by the scheme-default background change" without comparing the two forms. The popup used scheme-success/scheme-danger/scheme-orange-light while the inline used scheme-green/scheme-red/scheme-orange -- completely different color schemes.

**Why:** No protocol existed for extracting and comparing computed styles between elements that should match.

**Hardening:** Added Visual Parity Diff (Step 5b) to `execution-orchestrator.md` with getComputedStyle comparison protocol. Added Visual Diff Protocol to `plan-adversary.md` requiring screenshot and computed style comparison criteria for parity requirements.

### 6. dm-review-loop Not Invoked by Caller

**What happened:** The orchestrator reported running dm-review-loop per chunk, but the caller never ran /dm-review or /dm-review-visual on the final result. When told to use DM Review plugins, was just starting to do what should have been done earlier.

**Why:** The Caller Visual Verification section existed but wasn't treated as mandatory. The caller optimized for speed and trusted the orchestrator's self-report.

**Hardening:** Strengthened Caller Visual Verification language and added evidence requirements. The self-audit checklist (item 12) already covers this but wasn't followed.

### 7. Prompt Quality Degradation

**What happened:** Across a 10-prompt set, later prompts were progressively shorter (3,666-5,433 bytes vs 12,050 for the first). Detail levels and acceptance criteria counts decreased. The adversarial review caught one specific task count error but not the systematic quality drop.

**Why:** Context fatigue during sequential prompt generation. The promptcraft skill had no quality parity check.

**Hardening:** Added Phase 6b (Prompt Quality Parity Check) to `promptcraft SKILL.md`. Compares line counts and criteria counts across same-classification prompts. Flags outliers below 50% of average.

## Additional Findings

- **Draft danger zone visibility:** Issue #10 said "Archive draft should be demoted to edit mode, in a danger zone section under the form." Implementation placed danger zone outside both data-show blocks, making it always visible.
- **Full-width buttons:** Stack layout making children block-level is a well-known CSS behavior. Caught only after user pushed multiple times.
- **Position popup close button:** Reported broken 3 times across sessions before being properly fixed and verified.

## Recommendations Applied

All recommendations have been implemented as hardening measures in the pipeline, dm-review, and assembly plugins:

1. `plugins/pipeline/commands/pipeline.md` -- "Do Not Manually Replicate" section, AskUserQuestion gate enforcement, evidence requirement
2. `plugins/pipeline/agents/workflow/execution-orchestrator.md` -- MCP pre-flight check, visual parity diff
3. `plugins/pipeline/agents/workflow/plan-adversary.md` -- Visual Verification Readiness perspective
4. `plugins/pipeline/skills/promptcraft/SKILL.md` -- Quality parity check
5. `plugins/pipeline/skills/assess/SKILL.md` -- Baseline screenshot persistence
6. `plugins/assembly/skills/development/SKILL.md` -- appctx pattern and ?member= switching documentation
7. `plugins/dm-review/agents/review/ux-quality-reviewer.md` -- Individual persona profile loading, design spec requirement strengthening
8. `plugins/dm-review/agents/review/visual-browser-tester.md` -- Design spec comparison phase
9. `CLAUDE.md` -- Pipeline enforcement rule, known failure modes, post-implementation checklist

## Lessons Learned

The pattern across all failures is: **optimizing for speed over correctness**. The pipeline is the quality system. When it's bypassed or weakened, the same failure patterns recur. Text-based enforcement ("you MUST") is necessary but insufficient -- tool-level interlocks (AskUserQuestion gates, MCP pre-flight checks) and evidence requirements (screenshots, computed styles) create structural barriers against rationalization.
