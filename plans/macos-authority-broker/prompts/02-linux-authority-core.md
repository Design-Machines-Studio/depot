# Chunk: Implement Linux authority core and replay-safe IPC

## Context

This is workstream B on the M1 serial critical path. It consumes the frozen M0 schemas and vectors and builds the Linux authority foundation, including the production libfido2 path, without provider credentials or network transport.

The supported boundary protects against repository workers and unattended same-UID agents, not compromised root. Peer credentials establish local eligibility but never distinguish same-UID code. M1 therefore requires FIDO UP+UV over the exact single provider request; broad reusable run authority is deferred.

## Task

Create a Go 1.26.5 module. Implement bounded Unix framing, strict protocol decoding, Linux `SO_PEERCRED`, enrolled-operator eligibility, a pinned libfido2 1.17.0 cgo adapter, internal-UV-only enrollment/assertion verification, exact-request terminal consent, memory-only Ed25519 result signing, and a crash-consistent single-use WAL state machine.

The operator-initiated client renders the exact repository/run/lane/candidate/model/policy/final-body digest/expiry scope on its controlling terminal before asking for UP+UV. Authenticators requiring a host PIN are `fido_unavailable`; no host PIN path exists. Implement states `reserved → fido_authorized_exact_request → send_started → terminal → cleanup`. This chunk exposes interfaces for provider transport but does not load a provider key, scan content, compose the daemon, or contact a network.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/go.mod` | Create | Go 1.26.5 module, no third-party Go dependencies |
| `native/workflow-authority/internal/protocol/protocol.go` | Create | Bounded framing and schema-aligned types |
| `native/workflow-authority/internal/authority/run.go` | Create | FIDO run, peer identity, signer, WAL/replay state machine |
| `native/workflow-authority/internal/authority/run_test.go` | Create | Fake FIDO/clock/boot/fsync plus race and crash tests |
| `native/workflow-authority/internal/authority/fido_libfido2.go` | Create | Linux cgo adapter pinned to libfido2 1.17.0 |
| `native/workflow-authority/internal/authority/fido_stub.go` | Create | Explicit unavailable build for unsupported/test environments |
| `native/workflow-authority/internal/authority/fido_test.go` | Create | Enrollment, assertion, internal-UV, exact-request and ABI tests |
| `native/workflow-authority/internal/authority/consent.go` | Create | Controlling-terminal exact-scope rendering and confirmation |

## Files to Read (for context)

| File | Why |
|---|---|
| `tests/test_provider_dispatch_contract.py` | Frozen M0 vectors and negative cases |
| `native/workflow-authority-macos/Sources/AuthorityProtocol/AuthorityProtocol.swift` | Historical prototype only; harvest no platform-only behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/authority-provider-schema.json` | Existing domain separation and envelope constraints |

## Patterns to Follow

- Production socket is compile-time/platform-selected: `/run/design-machines/workflow-authority/authority.sock`.
- Test roots are injected through Go constructors, never production argv or environment.
- Treat `SO_PEERCRED` UID/PID plus the operator allowlist as eligibility only; authorize exactly one final request through same-connection FIDO UP+UV, never a reusable run.
- Bind each M1 FIDO assertion to the exact final body digest plus repository/run/lane/candidate/model/policy/budget/expiry scope displayed in the operator terminal.
- Keep the private result signer only in daemon memory. Restart, expiry, revoke, body mutation, or scope expansion requires fresh FIDO approval.
- Persist replay/tombstone state descriptor-relatively with no-follow, owner/type/mode/link checks and fsync of file plus parent directory.
- No automatic retry after `send_started`; an ambiguous restart becomes `outcome_unknown`.

## Companion Skills

- `assembly:golang-patterns` -- idiomatic Go package boundaries, contexts, and race-safe tests
- `developer-essentials:auth-implementation-patterns` -- multi-factor local authorization and replay design
- `developer-essentials:error-handling-patterns` -- stable fail-closed error taxonomy

## Acceptance Criteria

