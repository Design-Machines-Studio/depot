> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Implement FIDO2 Authority and Cross-Platform IPC

## Context

The shared Go protocol exists after chunk 02.
This chunk implements the actual host authority boundary used identically by Linux and macOS.
The private credential remains in a FIDO2 authenticator; one public assertion authorizes a closed run and binds an ephemeral in-memory run-signing key.
Peer credentials admit a caller but never substitute for user presence or user verification.

## Task

Implement a thin cgo adapter pinned to libfido2 1.17.0.
Implement verified credential enrollment, rotation, revocation, loss recovery, and one assertion ceremony per closed run.
Display the exact scope in the operator-initiated client terminal before assertion.
Generate and retain an ephemeral Ed25519 run key in daemon memory, then sign repeated closed operation/result/cleanup envelopes without additional touches.
Implement crash-consistent replay state, bounded prompt queues, rate limits, cancellation, and one-request Unix-socket IPC.
Add Linux `SO_PEERCRED` and macOS `getpeereid`/peer-PID adapters behind the shared platform interface.
Keep every user-facing operation, status, error, and test contract identical across operating systems.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/internal/fido/libfido2.go` | Create | cgo CTAP2 device/enrollment/assertion adapter |
| `native/workflow-authority/internal/fido/libfido2_stub.go` | Create | Explicit unavailable build, never a software-key fallback |
| `native/workflow-authority/internal/fido/fake.go` | Create | Deterministic test backend only |
| `native/workflow-authority/internal/fido/fido_test.go` | Create | Ceremony, verification, cancellation, and redaction tests |
| `native/workflow-authority/internal/state/replay.go` | Create | Atomic nonce/session/sequence/consumption ledger |
| `native/workflow-authority/internal/state/replay_test.go` | Create | Crash/replay/idempotency/time tests |
| `native/workflow-authority/internal/ipc/client.go` | Create | Fixed-socket run-scoped client |
| `native/workflow-authority/internal/ipc/server.go` | Create | Bounded server, admission, queue, deadline, response |
| `native/workflow-authority/internal/ipc/socket.go` | Create | Root-owned no-follow pathname socket policy |
| `native/workflow-authority/internal/ipc/peer_linux.go` | Create | `SO_PEERCRED` implementation |
| `native/workflow-authority/internal/ipc/peer_darwin.go` | Create | `getpeereid` and available peer-PID evidence |
| `native/workflow-authority/internal/ipc/ipc_test.go` | Create | Shared and adapter-negative tests |
| `native/workflow-authority/internal/authority/service.go` | Create | Policy orchestration and closed authority result |
| `native/workflow-authority/internal/authority/service_test.go` | Create | End-to-end fake authority tests |

## Files to Read

| File | Why |
|---|---|
| `native/workflow-authority/internal/protocol/types.go` | Exact operation and message types |
| `native/workflow-authority/internal/protocol/framing.go` | One-operation framing contract |
| `native/workflow-authority/internal/platform/platform.go` | Required adapter interface |
| `tests/fixtures/workflow-authority-v2-golden.json` | Canonical request digests |
| `/usr/include/fido.h` or the resolved pinned libfido2 headers | Verify exact C API names and result semantics |

## libfido2 Boundary

Require libfido2 exactly 1.17.0 for the initial production artifact and preflight; document its OpenSSL 3/libcbor/zlib requirements.
Resolve current API behavior from official Yubico documentation and installed headers.
Build/package preflight requires `pkg-config --modversion libfido2` to report exactly `1.17.0`, verifies the linked shared-library dependency and required symbols, and records the package identity in private install state.
libfido2 exposes no documented public runtime version query; daemon startup therefore performs a required-symbol and minimal allocation/self-test and reports a version-integrity gap if the package identity cannot be established rather than inventing a runtime version check.
Use device manifest/discovery APIs with deterministic selection policy.
Require CTAP2 and ES256.
Enrollment uses a fixed domain-separated RP ID.
Use a non-discoverable credential with an explicit allow-list.
Require user presence and authenticator-internal user verification.
Reject authenticators that require a host-entered PIN; there is no PIN input or IPC path.
Verify enrollment output before persisting public metadata.
Persist only the public stable credential reference, the root-only raw allow-list credential ID required to request assertions for a non-discoverable credential, the enrolled public key, algorithm, generation, policy, and revocation data.
The raw credential ID never appears in signed evidence, logs, status, argv, environment, or fixtures.
For ES256, read the libfido2-normalized 64-byte `x || y` value through `fido_cred_pubkey_ptr`/`fido_cred_pubkey_len`, require the expected credential type and exact length, and persist canonical 65-byte SEC1 uncompressed form (`0x04 || x || y`).
Do not parse authenticator-controlled COSE/CBOR in Go; malformed type/length/point-on-curve enrollment output fails before persistence, and the retained SEC1 point is verifiable with the Go standard library.
Never persist or return PINs, private keys, assertion scratch buffers, or raw device diagnostics.
Zero sensitive mutable buffers where the API permits.

The unavailable build returns a stable `fido_unavailable` status.
It does not generate a software key.
It does not downgrade UV.
It does not call an external CLI.

## Run Authorization Ceremony

The daemon performs all libfido2 device I/O.
The client's only roles are rendering the canonical scope to its controlling terminal, collecting explicit operator confirmation, and transporting bounded IPC frames; the client never opens a FIDO device.

For every closed run:

1. Validate the closed request and recompute canonical bytes.
2. Generate a fresh ephemeral Ed25519 run key in daemon memory.
3. Bind its public key, exact repository/run/profile/base/candidate/boundary/allowed-operation scope, boot identity, session, issuance, and expiry.
4. Render that exact canonical scope and expiry to the operator-initiated client's controlling terminal and require explicit confirmation.
5. Allocate a server-generated 256-bit nonce and compute `SHA-256("workflow-kernel-authority-v2\0" || canonical_run_authorization)`.
6. Request one assertion restricted to the enrolled credential and RP.
7. Require signed UP and internal UV bits.
8. Verify the signature, client-data hash, and active public-key generation.
9. Atomically consume the challenge and activate the in-memory run signer.
10. Return the public run-authorization envelope and non-secret run handle.

This implements chunk 01's challenge flow: the first cadence request receives `authorization_required`, confirmation is read only from the controlling terminal, one resubmission performs the assertion, and absence of a terminal returns `authority_unavailable`.

Each later operation uses a fresh nonce and strict sequence, checks the allowed run scope, and signs the canonical operation/result/cleanup envelope with the ephemeral key.
The private run key never crosses IPC, never persists, and is zeroed/discarded on expiry, cancellation, revocation, daemon shutdown, or restart.
The non-secret handle cannot broaden scope and is useless after signer loss.

Cancellation, timeout, denial, and device removal consume the challenge.
No FIDO assertion is reused for another run.
No run-wide secret or bearer is exported.
The ephemeral key is a bounded run signer, not a stable host key.

The terminal is not a cryptographically trusted display.
The supported guarantee is that candidate/repository code and unattended agents cannot mint a run without operator confirmation plus internal UV.
Fully compromised desktop/session spoofing is an accepted documented residual risk.

## Replay and Idempotency

Use root-owned, no-follow, crash-consistent state.
Persist a boot marker, daemon-instance session UUID, next sequence, outstanding challenges, consumed challenges, committed result digest, and revocation generation.
State transitions are monotonic.
An exact duplicate committed request with the same idempotency key may return the same public result.
Reusing an idempotency key with different canonical content fails.
Future, stale, reordered, replayed, cross-session, and cross-boot requests fail.
Authenticator counters are recorded as optional clone evidence but never become the sole replay mechanism.
Use atomic replace plus fsync policy appropriate to security state.
Failure injection tests must cover every persistence boundary.
Persist only public run authorization and sequence/consumption metadata; never persist the ephemeral private key.
After daemon restart, historical envelopes remain verifiable but new operations require a new FIDO-approved run.

## Enrollment, Rotation, and Loss

First enrollment is a root-console administrative action plus authenticator credential-creation UP/internal-UV; it does not require an existing credential.
Rotation authorizes enrollment of a new generation, verifies it, activates it, then revokes the prior generation for issuance while retaining its public verification record.
Lost-authenticator recovery is an explicit root-console flow that revokes the missing generation and enrolls a replacement; it never creates a software FIDO credential or recovers a private key.
Default uninstall preserves public verification/revocation state.
Explicit purge uses FIDO when available and permits the documented root-console lost-key recovery path.

## IPC Admission

Use a root-owned pathname socket directory.
Reject symlinks and parent-directory swaps with descriptor-relative/no-follow checks.
Verify owner and mode before bind/connect.
Reject caller-supplied socket paths in production.
Linux reads kernel-provided `SO_PEERCRED`.
macOS reads kernel-provided effective UID/GID using `getpeereid` and peer PID where supported.
The client verifies it reached the fixed service identity/path.
The server rejects unauthorized UID/GID/session policy before parsing sensitive request content.
Enforce chunk 01's operation-admission matrix before mutation: UID-0 root-console peers alone may invoke key or endpoint lifecycle operations; cadence operations require the exact active run permission; read-only verification/status/doctor cannot mutate or issue authority.
Add negative tests for each lifecycle operation from a same-UID non-root repository peer and prove rejection occurs before handler dispatch.
Reject ancillary file descriptors.
Ignore `HOST_AUTHORITY_BROKER`, provider, FIDO, socket, and executable environment overrides.

## Concurrency and Prompt Flooding

Serialize authenticator access.
Bound the global queue.
Bound requests per peer and repository.
Use per-run locks for state transitions.
Do not hold global locks while waiting for user presence.
Cancellation propagates through queued, active FIDO I/O, persistence, and response stages.
Every terminal path releases locks and consumes or invalidates its challenge.
Errors remain bounded and secret-free.

## Companion Skills

Load:

- `assembly:golang-patterns` for contexts, concurrency, build tags, and test seams.
- `developer-essentials:auth-implementation-patterns` for FIDO, replay, and revocation boundaries.
- `developer-essentials:error-handling-patterns` for fail-closed error translation.
- `developer-essentials:e2e-testing-patterns` for IPC and cancellation scenarios.

## Acceptance Criteria

- [ ] AC-01 Linux and macOS compile the same protocol/authority packages with only peer/system adapters build-tagged.
- [ ] AC-02 The cgo adapter uses verified libfido2 1.17.0 APIs and production preflight rejects other versions for this release.
- [ ] AC-03 Enrollment requires CTAP2, ES256, fixed RP, explicit credential, UP, authenticator-internal UV, and verified output before public metadata persistence; host-PIN authenticators fail unavailable.
- [ ] AC-04 The unavailable build fails with `fido_unavailable` and contains no software-key or CLI fallback.
- [ ] AC-05 Each run creates one fresh domain-separated FIDO authorization binding exact scope and ephemeral Ed25519 public key; each later operation creates a fresh nonce/sequence and ephemeral signature within that scope.
- [ ] AC-06 Missing UP/UV, wrong RP, wrong credential, invalid signature, wrong client hash, revoked generation, and unsupported algorithm fail closed.
- [ ] AC-07 PINs, authenticator data, signatures, request bodies, raw libfido2 diagnostics, and real or authenticator-derived credential references are absent from logs, errors, argv, environment, and fixtures; synthetic placeholder public references are permitted in fixtures.
- [ ] AC-07A No host PIN input or transport path exists; PIN-requiring authenticators fail before authority activation.
- [ ] AC-07B Terminal consent displays exact operation allowance, repository scope, run, profile, base, candidate, boundary, and expiry derived from the same canonical bytes signed by FIDO.
- [ ] AC-07C Tests prove unattended direct invocation cannot activate a run without explicit terminal confirmation and internal UV; desktop display spoofing is documented outside scope.
- [ ] AC-08 Replay state rejects stale/future/reordered/replayed/cross-session/cross-boot challenges and consumes cancelled/time-out/device-removed challenges.
- [ ] AC-09 Idempotency returns only an exact previously committed public result; same key with altered content fails.
- [ ] AC-10 Crash/failure injection around write, fsync, rename, and response cannot resurrect or double-consume authority.
- [ ] AC-11 Linux peer tests verify `SO_PEERCRED`; macOS tests verify `getpeereid` semantics and available PID evidence without changing admission outcomes.
- [ ] AC-12 Socket symlinks, parent swaps, wrong owner/mode, replacement after inspection, arbitrary path, and ancillary descriptors are rejected.
- [ ] AC-13 Client and server mutually enforce fixed identity/path and ignore authority environment overrides.
- [ ] AC-14 Authenticator requests are serialized, queues/rates are bounded, prompt floods do not starve cancellation, and locks are released on every path.
- [ ] AC-15 Cancellation works before queue admission, while queued, before touch, during FIDO I/O, during persistence, and before response.
- [ ] AC-16 The same stable reason codes and exit-status mapping are asserted for Linux and macOS adapters.
- [ ] AC-17 Tests prove a public envelope contains no receipt key, private key, PIN, reusable bearer, or general-signing capability.
- [ ] AC-17A Tests prove the ephemeral private key is memory-only, cannot sign outside allowed scope, dies on expiry/restart/revocation, and leaves historical public verification intact.
- [ ] AC-17B Bootstrap enrollment, two-generation rotation, cancellation, authenticator loss, root-console recovery, and purge have parity state-machine tests.
- [ ] AC-18 Pinned Go 1.26.5 container tests and race tests pass where supported; macOS compilation/adapter tests use the same Go version or report the exact unavailable lane.
- [ ] AC-19 `git diff --check` passes and only owned files change.
- [ ] AC-20 Tests prove the root-only raw allow-list credential ID is used for assertion requests but absent from every signed envelope, log/status surface, argv, environment, and fixture.
- [ ] AC-21 Tests prove the client never opens a FIDO device and the stored raw P-256 public point is verifiable with the Go standard library alone.
- [ ] AC-22 Fake-IPC tests exercise `authorization_required` → controlling-terminal confirmation → one FIDO assertion → activation; missing terminal returns `authority_unavailable`, forged confirmation and a second assertion fail.
- [ ] AC-23 Non-root peers cannot invoke key or endpoint lifecycle handlers, while cadence and read-only operations follow the frozen admission matrix exactly.
- [ ] AC-24 Enrollment rejects wrong public-key type, wrong length, and off-curve points; ES256 public-key persistence uses the documented libfido2 64-byte output to SEC1 conversion without a Go CBOR parser.
- [ ] AC-25 Build/package preflight proves libfido2 1.17.0 via pkg-config and linked symbols; startup self-test is explicit about the absence of a public runtime version API.

## Behavioral Contract Inputs

- `REQ-003`: same security and product semantics on Linux and macOS.
- `REQ-004`: FIDO user presence/verification and non-exportability.
- `REQ-005`: no secret exfiltration channels.
- `REQ-007`: repeated fresh authority operations.
- `REQ-008`: unauthorized, replay, concurrency, cancellation, and path attacks.
- `CHK-007`: FIDO negative ceremony matrix.
- `CHK-008`: IPC peer and filesystem attack matrix.
- `CHK-009`: replay crash-consistency matrix.

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
- Do not implement Docker substrate, packaging, Workflow Kernel wiring, or docs here.
- Do not weaken UP or UV based on device availability.
- Do not accept caller assertions as verified without libfido2/public-key verification.
- Do not expose a host-entered PIN through argv, environment, logs, fixtures, or response data.
- Do not add a raw-key, general signing, long-lived bearer, plugin, or arbitrary-command endpoint.
- Do not stage, commit, push, install, enroll a real device, release, tag, publish, or modify external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

libfido2 supports Linux and macOS device discovery, credential creation, assertion retrieval, UP/UV enforcement, verification, cancellation, and timeouts.
Ordinary security keys do not display the canonical request, so trusted broker presentation remains a documented residual risk.
Peer credentials identify the kernel-reported process account, not human intent; FIDO remains mandatory.
