# OR-EFFORT-01 — truthful OpenRouter effort

> COMPLETED 2026-09-07: PR #127 is merged, tagged, synchronized and proven by
> an installed consumer call. Historical prompt; do not rerun.
> Next: [UI-READY-03](ui-ready-03-repository-target-discovery.md).

## Recommended start — human only, refreshed 2026-09-07

- Model: GPT-5.6 Sol.
- Harness/rail: Codex subscription; installed router reports attemptable.
- Effort: high.
- Why: bounded transport and receipt repair with read/write/tool-use requirements.
- Cost: included subscription; no paid API charge inferred. The installed
  API-equivalent estimate is stale and must not be presented as current billing.
- Exactly one fallback: GPT-5.6 Terra / Codex subscription / high.
- Matrix evidence date: 2026-08-27; native pricing evidence is older, 2026-08-12.

The current human planning session remains Astra. This execution recommendation
is the installed router's result, not a claim that the proposed Astra portfolio
has already shipped. Refresh the human recommendation before execution.

## Complete copy-paste execution prompt

```text
Work in Design-Machines-Studio/depot to complete OR-EFFORT-01: make the effort
reported for OpenRouter work agree with the request actually transmitted.

Repository: /home/ned/ai/depot
Exact prepared base: 76267e0e10845e1f9ea4a5eb533b6ca9628b12be
Owning plugins: model-router and openrouter
executorRole: builder-deep
executorCapabilities: [read-repository, write-repository, tool-use, long-context, structured-output]
executorEffort: high

Read AGENTS.md, its direct instruction references, CLAUDE.md, the relevant
model-router/OpenRouter contracts and validation instructions. Do not run a
full Pipeline for this bounded transport repair. Follow the repository's
required composition validation and use focused review appropriate to the fix.

Preserve the primary checkout and every existing worktree exactly. The primary
contains unrelated benchmark changes. Do not stash,
reset, clean, switch, rebase or remove anything. Fetch origin, compare current
main with the prepared base, and inspect any intervening changes. Create a new
clean worktree from current origin/main on fix/openrouter-effort-contract (use
a unique suffix if needed). Record the actual base/head. Refresh open Issues,
PRs and worktrees before claiming the change; avoid another active owner's work.

Demonstrated problem:
- model-router's role policy maps normalized effort for each transport.
- role-dispatch.sh computes EFFECTIVE_EFFORT and writes it into receipts.
- Both OpenRouter read and write paths omit that effort when invoking their
  wrapper/adapter. openrouter-wrapper.sh constructs the outgoing request without
  a reasoning effort field. Thus the report claims more than transmission proves.

Smallest intended change:
Carry normalized effort through both existing OpenRouter paths and map it to
currently supported provider request settings. Distinguish requested effort,
   what was actually sent, and unsupported/unavailable evidence. Never silently
claim an unsupported setting took effect. Verify the chosen request fields
against current official OpenRouter documentation and the relevant model's
capabilities. Preserve compatible direct invocations that omit an effort; they
must report default/unknown honestly. Reuse current request/receipt structures,
normalization policy, wrapper and terminal renderer. Adapt their existing
fields only where needed; do not invent another schema family or state system.

Likely surfaces:
- plugins/model-router/skills/model-router/references/role-dispatch.sh
- plugins/model-router/skills/model-router/references/openrouter-write-adapter.sh
- role-policy.json, receipt-contract.md, role-request-schema.json and the
  existing terminal renderer/contract only where their semantics require it
- plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh
- its invocation-protocol.md and existing receipt validation
- tools/test-model-router.sh, tools/test-openrouter-runner-policy.sh,
  tools/test-terminal-model-report.sh and their existing fixtures
- canonical manifests, dependency floors and generated/index surfaces as needed

Non-goals:
No new model portfolio, planning-model rollout, global Codex configuration, monthly budget
manager, model tournament, service, broker, browser target discovery, Pi transport,
consumer runbook changes, review-lane redesign or unrelated cleanup. Do not
add output-token controls to this chunk unless the supported effort API requires
an inseparable bound; otherwise leave that separate. Do not change ordinary
authorization, release boundaries or credential handling.

Acceptance:
1. A focused failing regression first captures the actual outgoing JSON for
   OpenRouter read and bounded-write paths, rather than only inspecting router
   stubs. Low/medium/high/max normalization reaches the supported wire field.
2. Requested, transmitted and reported effort agree. An omitted or unsupported
   setting cannot appear as a confirmed effective setting. Historical receipts
   remain readable without inventing missing evidence. A transmitted setting
   is not a measurement of the model's internal reasoning process.
3. Native subscription effort flags, anonymous participant packets, model
   identity separation, response attribution, fallback accounting and timeout
   behavior remain correct. Failed attempts cannot become clean passes.
4. A provider that cannot satisfy a required setting produces an honest bounded
   outcome/fallback. No retry loop or silent widening of candidate scope.
5. Focused regression tests and full composition validation pass on the final
   implementation. All retained P1/P2/P3 findings are fixed and affected checks
   rerun before requesting merge.

Verification:
Use current offline transport-capture fixtures and the focused router, wrapper
and terminal-report tests. Run ./tools/validate-composition.sh --all, which covers
generated manifests/aliases, dependencies, dual compatibility and Kernel checks.
Inspect script usage first; do not assume flags. Do not repeat unrelated tests
after they pass unless later changes invalidate them. Record COMMANDS-RUN.

Version and composition:
Prepared versions are model-router 0.6.1 and openrouter 1.20.1. A backward-compatible
fix normally means patches 0.6.2 and 1.20.2, subject to refreshed source/tags and
actual contract compatibility. Edit canonical Claude plugin manifests and the
canonical marketplace only; regenerate Codex manifests. Regenerate command-skill
aliases if their canonical commands changed. Refresh the existing search index
when indexed content changes. Move consumer dependency floors only where the
new behavior requires the new provider version; bump no unrelated plugin.
Check runtime minimum-version declarations as well as manifest dependencies.
The router currently declares optional OpenRouter >=1.19.0; require a bundle
that actually implements the new setting when using it. Existing router floors
are Pipeline >=0.6.0, dm-review >=0.4.0, and project-manager optional >=0.6.0.
Evaluate those callers explicitly; unchanged compatible calls do not by
themselves justify bumping three more plugins.

Delivery and consumer proof:
Commit verified owned changes, push the branch, and create/update one reviewable
PR with exact base/head, regression, scope, validation and remaining delivery
steps. Inspect exact-head hosted checks and review state. Depot currently has
no required hosted composition gate; SKIPPED or absent checks are not green CI.
Do not add unrelated CI machinery just to make that display green.

Do not merge, tag, publish or synchronize installations in this execution without
separate explicit authorization. Prepare the two version-specific release tags
and publication steps. After authorized merge, validate trusted main, publish the
changed plugins, synchronize both Claude and Codex caches using existing tools,
verify installed identities, and run one bounded real consumer call against the
changed installed path. Until then, report source/local proof and leave published,
cache and real installed-consumer proof pending. A local test against source is
not installed-consumer proof.

Real canary: a bounded repository-evidence analysis through the router using
the normalized effort, from an exact consumer revision, with an authoritative
provider receipt and one terminal report. The developer's OpenRouter target is
$50/month or less; use the configured provider cap and remaining budget, keep
this canary below $0.25, and do not increase any budget or use a paid benchmark
campaign. If the request cannot be bounded within available budget, retain
offline protocol proof and state the consumer-proof gap explicitly.

GitHub terminal state: one pushed, verified PR ready for review; no unresolved
retained findings. No native Issue creation/closure/reassignment is authorized.
If an existing issue is found, link it without changing its lifecycle. Project 1,
Assembly Coordination, may project this active tooling PR as Review/P1/Tooling
when its fields are confirmed; do not create another Project or mark it Done
while merge/publication/consumer requirements remain outstanding.

Treat about 40 tool calls as an exploration checkpoint. Stop broad research and
scope expansion then, but finish focused repair, verification, commit, push,
PR preparation and truthful reporting. Do not abandon completed work unverified.

Final response: concise result and one next action. Include actual base/head and
PR URL, strongest delivery level, SIMPLICITY-CHECK, NOT-COVERED and COMMANDS-RUN.
After dispatch is closed, emit one compact model-and-cost report with role,
attempted and served participant, rail, requested/transmitted effort, duration,
outcome, measured tokens, measured paid cost, subscription calls, fallbacks and
unavailable measurements. Do not infer subscription cost from API-equivalent
prices or treat an unavailable measurement as zero.
```
