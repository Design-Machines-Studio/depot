> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Integrate FIDO Authority Across Workflow Kernel Cadence

## Context

Chunks 01 through 04 establish the public FIDO provider contract and authoritative Docker substrate.
This chunk connects those components to every Workflow Kernel repository-verification command and cadence boundary.
Production must never invoke or receive a receipt key.
The existing `--receipt-key-stdin` behavior remains an explicit legacy path for schema-v1 compatibility and tests only.

## Task

Add an explicit authority-provider mode to Workflow Kernel CLI and runtime APIs.
Resolve only the fixed installed `workflow-authority` client and non-secret provider/substrate handles.
Construct one closed FIDO run authorization, then fresh ephemeral-key-signed requests/results for every approve, plan, run, record, provider-attestation, cleanup, and receipt operation.
Verify the complete public FIDO → run key → ordered operation/result/cleanup chain through the fixed Go verifier and independently compare all bindings in Python.
Resolve `DM_VERIFICATION_SUBSTRATE` as a non-secret broker handle to an authoritative signed document.
Preserve current fail-closed planning, execution, receipt, provider, mutation, cache, and cadence behavior.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Modify | Explicit provider flags/handles, mode exclusion, stable exit codes |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_authority.py` | Modify | Approval issuance/validation through provider abstraction |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_planning.py` | Modify | Provider and substrate binding in plans/reuse |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_orchestrator.py` | Modify | Fresh provider calls, broker execution, cleanup validity |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_execution.py` | Modify | Prevent production host-side candidate execution and inheritance |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_provider.py` | Modify | Exact remote-provider evidence and broker attestation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_repository.py` | Modify | Closed profile/provider/substrate handle admission |
| `plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md` | Modify | Fixed installed authority companion resolution contract |
| `native/workflow-authority/cmd/workflow-authority/main.go` | Modify | Final client composition root and offline verification command |
| `native/workflow-authority/cmd/workflow-authorityd/main.go` | Modify | Final daemon composition root with production backends |
| `native/workflow-authority/internal/authority/composition.go` | Create | Explicit production backend assembly with no fake/stub fallback |
| `native/workflow-authority/internal/authority/offline.go` | Create | Daemon-independent public-chain historical verifier |
| `native/workflow-authority/internal/authority/offline_test.go` | Create | Binary-facing offline verification and composition tests |
| `tests/test_runtime_cli.py` | Modify | CLI selection, mutual exclusion, resolution, exit tests |
| `tests/test_repository_verification.py` | Modify | Full cadence, execution, cache, mutation, provider tests |
| `tests/test_authority_provider.py` | Modify | Cross-process verifier and handle integration tests |

## Files to Read