- [ ] `REQ-M1-01`: production daemon ignores/rejects environment and argv attempts to override socket, policy, state, FIDO RP, boot/session, or trust material.
- [ ] `REQ-M1-02`: `SO_PEERCRED` is eligibility evidence only; every M1 send requires a fresh internal-UV FIDO assertion over the exact single request, so another same-UID process cannot substitute or race a different body.
- [ ] `REQ-M1-03`: FIDO approval binds the final body digest, ephemeral result public key, repository/run/lane/candidate/model/policy/budget/expiry scope; any change requires fresh approval.
- [ ] `REQ-M1-04`: private run signing material never appears in files, public memory dumps, logs, argv, environment, child processes, protocol responses, tests, or fixtures.
- [ ] `REQ-M1-05`: nonce/sequence/boot/session replay and duplicate concurrent reservation are atomically rejected.
- [ ] `REQ-M1-06`: WAL transitions and file/parent fsync points are explicit; crash injection before and after every point yields one deterministic resumable/rejected/unknown state.
- [ ] `REQ-M1-07`: cancellation before `send_started` prevents send; after `send_started` it cannot authorize retry or claim unsent; cancel/send has one linearization winner.
- [ ] `REQ-M1-08`: frames over 1 MiB, depth over 16, malformed/duplicate/unknown fields, ancillary descriptors, and extra/truncated frames fail before state mutation.
- [ ] `REQ-M1-09`: run budgets cap operations, bytes, expiry, and concurrency and are reconciled for every terminal/unknown/cleanup outcome.
- [ ] `REQ-M1-10`: Go builds require or explicitly report unavailable libfido2 1.17.0; ABI/version mismatch and stub builds can never report production readiness.
- [ ] `REQ-M1-11`: enrollment stores only public credential metadata, requires CTAP2 ES256 plus internal UV, and defines first enrollment, rotation, revoke, and lost-authenticator recovery without a software-secret fallback.
- [ ] `REQ-M1-12`: exact scope is rendered on a stable controlling terminal before FIDO; redirected/changed/missing TTY and host-PIN authenticators fail before authorization.
- [ ] `REQ-M1-13`: `go test -race ./...` passes using fake and ABI-shim FIDO, clock, boot ID, filesystem, and transport interfaces; real hardware execution remains an explicit enablement gate.
- [ ] Stable diagnostics disclose no prompt, response, credential, raw assertion, signature private material, or untrusted path.
- [ ] The Swift/XPC prototype is not extended, installed, or treated as parity evidence.

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
- No provider credential, HTTP client, Docker, macOS service, plugin integration, or live installation.
- Pin libfido2 1.17.0 behind an injectable cgo adapter; do not invent a software-secret or host-PIN fallback.
- Production config must fail closed at boot. Missing/invalid config never warns and continues.
- Shutdown ordering is explicit: stop accepting IPC, cancel unsent work, resolve/tombstone in-flight states, fsync, zeroize signer, close state.
- Do not touch the read-only PR15 worktree or unrelated dirty files.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.

## Research Context

Same-UID socket access is not independent authority. M1 therefore combines OS peer eligibility with one operator-present FIDO UP+UV assertion over one exact request and a memory-only result signer, while documenting fully compromised root as out of scope. Unattended reuse across dynamically generated requests is not authorized by this chunk and remains a later principal-boundary problem.

## Exact FIDO Challenge Contract

Domain-separate the challenge as `workflow-provider-dispatch-v1\0` plus canonical authorization bytes. Those bytes include the final OpenRouter body digest, mapping version, method/origin/path, model order, repository identity, run, lane, candidate, workload, daemon/scanner build digest, policy digest, connection nonce digest, nonce, sequence, boot/session, issued-at, expiry, byte budgets, and ephemeral result public key.

Verify RP ID hash, enrolled credential generation, ES256 algorithm, signed UP and UV flags, signature, counter evidence when non-zero, and exact challenge digest. The authenticator counter is clone evidence only; WAL nonce/sequence state remains replay authority.

## Required Negative Matrix

