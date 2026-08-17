# Agent Registry

Complete catalog of all review agents with trigger conditions, file matchers, and source plugins.

---

## Always-Run Agents (Full Mode)

These 5 criteria run on every full review. They become 6 logical lanes when
OpenRouter adds the separate security lens.

Every always-run lane receives the FULL diff and is never scoped -- cross-file
judgment is what they are for. See "Diff scoping per lane" in the review
skill's Phase 4 for the closed full-diff list and the `DM_REVIEW_FULL_DIFF=1`
kill switch.

| # | Agent | Source | Coding provider | What it reviews |
|---|-------|--------|-----------------|-----------------|
| 1 | code-simplicity-reviewer | dm-review | OpenRouter, then Codex | Complexity, redundancy, dead code, over-engineering, naming clarity |
| 2a | security-auditor-codex-signoff | dm-review | Independent family, full diff, required; Codex preferred when it was not the implementer | SQL injection, XSS, CSRF, auth, input validation, data exposure |
| 2b | security-auditor-openrouter | dm-review | Kimi K3 eligible-content lens, then Codex fallback | Same criteria; never substitutes for 2a |
| 3 | pattern-recognition-specialist | dm-review | OpenRouter, then Codex | Anti-patterns, naming conventions, duplication, magic values |
| 4 | architecture-reviewer | dm-review | Codex only | Component boundaries, SOLID, coupling, layer violations |
| 5 | doc-sync-reviewer | dm-review | OpenRouter, then Codex | CLAUDE.md, README, manual pages, docs, references, CHANGELOG |

### Configurable Parallel Reviewer Role

| Role | Default agent definition | Source | Family resolution | Trigger |
|---|---|---|---|---|
| second-perspective | `codex-perspective.md` | dm-review | Reviewer family differs from every implementing family; subscription headroom first, then the filtered ordered `second-perspective` role | Full mode only; fails open unless `DM_REVIEW_SECOND_PERSPECTIVE` or legacy `DM_REVIEW_CODEX_PERSPECTIVE` is exactly `0` |

`second-perspective` runs in parallel with the selected full-mode agents and reports in the same P1/P2/P3 shape. Quick mode does not add this lane. The compatibility-named `codex-perspective.md` file is its default prompt definition, not a provider lock. It is a second-opinion lane, not a replacement for either security lane or architecture-reviewer. Every second-perspective and security sign-off receipt records `implementer_family`, `reviewer_family`, and `resolution_reason`. Legacy `model:` frontmatter is Claude Code compatibility metadata, not a provider-routing instruction.

## Quick Mode

Ordinary quick review always runs exactly `pattern-recognition-specialist` and `code-simplicity-reviewer`. It adds `ui-standards-reviewer`, `go-build-verifier`, and `craft-reviewer` only when their existing triggers apply. Security-sensitive paths escalate to full mode.

---

## Conditional Agents (Full Mode Only)

These agents launch based on which file types were changed.

| # | Agent | Source Plugin | Trigger (file extensions) | Additional condition | Diff scope |
|---|-------|-------------|--------------------------|---------------------|-----------|
| 6 | a11y-html-reviewer | accessibility-compliance | `.templ`, `.twig`, `.html` | -- | scoped |
| 7 | a11y-css-reviewer | accessibility-compliance | `.css` | -- | scoped |
| 8 | css-reviewer | live-wires | `.css` | -- | scoped |
| 9 | a11y-dynamic-content-reviewer | accessibility-compliance | `.templ`, `.js`, `.ts` | Project is Go+Templ+Datastar | scoped |
| 10 | voice-editor | ghostwriter | `.md`, `.txt` | Or user-facing text in templates | scoped |
| 11 | test-coverage-reviewer | dm-review | Any source file | Test infrastructure exists in project | full |
| 12 | governance-domain | council | Paths containing: `governance`, `proposal`, `voting`, `member`, `resolution`, `bylaw` | -- | full |
| 13 | go-build-verifier | dm-review | `.go`, `.templ` | Project has `go.mod` + `docker-compose.yml` | scoped |
| 14 | craft-reviewer | dm-review | `.twig`, `.php` | Project has `craft/` or `.ddev/` | scoped |
| 15 | visual-browser-tester | dm-review | `.templ`, `.twig`, `.html`, `.css` | Dev server running. Six phases: Baseline (A), Responsive (B), State Testing (C), Accessibility Runtime (D), Live Wires (E), Live Wires CSS Compliance (F). UX design and visual design quality review moved to ux-quality-reviewer. | scoped |
| 16 | ux-quality-reviewer | dm-review | `.templ`, `.twig`, `.html`, `.css` | Dev server running. Nine phases: Information Hierarchy (1), Spacing & Alignment (2), UI State Completeness (3), Navigation & Wayfinding (4), Content Quality (5), Typography (6), Layout & Composition (7), Edge Case Resilience (8), Interaction Polish (9). Saves screenshots to `.claude/ux-review/`. | scoped |
| 17 | ui-standards-reviewer | dm-review | `.templ`, `.twig`, `.html`, `.css` | Dev server running. Six phases: Component Quality (1), Spacing System (2), State Completeness (3), Visual Polish (4), Token Compliance (5), Comparative Assessment (6). Reads project CSS tokens in Phase 0 and evaluates against Stripe/Notion/Linear quality bar. Also runs in quick mode when UI files change. | scoped |
| 18 | migration-validator | dm-review | `.sql` | File is under a migrations directory (`migrations/` or `seeds/`). Full mode only. | scoped |

