# Agent registry

Agent files define review criteria; they do not select concrete participants.
Resolve them from coherent installed bundles as described in `SKILL.md`.

| Agent | Role | Default effort | What it reviews |
|---|---|---|---|
| code-simplicity-reviewer | `review-deep` | high | Complexity, redundancy, dead code, over-engineering |
| security-auditor | `security-review` | high | Reachable credential, authorization, data-loss, and release-integrity boundaries |
| pattern-recognition-specialist | `review-deep` | high | Anti-patterns, conventions, duplication, magic values |
| architecture-reviewer | `review-deep` | high | Component boundaries, coupling, layering, current consumers |
| doc-sync-reviewer | `review-fast` | medium | Documentation and reference synchronization |
| second-perspective | `plan-critic` | high | Independent full-mode judgment |
| test/build/domain/UI agents | `review-fast` or `review-deep` | medium/high | Triggered criteria named in `SKILL.md` |

Quick mode selects patterns and simplicity plus triggered UI/build/domain lanes.
Full mode selects every always-run and triggered lane. The compatibility filename
`codex-perspective.md` does not select a participant. All card models inherit.

`migration-validator` is Full mode only. Ordinary quick mode does not add this lane.
Security-sensitive escalation selects the complete full roster.
