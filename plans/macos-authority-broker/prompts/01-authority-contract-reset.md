> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Reset the Authority Provider Contract for FIDO2

## Context

This is the first chunk of the Linux-first, cross-platform Workflow Authority Broker.
It repairs partial uncommitted schema-v2 work before any Go implementation depends on it.
The production contract must carry one public FIDO2 run authorization plus a chain of ephemeral run-key signatures and must never export an authority key.
The released schema-v1 HMAC path remains explicit legacy compatibility only.

## Task

Audit every task-owned partial authority/provider change in this worktree.
Replace generic native P-256 signer assumptions with a closed FIDO-authorized ephemeral run-key chain.
Define separate artifact roles for run authorization, operation authorization, observed substrate/result, cleanup result, and final receipt.
Freeze one exact operation vocabulary across schemas, Python, golden fixtures, and future Go consumers.
Separate issuance from historical verification and forbid automatic fallback or v1/v2 mixing.
Keep Workflow Kernel stdlib-only.
Do not implement FIDO cryptography in Python.
Python must invoke an injected or fixed-path verifier, validate its identity/result, and independently compare all canonical bindings.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/authority-provider-schema.json` | Modify | Closed request, FIDO response, verifier result, operations, and shared fixtures |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-substrate-schema.json` | Modify | Closed handle and attestation bindings; no opaque-label proof |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-approval-schema.json` | Modify | Versioned provider provenance and FIDO envelope reference |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-profile-schema.json` | Modify | Explicit production provider/substrate mode; legacy remains separate |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-provider-attestation-schema.json` | Modify | Exact provider evidence and authority provenance |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-receipts-schema.json` | Modify | v2 public authority evidence and historical v1 compatibility |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Modify | Canonical request validation and trusted verifier abstraction |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_receipts.py` | Modify | Authority abstraction and strict version/mode dispatch |
| `tests/fixtures/workflow-authority-v2-golden.json` | Create | Single shared source for three canonical vectors |
| `tests/test_authority_provider.py` | Modify | Contract, verifier, FIDO, redaction, and golden-vector tests |
| `tests/test_repository_verification.py` | Modify | Preserve legacy tests and add v2 receipt compatibility cases |

## Files to Read

| File | Why |
|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md` | Released pipe, cadence, receipt, and substrate semantics |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Existing partial canonical JSON, digest, and provider-error conventions to audit rather than trust |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_errors.py` | Stable verification error-code patterns |
| `tools/validate-workflow-kernel.py` | Release inventory that later chunks must keep coherent |
| `plans/macos-authority-broker/research.html` | Approved threat constraints and FIDO evidence requirements |

## Contract Vocabulary

Use exactly these operations:

- `approve_profile`
- `plan_verification`
- `run_verification`
- `record_result`
- `provider_attestation`
- `verify_envelope`
- `substrate_enroll_endpoint`
- `substrate_prepare`
- `substrate_inspect`
- `substrate_execute`
- `substrate_cleanup`
- `key_enroll`
- `key_rotate`
- `key_revoke`
- `status`
- `doctor`

Unknown operations fail closed.
Do not preserve aliases from the abandoned Swift prototype.
Do not translate operation names heuristically.

Operation admission is fixed:

| Operation class | Operations | Admission |
|---|---|---|
| Root-console lifecycle | `key_enroll`, `key_rotate`, `key_revoke`, `substrate_enroll_endpoint` | UID-0 peer through the admin/root-console path only; never reachable from Workflow Kernel |
| Run cadence | `approve_profile`, `plan_verification`, `run_verification`, `record_result`, `provider_attestation`, `substrate_prepare`, `substrate_inspect`, `substrate_execute`, `substrate_cleanup` | Exact operation must be allowed by an active FIDO-authorized closed run |
| Read-only | `verify_envelope`, `status`, `doctor` | Fixed local client and peer policy; no active run required; no mutation or authority issuance |

Freeze these protocol bounds across schema, Python, Go, fixtures, and validators: maximum frame 1,048,576 bytes; maximum UTF-8 string 4,096 bytes; maximum collection 256 entries; maximum nesting depth 16.

## Required Evidence Chain

Use this precise construction:

1. The daemon generates an ephemeral Ed25519 run key in memory.
2. A `run_authorization` FIDO assertion signs the canonical closed run scope plus the ephemeral public key, allowed operations, issuance, and expiry.
3. Each `operation_envelope` is signed by the ephemeral key and binds the run-authorization digest, exact operation/request/result bytes, fresh nonce, and strict sequence.
4. Pre-execution authorization covers immutable execution inputs.
5. `observed_result` covers exit/output digests and complete substrate observations after execution.
6. `cleanup_result` covers exact-ID cleanup and absence evidence after cleanup.
7. `final_receipt` covers the ordered digests of run authorization, operation authorization, observed result, cleanup result, and any provider evidence.

Historical verification needs only recorded public artifacts, the enrolled public FIDO key, and the ephemeral run public key.
It must not trust a live daemon.
Removal, substitution, duplication, or reordering of any chain element fails.

## Run Authorization Flow

The daemon validates the closed run scope declared by the kernel request.
A cadence operation without an active matching run returns bounded public reason `authorization_required` with the canonical closed scope and a server nonce; it does not perform the operation.
The fixed client renders that exact scope on its controlling terminal, opens the controlling terminal directly rather than using protocol stdin/stdout/stderr, and collects explicit operator confirmation.
Without a controlling terminal it fails closed with `authority_unavailable`.
After confirmation, the client resubmits the same operation with the daemon-issued confirmation reference; the daemon performs exactly one FIDO assertion, binds the ephemeral run public key, activates the closed run, and executes the requested allowed operation.
The client permits only one challenge/confirmation retry per invocation, preventing prompt loops.
Expiry, daemon restart, or revocation destroys the run signer; the next cadence operation repeats this flow once, and Workflow Kernel fails closed if reauthorization is denied or unavailable.
Protocol stdin carries only the original closed request frame and stdout only the final bounded public response.

Distinguish the public stable credential registry reference from the root-only raw FIDO allow-list credential ID.
Only the stable public reference may appear in signed evidence.

## Required FIDO Run Evidence

The approved response must bind, at minimum:

- schema version and artifact role
- exact closed run scope and scope digest
- canonical request document digest
- server nonce
- boot identity
- session identity: a daemon-instance UUID minted at startup and scoped within the boot identity
- allowed operation set
- issued-at and expiry timestamps
- stable public credential registry reference, never the root-only raw credential ID
- RP ID hash
- COSE algorithm identifier restricted to ES256 for v2
- public-key registry generation
- authenticator data
- client-data hash
- assertion signature
- signed user-presence flag
- signed user-verification flag
- optional signature-counter evidence
- verifier binary identity and verification result
- ephemeral Ed25519 run public key and algorithm
- repository, run, profile, candidate, boundary, and expiry bindings

The authenticator counter is clone evidence only.
Replay authority comes from the nonce/boot/session/sequence ledger.

First enrollment is authorized by root-console invocation plus the authenticator's own credential-creation UP/UV ceremony; it does not assume a prior credential.
Rotation uses the active credential when available and enrolls the replacement before revoking the old generation.
Lost-authenticator recovery requires explicit root-console recovery, revokes the lost public generation, and enrolls a replacement; it never creates a software authority key.
Default uninstall preserves public verification records.
Explicit purge uses FIDO when available or the documented root-console lost-key recovery path.

## Golden Fixtures

Create exactly three stable vectors in `tests/fixtures/workflow-authority-v2-golden.json`:

1. Minimal valid ASCII request.
2. Valid Unicode request exercising non-ASCII repository/profile/provider text.
3. Maximum permitted string and collection boundaries without exceeding the frame contract.

Each vector carries the structured request, exact canonical UTF-8 representation, and SHA-256 digest.
The fixture contains no private key, PIN, authentic credential identifier, assertion from a real device, token, or receipt key.
Future Go tests must consume this file directly rather than retyping values.
Vector 3 uses the frozen numeric bounds above exactly; companion negative cases exceed each limit by one.

## Patterns to Follow

- Continue closed-object schema style with `additionalProperties: false` or equivalent.
- Reuse existing canonical JSON rules; do not invent a second serializer.
- Preserve stable `VerificationPlannerError` reason codes and bounded error messages.
- Validate shape, size, types, timestamps, and bindings before invoking the verifier.
- Treat verifier success as necessary but not sufficient; compare the returned digest and evidence to the original request.
- Make the trusted verifier dependency explicit and injectable in tests.
- Production verifier resolution must be fixed-root/fixed-path and cannot use repository config, `PATH`, argv-selected programs, or environment-selected programs.
- Denied, cancelled, unavailable, malformed, and timeout responses carry only bounded reason codes.
- Historical v1 validation is an explicit caller-selected path; v2 issuance never calls the legacy HMAC implementation.

## Companion Skills

Load:

- `developer-essentials:auth-implementation-patterns` for credential, replay, and authorization boundaries.
- `developer-essentials:error-handling-patterns` for fail-closed typed failures and redacted diagnostics.

## Acceptance Criteria

- [ ] AC-01 The schema and Python operation vocabularies are byte-for-byte identical to the 16 names above.
- [ ] AC-02 The v2 run authorization requires FIDO authenticator data, client-data hash, signature, RP hash, ES256, public-key generation, signed UP/UV evidence, closed scope, and ephemeral Ed25519 public key.
- [ ] AC-03 Missing UP, missing UV, wrong RP, wrong credential reference, wrong algorithm, revoked generation, malformed authenticator data, and invalid signature all fail with closed non-secret reason codes.
- [ ] AC-04 Python rejects a verifier selected through repository content, `PATH`, environment, symlink substitution, or a non-enrolled verifier identity.
- [ ] AC-05 Python recomputes the request/document digest and exact bindings after verifier success; a forged `verified: true` response cannot approve altered content.
- [ ] AC-06 Issuance and historical verification are separate APIs; v2 issuance cannot silently invoke `LegacyHMACAuthority`.
- [ ] AC-07 Schema-v1 reads/tests remain available only through explicit legacy mode; version downgrade, mixed evidence, and automatic fallback fail closed.
- [ ] AC-07A Separate closed roles exist for run authorization, operation authorization, observed result, cleanup result, and final receipt, with exact signed bytes and prior digests defined.
- [ ] AC-07B Historical verification works offline and rejects removal, substitution, duplication, or reordering of any chain element.
- [ ] AC-07C The public stable credential reference is distinct from and cannot reveal the root-only raw FIDO credential ID.
- [ ] AC-07D Bootstrap enrollment, two-generation rotation, revocation, lost-authenticator recovery, default uninstall, and purge authorization semantics are frozen and tested.
- [ ] AC-08 The substrate schema requires endpoint/engine/image/container/toolchain/generator/run/candidate and cleanup evidence; a caller-invented label cannot validate.
- [ ] AC-09 Provider attestations bind exact lane/provider/head/result provenance and the same authority/substrate digests as the enclosing receipt.
- [ ] AC-10 Approval and receipt schemas preserve exact repository, run, profile, trusted base, candidate, boundary, and authority-provider provenance.
- [ ] AC-11 Cancelled, denied, unavailable, stale, future, replayed, reordered, and cross-boot responses reveal no request body or secret-shaped values.
- [ ] AC-12 The three golden vectors are committed in one shared fixture and Python tests verify their exact canonical bytes and SHA-256 digests.
- [ ] AC-13 Golden fixtures cover Unicode and maximum boundaries and contain no private or real authenticator material.
- [ ] AC-14 Existing focused repository-verification tests remain green without weakening their v1 assertions.
- [ ] AC-15 New tests cover wrong repository, run, profile, candidate, lane, provider, substrate, nonce, sequence, issuance, and expiry.
- [ ] AC-16 Schema files contain no fields named or described as raw key, secret, PIN, bearer token, or general signing RPC.
- [ ] AC-17 `python3 -m unittest tests.test_authority_provider tests.test_repository_verification` passes in the repository-required Python environment.
- [ ] AC-18 `./tools/validate-workflow-kernel.py` is run; any expected inventory red caused solely by later unimplemented Go assets is identified exactly and is not called a pass.
- [ ] AC-19 `git diff --check` passes and the chunk modifies only its owned files.
- [ ] AC-20 The admission matrix rejects every root-console lifecycle operation from a non-root repository peer before mutation and makes lifecycle operations unreachable from Workflow Kernel.
- [ ] AC-21 Golden vectors and schema constants use the exact frozen frame/string/collection/depth bounds; max values pass and max-plus-one values fail in Python.
- [ ] AC-22 The run-authorization handshake freezes `authorization_required`, `authority_unavailable`, direct controlling-terminal confirmation, a one-retry limit, and restart/expiry reauthorization semantics.

## Behavioral Contract Inputs

- `REQ-001`: production authority material is never exported.
- `REQ-003`: Linux and macOS share one authority contract.
- `REQ-004`: user presence and non-exportable credential protect minting.
- `REQ-005`: secret channels remain empty.
- `REQ-007`: fail-closed repeated cadence is preserved through the FIDO-authorized ephemeral run key.
- `CHK-001`: v2 FIDO envelope negative matrix.
- `CHK-002`: v1/v2 downgrade and mixing rejection.
- `CHK-003`: cross-runtime canonical golden vectors.

All are executable except real authenticator non-exportability, which remains a later hardware-gated manual check.

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

- Only modify the files listed above.
- Preserve the pre-existing `CLAUDE.md` Airlift marker and every unrelated worktree change.
- Do not implement Go, FIDO device I/O, Docker execution, packaging, or documentation in this chunk.
- Do not add third-party Python dependencies.
- Do not expose or fixture any real key, PIN, assertion, credential identifier, repository content, or token.
- Do not stage, commit, push, install, enroll, release, tag, publish, or mutate an external worktree.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

FIDO assertions sign authenticator data plus a client-data hash while keeping the credential private key inside the authenticator.
Signed UP/UV bits must be verified from authenticator data rather than trusted from caller booleans.
The public raw-key pipe is impossible to secure against a malicious same-UID worker.
Workflow Kernel must therefore verify public evidence and keep stdin HMAC as legacy-only.