**Trigger overlap note:** The visual-browser-tester, ux-quality-reviewer, and ui-standards-reviewer all share trigger extensions with a11y-html-reviewer (`.templ`, `.twig`, `.html`) and a11y-css-reviewer/css-reviewer (`.css`). This is intentional -- static agents analyze source code while the browser agents test rendered output. The visual-browser-tester owns rendering, responsive, and runtime a11y; the ux-quality-reviewer owns design philosophy and usability; the ui-standards-reviewer owns practical SaaS quality standards and token compliance. The ux-quality-reviewer and ui-standards-reviewer intentionally overlap on spacing auditing and state completeness (both evaluate these from different lenses -- theoretical vs practical). The consolidator deduplicates any overlapping findings at the file:line level.

---

## File Extension to Agent Mapping

Quick reference for Phase 3 agent selection (FULL mode). Quick mode runs its own dispatch list in
`plugins/dm-review/skills/dm-review-quick/SKILL.md`; the two must agree on every shared trigger, and
`migration-validator` is dispatched only in full mode on `.sql` under
`migrations/` or `seeds/`; quick mode does not add this lane.

| Extension | Full-mode always-run | Full-mode conditional agents added |
|-----------|-----------|------------------------|
| `.go` | All 5 | go-build-verifier, test-coverage-reviewer |
| `.templ` | All 5 | a11y-html-reviewer, a11y-dynamic-content-reviewer, go-build-verifier, test-coverage-reviewer, visual-browser-tester, ux-quality-reviewer, ui-standards-reviewer |
| `.css` | All 5 | a11y-css-reviewer, css-reviewer, visual-browser-tester, ux-quality-reviewer, ui-standards-reviewer |
| `.twig` | All 5 | a11y-html-reviewer, craft-reviewer, visual-browser-tester, ux-quality-reviewer, ui-standards-reviewer |
| `.html` | All 5 | a11y-html-reviewer, visual-browser-tester, ux-quality-reviewer, ui-standards-reviewer |
| `.php` | All 5 | craft-reviewer, test-coverage-reviewer |
| `.js`, `.ts` | All 5 | a11y-dynamic-content-reviewer (if Go project), test-coverage-reviewer |
| `.md`, `.txt` | All 5 | voice-editor |
| `.sql` | All 5 | migration-validator (when under `migrations/` or `seeds/`) |
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
plugins/dm-review/agents/review/ui-standards-reviewer.md
plugins/dm-review/agents/review/codex-perspective.md
```

The visual-browser-tester, ux-quality-reviewer, and ui-standards-reviewer all use Playwright MCP tools (`mcp__plugin_compound-engineering_pw__browser_*`) and require a running dev server. The **visual-browser-tester** runs six phases (Baseline, Responsive, State Testing, Accessibility Runtime, Live Wires, Live Wires CSS Compliance). The **ux-quality-reviewer** runs nine phases focused on design quality and usability (Information Hierarchy, Spacing, State Completeness, Navigation, Content, Typography, Layout, Edge Cases, Interaction Polish), uses the RAG knowledge library, and saves screenshots to `.claude/ux-review/`. If Playwright fails, visual-browser-tester follows a fallback chain; ux-quality-reviewer reports "Skipped."

---

## Agent Output Formats

All dm-review agents use this structure:

```markdown
## [Agent Name] Review

### Critical (P1)
- [file:line] Description -- reference (WCAG SC / OWASP / etc.)

### Serious (P2)
- [file:line] Description -- reference

### Moderate (P3)
- [file:line] Description -- reference

### Approved
- [file] Description of what passes checks
```

Depot-native agents use their own formats (see their definitions). The review-consolidator normalizes all formats during synthesis.
