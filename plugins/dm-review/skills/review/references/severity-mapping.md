# Severity Mapping

Rules for mapping each agent's native severity terminology to the unified P1/P2/P3 system.

## Zero-Deferral Policy (default)

All findings at all severities -- P1, P2, AND P3 -- must be fixed before the branch is considered ready to merge. "CLEAN" means zero findings. P3-only does NOT mean clean; it means APPROVE WITH FIXES and P3s are mandatory. The explicit opt-out is `--allow-defer-p3`, which requires each deferred item to carry a written justification and a tracking destination. See `plugins/dm-review/commands/dm-review.md` for the full policy statement.

---

## Unified Severity Levels

| Level | Label | Meaning | Merge Impact |
|-------|-------|---------|-------------|
| **P1** | Blocks Merge | Must fix before merging | Review recommendation = BLOCKS MERGE |
| **P2** | Should Fix | Fix soon, track if not immediate | Review recommendation = APPROVE WITH FIXES |
| **P3** | Fix Before Merge | Improvement required. Mandatory under zero-deferral policy. Resolve before merge or explicitly defer with `--allow-defer-p3` + justification. | APPROVE WITH FIXES (mandatory) |

---

## Severity Decision Tree

For each finding, walk this tree to assign consistent severity across all agents:

1. **Can the user complete their primary task?** NO -- P1
2. **Is there a WCAG, security, or legal compliance failure?** YES -- P1
3. **Can the user complete the task but with confusion or extra effort?** YES -- P2
4. **Is this a pattern that erodes trust or professionalism?** YES -- P2
5. **Is this a polish issue visible to a discerning eye?** YES -- P3
6. **Is this a preference or optimization with no user impact?** -- Not a finding

This tree ensures that a missing error state on a critical form (user stranded = P1) is classified differently from a missing hover state on a non-critical link (polish = P3), regardless of which agent detects it.

---

## Agent-Specific Mappings

### dm-review Agents

