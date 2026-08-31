---
name: visual-test
description: Standalone visual browser testing for rendered web pages. Tests responsive layouts, interactive states, and runtime accessibility using Playwright MCP tools. Use with /dm-review-visual, /dm-review-visual <url>, or when the user says "test this visually", "check in the browser", "test responsive", "visual QA", or "check the page".
disable-model-invocation: true
argument-hint: "[url|--states|--a11y|--all]"
allowed-tools:
  - mcp__plugin_compound-engineering_pw__browser_navigate
  - mcp__plugin_compound-engineering_pw__browser_take_screenshot
  - mcp__plugin_compound-engineering_pw__browser_snapshot
  - mcp__plugin_compound-engineering_pw__browser_resize
  - mcp__plugin_compound-engineering_pw__browser_click
  - mcp__plugin_compound-engineering_pw__browser_evaluate
  - mcp__plugin_compound-engineering_pw__browser_close
  - mcp__plugin_compound-engineering_pw__browser_tabs
  - mcp__plugin_compound-engineering_pw__browser_press_key
  - mcp__plugin_compound-engineering_pw__browser_hover
  - mcp__plugin_compound-engineering_pw__browser_console_messages
  - mcp__plugin_compound-engineering_pw__browser_fill_form
  - mcp__plugin_compound-engineering_pw__browser_wait_for
---

# Visual Browser Testing

Standalone visual testing that loads pages in a real browser, screenshots at multiple breakpoints, tests interactive states, and runs runtime accessibility checks. This is the same testing protocol used by the `visual-browser-tester` agent in `/dm-review`, but invokable independently.

## Usage

- `/dm-review-visual` -- use an attached T3 preview or optional tracked
  `.dm/ui-review.json`, then test the affected selected cases
- `/dm-review-visual <url>` -- test a specific URL
- `/dm-review-visual --states` -- focus on interactive state testing only
- `/dm-review-visual --a11y` -- focus on runtime accessibility checks only
- `/dm-review-visual --all` -- run the complete repository-declared matrix

## Process

### Phase 1: Target Resolution

**If a URL argument was provided:** use it directly.

**If no URL provided:** first use an already attached, automation-capable T3
preview and its exact current URL. Otherwise use optional tracked
`.dm/ui-review.json` through the shared `ui-review-readiness.md` start/readiness
contract. Do not scan localhost ports, infer a target from the project type, or
guess a mutating start command.

This command explicitly requires rendered evidence. Run the shared helper with
`--visual-required true`. If neither source exists or navigation cannot be
proved, record `target unavailable` and emit one `REVIEW INCOMPLETE` coverage
result with the exact missing
persona/scenario/route/engine/viewport cases and one next action. Never return a
bare stop, skip, approval, or pass.

If Playwright tools fail, follow
`plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md`
and the Browser Fallback Chain defined in the `visual-browser-tester` agent.
The receipt must preserve every failed and recovered attempt, prove a primary
process/session quit plus fresh relaunch, then try a genuinely different engine.
Exhaustion returns blocked `human_help_required` with exact missing cases. Never
silently skip required browser testing, and never treat curl as browser proof.

**Local target:** Use the exact selected URL. Do not substitute a preferred
domain or guessed port.

**Case selection:** Load the review skill's `ui-case-selection.md`. Ordinary
invocations start from changed rendered files/routes, matching prototype and
acceptance cases, directly affected dimensions, and at most one justified
baseline. Do not widen supported engine/viewport declarations into a full
matrix. `--all` is the explicit full-matrix mode.

Map changed source to candidate pages without making every candidate required:

- **Assembly Baseplate:** Scan `internal/fixtures/*/routes.go` for route registrations (`r.Get`, `r.Post`, `r.Handle`) to build the testable URL list. Each fixture's routes file declares all its HTTP endpoints.
- Check for a sitemap at `/sitemap.xml`
- Scan the codebase for route registrations (Go handlers) or template files (Twig, HTML)
- Use the base URL `/` as the minimum test target
- If git diff context is available, select pages affected by changed files

### Phase 2: Visual Testing

Read the visual-browser-tester agent definition from `plugins/dm-review/agents/review/visual-browser-tester.md` and execute its full eight-phase testing protocol (Baseline, Responsive, State Testing, Accessibility Runtime, Live Wires, UX Design, Visual Design Quality, Live Wires CSS Compliance).

Use `${CLAUDE_SKILL_DIR}/references/breakpoints.md` for viewport dimensions and `${CLAUDE_SKILL_DIR}/references/state-testing.md` for the interactive element state matrix.

**Flag handling:**

- `--states` -- run Phase C (State Testing) only
- `--a11y` -- run Phase D (Accessibility Runtime) only
- `--all` -- run all phases for the complete declared case matrix
- No flag -- run all eight phases

### Phase 3: Report

Output findings using the standard P1/P2/P3 format:

```markdown
## Visual Browser Testing Report

**Date:** [today]
**Target:** [URL or project name]
**Pages Tested:** [count]
**Breakpoints:** 320px, 768px, 1024px, 1440px

---

### Merge Recommendation

[BLOCKS MERGE / APPROVE WITH FIXES / CLEAN]

---

### Critical (P1)
- [url @ breakpoint] Description -- reference

### Serious (P2)
- [url @ breakpoint] Description -- reference

### Moderate (P3)
- [url @ breakpoint] Description -- reference

### Approved
- [url] Description of what passes

### Screenshots
Summary of screenshots taken during testing.
```

After the report, suggest next steps:

- If findings exist: "Fix every P1/P2/P3 issue and re-run `/dm-review-visual` to verify."
- If clean: "Visual tests passed. Run `/dm-review` for a full code review."

## Reference Files

- `${CLAUDE_SKILL_DIR}/references/breakpoints.md` -- Responsive breakpoint definitions and testing rationale
- `${CLAUDE_SKILL_DIR}/references/state-testing.md` -- Interactive element state matrix by component type

## Playwright MCP Tools

This skill uses the Playwright MCP tools prefixed `mcp__plugin_compound-engineering_pw__browser_*`. Load them with `ToolSearch` before use:

```
ToolSearch query: "+pw browser_navigate"
```

Key tools: `browser_navigate`, `browser_take_screenshot`, `browser_resize`, `browser_snapshot`, `browser_press_key`, `browser_hover`, `browser_click`, `browser_evaluate`, `browser_console_messages`, `browser_fill_form`, `browser_wait_for`.