| File | Why |
|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Provider request/response validation from chunk 01 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_receipts.py` | Versioned receipt authority abstraction |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md` | Released command and cadence behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/runtime_resolution.py` | Existing trusted launcher/bundle resolution patterns |
| `native/workflow-authority/internal/protocol/types.go` | Shared operation and handle vocabulary |

## Production Mode Selection

Introduce one explicit production authority-provider selection.
Use a fixed installed client resolved by trusted runtime policy.
The repository may carry only a non-secret logical handle or fixed provider-mode declaration.
It may not carry:

- executable paths
- socket paths
- command strings
- shell fragments
- environment-variable names used for secrets
- raw public-key registry paths outside the installed root
- receipt keys
- PINs
- bearer tokens

Production provider mode and `--receipt-key-stdin` are mutually exclusive.
If neither is supplied where authority is required, fail closed.
If both are supplied, fail closed.
If the provider is unavailable, malformed, stale, untrusted, or version-incompatible, fail closed.
Never fall back from provider mode to HMAC.

## Fixed Companion Resolution

Follow the existing runtime resolution principles:

1. Resolve an installed, root-owned authority companion from a fixed policy root.
2. Reject repository-relative, worktree-relative, cache-relative, `PATH`, symlink, and environment-selected binaries.
3. Verify regular-file type, ownership, permissions, no-follow path components, expected version, protocol version, and trusted distribution identity metadata.
4. Invoke exact argv without a shell.
5. Spawn the fixed root-owned `workflow-authority` client with exact argv, supply one closed request through isolated stdin, and capture one bounded public JSON response on stdout. The client opens the controlling terminal directly for the single `authorization_required` confirmation flow; stdin remains protocol-only. Without a controlling terminal it returns `authority_unavailable`. Python never opens the broker socket directly.
6. Capture only a bounded public JSON response.
7. Use minimal environment and isolated stdin/HOME rules consistent with the kernel.
8. Verify exit code and closed response together; neither alone is authority.

Interpretation pre-selected: Python always uses the fixed client process.
Rejected: a direct Python socket client, because it duplicates framing and bypasses the Go client verification boundary.

Tests inject a fake verifier through an internal Python dependency seam.
Production never accepts the test seam from user input.

## Fresh Operation Mapping

Map each Workflow Kernel action to exactly one shared operation:

| Kernel action | Authority operation |
|---|---|
| Approve verification profile | `approve_profile` |
| Create or refresh plan | `plan_verification` |
| Admit/execute verification lane | `run_verification` |
| Record local result/receipt | `record_result` |
| Import remote provider evidence | `provider_attestation` |
| Validate historical public envelope | `verify_envelope` |
| Prepare run-owned containment | `substrate_prepare` |
| Inspect/revalidate containment | `substrate_inspect` |
| Execute exact contained argv | `substrate_execute` |
| Finalize cleanup/absence evidence | `substrate_cleanup` |
| Read status/doctor | `status` / `doctor` read-only operations |

Do not alias old names.
Do not reuse a response for a different operation.
Workflow Kernel never invokes `key_enroll`, `key_rotate`, `key_revoke`, or `substrate_enroll_endpoint`; those are root-console admin operations only.

## Request Closure

Every request includes all applicable fields, and Python recomputes them from trusted local inputs:

- schema/protocol version
- operation
- repository scope digest
- canonical repository descriptor/root identity
- run ID
- profile ID and profile digest
- trusted base commit
- candidate commit or snapshot digest
- changed-path closure
- boundary and cadence value
- lane ID and command digest
- provider name and provider request/result digest
- authority files/environment digest
- substrate handle and signed substrate digest
- previous receipt/event prefix digest
- nonce/sequence/timestamps supplied by the service challenge flow

Do not accept caller-provided digests without recomputing the underlying trusted value.
The Go result must echo the exact request digest.
Python compares each expected field after cryptographic verification.

## Cadence Semantics

Preserve repeated access at these boundaries:

- `chunk`
- `revision_batch`
- `execution_level`
- `merge_candidate`
- provider attestation operations

Each boundary receives a fresh nonce/sequence and ephemeral-key signature within the FIDO-approved run scope.
No cross-process grant is serialized.
No run-wide bearer is placed in environment or files.
Cache reuse does not reuse signing authority.
Cache reuse remains bound to exact command, source closure, toolchain/container, authority/substrate, environment profile, and source digest.
Receipt-only successor commits do not broaden authority.
Revision-batch changes force the appropriate new plan/run/result operations.

## Approval Integration

`approve-verification-profile` in provider mode:

1. Loads and validates the closed profile.
2. Resolves repository scope/base/candidate/authority closure.
3. Resolves the non-secret provider handle.
4. Resolves and validates authoritative substrate capability policy.
5. Constructs `approve_profile` request.
6. Obtains or validates the FIDO run authorization and a fresh ephemeral-key-signed approval operation.
7. Verifies and independently compares it.
8. Writes a v2 approval containing public evidence/provenance only.

The approval contains no receipt key, PIN, credential secret, environment secret, or reusable capability.
Cancelled/denied/unavailable authority writes no approved artifact.

## Planning Integration

`plan-verification` in provider mode:

- validates v2 approval and its public evidence
- recomputes repository/profile/base/candidate closure
- revalidates provider identity/version
- revalidates authoritative substrate handle/document freshness
- requests fresh `plan_verification` evidence
- binds exact cadence/boundary and cache identity
- emits only a v2 plan

Legacy approval cannot authorize v2 plan issuance.
V2 approval cannot be consumed by legacy HMAC plan mode.
Missing, stale, mismatched, or incomplete substrate evidence cannot produce an executable verified plan.

## Execution Integration

Production provider mode must not execute repository commands directly on the host.
For each admitted lane:

1. Revalidate plan, candidate, repository, authority, and substrate closure.
2. Request fresh ephemeral-key-signed `run_verification` authority within the active run scope.
3. Ask the broker to prepare and inspect the exact run-owned container.
4. Send exact contained argv and declared environment through `substrate_execute`.
5. Receive bounded outputs and public execution evidence.
6. Reinspect image/container/toolchain/generator identity.
7. Receive an ephemeral-key-signed `observed_result` over the exact execution/substrate evidence.
8. Request cleanup and require a distinct ephemeral-key-signed `cleanup_result` over exact-ID absence evidence.
9. Request `record_result`/final-receipt authority over the ordered run-authorization, execution, observation, cleanup, and provider digests.
10. Publish a passing receipt only if the complete chain validates.

Host runner behavior remains for explicit legacy/unit-test modes only.
No production child inherits provider socket, Docker socket, FIDO devices, authority state, HOME credentials, receipt key, or verifier handles.

## Provider Attestation Integration

Remote evidence is not trusted merely because a provider name appears.
The kernel must:

- validate exact declared provider and lane
- bind exact head/candidate and request digest
- validate provider-origin evidence under existing policy
- obtain a fresh `provider_attestation` FIDO operation
- compare the returned provider/lane/head/result/substrate bindings
- record provider provenance in the receipt
- reject altered, replayed, cross-run, cross-lane, cross-provider, stale, or incomplete evidence

The broker is not allowed to invent a successful provider result.
It authorizes a caller-supplied result only after exact evidence validation inputs are present.

## Substrate Handle Resolution

In v2/provider mode, `DM_VERIFICATION_SUBSTRATE` is a non-secret logical handle only.
Do not hash the handle string as proof.
Resolve it through the fixed companion.
Require a valid signed schema-v2 substrate document.
Require authoritative status.
Require candidate-container endpoint access denial: the contained workload receives no Docker, broker, FIDO, credential, or service-manager surface.
Require exact endpoint/engine/image/container/toolchain/generator/run/candidate/lane bindings.
Require freshness before and after execution.
Require verified cleanup for a passing receipt.
An opaque label, Docker context, tag, socket pathname, stale document, incomplete evidence, or tombstone cannot pass.
Explicit schema-v1 legacy mode retains the released opaque-substrate semantics and cannot enter provider mode; tests keep that behavior separate and prove no cross-mode reuse.

## Production Composition and Offline Verification

Replace the chunk-02 binary skeleton wiring with explicit production composition after FIDO, IPC, state, and Docker packages exist.
The daemon binary rejects unavailable or stub libfido2 and cannot silently select fake backends.
The client exposes a stable offline verification invocation that accepts only recorded public enrollment, revocation, FIDO authorization, ephemeral public key, and ordered signed-chain artifacts.
Offline verification does not connect to the daemon, Docker, or a FIDO device; it returns stable exit codes for valid, malformed, incomplete, revoked-at-issuance, reordered, substituted, and unknown-generation evidence.
Binary-level tests prove the real mains select production backends and historical verification remains usable after daemon shutdown or uninstall with retained public state.
Daemon `verify_envelope` and client offline verification call one shared internal chain verifier rather than duplicating signature/binding logic.

## Mutation and Concurrency

Retain existing repository mutation detection.
If candidate inputs change, invalidate or refresh according to current policy and require fresh authority.
Receipt append/merge remains lock-protected.
Concurrent lanes may execute only when their dependency/cadence policy permits.
Authority calls remain independent and uniquely sequenced.
Cancellation propagates to broker execution and cleanup.
If the client dies after execution but before receipt publication, recovery cleanup runs and no passing receipt appears without revalidation.

## Stable Error Semantics

Add closed errors for:

- provider required
- provider/legacy mode conflict
- provider unavailable
- provider identity invalid
- provider version incompatible
- provider response malformed
- provider verification failed
- authority denied
- authority cancelled
- authority stale/replayed
- substrate handle invalid
- substrate evidence incomplete
- candidate control surface exposed
- substrate drifted
- cleanup unverified

Errors must not embed request bodies, signatures, raw credential IDs, paths outside safe installed roots, Docker bodies, environment values, or repository content. Stable public credential references may appear only inside signed v2 evidence, never logs, diagnostics, status output, argv, environment, or fixtures.

## Companion Skills

Load:

- `developer-essentials:auth-implementation-patterns` for mode separation and exact authorization bindings.
- `developer-essentials:error-handling-patterns` for stable fail-closed error translation.
- `developer-essentials:e2e-testing-patterns` for CLI/cadence/cancellation coverage.

## Acceptance Criteria

- [ ] AC-01 All four repository-verification CLI commands support explicit provider mode and retain explicit legacy `--receipt-key-stdin` compatibility.
- [ ] AC-02 Provider mode and legacy mode are mutually exclusive and neither automatically falls back to the other.
- [ ] AC-03 Production resolves only the fixed root-owned companion with version/protocol/ownership/mode/no-follow checks; repository, `PATH`, environment, cache, and symlink selections fail.
- [ ] AC-04 The exact operation mapping table is implemented with no aliases or reused response across operations.
- [ ] AC-05 Python reconstructs and compares every applicable repository/run/profile/base/candidate/lane/provider/authority/substrate/result binding after public verification.
- [ ] AC-06 A forged verifier success, altered response, altered request digest, wrong verifier identity, or untrusted registry generation fails.
- [ ] AC-07 One FIDO run authorization binds the ephemeral public key and closed scope; `approve_profile`, `plan_verification`, `run_verification`, observed result, cleanup result, `record_result`, and `provider_attestation` each require a fresh nonce/sequence/ephemeral signature.
- [ ] AC-08 Chunk, revision-batch, execution-level, merge-candidate, and provider-attestation cadence tests prove repeated scoped authority without repeated touch or an exported bearer.
- [ ] AC-09 V1 approval/plan/receipt cannot authorize v2 issuance and v2 artifacts cannot silently enter legacy mode.
- [ ] AC-10 Production provider mode never sends a receipt key to Python or a child process and never executes candidate commands through the host runner.
- [ ] AC-11 Candidate execution occurs in the exact broker-measured container with exact argv and no provider/Docker/FIDO/authority/credential inheritance.
- [ ] AC-12 In v2/provider mode `DM_VERIFICATION_SUBSTRATE` resolves to an authoritative signed document and opaque labels/hashing the handle fail; explicit schema-v1 mode retains its released substrate semantics with no cross-mode fallback or artifact reuse.
- [ ] AC-13 Unenrolled endpoint, stale document, engine/image/toolchain drift, missing candidate isolation, or cleanup tombstone cannot produce a passing plan or receipt; trusted-host daemon tampering is explicitly outside scope.
- [ ] AC-14 Engine/image/container/Go 1.26.5/generator/run/candidate/lane evidence is checked before and after execution.
- [ ] AC-15 Passing receipts require signed exact-ID cleanup absence evidence; execution success with cleanup failure is non-passing.
- [ ] AC-15A Python and the fixed Go verifier validate the complete FIDO run authorization → ephemeral operation → observed result → cleanup result → final receipt chain offline; missing/reordered/substituted elements fail.
- [ ] AC-16 Cache reuse remains bound to exact command, source closure, toolchain/container, authority/substrate, environment profile, and source digest.
- [ ] AC-17 Repository mutation and revision-batch paths invalidate stale authority and request fresh operations without corrupting concurrent receipt suffixes.
- [ ] AC-18 Provider evidence binds exact provider, lane, candidate/head, request, result, authority, and substrate provenance.
- [ ] AC-19 Wrong repository, run, profile, base, candidate, boundary, lane, provider, substrate, result, nonce, sequence, timestamp, or operation fails.
- [ ] AC-20 Cancellation/timeout/client death invokes broker cleanup and cannot publish a pass without fresh revalidation.
- [ ] AC-21 Errors and CLI output remain bounded/redacted and contain no secret-shaped values, assertions, Docker bodies, environment values, or repository content.
- [ ] AC-22 Focused CLI, authority-provider, repository-verification, planning, execution, provider, mutation, cache, and concurrency tests pass.
- [ ] AC-23 `./tools/validate-workflow-kernel.py` passes or reports only an exact later-owned inventory gap; no expected red is called green.
- [ ] AC-24 `git diff --check` passes and only owned files change.
- [ ] AC-25 Tests assert no Python Workflow Kernel module opens the broker socket path directly.
- [ ] AC-26 Both final Go mains use explicit production composition with real FIDO/IPC/state/Docker implementations and no fake, stub, or environment-selected fallback.
- [ ] AC-27 The fixed client provides daemon-independent offline historical verification with stable exit codes and rejects every missing, reordered, altered, revoked-at-issuance, or unknown-generation chain element.
- [ ] AC-28 Binary-facing tests prove production backend wiring and offline verification after daemon shutdown using retained public state only.
- [ ] AC-29 Static and runtime tests prove Workflow Kernel cannot reach key/endpoint lifecycle operations and follows `authorization_required`/`authority_unavailable` retry semantics without prompt loops.
- [ ] AC-30 The same vector corpus produces identical verdicts through daemon `verify_envelope` and client offline verification because both use one shared internal verifier.

## Behavioral Contract Inputs

- `REQ-001`: preserve inspected Workflow Kernel conventions.
- `REQ-003`: identical Linux/macOS authority semantics through one provider contract.
- `REQ-004`: FIDO authority without exported key.
- `REQ-005`: no secret inheritance or output.
- `REQ-006`: authoritative substrate binding.
- `REQ-007`: fail-closed repeated cadence and provider operations.
- `REQ-008`: binding, replay, cancellation, concurrency, and cleanup adversaries.
- `CHK-013`: CLI mode and resolution matrix.
- `CHK-014`: cadence fresh-authority matrix.
- `CHK-015`: contained execution and cleanup matrix.
- `CHK-016`: provider evidence provenance matrix.

## Verification Commands

Use repository-sanctioned Python 3.12 execution.
Run focused unit modules first.
Run the offline Workflow Kernel validator after focused convergence.
Run `git diff --check`.
Do not use a live broker, authenticator, installed service, or external repository.
Do not call a missing lane a pass.

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

## Ambiguity Protocol

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify listed files.
- Do not modify Go internal packages other than the five listed composition-root files; do not modify `internal/admin/`, `packaging/`, or any file owned by chunk 06, which runs in parallel.
- Do not edit external Assembly/Baseplate worktrees.
- Do not expose a raw key, PIN, raw FIDO credential ID, general signing capability, socket path override, or reusable bearer. Stable public credential references may appear only inside signed v2 evidence and receipts; never in logs, diagnostics, status output, environment, argv, or fixtures.
- Do not trust caller digests, opaque substrate labels, Docker contexts, or provider names without recomputation/evidence.
- Do not weaken legacy validation to make new tests pass.
- Do not stage, commit, push, install, enroll, release, tag, publish, or run live services.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

The production raw-key pipe is impossible to protect from same-UID worker interception.
FIDO public evidence avoids key export, while Python binding checks prevent a confused-deputy verifier result.
The enrolled Docker engine is trusted host infrastructure; candidate containers receive none of its control surfaces.
Cleanup is part of receipt validity.