| Agent | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|------------|------------|-------------|
| **code-simplicity-reviewer** | God functions (100+ lines), keyboard traps, dead code hiding bugs | Unnecessary abstraction, redundant logic, unclear naming | Verbose but correct code, minor style preferences |
| **security-auditor** | SQL injection, XSS, auth bypass, credential exposure | Missing CSRF token, permissive CORS, unvalidated input | Missing rate limiting, verbose error messages |
| **pattern-recognition-specialist** | Circular dependencies, data races, resource leaks | Anti-patterns (God objects, feature envy), naming inconsistencies | Minor duplication, magic numbers in non-critical paths |
| **architecture-reviewer** | Layer violations (templates calling DB), broken module boundaries | SOLID violations, excessive coupling, wrong package | Minor cohesion issues, suboptimal but functional structure |
| **doc-sync-reviewer** | API docs contradict implementation, CLAUDE.md has wrong paths | README outdated, missing docs for new features | Minor formatting, stale examples |
| **test-coverage-reviewer** | Existing tests now fail | Changed code has no tests (when project has test infrastructure) | Missing edge case tests |
| **go-build-verifier** | Compilation failure | `go vet` warnings | — |
| **craft-reviewer** | N+1 queries in loops, `\|raw` on user input | Missing eager loading, no null checks on relations | Suboptimal query patterns, minor template issues |
| **visual-browser-tester** | Layout completely broken at any breakpoint, keyboard trap in browser, axe-core critical violations, focus indicators missing entirely, JS exceptions preventing render | Layout degraded at mobile (content cut off, overlapping, horizontal scroll), interactive states not visually distinct, axe-core serious violations, console JS errors, contrast failures, missing scheme tokens | Minor spacing inconsistencies, axe-core moderate violations, responsive polish, baseline rhythm misalignment |
| **ux-quality-reviewer** | Navigation dead ends, missing error states that strand users, primary action invisible or unreachable, voting interface ambiguous enough to cause wrong votes | Missing feedback states (loading, empty, success), inconsistent interaction patterns, poor hierarchy burying content, missing empty states on lists/tables, AI slop score below 20/25 | Spacing inconsistencies, minor alignment drift, suboptimal typography, missing hover states, orphaned headings, edge case overflow |
| **ui-standards-reviewer** | Missing component states that strand users (no error feedback, no loading indicator on async actions), broken visual hierarchy (can't tell primary from secondary action) | Inconsistent spacing system (hardcoded values instead of `--line-*`), missing empty/loading states, amateur patterns (spinners instead of skeletons, `alert()` instead of inline errors, centered text in left-aligned layouts), missing hover/focus transitions, AI slop score below 20/25 | Minor polish gaps (border-radius inconsistency, suboptimal shadow hierarchy, minor transition timing) |

### Depot-Native Agents (from other plugins)

| Agent | Plugin | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|--------|------------|------------|-------------|
| **a11y-html-reviewer** | accessibility-compliance | Missing form labels, keyboard traps, no alt on functional images | Broken heading hierarchy, missing landmarks, generic link text | Missing aria-describedby, suboptimal ARIA |
| **a11y-css-reviewer** | accessibility-compliance | `outline: none` without replacement, failing contrast on primary text | Animations without motion check, targets below 24px | Low contrast on secondary text, missing forced-colors |
| **a11y-dynamic-content-reviewer** | accessibility-compliance | Click handlers on non-interactive elements, no live regions for state changes | Focus lost after morph, loading states silent | ARIA states not synced, suboptimal focus target |
| **css-reviewer** | live-wires | — (errors) | Cascade layer violations, class invention, naming rule breaks | Token recommendations, container query suggestions |
| **voice-editor** | ghostwriter | — | Spine failure (no point of view), AI pattern detected | Rhythm issues, minor register drift |
| **governance-domain** | council | Legal compliance failure (wrong voting threshold) | Architecture violation (fixture boundaries) | Naming recommendations, values alignment |

---

### Browser Agent Phases

| Agent | Phase | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|-------|------------|------------|-------------|
| **visual-browser-tester** | Live Wires CSS Compliance | — | Invented classes when primitives exist, arbitrary values instead of tokens, media queries instead of container queries | Minor token recommendations, alternative primitive patterns (mandatory -- zero-deferral applies) |

UX Design and Visual Design Quality phases have moved to **ux-quality-reviewer** (see dm-review Agents table above).

---

## Escalation Rules

1. **Any P1 from any agent** -> merge recommendation = `BLOCKS MERGE`
2. **P2 present (any count, regardless of P3)** -> merge recommendation = `APPROVE WITH FIXES` (must fix before merge)
3. **P3 only (no P1/P2)** -> merge recommendation = `APPROVE WITH FIXES -- P3s mandatory under zero-deferral.` This is NOT clean. Run `/dm-review-fix` (or `/dm-review-loop`) to resolve every P3 before merging. To explicitly opt out for one or more P3s, pass `--allow-defer-p3` to the review-fix command with written justifications and tracking destinations.
4. **Zero findings** -> merge recommendation = `CLEAN`
5. **Security P1** always escalates -- no exceptions, no "we'll fix it later"
6. **Accessibility P1** always escalates -- legal compliance (EAA, ADA)
7. **Governance P1** always escalates -- statutory requirements
8. **Visual P1** always escalates -- if layout is completely broken or keyboard traps exist in the rendered page

## De-escalation Rules

1. P3 findings are shown in the report with full detail (same format as P1/P2) AND must be fixed before the branch is considered ready to merge (zero-deferral default). They no longer carry a "no merge impact" free pass.
2. Findings from agents that partially overlap (e.g., both a11y-css-reviewer and css-reviewer flag the same file) count as ONE finding at the higher severity.
3. If a finding is already tracked in a known issue / TODO with a specific ticket ID: note the tracker reference in the todo file AND still require a fix in this branch OR an explicit `--allow-defer-p3` with justification. "It's tracked" is not a substitute for "it's fixed."
