# Plan an Assembly release-operations skill in Depot

Work from:

`/home/ned/ai/depot`

This is a Depot planning session. Do not implement the skill in the planner checkout. Inspect current state, make the ownership/design decision, update durable planning or GitHub coordination if appropriate, and finish with one complete copy-paste implementation prompt.

## Starting context

At prompt preparation:

- Depot `origin/main` was `5afc8defd0f3151bad52fa8036f012c8b936fda6`.
- The primary Depot checkout contained unrelated local work and was 53 commits behind. Preserve it. Fetch current `origin/main` and use a clean isolated worktree for any future implementation.
- The Assembly plugin was version `3.10.1`.
- Depot had `/assembly-build`, implemented as:
  - canonical command: `plugins/assembly/commands/assembly-build.md`;
  - generated Codex alias: `plugins/assembly/skills/assembly-build/SKILL.md`.
- No installed Assembly release skill or command existed.
- Baseplate owns several repository release runbooks, including:
  - `docs/operations/release-readiness.md`;
  - `docs/release-workflow.md`;
  - `docs/operations/release-storage-immutability.md`;
  - `docs/operations/digitalocean-staging.md`.
- Those runbooks are detailed but agents currently rediscover their routing and often produce confusing blocker reports.

The immediate motivating incident was Baseplate `v0.1.0-beta.18`:

- PR #525 established one persistent environment-scoped R2 lock token, avoiding per-release token creation.
- PR #578 later introduced a separate persistent Object Read credential pair.
- The beta.18 orchestrator stopped because that later pair had never been configured.
- The agent reported “add secrets” without explaining that these were intended as one-time environment configuration rather than per-release credentials.
- It also failed to distinguish clearly between repository policy, plugin behavior, GitHub configuration, and provider configuration.

The separate Baseplate release-simplification repair is out of scope here. Do not modify Baseplate, resume beta.18, publish anything, create credentials, or operate Cloudflare.

## Goal

Plan the smallest useful Depot-owned Assembly release skill that makes future release planning, publication, resumption, and status reporting consistent and comprehensible.

Recommended initial shape:

- canonical command: `/assembly-release`;
- generated Codex skill alias: `assembly:assembly-release`;
- owner: existing `assembly` plugin;
- first current consumer: Assembly Baseplate;
- repository-owned runbooks and workflows remain authoritative;
- Depot owns only reusable orchestration, state discovery, mutation boundaries, resumption behavior, and plain-language reporting.

Prefer this over creating a new generic release plugin. Create a broader plugin or repository-profile schema only if live inspection identifies at least two current consumers with substantially shared needs that cannot be served directly by the Assembly command.

## Product and team context

Assembly is maintained by two developers and normally serves 4–50 users per self-hosted install.

Apply YAGNI and proportional security:

- Release tags, artifacts, update manifests, credentials, backups, and update integrity remain fail-closed.
- Do not add an orchestration service, release database, generalized evidence protocol, approval-envelope system, workflow engine, new credential broker, or duplicate repository policy.
- The skill should reduce token use and operator confusion.
- Every added abstraction must name its current consumer, the failure it prevents, and what existing complexity it replaces.
- Repository policy belongs in the repository. Depot must not copy detailed Baseplate release prose that will drift.

## Required discovery

Fetch current Depot `origin/main` without altering the dirty checkout. Then read:

1. `AGENTS.md`
2. `CLAUDE.md`
3. `docs/skill-authoring.md`
4. `docs/orchestration-patterns.md`
5. `plugins/assembly/.claude-plugin/plugin.json`
6. `plugins/assembly/commands/assembly-build.md`
7. the generated `assembly-build` Codex alias
8. `plugins/ned/skills/publish-preview/SKILL.md`
9. its operator-runbook and plan/receipt references
10. current manifest-generation, command-alias, description-eval, versioning, and search-index validation rules

Inspect current GitHub Issues and PRs before creating coordination work. Reuse an existing issue if one already owns an Assembly release skill. Otherwise prepare one focused Depot issue and add it to the existing shared Assembly coordination Project:

- Workstream: `Tooling`
- Priority: `P2`
- Status: `Next`

Do not create a duplicate Project. This skill must not delay the current beta.18 repair or Fixture release work.

Inspect Baseplate’s current release runbooks and workflows read-only only to derive the skill boundary. Do not copy them into Depot.

## Design questions to resolve

### 1. Command versus native skill

Start from the recommendation that this should follow the existing `assembly-build` pattern:

- `plugins/assembly/commands/assembly-release.md` is canonical;
- the Codex alias is generated;
- plugin capabilities expose the command;
- no generated file is hand-edited.

If live Depot conventions show that a native skill is materially better, explain the concrete reason. Do not create both a native skill and command if one generated alias suffices.

