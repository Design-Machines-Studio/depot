# Chunk: Integrate Depot with the fixed broker client seam

## Context

This is the Depot adapter workstream. It develops solely against a production-ineligible executable fake client. M1 enables only the Pipeline assessment artifact-delegation lane; every other Pipeline, dm-review, execution, adversarial, and Airlift lane remains `host_authority_unavailable`.

Production automated OpenRouter must remain `host_authority_unavailable` until the M1 acceptance chunk proves the installed broker. This chunk supplies exact content and requested routing as untrusted input; it supplies no authority knobs.

## Task

Replace the caller-selected authorization/digest plus direct-wrapper blocks in `dispatch_wrapper`, `openrouter_allowed`, and the corresponding authorization block in `openrouter-exec.sh` with one fixed `workflow-authority dispatch-provider-request` protocol call.

Preserve the dormant test seam so adapter tests can use M0's fake broker only when an explicit fixture marker and injected test root are present. Production accepts no alternate broker path or socket. Preserve direct interactive `/openrouter` behavior outside these automated Pipeline seams.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `plugins/pipeline/references/cascade-dispatch.sh` | Modify | Replace automated wrapper authorization/send branch with fixed broker client call |
| `plugins/pipeline/references/openrouter-exec.sh` | Modify | Replace snapshot/mode/wrapper execution with broker request/result handling |
| `tools/fixtures/fake-workflow-authority-client.py` | Create | Executable production-ineligible exact-frame/result fixture |
| `tools/test-openrouter-runner-policy.sh` | Modify | Adapter, allowlist, fallback, forged-result and interactive regressions |

## Files to Read (for context)

| File | Why |
|---|---|
| `plugins/pipeline/references/openrouter-authorization-contract.md` | Existing disclosure and fallback contract |
| `plugins/pipeline/references/routing-policy.json` | Routing remains unchanged |
| `plugins/openrouter/skills/openrouter-delegate/references/invocation-protocol.md` | Current response/output expectations |
| `tests/test_provider_dispatch_contract.py` | Fake broker and exact request vectors |
| `tools/test-openrouter-runner-policy.sh` | Existing dormant-production and fallback assertions |

## Patterns to Follow

- Keep `openrouter_allowed` as the single production availability gate.
- Admit broker dispatch only for the exact stable lane identifier `pipeline-assessment-artifact-delegation-v1`; all other automated lane IDs fail closed to Codex.
- Use stable anchors `dispatch_wrapper`, `openrouter_allowed`, and the `AUTHORIZATION_MODE` block; do not target line numbers.
- Automated callers pass ordered system/user bytes, requested model/fallback, workload, repository/run/lane/candidate identifiers, and nonce only.
- Strip `OPENROUTER_API_KEY`, `OPENROUTER_BASE`, `OPENROUTER_PAYLOAD_AUTHORIZATION`, `OPENROUTER_PAYLOAD_APPROVAL_SHA256`, wrapper path, policy path, scanner path, and receipt output path from the broker process environment.
- Response content is read only from the original broker connection contract; stdout is reserved for the signed content-free result. Do not accept an output file path or later retrieval token.
- A missing, invalid, unsigned, wrong-scope, or nonterminal receipt is never provider success.

## Companion Skills

- `developer-essentials:auth-implementation-patterns` -- prevent caller self-promotion and downgrade
- `developer-essentials:error-handling-patterns` -- preserve explicit fallback classes and stable exits

## Acceptance Criteria

