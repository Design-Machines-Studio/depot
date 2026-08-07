# Original Prompt

## User Input

Implement a production-grade macOS host authority broker for Workflow Kernel repository verification as a separate Depot task.

Context and objective:
- Workflow Kernel 0.6.1 defines approve-verification-profile, plan-verification, run-verification, and record-verification-result with --receipt-key-stdin.
- The current Baseplate pipeline is blocked because no HOST_AUTHORITY_BROKER implementation is installed and DM_VERIFICATION_SUBSTRATE is unavailable.
- The broker must preserve the security boundary: repository/worker code must not read, mint, log, inherit, or pass the authority key through argv or environment.
- A chmod-600 plaintext key or same-user shell script is not acceptable.
- Target macOS with OrbStack, currently exposed at unix:///Users/trav/.orbstack/run/docker.sock.

Required work:
1. Inspect current Depot/Workflow Kernel architecture, AGENTS.md, relevant skills, schemas, CLI contracts, tests, and release/install conventions before designing.
2. Work only in the new isolated worktree; do not disturb existing Depot or Assembly/Baseplate worktrees and do not absorb unrelated changes.
3. Produce a threat model and select a practical macOS authority boundary using user-presence or equivalent host authorization (for example a native broker backed by Keychain/Secure Enclave or a narrowly scoped launchd/XPC service). Explain why repository workers cannot extract the key.
4. Implement the broker and its installation/uninstallation/status workflow. Never expose the key in stdout except the exact bounded receipt-key protocol response, or in logs, files, argv, environment, crash reports, receipts, or test fixtures.
5. Implement caller-produced DM_VERIFICATION_SUBSTRATE attestation for OrbStack/Docker, binding the actual Docker endpoint/engine, containment identity, resolved image digest, exact Go 1.26.5, generator/toolchain identity, run ID, and lifecycle cleanup. Do not accept a caller-invented opaque label as proof.
6. Integrate with Workflow Kernel’s documented HOST_AUTHORITY_BROKER pipe contract without weakening fail-closed semantics. Preserve repeated access across chunk, revision_batch, execution_level, merge_candidate, and provider-attestation operations.
7. Add adversarial tests for unauthorized invocation, same-user worker attempts, key exfiltration channels, replay/stale authorization, wrong repository/run/profile/candidate, altered substrate, symlink/path attacks, concurrent requests, cancellation, and cleanup.
8. Add operator documentation with exact setup/use/recovery/uninstall steps and a minimal Baseplate-compatible example that exports only non-secret broker/substrate handles.
9. Run all required repository validation according to Depot instructions. Use existing project skills and current documentation. Do not run release, push, PR, merge, tag, marketplace publication, or live installation without separate explicit authorization.
10. Hand off the implementation, threat-model decisions, test evidence, remaining risks, and the exact next authorization gate.

Start from the project default branch in the Codex-managed worktree.

## Date

2026-08-02

## Key Requirements Extracted

1. Inspect Depot and Workflow Kernel architecture, instructions, skills, schemas, CLI contracts, tests, and release/install conventions before design.
2. Keep all work inside the isolated Codex-managed Depot worktree based on the default branch, preserving unrelated worktrees and changes.
3. Define a macOS threat model and a practical host authority boundary with user presence or equivalent authorization that prevents repository workers from extracting the receipt key.
4. Implement broker setup, bounded receipt-key delivery, status, recovery, and uninstall without leaking the key through files, logs, argv, environment, crash reports, receipts, or fixtures.
5. Implement a caller-produced OrbStack/Docker substrate attestation bound to the real endpoint and engine, containment identity, resolved image digest, exact Go 1.26.5, generator/toolchain identity, run ID, and cleanup lifecycle.
6. Integrate with the existing fail-closed HOST_AUTHORITY_BROKER pipe contract and support repeated authority operations across all required verification boundaries and provider attestation.
7. Add adversarial coverage for authorization, same-user attacks, exfiltration, replay/staleness, binding mismatches, substrate alteration, path attacks, concurrency, cancellation, and cleanup.
8. Document exact operator setup, use, recovery, uninstall, and a Baseplate-compatible example exporting only non-secret handles.
9. Run Depot-required validation, but do not install live, release, commit, push, open a PR, merge, tag, or publish without separate authorization.
10. Hand off implementation evidence, threat-model decisions, remaining risks, and the exact next authorization gate.

## Iteration 1 Feedback

The user approved the following Phase 3 classifications without modification:

- `workflowClass`: `security`
- `decisionProfile`: `{"uncertainty":"high","consequence":"high","rationale":"The design changes the authority trust boundary, cryptographic receipt contract, native macOS service architecture, and verification substrate; mistakes could expose signing authority or falsely attest repository verification."}`

## Iteration 2 Feedback

After reviewing `plans/macos-authority-broker/plan.html`, the user responded `aspproved`. This explicitly approves the full plan, including decision D1: production uses the v2 asymmetric authority-provider contract and the public stdin HMAC pipe remains legacy compatibility only because it cannot satisfy the same-user threat model.

## Iteration 3 Feedback

The user rejected platform-specific product behavior after learning that the Swift/XPC implementation would not run on Linux:

- Linux will be the primary development platform moving forward.
- macOS and Linux must have parity; the product must not include security or workflow features that are unavailable on Linux.
- The previously approved Swift/XPC/Secure Enclave plan is superseded and no longer authorizes implementation.
- The user approved replacement planning around a Linux-first, cross-platform Go broker with a shared FIDO2/libfido2 user-presence and non-exportable-key boundary.
- Platform adapters may differ only where the operating systems require it, such as `systemd` versus `launchd` and Unix-socket peer credential APIs. User-facing operations, authorization semantics, receipt/substrate contracts, failure behavior, lifecycle commands, and adversarial coverage must remain equivalent.
- Existing partial macOS implementation work must remain paused until the replacement plan completes fresh adversarial review and receives a new explicit execution approval.

## Iteration 4 Feedback

The user approved the replacement research brief and its three decisions:

1. Production uses public FIDO-signed schema-v2 authority envelopes; raw `--receipt-key-stdin` remains explicit legacy compatibility only.
2. Authoritative Docker verification requires a separate worker OS principal denied access to the enrolled Docker socket, or a broker-exclusive engine/socket. The current same-user OrbStack endpoint is observational until this separation exists.
3. Linux and macOS use one Go core with a thin cgo adapter to pinned libfido2; only peer-credential and service-manager adapters differ.

## Iteration 5 Feedback

The user approved the corrected replacement implementation plan after its closed `decisionProfile` metadata was repaired to include the exact approved high/high rationale. This approval authorizes Phase 4 prompt and manifest generation plus adversarial plan review; it does not authorize implementation or any live, git-publication, installation, enrollment, or release action.

## Iteration 6 Feedback

After both adversarial lenses returned `REVISE`, the user explicitly selected the practical consent boundary and directed the design to avoid enterprise-scale over-hardening for the current two-person team:

- Keep the design as simple as possible while preserving the useful repository/candidate-code boundary.
- Production protects against candidate code, repository-controlled commands, accidental leakage, and unattended agent minting. A fully compromised developer desktop, deliberate developer tampering with Docker, and sophisticated consent-display spoofing are outside the supported threat boundary and must be documented honestly.
- The genuine broker displays the exact run scope in the operator-initiated terminal and requires authenticator-internal UV. The user accepts that this is not a cryptographically trusted display.
- Use one FIDO approval per closed run rather than one touch per operation. The daemon generates an ephemeral run signing key held only in root-process memory; the FIDO assertion binds its public key and run scope. Repeated operation/result/cleanup envelopes are signed by that ephemeral key. Restart or expiry destroys the run authority and requires another FIDO approval.
- Treat the enrolled Docker engine as trusted host infrastructure. Candidate containers must not receive Docker, broker, FIDO, credential, or service-manager access. The broker still measures and revalidates endpoint, engine, image, container, Go 1.26.5, generator, exact workload, and cleanup, but does not claim resistance to a developer or host agent that intentionally controls the same Docker daemon.
- Continue to implement real install/status/recovery/uninstall adapters, but do not invoke them live without a later authorization gate.

## Iteration 7 Feedback

The user stopped the prior prompt/adversarial-review track and supplied the canonical expansion request at:

`/Users/trav/.codex/attachments/717c6122-a5c8-42b4-b10b-10e21e7007f6/pasted-text.txt`

This is a material planning-scope revision. It does not authorize implementation, replacement prompt generation, edits to the PR15 worktree, installation, enrollment, credential access, provider calls, validation against live services, staging, commit, push, PR, merge, tag, publication, or release.

The expansion requires the current Linux-first/macOS-parity authority broker plan to cover independently authorized external-provider dispatch, initially OpenRouter. Repository verification and provider dispatch remain separate operation families sharing the same FIDO-authorized closed-run foundation.