- Missing UP or UV; host PIN requested; wrong RP ID; wrong credential or generation.
- Altered final body, model order, origin, policy digest, repository, lane, candidate, expiry, or signer public key after assertion.
- Same-UID competing process submits a different request before or after approval.
- Consent acknowledgement arrives from a different connection, peer, transaction, challenge digest, or after the original connection closes.
- Exact duplicate arrives concurrently, after send start, after terminal, and after restart.
- TTY disappears or changes between display and assertion; redirected standard input cannot substitute.
- Enrollment bootstrap, rotation overlap, revoked generation, lost authenticator, and recovery operator cases.
- libfido2 absent, wrong ABI, stub build, cancellation, device removal, timeout, and malformed authenticator data.

## Production Readiness Receipt

Report the compiled libfido2 version/ABI, whether production or stub adapter was selected, enrolled public credential generation, internal-UV capability, exact-request challenge vector digest, fake-versus-native tests executed, and every native hardware gap. No raw credential ID, assertion, prompt, response, or private key appears in the receipt.

## Implementation Sequence

1. Freeze Go protocol structs against the M0 canonical vectors before adding device code.
2. Implement bounded framing and closed decoding with pure unit tests.
3. Implement WAL reservation and replay transitions with fake clock/boot/fsync hooks.
4. Add the FIDO interface and fake implementation; prove exact challenge construction first.
5. Add the libfido2 1.17.0 cgo adapter without changing the interface or canonical bytes.
6. Add the explicit stub adapter whose readiness method always returns unavailable.
7. Implement enrollment generation records and public-key verification.
8. Implement controlling-terminal scope rendering and stability checks.
9. Join FIDO authorization to the reserved exact request and ephemeral result signer.
10. Run race, cancellation, crash-boundary, ABI and secret-surface tests.

## State Transition Table

| From | Input | To | Durable action |
|---|---|---|---|
| absent | valid exact request | reserved | persist nonce, sequence, full scope and final-body digest; fsync |
| reserved | valid matching UP+UV assertion | fido_authorized_exact_request | persist assertion digest and signer public key; fsync |
| reserved | decline/timeout/cancel | cleanup | consume nonce; record safe rejection; fsync |
| fido_authorized_exact_request | transport begins | send_started | persist irreversible send marker; fsync before network write |
| send_started | terminal provider result | terminal | persist digests/outcome/budget; fsync |
| send_started | restart/ambiguous failure | terminal | persist or reconstruct `outcome_unknown`; never retry |
| terminal | cleanup complete | cleanup | persist cleanup/tombstone; fsync file and parent |

No transition accepts a different body or scope under an existing nonce. A duplicate matching request observes the current state but never acquires a second send right.

## Enrollment and Recovery Contract

First enrollment is a root/operator ceremony on a controlling terminal and requires a new CTAP2 ES256 credential with internal UV. Store only stable public credential reference, public key, algorithm, generation, RP ID, enrollment time, status and revocation metadata. Raw credential IDs remain root-private.

Rotation creates and verifies the new generation before activating it, retains old public verification metadata, and prevents the old generation from authorizing new requests after cutover. Lost-authenticator recovery requires root plus a separately documented local recovery ceremony; it never accepts repository input or a software shared secret. Purge is not implemented in M1.

## Exit-Code Contract

- `0`: verified operation/result.
- `2`: malformed or non-canonical input.
- `3`: authorization denied, expired, replayed, or scope mismatch.
- `4`: libfido2/device/internal-UV unavailable.
- `5`: durable-state or parity gap.
- `6`: conflict, cancellation, or ambiguous terminal state.

Every code maps to a fixed content-free diagnostic identifier. Arbitrary cgo, OS, filesystem, or authenticator text is redacted before it crosses IPC.

## Required Handoff Evidence

- Include the run-state transition table and its fsync linearization points.
- Report the fake-FIDO cases separately from unavailable real-hardware evidence.
- List every exported interface consumed by provider transport and Linux packaging.
- Include race-test results and every injected crash point exercised.
- State whether any private-key or assertion-shaped sentinel survived the secret scan.
