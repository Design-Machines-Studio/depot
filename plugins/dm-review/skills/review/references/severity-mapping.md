# Severity Mapping

Rules for mapping each agent's native severity terminology to the unified P1/P2/P3 system.

## Zero-Deferral Finding Policy

`plugins/dm-review/commands/dm-review.md` owns the full policy statement; this
file owns the severity mapping it applies. In short: every retained P1, P2, and
P3 finding must be fixed and rechecked before `CLEAN`, and severity controls
ordering and merge language, not whether the work is owed. Every retained
finding names an observable current defect, its location or reachable path, and
the smallest adequate repair; every P1/P2 also names the affected current user
or operator, the reachable actor/input/path, the realistic harm or regression,
and a security P1/P2 the actual trust boundary. Default to the Design Machines
context -- two developers, first-party private repositories, trusted Fixture
authors, self-hosted co-op applications of roughly 4--50 people -- so
hypothetical actors, future marketplaces, enterprise scale, generic OWASP
possibilities, and "defence in depth would be better" are not findings by
themselves.

Real reachable authentication or authorization bypass, credential disclosure, unsafe destructive operations, corruptible state or backups, public untrusted input, release/update integrity failures, and false verification claims remain blocking at their supported severity.

---

## Unified Severity Levels

| Level | Label | Meaning | Merge Impact |
|-------|-------|---------|-------------|
| **P1** | Blocks Merge | Must fix before merging | Review recommendation = BLOCKS MERGE |
| **P2** | Important Fix | Must fix before merging | Review recommendation = APPROVE WITH FIXES |
| **P3** | Required Fix | Observable minor defect or maintainability debt. Must fix before merging. | Review recommendation = APPROVE WITH FIXES |

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
| **code-simplicity-reviewer** | Reachable correctness failure hidden by complexity | Unnecessary complexity with a demonstrated current regression or realistic harm | Bounded duplication or complexity with an observable current maintenance defect; numeric thresholds and style preferences alone are discarded |
| **security-auditor** | SQL injection, XSS, auth bypass, credential exposure | Missing CSRF token, permissive CORS, unvalidated input | Minor reachable disclosure or abuse defect at an actual current boundary; generic hardening suggestions are discarded |
| **pattern-recognition-specialist** | Circular dependencies, data races, resource leaks | Anti-patterns (God objects, feature envy), naming inconsistencies | Minor duplication that has diverged or a magic value that obscures changed behavior; preferences alone are discarded |
| **architecture-reviewer** | Broken trust/module boundary with concrete current harm | Coupling or placement that causes a current regression or reachable failure | Bounded current boundary or maintainability defect; SOLID preferences, size thresholds, layer counts, and optional abstractions alone are discarded |
| **doc-sync-reviewer** | API docs contradict implementation, CLAUDE.md has wrong paths | README outdated, missing docs for new features | Minor formatting, stale examples |
| **test-coverage-reviewer** | Existing tests now fail | Changed code has no tests (when project has test infrastructure) | Missing edge case tests |
| **go-build-verifier** | Compilation failure | `go vet` warnings | -- |
| **craft-reviewer** | N+1 queries in loops, `\|raw` on user input | Missing eager loading, no null checks on relations | Suboptimal query patterns, minor template issues |
| **visual-browser-tester** | Layout completely broken at any breakpoint, keyboard trap in browser, axe-core critical violations, focus indicators missing entirely, JS exceptions preventing render | Layout degraded at mobile (content cut off, overlapping, horizontal scroll), interactive states not visually distinct, axe-core serious violations, console JS errors, contrast failures, missing scheme tokens | Minor spacing inconsistencies, axe-core moderate violations, responsive polish, baseline rhythm misalignment |
| **ux-quality-reviewer** | Navigation dead ends, missing error states that strand users, primary action invisible or unreachable, voting interface ambiguous enough to cause wrong votes | Missing feedback states (loading, empty, success), inconsistent interaction patterns, poor hierarchy burying content, missing empty states on lists/tables, AI slop score below 20/25 | Spacing inconsistencies, minor alignment drift, suboptimal typography, missing hover states, orphaned headings, edge case overflow |
| **ui-standards-reviewer** | Missing component states that strand users (no error feedback, no loading indicator on async actions), broken visual hierarchy (can't tell primary from secondary action) | Inconsistent spacing system (hardcoded values instead of `--line-*`), missing empty/loading states, amateur patterns (spinners instead of skeletons, `alert()` instead of inline errors, centered text in left-aligned layouts), missing hover/focus transitions, AI slop score below 20/25 | Minor polish gaps (border-radius inconsistency, suboptimal shadow hierarchy, minor transition timing) |

### Depot-Native Agents (from other plugins)

When the selected roster includes an agent from `accessibility-compliance`,
`live-wires`, `ghostwriter`, or `council`, load
`severity-depot-native-agents.md` for its mapping. A roster of dm-review agents
alone does not load it.

### Browser Agent Phases

| Agent | Phase | Critical/P1 | Serious/P2 | Moderate/P3 |
|-------|-------|------------|------------|-------------|
| **visual-browser-tester** | Live Wires CSS Compliance | -- | Invented classes when primitives exist, arbitrary values instead of tokens, media queries instead of container queries | Observable minor token or primitive defect; preference-only alternatives are discarded |

UX Design and Visual Design Quality phases have moved to **ux-quality-reviewer** (see dm-review Agents table above).

---

## Escalation Rules

1. **Any P1 from any agent** -> merge recommendation = `BLOCKS MERGE`
2. **P2 present (any count, regardless of P3)** -> merge recommendation = `APPROVE WITH FIXES` (must fix before merge)
3. **P3 present with no P1** -> merge recommendation = `APPROVE WITH FIXES` (must fix before merge)
4. **Zero findings** -> merge recommendation = `CLEAN`
5. **Supported security P1** always escalates when it names the current reachable path, realistic harm, actual trust boundary, and smallest adequate repair -- no exceptions, no "we'll fix it later"
6. **Accessibility P1** always escalates -- legal compliance (EAA, ADA)
7. **Governance P1** always escalates -- statutory requirements
8. **Visual P1** always escalates -- if layout is completely broken or keyboard traps exist in the rendered page

## Validity and De-escalation Rules

1. P3 findings use the same complete evidence, todo/issue, fix-queue, and convergence path as P1/P2. A preference or future improvement without an observable current defect is not a P3; discard it.
2. Findings from agents that partially overlap (e.g., both a11y-css-reviewer and css-reviewer flag the same file) count as ONE finding at the higher severity.
3. If a retained finding is already tracked in a known issue/TODO, note the tracker reference and still follow the required fix policy. An existing tracker never makes the current review clean.
