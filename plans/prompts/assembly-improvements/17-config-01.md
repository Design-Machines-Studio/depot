# CONFIG-01 — Align only the operator’s saved CLI driver settings

Open a fresh session in `/home/ned/ai/depot`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-6-astra
- Harness/rail: Codex / subscription
- Effort: low
- Why: The task requires actual host filesystem or release tools; low effort on the native driver is sufficient for this bounded procedure.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: gpt-5.6-sol / Codex / low; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement only CONFIG-01: Align only the operator’s saved CLI driver settings.

Repository: Design-Machines-Studio/depot
Checkout for discovery: /home/ned/ai/depot
Prepared exact base (2026-09-08): 386b98e26f493cc220047c981cd5c01b1513b24d
Owning plugin: none; operator-local configuration
executorRole: builder-deep
executorCapabilities: ["read-repository", "write-repository", "structured-output", "tool-use"]
executorEffort: low

Prerequisite and collision boundary:
Optional operator-local task. Run only when you intend to set the saved driver to the agreed low-effort default. The planning session observed a newer high-effort setting and did not overwrite it.

Workspace:
This is an operator-local configuration task. Use the repository only to read current guidance; do not create a branch/worktree or commit private configuration. Preserve every existing checkout. The context below is a source snapshot, not permission to change unrelated local settings.

Read AGENTS.md, directly referenced instructions, CLAUDE.md, engineering principles, relevant plans/lessons and affected local skills/hooks. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. Shared skills belong in Depot; local skills belong in their repository. No personal Notion/RAG/memory dependency or cache edits.

Task and non-goals:
Inspect only relevant non-secret keys in /home/ned/.codex/config.toml and current model catalog metadata. Set the saved driver model/effort to the user-selected primary driver at low effort using the current model-router human guidance; preserve all other configuration. Do not place concrete identity in participant packets. Before writing, preserve an exact local recovery copy with restrictive permissions outside Git.

Keep model_context_window=1000000 and model_auto_compact_token_limit=400000 unchanged unless the user explicitly asks otherwise. Reverify current catalog caps and explain the source-derived effective context/compaction values. Do not propagate these overrides to repositories, other models, Claude or OpenRouter. No credentials, installations, cache refresh, account settings or plugin source changes.

Acceptance and focused verification:
TOML parses, the intended two settings match the agreed driver choice, and all other values are unchanged. Report configured values separately from effective/observed runtime behavior. Do not spend model tokens simply to prove a config edit or claim a long-session performance benefit.

Consumer canary:
Read back only model, effort and context-related keys. Do not print or commit the complete private configuration.

Working constraints:
Build for two trusted developers and self-installed, federated co-op intranets of 5–50 people with trusted internal Fixtures. Apply YAGNI, pragmatic DRY, Live Wires/component reuse, accessibility, performance and maintainability. Preserve real authorization, credential, data-loss and release protections. No enterprise infrastructure. The driver retains design/integration/final acceptance; workers get bounded ownership. Route only role/capabilities/effort, with no concrete identities in participant packets or automatic inheritance of driver/max effort.

Use a direct, proportionate workflow and reuse still-exact evidence. No automatic full Pipeline/adversarial suite for instruction edits. Fix every retained P1/P2/P3 and verify affected behavior; stop review churn after convergence. Routine implementation choices are yours; ask only for a real missing decision or authorization.

Economics:
Refresh installed routing/matrix evidence before dispatch. Prefer eligible subscriptions and useful bounded OpenRouter offload. Paid calls have a $0.25 total ceiling, subject to known remaining monthly budget; $50/month is a goal, not verified headroom. Use deterministic checks where sufficient. Respect real export restrictions; report unavailable lanes and distinguish fixtures from actual calls.

Terminal state:
No merge, release tag, installation/cache refresh or GitHub Issue/PR change. Keep private configuration and its recovery copy outside Git. A local config edit does not warrant an empty PR. Report the exact non-secret keys changed, verification and recovery-copy path. Project items: None.

Treat 40 tool calls as an exploration checkpoint; finish authorized repairs, verification, commit, push and PR creation. Keep updates brief.

Final report:
Report result, exact base/head, changes, actual checks, PR/Project state, delivery level and one next action. For routed work, report role, attempted/served participant, rail, effort, duration, outcome, measured tokens/cost, subscription calls, fallbacks and unavailable measurements. Finish with SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
```
