# Agent Registry

Complete catalog of all review agents with trigger conditions, file matchers, and source plugins.

---

## Always-Run Agents (Full + Quick Mode)

These 5 agents run on every review regardless of file types changed.

| # | Agent | Source | Model | What it reviews |
|---|-------|--------|-------|-----------------|
| 1 | code-simplicity-reviewer | dm-review | sonnet | Complexity, redundancy, dead code, over-engineering, naming clarity |
| 2 | security-auditor | dm-review | sonnet | SQL injection, XSS, CSRF, auth, input validation, data exposure |
| 3 | pattern-recognition-specialist | dm-review | sonnet | Anti-patterns, naming conventions, duplication, magic values |
| 4 | architecture-reviewer | dm-review | sonnet | Component boundaries, SOLID, coupling, layer violations |
| 5 | doc-sync-reviewer | dm-review | sonnet | CLAUDE.md, README, manual pages, docs, references, CHANGELOG |

---

## Conditional Agents (Full Mode Only)

These agents launch based on which file types were changed.

| # | Agent | Source Plugin | Trigger (file extensions) | Additional condition |
|---|-------|-------------|--------------------------|---------------------|
| 6 | a11y-html-reviewer | accessibility-compliance | `.templ`, `.twig`, `.html` | — |
| 7 | a11y-css-reviewer | accessibility-compliance | `.css` | — |
| 8 | css-reviewer | live-wires | `.css` | — |
| 9 | a11y-dynamic-content-reviewer | accessibility-compliance | `.templ`, `.js`, `.ts` | Project is Go+Templ+Datastar |
| 10 | voice-editor | ghostwriter | `.md`, `.txt` | Or user-facing text in templates |
| 11 | test-coverage-reviewer | dm-review | Any source file | Test infrastructure exists in project |
| 12 | governance-domain | council | Paths containing: `governance`, `proposal`, `voting`, `member`, `resolution`, `bylaw` | — |
| 13 | go-build-verifier | dm-review | `.go`, `.templ` | Project has `go.mod` + `docker-compose.yml` |
| 14 | craft-reviewer | dm-review | `.twig`, `.php` | Project has `craft/` or `.ddev/` |
| 15 | visual-browser-tester | dm-review | `.templ`, `.twig`, `.html`, `.css` | Dev server running. Six phases: Baseline (A), Responsive (B), State Testing (C), Accessibility Runtime (D), Live Wires (E), Live Wires CSS Compliance (F). UX design and visual design quality review moved to ux-quality-reviewer. |
| 16 | ux-quality-reviewer | dm-review | `.templ`, `.twig`, `.html`, `.css` | Dev server running. Nine phases: Information Hierarchy (1), Spacing & Alignment (2), UI State Completeness (3), Navigation & Wayfinding (4), Content Quality (5), Typography (6), Layout & Composition (7), Edge Case Resilience (8), Interaction Polish (9). Saves screenshots to `.claude/ux-review/`. |

**Trigger overlap note:** The visual-browser-tester and ux-quality-reviewer share trigger extensions with a11y-html-reviewer (`.templ`, `.twig`, `.html`) and a11y-css-reviewer/css-reviewer (`.css`). This is intentional — static agents analyze source code while the browser agents test rendered output. The visual-browser-tester owns rendering, responsive, and runtime a11y; the ux-quality-reviewer owns design quality and usability. Both perspectives are needed; the consolidator deduplicates any overlapping findings.

---

## File Extension to Agent Mapping

Quick reference for Phase 3 agent selection:

| Extension | Always-run | Conditional agents added |
|-----------|-----------|------------------------|
| `.go` | All 5 | go-build-verifier, test-coverage-reviewer |
| `.templ` | All 5 | a11y-html-reviewer, a11y-dynamic-content-reviewer, go-build-verifier, test-coverage-reviewer, visual-browser-tester, ux-quality-reviewer |
| `.css` | All 5 | a11y-css-reviewer, css-reviewer, visual-browser-tester, ux-quality-reviewer |
| `.twig` | All 5 | a11y-html-reviewer, craft-reviewer, visual-browser-tester, ux-quality-reviewer |
| `.html` | All 5 | a11y-html-reviewer, visual-browser-tester, ux-quality-reviewer |
| `.php` | All 5 | craft-reviewer, test-coverage-reviewer |
| `.js`, `.ts` | All 5 | a11y-dynamic-content-reviewer (if Go project), test-coverage-reviewer |
| `.md`, `.txt` | All 5 | voice-editor |
| `.sql` | All 5 | (security-auditor covers SQL) |
| `.json`, `.yaml`, `.toml` | All 5 | (doc-sync covers config) |

---

## Depot-Native Agent Paths

Read these files at runtime to get agent system prompts:

```
plugins/accessibility-compliance/agents/review/a11y-html-reviewer.md
plugins/accessibility-compliance/agents/review/a11y-css-reviewer.md
plugins/accessibility-compliance/agents/review/a11y-dynamic-content-reviewer.md
plugins/live-wires/agents/review/css-reviewer.md
plugins/ghostwriter/agents/review/voice-editor.md
plugins/council/agents/review/governance-domain.md
```

These paths are relative to the depot root. When the depot is installed as a plugin, the paths will be inside the plugin cache directory. Search for the file by name if the exact path is not accessible.

### dm-review Browser Agents

```
plugins/dm-review/agents/review/visual-browser-tester.md
plugins/dm-review/agents/review/ux-quality-reviewer.md
```

Both agents use Playwright MCP tools (`mcp__plugin_compound-engineering_pw__browser_*`) and require a running dev server. The **visual-browser-tester** runs six phases (Baseline, Responsive, State Testing, Accessibility Runtime, Live Wires, Live Wires CSS Compliance). The **ux-quality-reviewer** runs nine phases focused on design quality and usability (Information Hierarchy, Spacing, State Completeness, Navigation, Content, Typography, Layout, Edge Cases, Interaction Polish), uses the RAG knowledge library, and saves screenshots to `.claude/ux-review/`. If Playwright fails, visual-browser-tester follows a fallback chain; ux-quality-reviewer reports "Skipped."

---

## Agent Output Formats

All dm-review agents use this structure:

```markdown
## [Agent Name] Review

### Critical (P1)
- [file:line] Description — reference (WCAG SC / OWASP / etc.)

### Serious (P2)
- [file:line] Description — reference

### Moderate (P3)
- [file:line] Description — reference

### Approved
- [file] Description of what passes checks
```

Depot-native agents use their own formats (see their definitions). The review-consolidator normalizes all formats during synthesis.
