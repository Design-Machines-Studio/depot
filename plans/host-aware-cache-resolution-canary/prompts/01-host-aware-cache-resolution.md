# Chunk: Host-aware cache resolution

## Context

Depot Issue #28 remains reachable because active Pipeline and dm-review instructions still scan the Claude plugin cache first and stop before comparing the Codex cache. The installed Workflow Kernel already provides the required resolver behavior: highest compatible semantic version across both caches, active-host tie-breaking, and one coherent root for a required asset set. This is one bounded low-uncertainty, low-consequence canary chunk; use that existing resolver directly and do not broaden the repair.

## Task

Remove the active stale-selection paths in dm-review and Pipeline by replacing their first-root cache loops with Workflow Kernel `resolve-plugin-bundle` or `resolve-plugin-asset` calls. Add mutation-sensitive tests and validator coverage for both stale directions, both equal-version active-host ties, coherent required assets, graceful optional skips, and rejection of the old active-consumer lookup. Patch-bump only dm-review and Pipeline and regenerate their derived Codex manifests.

This prompt may be invoked only after executable deficit-round-robin policy selects the OpenRouter rail. If policy selects another rail, do not invoke this prompt: record the policy rejection and stop without Codex implementation fallback. If invoked, this is the only paid implementation attempt and must use exactly `deepseek/deepseek-v4-flash-0731`; do not traverse to Grok, MiniMax, GLM, another provider, or Codex implementation after rejection, unavailability, or failure.

