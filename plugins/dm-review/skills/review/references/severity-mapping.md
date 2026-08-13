# Severity Mapping

Rules for mapping each agent's native severity terminology to the unified P1/P2/P3 system.

## Finding Policy

P1 blocks merge and P2 must be fixed before merge. P3 is advisory: preserve complete evidence, provenance, count, and detail, but do not create mandatory work, drive convergence, or prevent `CLEAN`. See `plugins/dm-review/commands/dm-review.md` for the full policy statement.

Every P1/P2 must include concrete current evidence:

1. the affected current user or operator;
2. the reachable actor, input, or path;
3. the realistic harm or regression; and
4. the smallest adequate repair.

Security P1/P2 findings must additionally name the actual trust boundary. For Design Machines work, assume two developers, primarily first-party private repositories, trusted Fixture authors, and self-hosted co-op applications of roughly 4--50 people unless approved scope says otherwise. There is no public Fixture marketplace or hostile third-party plugin channel by default. Hypothetical actors, future marketplaces, enterprise scale, generic OWASP possibilities, and “defence in depth would be better” are P3 at most and usually not findings.

Real reachable authentication or authorization bypass, credential disclosure, unsafe destructive operations, corruptible state or backups, public untrusted input, release/update integrity failures, and false verification claims remain blocking at their supported severity.

---

## Unified Severity Levels

| Level | Label | Meaning | Merge Impact |
|-------|-------|---------|-------------|
| **P1** | Blocks Merge | Must fix before merging | Review recommendation = BLOCKS MERGE |
| **P2** | Should Fix | Fix soon, track if not immediate | Review recommendation = APPROVE WITH FIXES |
| **P3** | Advisory | Improvement recommendation. Retain visibly with full evidence and provenance; no mandatory fix. | CLEAN when no P1/P2 |

---

## Severity Decision Tree

For each finding, walk this tree to assign consistent severity across all agents:

