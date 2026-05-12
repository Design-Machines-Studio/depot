---
name: visual-test
description: Standalone visual browser testing for rendered web pages. Tests responsive layouts, interactive states, and runtime accessibility using Playwright MCP tools. Use with /dm-review-visual, /dm-review-visual <url>, or when the user says "test this visually", "check in the browser", "test responsive", "visual QA", or "check the page".
disable-model-invocation: true
argument-hint: "[url]"
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

- `/dm-review-visual` — auto-detect dev server, test all discoverable pages
- `/dm-review-visual <url>` — test a specific URL
- `/dm-review-visual --states` — focus on interactive state testing only
- `/dm-review-visual --a11y` — focus on runtime accessibility checks only

## Process

### Phase 1: Target Resolution

**If a URL argument was provided:** use it directly.

**If no URL provided:** detect the dev server by trying these URLs in order with `browser_navigate`:

1. `http://localhost:8080` (Go+Templ+Datastar)
2. `http://localhost:3000` (Node/general)
3. `https://[project-name].ddev.site` (Craft CMS DDEV)
4. `http://localhost:5173` (Vite)

Use the first URL that loads successfully. If none respond, ask the user for the URL.

If Playwright tools fail, follow the Browser Fallback Chain defined in the `visual-browser-tester` agent definition. Never silently skip browser testing.

**Local domain preference:** For Assembly projects, prefer local `.site`/`.test` TLD domains (e.g., `http://assembly.coop.site`) over `localhost:PORT`. These are configured via Caddy/DDEV and match the visual-browser-tester's URL discovery order.

**Page discovery:** After connecting to the dev server, discover testable pages:

- **Assembly Baseplate:** Scan `internal/fixtures/*/routes.go` for route registrations (`r.Get`, `r.Post`, `r.Handle`) to build the testable URL list. Each fixture's routes file declares all its HTTP endpoints.
- Check for a sitemap at `/sitemap.xml`
- Scan the codebase for route registrations (Go handlers) or template files (Twig, HTML)
- Use the base URL `/` as the minimum test target
- If git diff context is available, prioritize pages affected by changed files

### Phase 2: Visual Testing

Read the visual-browser-tester agent definition from `plugins/dm-review/agents/review/visual-browser-tester.md` and execute its full eight-phase testing protocol (Baseline, Responsive, State Testing, Accessibility Runtime, Live Wires, UX Design, Visual Design Quality, Live Wires CSS Compliance).

Use `${CLAUDE_SKILL_DIR}/references/breakpoints.md` for viewport dimensions and `${CLAUDE_SKILL_DIR}/references/state-testing.md` for the interactive element state matrix.

**Flag handling:**

- `--states` — run Phase C (State Testing) only
- `--a11y` — run Phase D (Accessibility Runtime) only
- No flag — run all eight phases

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
- [url @ breakpoint] Description — reference

### Serious (P2)
- [url @ breakpoint] Description — reference

### Moderate (P3)
- [url @ breakpoint] Description — reference

### Approved
- [url] Description of what passes

### Screenshots
Summary of screenshots taken during testing.
```

After the report, suggest next steps:

- If findings exist: "Fix the P1/P2 issues and re-run `/dm-review-visual` to verify."
- If clean: "Visual tests passed. Run `/dm-review` for a full code review."

## Reference Files

- `${CLAUDE_SKILL_DIR}/references/breakpoints.md` — Responsive breakpoint definitions and testing rationale
- `${CLAUDE_SKILL_DIR}/references/state-testing.md` — Interactive element state matrix by component type

## Playwright MCP Tools

This skill uses the Playwright MCP tools prefixed `mcp__plugin_compound-engineering_pw__browser_*`. Load them with `ToolSearch` before use:

```
ToolSearch query: "+pw browser_navigate"
```

Key tools: `browser_navigate`, `browser_take_screenshot`, `browser_resize`, `browser_snapshot`, `browser_press_key`, `browser_hover`, `browser_click`, `browser_evaluate`, `browser_console_messages`, `browser_fill_form`, `browser_wait_for`.
