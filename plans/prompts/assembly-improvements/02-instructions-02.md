# INSTRUCTIONS-02 — Shorten Baseplate instructions and local skills

Open a fresh session in `/home/ned/assembly/assembly-baseplate`. Copy the entire fenced prompt below. The recommendation above it is for the human operator; it is not part of a worker packet.

Recommended start

- Model: gpt-5.6-luna
- Harness/rail: Codex / subscription
- Effort: high
- Why: Bounded requirements, named file ownership and verifiable acceptance fit this execution role; subscription evidence permits a bounded attempt.
- Cost: included subscription; native token/charge measurements may be unavailable. API-equivalent estimates are not billed subscription spend.
- Fallback: deepseek/deepseek-v4-flash-0731 / OpenRouter / high; recheck capability fit and availability before attempting.
- Matrix evidence date: 2026-08-27; installed model-router 0.7.0 and OpenRouter matrix 1.20.3, recommendation observed 2026-09-08.

```text
Implement INSTRUCTIONS-02: repair Baseplate instructions and local hooks.

Repository: Design-Machines-Studio/assembly-baseplate
Checkout for discovery: /home/ned/assembly/assembly-baseplate
Prepared exact base: 82c25a8be8e32a00b186d55fb2c430698cefd93b
Owning plugin: none; this is repository-owned instruction/hook maintenance
executorRole: builder-fast
executorCapabilities: ["read-repository", "write-repository", "structured-output"]
executorEffort: high

Prerequisite and collision boundary:
Ready independently. This complete prompt supersedes the earlier instruction to wait for Depot INSTRUCTIONS-01. That is a generator task, not a Baseplate prerequisite. PR #132 contains prompts, not its implementation. No generator merge, prompt-pack merge, new plugin API, tag or cache update is needed. Apply the agreed policy below using Baseplate's current engineering contracts.

PR #865 is now merged. At refresh, only dependency PRs #826–#828 were open. Recheck actual file ownership; an unrelated PR is not a collision. If this task already has a completed or active PR, inspect it and avoid duplicate work.

Workspace:
Fetch origin/main and record its exact current SHA. If newer than the prepared base, inspect the relevant delta and continue from current compatible main; do not revert newer work. Create a clean worktree under /home/ned/assembly/assembly-baseplate-worktrees and an unused fix/instructions-02 branch, adding a unique suffix if needed. A dirty primary checkout or missing task branch is not a blocker. Preserve every existing checkout/worktree: no stash, reset, clean, rebase, branch switch, removal or discarded files.

Reuse the prior read-only mapping. The AGENTS/CLAUDE/RTK/.claude/.codex source trees are unchanged between the earlier 0a16152f base and this prepared head. Read any changed applicable instructions and references, including engineering principles, testing, Fixture authoring and release authority; do not repeat the entire discovery pass when the evidence is still exact. Use Assembly Coordinator and Design Machines strategy when available. Follow local RTK rules. No personal Notion/RAG/memory dependency.

Task and non-goals:
Current root sizes are AGENTS.md 82,738 bytes, CLAUDE.md 42,576 and RTK.md 562. The mapping found six hooks per harness, ten Claude agents, ten Codex shims and .claude/settings.json. No repository-local .claude/skills, .agents/skills or .codex/skills were present; verify cheaply rather than inventing new skills.

1. Shorten root instructions with one coherent shared authority and task-specific references. Aim for roughly 8 KiB across entrypoints where practical; preserve necessary contracts and keep the actual discovery chain within its harness allowance. Do not solve repetition merely by increasing the instruction limit.
2. Apply this agreed policy to root guidance and affected local agents/hooks: plan and verify according to task/risk, not file count; remove automatic documentation-agent, lesson-update, file-count commit and repeated approval chores; document meaningful behavior/runbook changes and keep personal systems optional. This policy is sufficient without a generator change.
3. Fix .codex/hooks.json's six commands hard-coded to a macOS checkout. Use an existing supported repository-relative or runtime-resolved path mechanism, not another developer's absolute path. Preserve the Go-in-Docker guard. Identify canonical sources and regenerate any affected generated Codex shims with the existing mechanism.
4. Preserve repository-owned Go/Docker/generation commands, authorization, migrations, federation, trusted Fixture contracts, release authority, Live Wires/component reuse, prototype fidelity, accessibility, performance and maintenance.

Build for two trusted developers and self-installed federated co-op intranets of 5–50 people with trusted internal Fixtures. Apply YAGNI and pragmatic DRY. No product behavior, dependencies, CI policy, release files, tasks/lessons.md, generated Templ output, installed plugins or caches should change. Shared plugin defects stay Depot-owned.

Acceptance and focused verification:
Report before/after root bytes and the actual instruction discovery chain. Preserve every necessary contract through the rewrite. Verify local links, canonical/generated consistency and portability. Exercise changed hooks in temporary fixtures: paths resolve in the fresh checkout, ordinary edits avoid repeated chores, and a forbidden bare-Go invocation is still rejected. Test the guard's input/output; do not execute bare Go on the host. Run any other affected repository checks, not unrelated full application lanes.

Consumer canary:
Walk a docs repair, ordinary Go/Templ change and authorization change through the new instruction and verification selection. Distinguish that walkthrough from commands actually executed. The prior mapping is reusable evidence, not a post-change test pass.

Use a direct workflow and reuse still-exact evidence. No automatic full Pipeline/adversarial suite for these edits. Review the actual diff, fix every retained P1/P2/P3 and verify affected behavior. Stop review churn after convergence. Keep real credential, authorization, destructive-action and release boundaries closed. Routine implementation choices are yours.

Routing and economics:
Keep driver design/integration/final acceptance separate from bounded workers. Refresh installed routing/matrix evidence before delegated work; request only role/capabilities/effort and keep concrete identities out of participant packets. Prefer eligible subscriptions and useful bounded OpenRouter offload. Paid calls have a $0.25 total ceiling subject to known remaining monthly budget; $50/month is a goal, not verified headroom. Respect real export restrictions and report unavailable measurements/lanes honestly.

GitHub and delivery:
Use authenticated REST if GraphQL or a gh command is rate-limited. A missing Project item or unavailable Project API does not block edits, tests, commits, push or a PR. Verify, commit, push and open a proper PR to Baseplate main with INSTRUCTIONS-02 in its title. If PR creation itself is unavailable, finish safe isolated work, push when Git transport works and report that publication step pending; never claim it succeeded.

Use only Assembly Coordination Project 1: Review / P1 / Tooling for the relevant PR, or a real blocked dependency. If Project access is unavailable, report the update pending and continue repository work. Do not mutate native Issues, merge, tag or refresh installations. Instruction-only changes require no app version bump or Depot composition run; follow actual repository policy for changed hooks. No plugin publication/cache synchronization is needed for this local repair.

Treat 40 tool calls as an exploration checkpoint, not a stop before necessary repairs, checks, commit, push and PR creation. Keep updates brief.

Final report:
Report exact base/head, changes, checks, root sizes, PR/Project state, evidence gaps and one next action. For actual routed work, report role, attempted/served participant, rail, effort, duration, outcome, measured tokens/cost, subscription calls, fallbacks and unavailable measurements. Finish with SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
```