Return only a unified diff for the canonical non-generated files you can implement from the supplied context. You have no repository shell or generator access. The native Codex supervisor, not this worker, runs generators, completes generated files, executes tests/validators, inspects every changed line, and performs at most one bounded repair pass if the worker produced a usable diff. Do not change routing policy, model snapshots, Workflow Kernel runtime, release preflight, or unrelated consumers. Do not run release preflight, tag, merge, synchronize caches, invoke another model, or perform a broad review.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/dm-review/skills/review/SKILL.md` | Modify | Replace active agent, consolidator, and recorder first-root resolution; preserve optional skips and coherent roots. |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Modify | Replace `Step 0e: Ref Registry Init` cleanup-contract lookup. |
| `tests/test_runtime_cli.py` | Modify | Add inverse stale-cache and active-Codex tie fixtures; keep existing coherent-root proof. |
| `tools/validate-openrouter-resolution.sh` | Modify | Guard the exact active consumers and mutation-test restoration of the old first-root form. |
| `plugins/dm-review/.claude-plugin/plugin.json` | Modify | Patch bump `1.62.0` to `1.62.1`. |
| `plugins/pipeline/.claude-plugin/plugin.json` | Modify | Patch bump `1.51.0` to `1.51.1`. |
| `.claude-plugin/marketplace.json` | Modify | Apply the same canonical patch versions. |
| `.agents/plugins/marketplace.json` | Regenerate | Never hand-edit. |
| `plugins/dm-review/.codex-plugin/plugin.json` | Regenerate | Never hand-edit. |
| `plugins/pipeline/.codex-plugin/plugin.json` | Regenerate | Never hand-edit. |

Do not modify any other tracked file. Pipeline-owned ignored receipts and temporary test files are not product changes.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md` | Canonical launcher and cache-resolution contract. |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/runtime_resolution.py` | Existing semantic-version/coherence implementation; do not modify it. |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Exact stable `resolve-plugin-bundle` and `resolve-plugin-asset` CLI surfaces. |
| `tests/test_runtime_cli.py` | Existing semver, tie, and split-root fixtures to extend. |
| `tools/validate-dual-compat.sh` | Understand why naming both roots alone does not prevent first-root selection. |
| `plugins/dm-review/.claude-plugin/plugin.json` | Dependency floors and canonical metadata. |
| `plugins/pipeline/.claude-plugin/plugin.json` | Dependency floors and canonical metadata. |
| `AGENTS.md` and `CLAUDE.md` | Repository editing and generation rules. |

## Patterns to Follow

The old active pattern is unsafe and must disappear from the named consumers:

```bash
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ASSET=$(ls -t "$CACHE_ROOT"/<plugin>/*/<asset> 2>/dev/null | head -1)
  [ -n "$ASSET" ] && break
done
```

Use the already pinned `$WORKFLOW_KERNEL` and existing CLI behavior. Follow the established host detection and omit the tie-break flag when neither host is proven:

```bash
ACTIVE_HOST=""
[ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && ACTIVE_HOST="claude"
[ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && ACTIVE_HOST="codex"
ACTIVE_HOST_ARGS=()
[ -n "$ACTIVE_HOST" ] && ACTIVE_HOST_ARGS=(--active-host "$ACTIVE_HOST")
```

For Pipeline's one required cleanup contract, follow this form with the current compatible dm-review floor:

```bash
CONTRACT=$("$WORKFLOW_KERNEL" resolve-plugin-asset \
  --plugin dm-review \
  --asset skills/review/references/repo-cleanup-contract.md \
  --minimum-version 1.62.0 \
  "${ACTIVE_HOST_ARGS[@]}") || exit 1
```

For dm-review, do not resolve related dm-review files independently. Resolve the applicable required set in one `resolve-plugin-bundle` call, preserve its returned root/identity, and derive the selected agent, consolidator, and full-mode recorder paths from that root. For agent definitions owned by another plugin, resolve that plugin's selected required asset set coherently with its declared dependency floor. A genuinely optional plugin/agent that cannot resolve must remain a visible skip; a required dm-review/Pipeline asset must fail closed. Do not introduce a reusable resolver framework or shell service.

Extend the existing runtime resolver fixture rather than duplicating its setup. It must prove:

- stale Claude + newer compatible Codex selects Codex;
- stale Codex + newer compatible Claude selects Claude;
- equal highest versions select active Claude and active Codex in separate assertions;
- required assets split across roots do not combine.

Extend `tools/validate-openrouter-resolution.sh`, the existing coherent consumer validator. Factor only a small local validation function if needed. It must validate the canonical active files and run mutation-sensitive temporary-copy cases that reintroduce the old first-root loop for dm-review and Pipeline and assert failure. The mutation must exercise the same predicate used for canonical validation. Prove optional resolution is guarded as a skip rather than merely checking for the word “optional.” Do not sweep Airlift, Live Wires, historical prompts, or other optional surfaces.

The native supervisor changes the two canonical Claude manifests and marketplace, then runs `./tools/generate-codex-manifests.py`. Do not hand-author generated Codex manifests. No command source changes are expected, so generated command aliases should remain unchanged.

## Companion Skills

No additional domain companion skill is required. Follow the repository's Workflow Kernel runtime-resolution contract already provided in context; do not modify the runtime.

## Acceptance Criteria

- [ ] A stale Claude cache cannot beat a newer compatible Codex cache.
- [ ] A stale Codex cache cannot beat a newer compatible Claude cache.
- [ ] Equal highest versions prefer Claude when Claude is active and Codex when Codex is active.
- [ ] Every required asset set is selected from one coherent plugin root; split roots fail closed.
- [ ] Missing optional dm-review dependencies/assets skip gracefully, while required assets fail closed.
- [ ] Active Pipeline cleanup-contract resolution and dm-review agent/consolidator/recorder resolution no longer use Claude-first `ls -t` selection.
- [ ] The existing resolver-consumer validator passes the repaired canonical files and fails mutation copies that restore the prior active lookup.
- [ ] No new resolver framework, generic abstraction, background service, broker, authorization mechanism, cache synchronization machinery, or repo-relative stale fallback is added.
- [ ] Workflow Kernel runtime, release preflight, routing policy, model cascade, model matrix, Issue #54, planning coordinator, efficiency plan, unrelated plugins, product repos, and Fixture repos are unchanged.
- [ ] The worker diff does not hand-edit generated Codex manifests. Native supervision patch-bumps only dm-review and Pipeline, regenerates Codex manifests, and confirms command aliases remain current.
- [ ] Native supervision runs the exact focused command `python3 -m unittest tests.test_runtime_cli.RuntimeCliTests.test_plugin_bundle_resolver_is_semver_coherent_and_active_host_only_breaks_ties tests.test_runtime_cli.RuntimeCliTests.test_plugin_bundle_resolver_never_combines_assets_across_roots`, adding any newly split inverse/tie test name to the same invocation, plus `./tools/validate-openrouter-resolution.sh`.
- [ ] Native supervision runs `./tools/generate-codex-manifests.py --check`, `./tools/generate-codex-command-skills.py --check`, `./tools/validate-dual-compat.sh`, `./tools/validate-workflow-contracts.sh`, `./tools/validate-composition.sh --all`, and `git diff --check`.
- [ ] The worker ends its response with the unified diff only. The native supervisor records exact changed files, commands, unresolved gaps, accepted/rejected/rewritten hunks, and validation.

## Tool-Call Exploration Checkpoint & Delivery Contract

This adapter gives the worker no shell, repository, test, commit, publication, or
receipt tools. Return one unified diff and nothing else. Do not claim commands
were run. Stop adding speculative work when the listed files and acceptance
criteria are covered. The native Codex supervisor owns applying or rejecting the
diff, generator execution, tests, at most one bounded repair, commits, pushing,
PR/Issue state, receipts, `NOT-COVERED:`, and `COMMANDS-RUN:` reporting.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` adversarial scope review (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- Because this transport accepts only a unified diff, do not emit prose or commit trailers. If a material ambiguity remains after reading this prompt, return no patch. The native supervisor records any chosen interpretation and rejected alternatives as `Chose:` / `Rejected:` commit trailers and sets `ambiguity_resolved` in the chunk receipt before accepting the diff.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify the files listed above.
- Follow existing patterns; do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, or adjust unrelated lines.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk actually changes authentication, middleware, an Authorizer action/resource, a privileged read/write, a role/member/account/install/module permission, or a privileged UI capability in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. A matching path name is a review hint, not proof that the boundary changed.
- Do not commit, push, open or update a PR, or alter Issue/Project state; the native supervisor owns intentional publication and closeout.
- Do not edit or synchronize installed plugin caches.

## Research Context

- Active reachability is proven at dm-review `Phase 3: Agent Selection`, `Phase 4: Parallel Agent Launch`, `Phase 5: Consolidation`, and full-mode `Phase 7: Memory Capture`, plus Pipeline `Step 0e: Ref Registry Init`.
- Current installed caches happen to tie, so the defect is latent; mutation fixtures are the evidence.
- `runtime_resolution.resolve_plugin_bundle` scans both caches, filters compatible semantic versions, admits only complete roots, selects the global maximum, and uses active host only among equal maxima.
- Existing tests cover stale-Claude/newer-Codex, active-Claude tie, and coherent-root failure. The inverse stale direction and active-Codex tie are missing.
- Existing validators pass the old loops because dual compatibility only checks that both cache roots are named and the OpenRouter validator's old-lookup predicate does not cover these dm-review assets.
- The release-preflight cache check already exists and is out of scope.

## Behavioral Verification Inputs

- `REQ-01`: Newer compatible cache version wins in both host directions.
- `REQ-02`: Equal highest versions prefer the active host.
- `REQ-03`: Required asset sets bind to one coherent root.
- `REQ-04`: Missing optional dependencies skip gracefully.
- `REQ-05`: Active Pipeline and dm-review consumers cannot regress to first-root lookup.
- `REQ-06`: No prohibited framework, cache synchronization, policy, preflight, or kernel-runtime scope enters the diff.
- `REQ-07`: Preserve exact measured canary fields; execution receipts, not this worker, supply provider usage.
- `REG-01`: Reintroducing a Claude-first loop in either active consumer must make the validator fail.
- `REG-02`: Independently resolving related dm-review required assets must not permit mixed roots.
- `CHK-01`: focused `pytest` selection for resolver semver/tie/coherence fixtures; proves `REQ-01`, `REQ-02`, `REQ-03`.
- `CHK-02`: `./tools/validate-openrouter-resolution.sh`; proves `REQ-04`, `REQ-05`, `REG-01`, `REG-02`.
- `CHK-03`: generated-manifest, generated-alias, dual-compatibility, workflow-contract, and diff checks; proves `REQ-06`.
- No persona or browser case IDs apply; verification profile ID and digest are null.