1. **Can the user complete their primary task?** NO -- P1
2. **Is there a reachable WCAG, security, or legal compliance failure with concrete current harm?** YES -- P1
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
| **code-simplicity-reviewer** | Reachable correctness failure hidden by complexity | Unnecessary complexity with a demonstrated current regression or realistic harm | Numeric length/complexity thresholds, verbose but correct code, minor style preferences |
| **security-auditor** | SQL injection, XSS, auth bypass, credential exposure | Missing CSRF token, permissive CORS, unvalidated input | Missing rate limiting, verbose error messages |
| **pattern-recognition-specialist** | Circular dependencies, data races, resource leaks | Anti-patterns (God objects, feature envy), naming inconsistencies | Minor duplication, magic numbers in non-critical paths |
| **architecture-reviewer** | Broken trust/module boundary with concrete current harm | Coupling or placement that causes a current regression or reachable failure | SOLID preferences, file/function size thresholds, layer counts, interfaces, service/repository patterns, suboptimal but functional structure |
| **doc-sync-reviewer** | API docs contradict implementation, CLAUDE.md has wrong paths | README outdated, missing docs for new features | Minor formatting, stale examples |
| **test-coverage-reviewer** | Existing tests now fail | Changed code has no tests (when project has test infrastructure) | Missing edge case tests |
| **go-build-verifier** | Compilation failure | `go vet` warnings | -- |
| **craft-reviewer** | N+1 queries in loops, `\|raw` on user input | Missing eager loading, no null checks on relations | Suboptimal query patterns, minor template issues |
| **visual-browser-tester** | Layout completely broken at any breakpoint, keyboard trap in browser, axe-core critical violations, focus indicators missing entirely, JS exceptions preventing render | Layout degraded at mobile (content cut off, overlapping, horizontal scroll), interactive states not visually distinct, axe-core serious violations, console JS errors, contrast failures, missing scheme tokens | Minor spacing inconsistencies, axe-core moderate violations, responsive polish, baseline rhythm misalignment |
| **ux-quality-reviewer** | Navigation dead ends, missing error states that strand users, primary action invisible or unreachable, voting interface ambiguous enough to cause wrong votes | Missing feedback states (loading, empty, success), inconsistent interaction patterns, poor hierarchy burying content, missing empty states on lists/tables, AI slop score below 20/25 | Spacing inconsistencies, minor alignment drift, suboptimal typography, missing hover states, orphaned headings, edge case overflow |
| **ui-standards-reviewer** | Missing component states that strand users (no error feedback, no loading indicator on async actions), broken visual hierarchy (can't tell primary from secondary action) | Inconsistent spacing system (hardcoded values instead of `--line-*`), missing empty/loading states, amateur patterns (spinners instead of skeletons, `alert()` instead of inline errors, centered text in left-aligned layouts), missing hover/focus transitions, AI slop score below 20/25 | Minor polish gaps (border-radius inconsistency, suboptimal shadow hierarchy, minor transition timing) |

### Depot-Native Agents (from other plugins)

| Agent | Plugin | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|--------|------------|------------|-------------|
| **a11y-html-reviewer** | accessibility-compliance | Missing form labels, keyboard traps, no alt on functional images | Broken heading hierarchy, missing landmarks, generic link text | Missing aria-describedby, suboptimal ARIA |
| **a11y-css-reviewer** | accessibility-compliance | `outline: none` without replacement, failing contrast on primary text | Animations without motion check, reflow broken at 320px | Low contrast on secondary text, missing forced-colors |
| **a11y-dynamic-content-reviewer** | accessibility-compliance | Click handlers on non-interactive elements, no live regions for state changes | Focus lost after morph, loading states silent | ARIA states not synced, suboptimal focus target |
| **css-reviewer** | live-wires | -- (errors) | Cascade layer violations, class invention, naming rule breaks | Token recommendations, container query suggestions |
| **voice-editor** | ghostwriter | -- | Spine failure (no point of view), AI pattern detected | Rhythm issues, minor register drift |
| **governance-domain** | council | Legal compliance failure (wrong voting threshold) | Architecture violation (fixture boundaries) | Naming recommendations, values alignment |

---

### Browser Agent Phases

| Agent | Phase | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|-------|------------|------------|-------------|
| **visual-browser-tester** | Live Wires CSS Compliance | -- | Invented classes when primitives exist, arbitrary values instead of tokens, media queries instead of container queries | Minor token recommendations, alternative primitive patterns (advisory) |

UX Design and Visual Design Quality phases have moved to **ux-quality-reviewer** (see dm-review Agents table above).

---

## Escalation Rules

1. **Any P1 from any agent** -> merge recommendation = `BLOCKS MERGE`
2. **P2 present (any count, regardless of P3)** -> merge recommendation = `APPROVE WITH FIXES` (must fix before merge)
3. **P3 only (no P1/P2)** -> merge recommendation = `CLEAN`. Render every P3 with complete evidence, source identity, raw reference, synthesis disposition, counts, and provenance.
4. **Zero findings** -> merge recommendation = `CLEAN`
5. **Supported security P1** always escalates when it names the current reachable path, realistic harm, actual trust boundary, and smallest adequate repair -- no exceptions, no "we'll fix it later"
6. **Accessibility P1** always escalates -- legal compliance (EAA, ADA)
7. **Governance P1** always escalates -- statutory requirements
8. **Visual P1** always escalates -- if layout is completely broken or keyboard traps exist in the rendered page

## De-escalation Rules

1. P3 findings are shown in the report with full detail (same format as P1/P2) as visible advisories. They do not create todos/issues, enter the fix queue, drive convergence, or block merge.
2. Findings from agents that partially overlap (e.g., both a11y-css-reviewer and css-reviewer flag the same file) count as ONE finding at the higher severity.
3. If a P1/P2 finding is already tracked in a known issue/TODO, note the tracker reference and still follow the required fix policy. Existing user-owned P3 trackers are left untouched; dm-review does not create new ones.