The governing requirements added by this iteration are:

1. Treat `/private/tmp/depot-pipeline-speed-matrix` and its P1 todo `todos/112-pending-p1-openrouter-host-authority.md` as read-only evidence. Current automated callers cannot establish independent authority because repository workers select the authorization mode and can compute the claimed approved digest themselves.
2. Preserve the shared Go core, pinned libfido2, Linux-primary/macOS-parity behavior, fixed root-owned service and socket, `SO_PEERCRED`/`getpeereid` adapters, one FIDO-approved closed run, memory-only ephemeral run signer, replay protection, public v2 evidence, and candidate control-surface exclusion.
3. Add a provider-dispatch threat model covering self-selected trusted-boundary mode/digest, cross-scope replay, post-authorization payload/destination changes, redirect/key theft/direct-curl bypass, model/policy/scanner substitution, forged response provenance, malicious candidate code, same-UID attacks, restart/expiry/revocation, and bounded compromised-host residuals.
4. Compare broker-owned transport, a privileged local proxy, and signed child grants. Prefer broker-owned transport; reject a signed grant if the child still has the API key or authoritative network path.
5. Define closed provider operations and decide whether authorization/dispatch are indivisible or a short-lived pair. Avoid reusable bearer capabilities.
6. Bind authorization to the exact ordered payload manifest and per-file bytes/digests; pinned OpenRouter origin; requested/fallback models; workload; routing/disclosure policy digests; byte/response limits; repository/run/base/candidate/snapshot/lane/authority/substrate; nonce/sequence/boot/session/time/expiry/single-use; and complete response bounds.
7. Preserve exact bytes with bounded frames/files, rehash immediately before transport, run a fixed trusted disclosure scanner, bind scanner/policy identity, log no prompt/response content, reject malformed/binary/secret-bearing content before network contact, and clean temporary artifacts securely.
8. Keep the provider key and network transport inside the broker boundary. Production origin is pinned; arbitrary base overrides are impossible; tests use isolated authority and fixture-only credentials; candidate code has no provider route; host firewall/sandbox assumptions are explicit.
9. Define one-run consent and cadence, the exact changes requiring fresh approval, a narrower interactive exact-digest mode, fail-closed missing authority, and explicit local-Codex fallback behavior.
10. Sign provider-result evidence over request and authorization digests, exact destination, requested/fallback/actual models, serving-provider provenance, generation ID, usage, fallback, response digest/bytes, safe outcome, run/lane/candidate/substrate, prior-chain digest, and cleanup—never content, key, or secret-shaped diagnostics.
11. Migrate OpenRouter, dm-review, Pipeline, Airlift, and Workflow Kernel through a fixed broker client; remove caller-controlled authorization environment values and child provider keys; preserve fail-closed fallback receipts and direct interactive `/openrouter` compatibility.
12. Expand the plan to ownership-isolated chunks for provider schema, Go vectors, FIDO run scope, broker transport, OpenRouter adapter, workflow integrations, OS parity, hostile harness, migration/docs/generated surfaces, and release/install gates.
13. Add the full adversarial matrix for payload/destination/model/policy/scope/replay/credential/peer/path/frame/FIDO/cancellation/stream/provenance/cleanup/parity cases. Unavailable hardware or service lanes are gaps, never passes.
14. Update assessment, research, plan diagrams, threat model, protocol, alternatives, chunk dependencies/ownership, tests, PR15 migration, coverage gaps, and machine metadata. Because scope is material, stop after planning artifacts and request fresh approval.

This iteration supersedes the old plan's treatment of `provider_attestation` as sufficient provider authority. That operation remains inbound repository-verification evidence; it does not authorize outbound disclosure. The previously generated manifest, eight prompts, and OpenRouter adversary payload are historical and non-dispatchable for this expanded scope.

## Iteration 8 Feedback

The user approved plan revision 6 only for read-only adversarial review. This did not authorize OpenRouter transmission, credential access, prompt generation, implementation, installation, live validation, git mutation, publication, or release.

One independent local Codex adversarial reviewer returned `REVISE` with eight planning gaps: literal installed paths and modes; exact OpenRouter wire-body mapping and digest order; daemon/admin/service-manager lifecycle ownership; distinct status/doctor contracts; controlling-terminal custody; provider credential at-rest lifecycle; original-connection response delivery; and durable replay/cancellation/budget linearization.

Plan revision 7 incorporates those findings. The next gate is explicit post-review approval of revision 7 before replacement prompt generation. Even that approval will not authorize implementation or any live, credential, external-transmission, git-publication, or release action.

