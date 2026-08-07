> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Build the Shared Go Protocol Foundation

## Context

This chunk replaces the paused Swift/macOS-only prototype with the shared implementation foundation.
Linux is the primary development platform, but macOS must expose the same operations, protocol, errors, lifecycle semantics, and evidence.
No native security or workflow feature may exist on only one platform.

## Task

Create `native/workflow-authority` as a Go 1.26.5 module.
Implement closed protocol types, canonicalization, bounded framing, redaction, platform interfaces, and thin client/daemon entry points.
Consume the shared Python golden fixture produced by chunk 01.
Create interfaces for FIDO and Docker without implementing real device or engine access yet.
Delete every file under the paused `native/workflow-authority-macos` Swift prototype listed below.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/go.mod` | Create | Module and exact Go 1.26.5 requirement; no third-party Go packages |
| `native/workflow-authority/Dockerfile.test` | Create | Pinned Linux test toolchain image |
| `native/workflow-authority/README.md` | Create | Developer-only build/test overview and parity rules |
| `native/workflow-authority/cmd/workflow-authority/main.go` | Create | Thin client entry point; no business logic |
| `native/workflow-authority/cmd/workflow-authorityd/main.go` | Create | Thin daemon entry point; no business logic |
| `native/workflow-authority/internal/protocol/types.go` | Create | Closed request/response and stable reason-code types |
| `native/workflow-authority/internal/protocol/canonical.go` | Create | Canonical UTF-8 JSON and SHA-256 digest |
| `native/workflow-authority/internal/protocol/framing.go` | Create | Length-bounded stream framing and depth/field enforcement |
| `native/workflow-authority/internal/protocol/redaction.go` | Create | Allowlist diagnostics and secret-value suppression |
| `native/workflow-authority/internal/protocol/protocol_test.go` | Create | Golden, boundary, redaction, and malformed-frame tests |
| `native/workflow-authority/internal/platform/platform.go` | Create | Minimal peer/socket/service abstraction shared by OS adapters |
| `native/workflow-authority/internal/fido/fido.go` | Create | FIDO run-approval and ephemeral signer interfaces |
| `native/workflow-authority/internal/dockerapi/docker.go` | Create | Docker interface and observation structures |
| `native/workflow-authority-macos/Package.swift` | Delete | Superseded Swift package |
| `native/workflow-authority-macos/README.md` | Delete | Superseded Swift documentation |
| `native/workflow-authority-macos/Sources/AuthorityProtocol/AuthorityProtocol.swift` | Delete | Superseded protocol |
| `native/workflow-authority-macos/Sources/AuthorityClientCore/AuthorityClientCore.swift` | Delete | Superseded client core |
| `native/workflow-authority-macos/Sources/AuthorityClient/main.swift` | Delete | Superseded client |
| `native/workflow-authority-macos/Tests/AuthorityProtocolTests/AuthorityProtocolTests.swift` | Delete | Superseded tests |

## Files to Read

| File | Why |
|---|---|
| `tests/fixtures/workflow-authority-v2-golden.json` | Canonical cross-runtime source of truth |
| `plugins/workflow-kernel/skills/workflow-kernel/references/authority-provider-schema.json` | Exact operations and public evidence fields |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Python validation and digest semantics |
| `AGENTS.md` | Depot executable and validation conventions |

## Architecture Rules

Use package boundaries rather than build-tagging the product model.
Only OS syscall adapters may use `_linux.go` or `_darwin.go` later.
Protocol types, status values, error codes, FIDO ceremony inputs, Docker evidence, admin operations, and lifecycle state machines are shared.
The Go core must not import repository-controlled plug-ins or execute arbitrary hooks.
The command packages parse arguments, invoke an internal API, write a bounded public result, and translate stable exit codes.
They do not contain policy.

The run-authority interface generates an ephemeral Ed25519 key, binds its public key into one FIDO-approved closed run scope, retains the private key in daemon memory only, and signs repeated operation/result/cleanup envelopes until expiry or restart.
The interface never serializes, persists, or returns the ephemeral private key.

## Canonicalization Rules

- Import the frozen limits from chunk 01: 1,048,576-byte frame, 4,096-byte UTF-8 string, 256-entry collection, and nesting depth 16; do not choose new values.
- UTF-8 only.
- Closed JSON objects.
- Deterministic object-key ordering.
- No insignificant whitespace.
- No NaN, infinities, floats, duplicate keys, or implicit numeric coercion.
- Explicit integer and string length bounds.
- Explicit collection-size and nesting-depth bounds.
- SHA-256 over exact canonical bytes.
- Domain separation remains part of the FIDO layer, not generic JSON canonicalization.
- Do not copy Go's default map encoding behavior as an undocumented protocol promise.

If exact compatibility with Python requires a custom encoder, implement the smallest deterministic encoder for the closed protocol value set.
Reject values outside that set before encoding.

## Framing Rules

Use pathname Unix `SOCK_STREAM` semantics.
Define a fixed protocol header/version and enforce chunk 01's 1,048,576-byte maximum payload.
Read exactly one request and write exactly one response per connection.
Reject trailing frames, truncation, integer overflow, overlong lengths, excessive depth, duplicate fields, unknown fields, and ancillary descriptors.
Cancellation and deadlines must be carried through context.
Never include request JSON in an error.

## Redaction Rules

Diagnostics use an allowlist of stable reason codes and safe scalar metadata.
Never log or echo:

- PINs
- environment values
- argv beyond a safe operation name
- repository file content
- authenticator data
- signatures
- credential references
- raw Docker responses
- tokens, cookies, connection strings, or key-shaped bytes
- full canonical request bodies

Public signed envelopes are protocol output, not log content.

## Test Doubles

The FIDO interface must support deterministic enrollment and assertion fakes without embedding a real key.
The Docker interface must support deterministic endpoint, engine, image, container, execution, and cleanup observations.
The platform interface must support peer identity, socket ownership, boot identity, clock, cancellation, and service status fakes.
No fake may be automatically selected in a production build.

## Client Entry-Point Contract

The `workflow-authority` binary is a narrow adapter.
It accepts one operation from the fixed shared vocabulary.
It reads one bounded public request from isolated stdin or the fixed IPC layer selected internally.
It never accepts a receipt key.
It never accepts a PIN.
It never accepts a caller-selected executable.
It never accepts a caller-selected socket in production mode.
It never shells out.
It never reads repository configuration to find the daemon.
It writes one bounded public JSON response on stdout.
Human diagnostics go to stderr as closed safe reason codes.
JSON mode never interleaves prose with protocol output.
Cancellation and deadline are propagated through `context.Context`.
Exit codes are stable and defined from shared result categories.

Define result categories for at least:

- success
- denied
- cancelled
- unavailable
- invalid request
- protocol mismatch
- peer rejected
- stale or replayed request
- substrate non-authoritative
- internal failure

Do not map multiple security-distinct failures to success-like exit zero.
Do not expose internal Go errors as protocol strings.

## Daemon Entry-Point Contract

The `workflow-authorityd` binary is also a narrow adapter.
It loads only fixed installed configuration through an injected platform layer.
It does not read `.env` files.
It does not scan the repository.
It does not accept plug-ins.
It does not accept arbitrary listen addresses.
It does not daemonize itself when service managers own lifecycle.
It handles shutdown through context cancellation and explicit ordering.
It rejects positional arguments not part of the closed service surface.
It disables or requests disabling core dumps through the later platform implementation seam.

Shutdown order must be expressible as:

1. stop accepting new IPC requests
2. cancel queued authorization work
3. cancel active operations
4. allow bounded cleanup/recovery hooks
5. flush crash-consistent state
6. close the socket/listener
7. exit with a stable reason

This chunk defines the interfaces and orchestration skeleton only.
Real FIDO, Docker, persistence, and service-manager behavior arrives later.

## Platform Interface Design

Keep the shared interface small enough that both operating systems can implement it without semantic branching.
It may expose:

- fixed runtime/state/install roots
- boot identity
- peer identity retrieval
- socket ownership and no-follow operations
- clock and randomness dependencies
- core-dump policy request
- service status abstraction
- context-aware shutdown signal

It must not expose:

- XPC connections
- Secure Enclave or Keychain types
- LocalAuthentication
- systemd-specific unit objects
- launchd-specific dictionary objects
- Docker context lookup
- arbitrary subprocess execution
- repository file reads

Platform-specific structs stay inside adapter packages.
The protocol never serializes an OS-specific peer credential structure.
Normalize only the minimum shared peer facts needed by policy.

## Protocol Versioning

Define one explicit protocol version for the new companion.
Requests and responses carry schema version and artifact role.
Unknown future versions fail closed.
Do not accept missing version as v1.
Do not negotiate down to the HMAC protocol.
Compatibility is an explicit fixed range checked by both client and daemon.
Version mismatch returns a closed public error with no request echo.

## Survivor Audit

After deleting the Swift prototype, search the worktree for:

- `workflow-authority-macos`
- `AuthorityProtocol.swift`
- `AuthorityClientCore`
- `Package.swift` references tied to this broker
- XPC service identifiers
- Secure Enclave authority instructions
- Swift-specific build validation

Any remaining reference must either be historical planning evidence under `plans/` or be removed by an owned file in this chunk.
The six listed paths are the verified current inventory; do not delete a surprise unrelated file silently, and report it as an ownership conflict.
Do not edit unrelated historical artifacts outside owned paths.
Report any survivor requiring a later documentation chunk as `Noted, not fixed` with its exact path.

Search new Go definitions for zero callers after implementation.
Inline or remove unused helpers inside owned files.
Do not retain abstraction scaffolding that only mirrors the deleted Swift design.

## Integration Test Matrix

The protocol test file should exercise client/daemon core interaction in memory:

- minimal valid request round trip
- Unicode golden request round trip
- maximum-boundary request round trip
- operation mismatch
- protocol version mismatch
- unknown request field
- unknown response field
- duplicate JSON key
- invalid UTF-8
- truncated frame
- overlong frame
- extra trailing frame
- cancellation before write
- cancellation during read
- responder unavailable
- safe denied response
- safe internal failure response
- forbidden diagnostic value redaction

These tests use fakes and in-memory connections only.
They do not open a production socket or device.

## Build and Portability Evidence

Before writing `Dockerfile.test`, verify the pinned digest with a read-only registry query and confirm the resolved image reports `go1.26.5`.
The planning pass observed multi-architecture digest `sha256:4ee9ffa999b4583ce281939cdff828763083610292f252279a0cee77473bd9a7`; do not trust that observation if the registry has drifted.
On mismatch, stop, record the observed digest under `NOT-COVERED`, and surface the drift through the Ambiguity Protocol rather than silently substituting another digest.

Use build constraints only for files that truly require OS or cgo behavior.
The shared foundation must build with `CGO_ENABLED=0` on Linux and macOS targets because real libfido2 is not implemented yet.
Chunk 03 may introduce cgo-specific builds without changing protocol semantics.
Check at least:

- native Linux build/test under Go 1.26.5
- `GOOS=darwin` compile of shared packages under Go 1.26.5 where cgo-free
- `GOOS=linux` compile of shared packages under Go 1.26.5
- no platform build produces a different operation list or JSON fixture

Cross-compilation is portability evidence only.
It is not native peer/service acceptance evidence.

`Dockerfile.test` must use the official multi-platform image exactly as:

`docker.io/library/golang:1.26.5-trixie@sha256:4ee9ffa999b4583ce281939cdff828763083610292f252279a0cee77473bd9a7`

The validator must reject tag-only, version drift, or digest drift.
The pinned image is used for Linux unit, race, vet, and cross-compilation lanes; it is not a production runtime image.

## Companion Skills

Load:

- `assembly:golang-patterns` for Go package, context, error, and testing patterns.
- `developer-essentials:auth-implementation-patterns` for protocol and authority boundaries.
- `developer-essentials:error-handling-patterns` for stable failure taxonomy and redaction.

## Acceptance Criteria

- [ ] AC-01 `go.mod` declares the exact approved Go 1.26.5 toolchain policy and introduces no third-party Go module dependency.
- [ ] AC-01A `Dockerfile.test` pins the exact approved Go 1.26.5-trixie multi-architecture digest and later validation uses only that definition.
- [ ] AC-02 Both binaries are thin; policy, canonicalization, framing, and redaction live in importable internal packages.
- [ ] AC-03 The exact 16 operation values match chunk 01 and no Swift-era aliases remain.
- [ ] AC-04 Go consumes all three shared golden vectors directly and matches Python canonical UTF-8 bytes and SHA-256 digests.
- [ ] AC-05 Unicode, maximum boundaries, duplicate fields, unknown fields, invalid UTF-8, floats, excessive nesting, oversized frames, truncation, and trailing data have negative tests.
- [ ] AC-06 One connection accepts one request and returns one bounded public response; it cannot stream arbitrary data or request raw key output.
- [ ] AC-07 Error and logging tests prove forbidden secret-shaped fields never appear on stdout, stderr, formatted errors, or injected log sinks.
- [ ] AC-08 FIDO, Docker, clock, boot identity, peer identity, filesystem, and cancellation interfaces have deterministic fakes.
- [ ] AC-08A Interface-contract tests against fakes prove the ephemeral run private key is never serialized or returned, is invalidated by restart/expiry, and signs only operations allowed by the FIDO-bound run scope; the production security proof remains chunk 03 AC-17A.
- [ ] AC-09 Production command construction cannot select a fake backend through argv or environment.
- [ ] AC-10 The shared platform interface contains only unavoidable OS primitives; no macOS-only product operation appears in an interface.
- [ ] AC-11 Linux and darwin compile-time assertions can implement the same platform interface without conditional protocol fields.
- [ ] AC-12 Client and daemon ignore authority-related environment overrides and do not resolve executables or sockets through `PATH`.
- [ ] AC-13 All six listed Swift files are deleted, `find native/workflow-authority-macos -type f` returns no survivors, and no Swift/XPC/Secure Enclave production instructions remain in the new module.
- [ ] AC-14 The module README states Linux-primary parity, hardware fail-closed behavior, and the prohibition on raw receipt-key output without claiming installation is complete.
- [ ] AC-15 Pinned Go 1.26.5 container tests run `go test ./...`; if the image/toolchain is unavailable, record the exact gap rather than using another version.
- [ ] AC-16 The Go race suite is run under the pinned toolchain where supported and any unsupported host/toolchain condition is explicit.
- [ ] AC-17 `go vet ./...` or the repository-approved equivalent passes under the pinned container; no bare host-Go proof is substituted for a missing pinned lane.
- [ ] AC-18 `git diff --check` passes and only owned files change.
- [ ] AC-19 Go constants match chunk 01's frozen frame/string/collection/depth values; exact-limit frames pass and max-plus-one frames fail.

## Behavioral Contract Inputs

- `REQ-003`: identical Linux/macOS product contract.
- `REQ-004`: authority private key is structurally absent from the host protocol.
- `REQ-005`: no secret output channels.
- `REQ-008`: shared adversarial fixtures.
- `CHK-004`: Python/Go canonical vector equality.
- `CHK-005`: frame and diagnostic negative matrix.
- `CHK-006`: Swift production surface removed.

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

- Only modify the listed files.
- Do not implement real libfido2, service-manager, peer-credential, Docker Engine, installer, or Workflow Kernel integration in this chunk.
- Do not keep a Swift compatibility target.
- Do not introduce a pure-Go CTAP stack.
- Do not add a raw-key, general-signing, shell-execution, plugin-loading, or arbitrary-socket API.
- Do not include secrets or authentic device artifacts in source or fixtures.
- Do not stage, commit, push, install, enroll, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

libfido2 is the approved shared FIDO implementation for Linux and macOS.
The thin cgo adapter arrives in the next chunk.
This foundation makes platform parity testable by putting all semantic decisions above the OS adapter boundary.
