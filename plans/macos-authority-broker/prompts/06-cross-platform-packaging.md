> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Add Parity Packaging and Operator Lifecycle

## Context

This chunk runs in parallel with Workflow Kernel integration after the Go authority and Docker substrate exist.
It packages the same broker operations for Linux and macOS without introducing platform-only features.
Real apply adapters are implemented and tested against temporary/fake roots, but never invoked against live root/service state in this task.

## Task

Implement the shared admin command dispatcher, real injectable filesystem/service apply adapters, and deterministic staged lifecycle operations.
Add systemd socket/service resources for Linux and a launchd socket-activation plist for macOS.
Expose identical commands, status fields, reason codes, safety checks, state retention, rollback, and uninstall semantics.
Keep service-manager mechanics behind platform adapters.
Leave the consolidated hostile matrix to chunk 07, but implement and unit-test the actual install/rollback/status/recover/uninstall/purge behavior here without live invocation.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/cmd/workflow-authority-admin/main.go` | Create | Thin stable admin CLI and exit mapping |
| `native/workflow-authority/internal/admin/admin.go` | Create | Shared lifecycle state machine and dry-run/staging implementation |
| `native/workflow-authority/internal/admin/apply_linux.go` | Create | Real injectable systemd/filesystem apply adapter |
| `native/workflow-authority/internal/admin/apply_darwin.go` | Create | Real injectable launchd/filesystem apply adapter |
| `native/workflow-authority/internal/admin/filesystem.go` | Create | No-follow atomic install/rollback/remove primitives |
| `native/workflow-authority/internal/admin/admin_test.go` | Create | Focused fake-root lifecycle and rollback tests for both real adapters |
| `native/workflow-authority/packaging/systemd/workflow-authority.socket` | Create | Root-owned pathname socket activation |
| `native/workflow-authority/packaging/systemd/workflow-authority.service` | Create | Hardened Linux service policy |
| `native/workflow-authority/packaging/launchd/studio.designmachines.workflow-authority.plist` | Create | Equivalent macOS socket/service activation |

## Files to Read

| File | Why |
|---|---|
| `native/workflow-authority/cmd/workflow-authority/main.go` | Thin command conventions |
| `native/workflow-authority/internal/platform/platform.go` | Shared service-manager boundary |
| `native/workflow-authority/internal/authority/service.go` | Runtime identity and state requirements |
| `native/workflow-authority/internal/state/replay.go` | Public enrollment/revocation/audit retention |
| `native/workflow-authority/internal/dockerapi/cleanup.go` | Exact-ID ledger, cleanup, and recovery state |
| `native/workflow-authority/internal/dockerapi/endpoint.go` | Enrolled endpoint identity and revalidation state |

## Shared Command Surface

Implement exactly:

- `install`
- `enroll-key`
- `enroll-endpoint`
- `status`
- `doctor`
- `rotate-key`
- `revoke-key`
- `recover`
- `uninstall`
- `uninstall --purge`

Do not add platform-specific commands.
The same command on both platforms accepts the same logical options and returns the same public JSON/status/reason schema.
Platform-specific paths may appear only as redacted/safe installed identity metadata where operator documentation requires them.

CLI to protocol mapping:

| CLI command | Protocol operation |
|---|---|
| `enroll-key` | `key_enroll` |
| `enroll-endpoint` | `substrate_enroll_endpoint` |
| `rotate-key` | `key_rotate` |
| `revoke-key` | `key_revoke` |
| `status` | `status` |
| `doctor` | `doctor` |
| `install`, `recover`, `uninstall`, `uninstall --purge` | Local lifecycle operations; no authority protocol frame |

`uninstall --purge` is one command plus a flag, not a separate protocol operation.

Lost-authenticator recovery is exactly:

1. From a UID-0 root console, run `workflow-authority-admin revoke-key --lost <generation>`; this records the lost generation as issuance-revoked without requiring the missing authenticator and preserves its public historical-verification record.
2. Run `workflow-authority-admin enroll-key`; require the replacement authenticator's credential-creation UP/internal-UV ceremony and atomically activate the new generation.
3. Run `workflow-authority-admin doctor`; it must report an active replacement generation and no software-key fallback, without printing credential identifiers.

No repository-context client or Workflow Kernel operation may invoke this sequence.

## Dry-Run and Staging Boundary

Every mutating command supports an injected filesystem/service manager and a non-mutating dry-run plan.
This chunk may build a deterministic staging tree under a test temporary directory.
It must not write `/usr`, `/etc`, `/Library`, `/var`, service-manager state, FIDO devices, or a live Docker endpoint.
The CLI contains the real live-apply path, but tests inject temporary roots/fake service managers and this task never invokes live apply.
Dry-run output contains actions and safe destinations but no keys, PINs, credential references, assertions, raw endpoint responses, or repository content.

## Installation Policy

Define root-owned fixed destinations for:

- client binary
- daemon binary
- admin binary
- service-manager resource
- root state directory
- root run/socket directory
- public trust/enrollment metadata
- audit/revocation metadata

Every path is absolute, normalized, no-follow, and below an approved installation root.
Reject symlinks, hard-link surprises where detectable, wrong owner/mode, writable parents, non-regular binaries, and destination replacement races.
Use a staging directory, verify all candidate files, fsync as appropriate, and atomically install.
Do not trust repository-side scripts as installer authority.

## Candidate Preflight

Before replacement, validate the candidate:

- closed distribution inventory
- exact filenames and roles
- SHA-256 checksums
- Go companion version
- protocol version
- libfido2 exactly 1.17.0 via `pkg-config --modversion libfido2`, linked-library/required-symbol inspection, plus required OpenSSL 3/libcbor/zlib dependencies; because libfido2 has no documented public runtime version query, runtime startup uses the chunk-03 symbol/allocation self-test and reports unverifiable package identity as unavailable
- expected target OS/architecture
- no unexpected writable/executable files
- no secret material
- service resource syntax/closed fields
- version ordering and downgrade policy

Because real distribution signing/notarization is outside this task, model signature/trust verification as an injected required policy.
Never call an unsigned staged artifact production-ready.
Failure leaves the prior installation intact.

## Linux Service Policy

The systemd socket unit owns a pathname Unix socket in a protected runtime directory.
Set explicit user/group/mode and `RemoveOnStop=true`; launchd removal/uninstall implements the equivalent explicit socket cleanup.
The service unit consumes socket activation rather than accepting arbitrary `--socket` input.
Apply applicable hardening:

- no new privileges
- private temporary directory
- protected system/home/control groups/kernel tunables/modules where compatible
- restrictive address families
- explicit device access needed for FIDO only
- bounded file descriptors/processes/memory
- working/state/runtime directories with fixed ownership
- disabled core dumps
- restart and timeout policy that does not loop prompt floods
- minimal environment

Document any hardening directive omitted because it conflicts with required HID/Docker Unix-socket access.
Omission must be explicit and tested later, not silent.

## macOS Service Policy

The launchd plist uses socket activation with a fixed pathname and root service label.
Set fixed program arguments and service identity.
The LaunchDaemon performs libfido2 HID device I/O for the authenticator; document any macOS device-access constraint explicitly and keep the real internal-UV hardware lane gated rather than substituting a client-side device path.
Do not use `PATH`, shell commands, user-selected sockets, LaunchAgent-only authority, or repository paths.
Use equivalent keepalive/throttle/resource/core-dump controls available in launchd.
The daemon still enforces peer credentials and FIDO authorization; launchd identity alone is not approval.
Do not add XPC, Secure Enclave, LocalAuthentication, Swift, app-bundle, or GUI-only behavior.

## Enrollment and Key Lifecycle

`enroll-key` invokes the shared FIDO ceremony and persists public enrollment only.
`rotate-key` enrolls a new generation, verifies it, atomically activates it, and retains prior public verification material.
`revoke-key` prevents new authority under the generation while preserving historical verification.
Key loss never triggers a software-key fallback.
No operation prints credential identifiers or assertions.
Real device operations remain unavailable in dry-run/unit mode.

`enroll-endpoint` derives endpoint/engine evidence through the broker.
It never trusts `DOCKER_HOST` or a context label.
Enrollment records the actual endpoint and engine identity; the engine is trusted host infrastructure, and status reports whether candidate-control-surface exclusion checks are configured.
Endpoint rotation retains audit history and invalidates active substrate state.

## Status and Doctor

Expose safe parity fields:

- installed/staged version
- protocol compatibility
- service configured/running/reachable state
- socket ownership/mode validity
- FIDO availability and enrollment generation state without credential reference
- libfido2 ABI compatibility
- endpoint enrolled/reachable/identity-matched state
- candidate-control-surface policy state
- cleanup/recovery backlog counts without object IDs
- public audit/revocation health
- last safe error code

Do not print raw config, paths containing private user data unless required and safe, device serials, credential references, signatures, Docker bodies, container IDs, repository identifiers, or environment values.

## Recovery and Uninstall

`recover` reconciles only exact substrate IDs in root-owned state and reports safe counts/reasons.
Default `uninstall` stops/disables service, removes binaries/socket/resources, and preserves public enrollment, revocation, historical verification, and audit state.
It reports the exact recovery command if rollback/uninstall cannot finish.
`uninstall --purge` requires explicit root-console confirmation. It attempts FIDO UV when the enrolled authenticator is available, but root-console lost-authenticator recovery must remain possible.
Lost-authenticator recovery permits the documented root-console path, records revocation of the lost generation, and never recovers or generates a software private credential.
It uses the exact `revoke-key --lost <generation>` → `enroll-key` → `doctor` sequence above on both platforms.
Purge never follows symlinks or removes outside exact approved roots.
Every step is idempotent and rollback-aware.

## Platform Parity Matrix

For each shared command, define:

- identical input validation
- identical logical state transition
- identical public response schema
- identical success/failure reason codes
- identical preservation/destruction policy
- OS-specific service-manager calls hidden behind one interface
- explicit unsupported-environment status only when a required dependency is absent on both product paths

Hardware or libfido2 absence is fail-closed availability, not a reduced feature mode.

## Companion Skills

Load:

- `assembly:golang-patterns` for Go CLI/state interfaces.
- `developer-essentials:auth-implementation-patterns` for enrollment, rotation, revocation, and purge confirmation.
- `developer-essentials:error-handling-patterns` for rollback and actionable recovery messages.
- `developer-essentials:e2e-testing-patterns` for injectable lifecycle seams.

## Acceptance Criteria

- [ ] AC-01 Both platforms expose exactly the ten shared commands and identical logical options/status/reason schemas.
- [ ] AC-02 Real Linux and macOS apply/service/filesystem paths are implemented behind injected interfaces; tests execute them only against temporary/fake roots and this task performs no live mutation.
- [ ] AC-03 Fixed installation roots, ownership, modes, no-follow components, writable-parent checks, and atomic replacement are enforced.
- [ ] AC-04 Candidate preflight verifies inventory, checksums, version ordering, OS/arch, protocol, libfido2 exactly 1.17.0/dependencies, and injected distribution trust before replacement; unavailable/stub builds are rejected.
- [ ] AC-05 Failed preflight or any install step leaves the prior installation usable and returns an actionable recovery command.
- [ ] AC-06 systemd socket/service units use fixed socket activation, root ownership, minimal environment, core-dump suppression, and documented hardening exceptions.
- [ ] AC-07 launchd uses fixed socket activation and program identity with equivalent resource/throttle/core policy and no XPC/Swift/GUI-only features.
- [ ] AC-07A systemd and launchd packaging declare the daemon-owned HID access intent required by libfido2; platform-specific constraints remain explicit native-lane gaps.
- [ ] AC-08 Key enrollment/rotation/revocation persist no private material; prior public keys remain for historical verification and revoked generations cannot issue.
- [ ] AC-09 Endpoint enrollment derives live endpoint/engine evidence and reports candidate-control-surface policy without claiming resistance to deliberate host-engine tampering.
- [ ] AC-10 Status/doctor output passes a closed safe-field allowlist and excludes credential/device/object/repository/secret/raw-response data.
- [ ] AC-11 Recovery acts only on exact root-ledger IDs and never expands authority from labels or names.
- [ ] AC-12 Default uninstall preserves public enrollment/revocation/audit state; purge is explicit, uses FIDO when available, and supports documented root-console lost-authenticator recovery.
- [ ] AC-13 Install, status, doctor, recover, rotate, revoke, uninstall, and purge plans are idempotent under repeated calls and partial-failure injection.
- [ ] AC-14 Invalid config fails before service start and never warns-then-continues with permissive defaults.
- [ ] AC-15 The same parity state-transition table is consumable by chunk 07 tests for both platform adapters.
- [ ] AC-16 No live installation, service registration, FIDO operation, endpoint enrollment, or privileged write occurs during verification.
- [ ] AC-17 Pinned Go 1.26.5 build/vet for `./cmd/workflow-authority-admin` and `./internal/admin` passes; injected filesystem/service/FIDO/endpoint fakes are constructible from an external test package.
- [ ] AC-17A Tests prove install, rollback, status, recover, uninstall, and purge execute real adapter logic against temporary/fake roots while leaving live host state unchanged.
- [ ] AC-17B Chunk-local tests execute each real apply adapter through injected fake service managers and temporary roots; cross-compilation alone is not native adapter proof.
- [ ] AC-18 `git diff --check` passes and only owned files change.
- [ ] AC-19 Linux and macOS parity tests execute the exact lost-authenticator command sequence and reject it from non-root/repository peers.
- [ ] AC-20 Fake-root tests assert every write remains under the injected root and run each mutating command twice to prove idempotent end state.

## Behavioral Contract Inputs

- `REQ-003`: parity install/status/recovery/uninstall semantics.
- `REQ-004`: non-exportable FIDO enrollment lifecycle.
- `REQ-005`: safe operator output.
- `REQ-009`: systemd/launchd parity and Baseplate prerequisites.
- `REQ-010`: no live install/enrollment/publication without another gate.
- `CHK-017`: parity admin state-transition table.
- `CHK-018`: install rollback and no-follow safety.
- `CHK-019`: public-state retention and explicit root-console purge, including lost-authenticator recovery.

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
- Do not modify Workflow Kernel files; chunk 05 runs in parallel.
- Do not add platform-only commands or reduced-security fallback modes.
- Do not perform a live privileged mutation.
- Do not expose credential references, assertions, PINs, Docker bodies/object IDs, repository identities, or environment values.
- Do not stage, commit, push, install, enroll, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

systemd and launchd both support socket activation, enabling one daemon/client protocol with narrow packaging adapters.
Public enrollment and revocation state must outlive ordinary uninstall so historical receipts remain verifiable.
The real privileged, hardware, and endpoint acceptance suite remains a separate authorization gate.