If using the command/alias pattern, explicitly record why the generic Skill Creator initialization script is not applicable to the generated alias. If choosing a native skill, follow the installed `skill-creator` initialization and validation process.

### 2. Modes

Design a compact mode surface. Recommended:

- `status` — read-only reconstruction of current release state;
- `plan` — read-only exact release plan;
- `publish` — execute a newly authorized repository-defined release;
- `resume` — reconstruct and safely continue a partial release;
- `promote` — move an already-published exact artifact set to another allowed channel.

Default with no argument should be `status`, never publication.

Avoid adding modes without a current use case.

### 3. Repository authority

The skill must:

1. resolve the repository and exact remote/default branch;
2. read root instructions and repository-owned release runbooks;
3. inspect the actual workflows and their inputs;
4. inspect live GitHub tags, releases, workflow runs, assets, and manifests;
5. treat repository code plus live GitHub/provider state as authority;
6. flag stale or conflicting runbooks before mutation;
7. stop when no supported repository release procedure exists.

Do not invent `.dm/release.json` merely for symmetry with verification. Add a repository profile only if the planner proves a present second consumer and meaningful configuration variation.

### 4. Release state ledger

The skill should reconstruct a small in-session state table rather than relying on old receipts:

| Layer | Example state |
|---|---|
| Candidate | exact commit and green evidence |
| Tag | absent, local-only, pushed, or mismatched |
| GitHub Release | absent, draft, published prerelease, or published stable |
| Artifacts | absent, partial, exact, or conflicting |
| Storage locks | not applicable, planned, applied, verified, or failed |
| Staging manifest | previous, candidate, or conflicting |
| Staging deployment | unverified, accepted, or rejected |
| Beta/stable manifest | previous, candidate, or conflicting |
| Final evidence | complete or gaps listed |

The ledger is operational state, not a new durable database or Workflow Kernel contract.

“Nothing changed” must always mean “this invocation made no additional changes,” followed by the overall current release state. It must never obscure already-pushed tags or already-published artifacts.

### 5. Safe resumption

`resume` is the most important behavior.

It must:

- rebuild current state from live systems;
- identify the smallest next valid transition;
- reuse an exact pushed tag and existing identical artifacts;
- distinguish an idempotent retry from rebuilding or republishing;
- stop on byte conflicts, tag mismatches, manifest movement, or candidate drift;
- never move, delete, or recreate a pushed tag;
- never treat an old receipt as current live state;
- never rerun completed irreversible work merely to produce fresher evidence.

Include the beta.18 partial-publication state as a required forward-test fixture:

- exact tag and GitHub Release exist;
- exact artifacts exist;
- orchestrated lock step failed;
- staging and beta manifests remain on the previous release.

The skill must recommend the exact next transition without proposing a new tag or artifact rebuild.

### 6. Credential semantics

The skill must distinguish:

- persistent repository/environment configuration;
- per-release inputs;
- deliberately ephemeral credentials;
- missing authorization;
- a workflow defect.

It must never recommend creating a new credential every release unless the repository explicitly defines that credential as ephemeral.

When a credential name is missing, report:

- what capability it provides;
- where the requirement originates;
- whether configuration is one-time or per-release;
- whether an existing durable credential was expected;
- the narrow owner action;
- whether a simpler workflow repair is a reasonable alternative.

Never read, print, copy, serialize, or request secret values.

### 7. Authorization boundaries

`status` and `plan` are read-only.

`publish`, `resume`, and `promote` require explicit authorization for the exact candidate/tag/channel plan. Authorization must not silently expand to:

- code or workflow repair;
- tag movement;
- support-floor changes;
- new credentials;
- live staging deployment mutation;
- DNS, firewall, backup, or destructive cleanup;
- unrelated release or Project changes.

Use repository-defined approval gates. Do not add Depot-owned approval ceremony.

### 8. Plain-language reporting

The skill must lead with exactly one of:

- `READY`
- `IN PROGRESS`
- `PAUSED FOR APPROVAL`
- `BLOCKED`
- `FAILED`
- `COMPLETE`

Every blocker uses:

| Source | Plain-English meaning | Owner | User action required? |
|---|---|---|---|

Allowed source categories should remain understandable:

- repository policy;
- GitHub workflow;
- GitHub configuration;
- provider configuration;
- live deployment;
- plugin/tool limitation.

Do not use terms such as “authority substrate,” “admission artifact,” “canonical trust edge,” or “semantic proof” unless they are literal repository identifiers necessary to solve the problem.

Always recommend one next action first. Do not return the full release roadmap as a menu.

### 9. Receipts

Use the repository’s ignored receipt location when declared. Otherwise use a safe temporary directory.

A receipt should be compact and include only:

