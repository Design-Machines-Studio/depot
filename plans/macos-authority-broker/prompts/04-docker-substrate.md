> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Implement Authoritative Docker Substrate Attestation

## Context

The broker now has cross-platform FIDO authority and IPC.
This chunk makes `DM_VERIFICATION_SUBSTRATE` meaningful by deriving evidence from an enrolled Docker Engine endpoint and broker-owned lifecycle.
The enrolled Docker engine is trusted host infrastructure under the user-approved small-team threat model.
Docker labels and caller strings are never authority.

## Task

Implement a stdlib Go Docker Engine API client over an enrolled Unix socket.
Enroll and revalidate endpoint/engine identity with no-follow descriptor checks.
Resolve immutable images, create the exact constrained container, measure Go 1.26.5 and the generator, execute exact argv, remeasure, and prove exact-ID cleanup.
Persist crash-consistent substrate ownership and recovery state.
Sign the observed result and post-cleanup evidence with the FIDO-authorized ephemeral run key and return only public evidence plus a non-secret handle.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/internal/dockerapi/client.go` | Create | Direct HTTP-over-Unix Engine API client |
| `native/workflow-authority/internal/dockerapi/endpoint.go` | Create | Enrollment, descriptor identity, access admission |
| `native/workflow-authority/internal/dockerapi/substrate.go` | Create | Minimal models, immutable image, container, probes, execution, and signed observations |
| `native/workflow-authority/internal/dockerapi/cleanup.go` | Create | Exact-ID state ledger, stop/kill/remove/absence, and reconciliation |
| `native/workflow-authority/internal/dockerapi/substrate_test.go` | Create | Client, endpoint, image, container, chain, cleanup, and fake-daemon tests |
| `native/workflow-authority/internal/authority/service.go` | Modify | Register substrate handlers and sign observed-result/cleanup envelopes through the active run signer |

## Files to Read

| File | Why |
|---|---|
| `native/workflow-authority/internal/dockerapi/docker.go` | Interface established by chunk 02 |
| `native/workflow-authority/internal/authority/service.go` | FIDO operation and replay integration |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-substrate-schema.json` | Required attestation shape |
| `plugins/workflow-kernel/skills/workflow-kernel/references/docker-ownership.md` | Exact positive ownership and cleanup patterns |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/docker_boundary.py` | Existing registry/label semantics to align with |

## Endpoint Enrollment

Accept only normalized pathname Unix endpoints.
Ignore `DOCKER_HOST`, Docker contexts, repository config, and caller engine labels.
Open the socket no-follow and bind enrollment to descriptor identity, owner, group, mode, and parent identity.
Connect and require `/_ping`.
Negotiate a supported Engine API version.
Read `/version` and `/info`.
Bind stable engine ID, server/API versions, OS, architecture, storage driver, runtimes, cgroup mode, security options, and enrollment policy.
Revalidate all relevant fields on every use.
Pathname equality alone is insufficient.

Enrollment records that the engine is trusted host infrastructure for this installation.
The broker does not claim resistance to a developer or host agent intentionally controlling the daemon.
Candidate containers must still be unable to access Docker, broker, FIDO, credential, or service-manager surfaces.
Status and documentation surface this threat-boundary choice explicitly.

## Image Resolution

Inspect the requested image reference.
Resolve it to an immutable `sha256:` image ID.
Record available repository/manifest digest provenance.
Reject ambiguous/missing platform resolution.
Create the container by immutable ID, never by mutable tag.
Inspect the created container and require its actual `.Image` to equal the measured ID.
Detect tag mutation between inspect and create.
Bind OS/architecture and relevant image configuration.

## Container Policy

Generate the name, nonce, labels, and ledger record in the broker.
Persist exact ownership before execution.
Require:

- non-root fixed user
- no privileged mode
- no Docker/OrbStack/containerd socket mount
- no authority/provider socket mount
- no FIDO/HID device
- no host credential/home directories
- network disabled unless the approved profile explicitly requires it
- read-only root filesystem
- all Linux capabilities dropped
- no-new-privileges
- controlled tmpfs and workspace mounts
- bounded CPU, memory, PIDs, output, and wall time
- exact argv array with no shell
- minimal explicit environment

Repository input is mounted read-only.
Outputs use a broker-owned staging mount with an explicit copy-out policy.
The container never receives the Docker client socket or broker connection.

## Toolchain and Workload Evidence

Before workload execution, run trusted probes inside the exact container.
Require:

- `go version` exactly `go1.26.5`
- `go env GOVERSION` exactly matching
- `GOROOT`
- `GOOS`
- `GOARCH`
- `CGO_ENABLED`
- Go executable path and SHA-256
- generator executable path
- generator version output
- generator SHA-256
- generator configuration digest
- canonical workload argv
- image ID and repository digest provenance
- exact container ID
- repository scope, run, profile, candidate, lane, and authority request digest

Remeasure identity-sensitive fields after the workload.
Any drift makes the attestation non-passing.

## Cleanup and Recovery

Cleanup runs on success, command failure, timeout, cancellation, client disconnect, daemon shutdown, and recovery.
Stop gracefully within a bound, then kill if required.
Remove the exact container and anonymous volumes.
Inspect the exact ID and prove absence.
Record cleanup start/end/status and evidence digest.
Passing attestation requires verified absence.
Never infer ownership or cleanup scope from labels or names alone.
Recovery reconciles only exact IDs in the root-owned ledger.
Forged labels are ignored.
Uninspectable or failed cleanup creates a blocked tombstone, never success.

## Signed Observation Chain

The pre-execution `operation_envelope` signs immutable execution inputs before the container runs.
After execution, an `observed_result` envelope signs exact output/exit digests and complete endpoint/engine/image/container/toolchain/generator observations plus the pre-execution digest.
After exact-ID absence is proven, a `cleanup_result` envelope signs cleanup evidence plus the observed-result digest.
All three use the active ephemeral run key and fresh nonces/sequences.
The final receipt later orders these digests.
Mutating any post-operation field after a valid pre-operation signature must fail verification.

## Companion Skills

Load:

- `assembly:golang-patterns` for contexts, HTTP clients, lifecycle, and tests.
- `developer-essentials:auth-implementation-patterns` for authority-to-substrate binding.
- `developer-essentials:error-handling-patterns` for bounded daemon/API failures.
- `developer-essentials:e2e-testing-patterns` for fake daemon and cancellation scenarios.

## Acceptance Criteria

- [ ] AC-01 Endpoint enrollment ignores `DOCKER_HOST`/contexts and binds no-follow descriptor, parent, ownership/mode, ping, API, version, info, and engine identity.
- [ ] AC-02 Symlink swaps, parent swaps, socket replacement, wrong owner/mode, engine drift, API drift, and unreachable/uninspectable endpoints fail closed.
- [ ] AC-03 Enrollment records the trusted-host Docker assumption and tests/docs do not claim resistance to deliberate developer or host-agent daemon control.
- [ ] AC-04 The current OrbStack endpoint may be enrolled under that trusted-host assumption while candidate containers remain unable to access any control surface.
- [ ] AC-05 Image tags resolve to immutable IDs and repository digest provenance; create uses the ID and post-create inspection must match it.
- [ ] AC-06 Mutable-tag races, platform mismatch, missing digest/ID, and container-image mismatch fail.
- [ ] AC-07 Container tests assert non-root, no privilege, no forbidden sockets/devices/credentials, dropped capabilities, no-new-privileges, read-only root, controlled mounts/network, and resource bounds.
- [ ] AC-08 Workload execution uses exact argv without a shell and a minimal declared environment.
- [ ] AC-09 The exact executing container is the measured container and binds repository/run/profile/candidate/lane/request identity.
- [ ] AC-10 Go version and `GOVERSION` must be exactly `go1.26.5`; binary path/digest and complete Go environment evidence are bound.
- [ ] AC-11 Generator path, version, digest, configuration, and workload argv are bound and revalidated.
- [ ] AC-12 Engine, image, container, toolchain, generator, or binding drift before/after workload makes the attestation non-passing.
- [ ] AC-12A Pre-execution authorization, post-execution observed result, and post-cleanup result are distinct ephemeral-key-signed envelopes chained by exact digests.
- [ ] AC-12B Mutating any observed or cleanup field after a valid pre-execution signature fails historical verification.
- [ ] AC-13 Cleanup runs for success, failure, timeout, cancellation, disconnect, shutdown, and recovery; exact-ID absence is required for pass.
- [ ] AC-14 Failed/uninspectable cleanup produces a blocked tombstone; labels/names cannot expand cleanup authority.
- [ ] AC-15 Restart recovery reconciles only root-ledger IDs and handles daemon disappearance without claiming residue-free success.
- [ ] AC-16 Candidate code cannot attach/exec/kill through a control socket because no Docker/broker/FIDO/service surface is present; deliberate trusted-host daemon actions are outside scope.
- [ ] AC-17 Public substrate handles contain no secret, raw Docker response, credential, repository content, or bearer authority.
- [ ] AC-18 Fake Docker tests cover bounded API bodies, malformed JSON, timeouts, cancellation, connection reuse safety, and redacted errors.
- [ ] AC-19 Pinned Go 1.26.5 tests and race tests pass; any real-engine suite remains a named gated gap unless actually run.
- [ ] AC-20 `git diff --check` passes and only owned files change.
- [ ] AC-20A The daemon dispatch table registers all 16 vocabulary operations; an IPC-level fake-engine/fake-FIDO test exercises `substrate_prepare` → `substrate_inspect` → `substrate_execute` → `substrate_cleanup` and proves observed-result and cleanup-result envelopes use the active ephemeral run key.
- [ ] AC-20B `substrate_enroll_endpoint` remains root-console-only, and an IPC-level non-root peer test proves rejection before any Engine API call.

## Behavioral Contract Inputs

- `REQ-006`: real endpoint/engine/image/container/Go/generator/run/cleanup binding.
- `REQ-008`: substrate alteration, path, cancellation, and cleanup attacks.
- `REQ-009`: OrbStack and Linux Docker share one contract.
- `CHK-010`: endpoint identity and candidate control-surface negative matrix.
- `CHK-011`: image/container/toolchain drift matrix.
- `CHK-012`: lifecycle and exact cleanup matrix.

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
- Do not wire Workflow Kernel, create service packaging, or edit docs here.
- Do not shell out to `docker` or trust caller contexts/labels as proof.
- Treat the enrolled engine as trusted host infrastructure, but never expose its socket or credentials inside a candidate container.
- Do not mount host authority, Docker, FIDO, credential, or service surfaces into the container.
- Do not accept best-effort cleanup as pass.
- Do not stage, commit, push, install, enroll a live endpoint, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

Docker daemon access is root-equivalent and defeats hostile-worker containment.
OrbStack is a Docker-compatible macOS endpoint adapter, not a separate security model.
The broker must derive evidence from live Engine API observations and exact owned IDs.