- [ ] `REQ-ADAPTER-01`: `cascade-dispatch.sh` and `openrouter-exec.sh` share one fixed broker-client invocation contract and never invoke the OpenRouter wrapper in production automation.
- [ ] `REQ-ADAPTER-02`: no caller-provided socket, client path, provider base, credential, authorization mode, approved digest, scanner, policy, or receipt-output path affects production dispatch.
- [ ] `REQ-ADAPTER-03`: exact ordered content bytes and route/scope fields are transmitted without concatenation, normalization, trimming, shell re-expansion, or temporary durable response files.
- [ ] `REQ-ADAPTER-04`: only a verified signed terminal result with matching repository/run/lane/candidate/request digest is accepted as provider-backed.
- [ ] `REQ-ADAPTER-05`: broker unavailable maps to the existing `host_authority_unavailable` Codex descent; disclosure decline maps to `host_disclosure_declined`; provider failure remains distinct.
- [ ] `REQ-ADAPTER-06`: dry-run model selection, routing economics, ladder order, quality floor, and fallback reporting remain behaviorally identical.
- [ ] `REQ-ADAPTER-07`: the fake broker is admitted only under the existing explicit automation test marker plus injected fixture root and can never make production status ready.
- [ ] `REQ-ADAPTER-08`: direct interactive `/openrouter` exact-digest behavior is untouched by these two files.
- [ ] `REQ-ADAPTER-09`: only `pipeline-assessment-artifact-delegation-v1` may enter the M1 broker branch; research, adversarial review, execution, dm-review, Airlift, unknown and missing lane IDs retain `host_authority_unavailable`.
- [ ] `REQ-ADAPTER-10`: the executable fake has a fixture-only trust marker, refuses the production socket/origin, cannot report production-ready, and emits exact signed-result fixtures for positive and forged cases.
- [ ] Negative tests cover environment self-promotion, fake approved digest, alternate socket/client/base, forged receipt, wrong scope, missing receipt, malformed response, wrapper/curl bypass, and later response retrieval.
- [ ] `tools/test-openrouter-runner-policy.sh`, `tools/validate-openrouter-cascade.sh`, and `tools/validate-routing-economics.sh` pass with updated M1 expectations.
- [ ] No provider, credential, DNS, TLS, live broker, or external worktree is touched.

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` Sprint Contract Negotiation (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify the files listed above.
- Do not redesign the routing matrix or change model/provider economics.
- Do not modify OpenRouter plugin files, dm-review, Airlift, Workflow Kernel, generated aliases, or manifests.
- Do not add a same-UID shared secret, caller path discovery, or environment authorization fallback.
- Do not enable production automation in this chunk; M1 acceptance owns that assertion change.
- Do not touch the read-only PR15 worktree.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.

## Research Context

PR15 correctly fails closed because its former automated path allowed the worker to choose `trusted-boundary` or copy its own digest into approval. The smallest safe adapter does not repair that shell authorization; it removes it and delegates the indivisible scan/authorize/send/result transaction to the host broker.

## Required Handoff Evidence

- Show the before/after authority path using function names, not line numbers.
- List every stripped authority/credential/transport environment variable.
- Record dry-run and Codex-fallback fixtures unchanged by the edit.
- Record fake-broker-only cases separately from production-unavailable cases.
- Confirm no new direct wrapper or curl call remains in automated branches.
- Report direct interactive `/openrouter` as unchanged or `NOT-COVERED` with evidence.

## Exact Adapter Matrix

- Assessment lane with fixture client: exact ordered system/user framing reaches the fake and a matching terminal result is accepted.
- Assessment lane with production broker unavailable: explicit Codex fallback and no wrapper/network call.
- Every non-assessment lane: explicit Codex fallback even if a fake or broker claims ready.
- Missing, malformed, unsigned, stale, wrong-scope, wrong-body, wrong-model, or wrong-lane result: rejected and fallback recorded.
- Caller key/base/socket/client/policy/scanner/output/auth-mode/digest variables: ignored or stripped and proven ineffective.
- fd-3 response path: anonymous pipe only, bounded, original invocation only, no stdout/file/later retrieval.
- Direct interactive `/openrouter`: unchanged exact-digest gate and wrapper path.
- Dry-run: unchanged route selection without authority or provider contact.

## Focused Test Ownership

Update `tools/test-openrouter-runner-policy.sh` in this chunk rather than promising later ownership. Preserve all existing disclosure, output-path, patch validation, model provenance, direct-interactive, and Codex fallback assertions. Replace only the dormant automated branch fixtures necessary for the single assessment lane.

The fake client is not the M0 protocol source of truth. It consumes M0 vectors and must fail its own startup if its fixture schema/digests drift. It must never read a provider key or open a network connection.

## Stable-Anchor Edit Map

### `cascade-dispatch.sh`

1. Keep argument parsing, routing-policy resolution, ladder selection, dry-run, capacity descent and Codex implementations unchanged.
2. At function `openrouter_allowed`, replace the unconditional production denial with a fixed-client readiness check plus exact lane allowlist. Readiness is not authority and does not contact the provider.
3. At function `dispatch_wrapper`, remove the automated snapshot/mode/digest/direct-wrapper branch. Materialize exact ordered parts only long enough to frame the broker request.
4. Invoke the installed fixed client with a closed subcommand and inherited anonymous response descriptor. Do not resolve it from plugin cache, PATH, repository, or environment.
5. Verify the content-free signed terminal result and exact scope before returning a provider-backed outcome.
6. Preserve existing return-code descent: unavailable and decline return to Codex; malformed broker output is a hard safe failure, never provider exhaustion.

### `openrouter-exec.sh`

1. Keep allowed-path discovery, disclosure classification, returned-diff validation and patch-path enforcement.
2. Remove the automated `AUTHORIZATION_MODE` case block and direct `openrouter-wrapper.sh` execution.
3. Build the same exact two-part system/user request used by the assessment lane and call the fixed broker client.
4. Read model response bytes only from the inherited anonymous response descriptor, never command substitution/stdout.
5. Keep signed terminal result separate from response bytes and validate its body/response/scope digests.
6. Preserve output validation: non-empty unified diff, exact owned paths, no model command authority.

## Closed Request Framing

The adapter consumes the exact M0 exchange unchanged: four-byte unsigned big-endian canonical-header length and header, followed by each part as an eight-byte unsigned big-endian length and exact UTF-8 bytes. It accepts only the frozen length-prefixed challenge/content/terminal or safe-error frames and fixed exit codes. Do not invent shell delimiters, alternate framing, or a second authorization/retrieval connection.

The final OpenRouter body does not exist in the shell adapter. The daemon constructs it deterministically, scans the original parts, returns the final body digest for terminal display/FIDO, and resumes the same reserved transaction only after exact authorization. The adapter cannot supply or approve that digest itself.

## Result Verification Contract

The fixed client verifies daemon trust and signature material; the shell additionally requires:

- terminal outcome belongs to `external_provider_dispatch`;
- request, body and response digests use lowercase `sha256:` form;
- repository/run/lane/candidate/model match the exact invocation;
- `substrate_authority` is `not_asserted`;
- sequence/nonce are present and terminal cleanup is explicit;
- response byte count matches bytes read from the anonymous descriptor;
- provider/model provenance is present when policy requires it;
- no prompt/response content or secret-shaped field appears in stdout JSON.

Any mismatch discards response bytes and records a safe local fallback. It never retries the provider or calls the legacy wrapper.

## Environment Scrub Contract

Before the fixed client starts, construct a minimal inherited environment. Remove at least:

- `OPENROUTER_API_KEY`, `OPENROUTER_BASE`, `OPENROUTER_ZDR`;
- `OPENROUTER_PAYLOAD_AUTHORIZATION`, `OPENROUTER_PAYLOAD_APPROVAL_SHA256`;
- `OPENROUTER_AUTHORIZATION_MODE`, `OPENROUTER_RECEIPT_FILE`;
- wrapper, boundary, scanner, policy, broker-client and socket override variables;
- proxy variables in upper/lower case;
- inherited response/output descriptor declarations other than the newly created anonymous pipe.

The broker owns authoritative routing policy. The adapter may submit the routing matrix's requested model order, but cannot expand it after FIDO approval or override the installed allowlist.

## Fake Client Contract

`tools/fixtures/fake-workflow-authority-client.py` is executable only from the explicit existing fixture seam. It requires an injected temporary root, fixture trust marker, and loopback-only fixture configuration. It refuses the production socket, provider origin, real-looking credential, absent fixture marker, or ordinary production invocation.

Support deterministic cases: ready, unavailable, disclosure declined, approval declined, signed success, safe provider failure, timeout, malformed frame, forged signature, wrong scope, wrong response length and unknown terminal outcome. It emits no real model content unless supplied as an explicit test fixture.

## Runner-Policy Regression Cases

- Production checkout without broker: exact historic `host_authority_unavailable` descent.
- Production checkout with API key only: still unavailable; wrapper not called.
- Production checkout with caller trusted-boundary/digest variables: still unavailable or stripped.
- Fixture assessment lane: broker fake invoked once; exact response/result verified.
- Fixture non-assessment lanes: broker fake not invoked; Codex fallback recorded.
- Forged/mismatched fake result: response discarded; safe failure/fallback; no patch application.
- Direct interactive runner: existing exact-digest approval-required and approved paths remain intact.
- Dry-run: route selection output unchanged and no broker/fake/provider contact.
- Secret-bearing outbound bytes: existing disclosure rejection occurs before fake invocation.
- Returned diff outside owned paths or malformed: existing output boundary rejects it.

## Chunk Receipt

Report the exact lane enabled, every lane left unavailable, stable functions changed, environment variables stripped, fake cases executed, existing regression cases preserved, and commands run. Include requested/attempted/actual implementer provenance for the chunk itself. Do not include prompt/response bytes or local secret-shaped values.