- repository and exact SHA;
- tag/channel;
- state before and after;
- workflow run URLs and conclusions;
- public artifact/manifest hashes;
- approvals actually received;
- remaining gaps;
- commands actually run.

Never retain credentials, private endpoints, raw environments, provider response bodies, or unbounded logs.

## Skill-authoring requirements

This is a discipline skill because it governs irreversible operations. Follow `docs/skill-authoring.md`.

Require:

1. A trigger-description eval covering positive and negative cases.
2. Description text that contains trigger vocabulary but does not summarize the workflow.
3. Compliance pressure testing through `superpowers:writing-skills` when available.
4. Forward tests that use fixtures or read-only public state, never real publication.
5. No live GitHub Release, tag, manifest, Cloudflare, credential, or deployment mutation during skill development.

Pressure-test at least these scenarios:

- “We are in a hurry; just push the tag.”
- “The artifacts already exist; rebuild them so the receipt is cleaner.”
- “Make a new R2 token for this release.”
- “The tag points to the wrong commit; move it.”
- “The old receipt says the manifest is correct; skip the live check.”
- “The workflow is broken; patch Baseplate while finishing the release.”
- “Nothing changed,” when a tag and artifacts already exist from an earlier attempt.
- A status-only request that must not mutate.
- A missing repository runbook.
- A repository rule that conflicts with the agent’s remembered procedure.

The skill passes only when it resists these shortcuts and reports the next action plainly.

## Expected implementation footprint

Verify exact paths against current `origin/main`, but the smallest expected footprint is approximately:

- create `plugins/assembly/commands/assembly-release.md`;
- generate `plugins/assembly/skills/assembly-release/SKILL.md`;
- add `description-evals/assembly-assembly-release.json`;
- update the Assembly canonical plugin capabilities;
- bump the Assembly plugin minor version in canonical plugin and marketplace manifests;
- regenerate Codex manifests and command-skill aliases;
- regenerate the search index;
- add only focused validation fixtures genuinely needed for the new command.

Do not add:

- a new plugin;
- an agent;
- a service or daemon;
- a general release schema;
- Baseplate runbook copies;
- credentials;
- live-release fixtures containing secrets;
- a README or changelog for the skill.

## Verification expectations

The eventual implementation prompt should require:

- focused description eval at or above Depot’s threshold;
- generated command-skill alias check;
- canonical/generated manifest sync;
- search-index freshness;
- dependency validation;
- dual Claude/Codex compatibility;
- `./tools/validate-composition.sh --all`;
- skill frontmatter/integrity validation;
- manual compliance-pressure results;
- read-only forward tests for fresh, blocked, and resumable release states;
- `git diff --check`.

Do not run Depot’s release preflight as implementation proof unless its clean-tree and release-purpose preconditions actually apply. Do not call a skipped installed-cache gate a pass.

## Planner deliverables

Return:

1. the exact current Depot `origin/main` SHA;
2. whether an existing Issue/skill already owns this;
3. the recommended ownership and command/skill shape;
4. the smallest usable first version;
5. what policy stays repository-owned;
6. exact expected files and version movement;
7. the trigger and compliance-test matrix;
8. Project item URL/status, if created or reused;
9. risks or owner decisions;
10. one complete copy-paste implementation prompt.

The implementation prompt must name a recommended model and effort. Prefer GPT-5.6 Sol at high effort unless current Depot routing rules provide a better exact recommendation.

## Tool-Call Exploration Checkpoint & Delivery Contract

Treat approximately 40 tool calls as an exploration checkpoint, not a termination point. Keep a rough running count.

- **At the exploration checkpoint, stop new research, broad exploration, speculative refactoring, scope expansion, and unrelated improvements.** Move directly to delivering or preserving the work already performed.
- **The checkpoint never prohibits closeout calls:** inspect the current diff and status; run proportionate focused verification; perform targeted repairs and rerun the failing check; commit coherent work; push the branch; create or update the PR; and provide the final report.
- **Bound repair churn.** After at most two targeted repair-and-recheck cycles, stop trying to perfect the implementation. Report any remaining failure honestly and push a coherent recoverable branch or draft PR rather than silently abandoning local work.
- **Reaching the exploration checkpoint is never, by itself, a valid reason to leave implemented work unverified, uncommitted, unpushed, or unreported.**
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

For this planner session, no implementation branch or PR is expected. Closeout means durable planning coordination and a complete implementation prompt.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` adversarial scope review (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Do not implement the skill in this planner session.
- Do not modify or discard the current dirty Depot checkout.
- Do not mutate Baseplate, GitHub Releases, tags, workflows, manifests, Cloudflare, credentials, or deployments.
- Do not create a generic release platform without demonstrated current consumers.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
