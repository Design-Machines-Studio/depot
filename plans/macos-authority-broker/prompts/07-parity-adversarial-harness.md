> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Prove Linux and macOS Security Parity

## Context

All product components are now implemented.
This chunk supplies the hostile cross-platform evidence needed before documentation and versioning can claim readiness.
Linux is the primary full integration lane; macOS must run the same contract fixtures plus its peer/service adapter tests.
Unavailable hardware, root-service, or real-engine lanes remain explicit gaps.

## Task

Create one consolidated Go adversarial suite and one admin lifecycle suite.
Extend Python authority-provider coverage where cross-runtime behavior needs proof.
Add a dedicated validator that builds/tests the Go companion with the exact Go 1.26.5 toolchain and checks parity artifacts.
Update the Workflow Kernel release inventory only for actual shipped/required files.
Do not compensate for missing real prerequisites with permissive fakes labeled as production proof.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/internal/adversarial/adversarial_test.go` | Create | Cross-package hostile protocol/FIDO/IPC/Docker suite |
| `native/workflow-authority/internal/admin/admin_test.go` | Modify | Extend chunk 06 fake-root lifecycle tests with the consolidated adversarial parity matrix |
| `tests/test_authority_provider.py` | Modify | Go/Python golden and fixed-verifier integration |
| `tools/validate-workflow-authority.py` | Create | Offline companion build/test/parity gate |
| `tools/validate-workflow-kernel.py` | Modify | Exact new runtime/schema/companion inventory |

## Files to Read

Read all Go `_test.go` files created by chunks 02–04.
Read `native/workflow-authority/internal/admin/admin_test.go` from chunk 06 before extending its focused fake-root coverage.
Read `tests/fixtures/workflow-authority-v2-golden.json`.
Read `tests/test_repository_verification.py` for already-owned cadence coverage; do not duplicate it here.
Read `tools/validate-workflow-kernel.py` conventions before changing its inventory.

## Required Attack Matrix

Cover:

- unauthorized UID/GID/session and wrong server identity
- same-user direct invocation, unsolicited run requests, terminal scope confirmation, internal-UV requirement, and bounded prompt flooding
- non-root attempts for every key/endpoint lifecycle operation, forged confirmation references, missing controlling terminal, and unsolicited `authorization_required` responses
- missing UP, missing UV, wrong RP, wrong credential, wrong generation, invalid signature
- stale, future, replayed, duplicated, reordered, and cross-boot requests
- wrong repository, run, profile, base, candidate, boundary, lane, provider, result, and substrate
- Unicode, duplicate-key, maximum-size, excessive-depth, truncated, trailing, and invalid-UTF8 messages
- stdout, stderr, log, formatted-error, argv, environment, core/crash diagnostic exfiltration
- socket symlink, parent swap, replacement, ownership/mode, and ancillary-descriptor attacks
- concurrent requests, authenticator serialization, idempotency collision, and cancellation at every stage
- Docker endpoint replacement, engine drift, mutable-image race, container mismatch, toolchain/generator drift
- candidate attempts to discover/use Docker, broker, FIDO, credential, or service-manager surfaces
- mutation/removal/reordering/substitution of every ephemeral evidence-chain element
- cleanup failure, daemon crash, restart recovery, forged labels, and exact-ID residue
- install/status/doctor/rotate/revoke/recover/uninstall/purge idempotence and rollback

## Cross-Platform Evidence

Use one table-driven shared suite for protocol, state, FIDO semantics, Docker semantics, admin transitions, reason codes, and exit status.
Run Linux syscall adapter tests on Linux.
Run macOS syscall adapter tests on macOS.
Cross-compilation may supplement but never replace native adapter execution.
The validator must distinguish `pass`, `fail`, and `unavailable` for:

- pinned Go toolchain
- libfido2 headers/library/ABI
- Linux native adapter
- macOS native adapter
- real FIDO hardware ceremony
- macOS LaunchDaemon HID assertion with authenticator-internal UV
- privileged service lifecycle
- real enrolled-engine identity, candidate control-surface exclusion, remeasurement, and exact cleanup

Only actual execution can produce `pass`.

## Validator Behavior

`tools/validate-workflow-authority.py` must be offline by default.
It validates file inventory, absence of Swift production files, `go.mod` toolchain policy, shared fixture consumption, build tags, service resources, secret-surface static rules, and available test lanes.
It uses the exact Go 1.26.5 environment supplied by repository validation.
It must not download tools silently, use another Go version, install libfido2, start services, enroll hardware, or mutate Docker.
Unavailable prerequisites produce explicit nonzero/gap output according to repository validator policy.

## Companion Skills

Load:

- `assembly:golang-patterns` for race-safe Go tests.
- `developer-essentials:auth-implementation-patterns` for adversarial authority coverage.
- `developer-essentials:error-handling-patterns` for failure assertions.
- `developer-essentials:e2e-testing-patterns` for lifecycle/cancellation matrices.

## Acceptance Criteria

- [ ] AC-01 The complete attack matrix above maps to named tests or an explicit externally gated acceptance case.
- [ ] AC-02 Shared protocol/state/FIDO/Docker/admin fixtures run unchanged on Linux and macOS; adapter-only cases are clearly separated.
- [ ] AC-03 Python and Go consume the same three golden vectors and match exact canonical bytes/digests.
- [ ] AC-04 Secret scans assert forbidden values are absent across stdout, stderr, logs, errors, argv, environment, and diagnostic fixtures.
- [ ] AC-05 Same-user prompt flooding is bounded and cannot bypass fresh UP/UV or starve cancellation indefinitely.
- [ ] AC-05A Tests prove a genuine direct request cannot activate an unattended run without operator terminal confirmation plus authenticator-internal UV; fully compromised desktop display spoofing is explicitly outside scope.
- [ ] AC-06 Candidate containers cannot discover or use Docker, broker, FIDO, credential, or service-manager control surfaces; deliberate trusted-host daemon tampering is outside scope.
- [ ] AC-07 Cancellation is tested before touch, during FIDO I/O, during Docker execution, during result recording, and during cleanup.
- [ ] AC-08 Concurrency tests prove sequence uniqueness, replay consumption, authenticator serialization, and exact idempotency behavior under the race detector.
- [ ] AC-09 Install/admin tests compare identical logical transitions, reason codes, preservation policy, rollback, and idempotence for systemd and launchd fakes.
- [ ] AC-10 Validator rejects missing Swift removal, wrong Go version, fixture drift, missing adapter, schema inventory drift, and secret-pattern regressions.
- [ ] AC-10A Validator rejects missing/drifted `Dockerfile.test`, wrong Go image digest, and libfido2 version other than 1.17.0.
- [ ] AC-10B Mutating any operation, observed result, provider result, cleanup result, prior digest, public run key, or ordering after a valid run authorization fails historical verification.
- [ ] AC-10C Bootstrap enrollment, rotation, lost-authenticator recovery, revocation, expiry, restart, and old-generation issuance have parity tests.
- [ ] AC-11 Cross-compilation is never reported as native macOS/Linux adapter proof.
- [ ] AC-12 Hardware, privileged service, and real-engine lanes are reported as gaps unless actually executed with separately authorized prerequisites.
- [ ] AC-13 Pinned Go 1.26.5 tests, race tests, vet/static checks, Python authority tests, and Workflow Kernel offline gate pass where available.
- [ ] AC-14 `git diff --check` passes and only owned files change.
- [ ] AC-15 Admission-matrix tests reject all non-root lifecycle requests before handler dispatch and prove read-only/cadence operations retain their distinct policies.
- [ ] AC-16 Terminal-dependent lanes report pass/fail/unavailable explicitly; no controlling terminal, forged confirmation, and prompt-loop attempts fail closed.

## Behavioral Contract Inputs

- `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, and `REQ-009` receive executable negative evidence here.
- `CHK-020`: complete adversarial traceability matrix.
- `CHK-021`: Linux/macOS parity result matrix.
- `CHK-022`: unavailable-lane honesty and non-promotion.

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- commands actually run.

## Ambiguity Protocol

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify listed files.
- Do not weaken product code merely to make a hostile test pass.
- Do not run live installation, enrollment, service registration, or Docker mutation.
- Do not claim unavailable lanes as pass.
- Do not stage, commit, push, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

The supported boundary protects non-exportable FIDO/run authority and excludes candidate code from host control surfaces.
It intentionally does not defend against a developer or fully compromised host session deliberately controlling Docker or spoofing the terminal.