## Iteration 9 Feedback

After approving revision 7 for replacement prompt generation, the user stopped that transition by supplying a narrower planning request. No replacement prompts or executable manifest were generated.

The user directed the plan to optimize for the earliest safe milestone that can re-enable Depot's automated OpenRouter dispatch while preserving the current PR15 fail-closed integration contract. The revised planning requirements are:

1. Identify the serial critical path to one authenticated broker-mediated OpenRouter request and prefer a small vertically complete provider slice over broad authority-broker scaffolding.
2. Separate work into the first safe dispatch, broader Pipeline/dm-review rollout, and later hardening/operations.
3. Test whether the first milestone can be limited to independently authenticated local client identity, broker-owned credential and transport, fixed endpoint discovery, exact request/scope/time binding, replay and downgrade rejection, signed content-free results, and fail-closed behavior.
4. Preserve the prohibition on same-UID secrets, caller-provided socket paths, environment authority, API-key presence as authority, self-attested substrate, and worker-controlled transport.
5. Freeze a dependency DAG, exclusive file ownership, concurrency opportunities, and the serial critical path.
6. Move schemas, golden vectors, test doubles, and negative tests ahead of the production daemon so integrations can target a stable contract.
7. Define the smallest Depot adapter seam that replaces `host_authority_unavailable` without redesigning the routing matrix.
8. Deliver Linux first and keep the shared protocol portable so macOS can follow without weakening it.
9. Justify every deferral against authority, credential custody, transport isolation, replay resistance, and fail-closed behavior.
10. Return revised milestones, parallel workstreams, critical-path estimate, milestone acceptance/negative tests, the earliest safe Depot integration point, and explicit human approval gates.

This iteration is planning only. It supersedes the prior prompt-generation approval and does not authorize implementation, prompt generation, installation, enablement, credential access, provider contact, mutation of the PR15 worktree, staging, commit, push, PR, merge, tag, publication, or release.

## Iteration 10 Feedback

The user approved plan revision 8 for replacement prompt and manifest generation only. The generated run is intentionally limited to M0/M1 workstreams A-F: contract/vectors/fake broker, Linux authority core, Depot adapter, broker-owned provider transport, minimal Linux packaging/admin, and offline Linux integration acceptance.

M2 broader Pipeline/dm-review/Workflow Kernel rollout and M3 macOS/Docker/repository-verification/hardening remain campaign deferrals requiring separately approved follow-up manifests. The generated manifest remains `dispatchable: false` and `executionAuthorized: false`. Prompt adversarial review is the next gate; implementation and every live, credential, provider, external-worktree, git-publication, and release action remain unauthorized.

## Iteration 11 Feedback

The user authorized ordinary future Pipeline runs and policy-accepted OpenRouter work for this session without repeated general-permission prompts. Repository hard gates remain controlling: automated OpenRouter work cannot bypass `host_authority_unavailable`, and live root/credential/provider/publication actions remain separately constrained by their concrete safety gates.

Prompt adversarial review round 1 returned `REVISE`. The revision makes M1 one exact FIDO-authorized request rather than a reusable broad run because `SO_PEERCRED` cannot distinguish same-UID code. It adds owned libfido2 1.17.0/internal-UV/terminal-consent implementation, moves scanning in-process, assigns daemon composition to provider transport, serializes Linux packaging after authority and transport, owns an executable fake plus adapter regression tests, and limits M1 to Pipeline assessment artifact delegation. Broader unattended automation now explicitly requires a later distinct-client-principal or equivalent non-transferable capability design.

## Iteration 12 Feedback

Prompt review round 2 found that the documents were frozen but the client/daemon rendezvous was not. Revision 10 freezes one Unix connection from reservation through challenge, terminal display acknowledgement, daemon-owned exact-request FIDO, bounded response, signed terminal result, and cleanup. It adds exact big-endian framing, original-connection binding, anonymous fd-3 release only after result verification, fixed exit codes, a production-ineligible fake exchange, and hostile substitution/flood/disconnect/later-retrieval vectors.

The FIDO challenge now also binds the measured daemon/in-process-scanner build digest and root-owned policy digest. A transaction identifier is non-authoritative and cannot authorize, resume, cancel, or retrieve from another connection. Stale broad-run wording was removed. Execution remains prohibited until the final metadata/residue recheck converges and the reviewed prompts are presented at the Pipeline execution gate.
