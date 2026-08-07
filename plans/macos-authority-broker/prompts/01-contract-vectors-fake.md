# Chunk: Freeze provider-dispatch contract, vectors, and fake broker

## Context

This is workstream A and milestone M0 of the earliest-safe Workflow Authority Broker campaign. It creates the production-neutral contract that every later Go daemon, Linux client, Depot adapter, and verifier must share before any real credential or network transport exists.

The operation family is `external_provider_dispatch`. It is distinct from repository verification and must carry `substrate_authority: not_asserted`; no artifact from this chunk can satisfy repository-verification authority.

## Task

Define closed provider-dispatch schema-v1 request, exchange, result, and status documents; implement the stdlib-only Python validator/canonicalizer; and add byte-exact golden vectors plus a production-ineligible fake broker fixture. Freeze the `openrouter-chat-v1` mapping, byte-level single-connection rendezvous, fd-3 delivery, exit codes, FIDO challenge, trust chain, and signed terminal projection. Authority-envelope v1/HMAC is never an allowed downgrade.

Assign stable requirement IDs `REQ-M0-01` through `REQ-M0-11` and check IDs `CHK-M0-*` in the tests. Do not bind a behavioral contract or authorize execution; the execution orchestrator owns that after `run.started`.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/provider-dispatch-request-schema.json` | Create | Closed external-dispatch request schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/provider-dispatch-result-schema.json` | Create | Content-free terminal result schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/provider-dispatch-status-schema.json` | Create | Public, non-secret availability/status schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/provider-dispatch-exchange-schema.json` | Create | Closed challenge/consent/content/terminal single-connection protocol |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/provider_dispatch.py` | Create | Strict parsing, canonical bytes, digest and signature-input helpers |
| `tests/test_provider_dispatch_contract.py` | Create | Golden vectors, fake broker, and negative corpus |
| `tools/validate-workflow-kernel.py` | Modify | Register the four new release-gated schema documents |
| `tests/test_release_validator.py` | Modify | Keep the schema inventory regression test exact |

## Files to Read (for context)

| File | Why |
|---|---|
| `plugins/pipeline/references/openrouter-authorization-contract.md` | Existing fail-closed disclosure semantics to preserve |
| `plugins/workflow-kernel/skills/workflow-kernel/references/authority-provider-schema.json` | Existing closed-schema and signature conventions |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Canonical parsing and safe-error patterns |
| `tests/test_authority_provider.py` | Cross-runtime golden-vector style |

## Patterns to Follow

- Use only Python 3.12 standard library and the repository's strict schema matcher.
- Reject duplicate keys, unknown keys, non-canonical numbers, invalid UTF-8, nesting deeper than 16, frames over 1 MiB, more than 256 parts, requests over 8 MiB, and responses over 8 MiB.
- Canonical JSON is compact UTF-8 with sorted object keys and no lossy Unicode normalization.
- Each ordered content part becomes one ordered OpenRouter `messages` entry with the same `system` or `user` role. Never concatenate, reorder, trim, or normalize content.
- The exact final compact request body digest is part of pre-send authority.
- Test fake trust material must use a fixture-only marker and injected socket root. It must be impossible to report production-ready status.

## Frozen Byte-Level Exchange

Use one Unix `SOCK_STREAM` connection from request reservation through terminal result. No second connection may authorize, resume, retrieve, or cancel the transaction.

1. Client sends four-byte unsigned big-endian canonical-header length, the canonical request header, then for each declared part an eight-byte unsigned big-endian length and the exact UTF-8 bytes.
2. Server validates bounds, scans parts, builds the exact final body, reserves durable single-use state, and sends a four-byte big-endian length plus canonical `challenge` JSON.
3. Challenge binds a server-random transaction ID, connection nonce digest, peer UID/PID, exact final body digest, daemon/scanner build digest, policy digest, complete request scope, issued-at and expiry. The transaction ID is diagnostic identity, never a bearer.
4. Fixed client renders the canonical challenge scope on its controlling `/dev/tty` and sends a length-prefixed canonical `consent_ack` containing only the challenge digest on the same socket.
5. The daemon accepts the ack only from that still-open connection and performs libfido2 UP+UV over the exact challenge. Ack is not authority and cannot be replayed elsewhere.
6. After send, server sends an eight-byte big-endian response-content length plus raw bytes, followed by a length-prefixed canonical signed `terminal` JSON. Safe errors are length-prefixed canonical `safe_error` JSON and never carry content.
7. Fixed client buffers at most 8 MiB, verifies the terminal signature/FIDO-bound ephemeral public key and response digest/length, then writes content once to inherited fd 3 and the content-free terminal JSON once to stdout. Verification failure discards content.

Reject ancillary descriptors on the broker socket. Client fd 3 must be an inherited anonymous pipe verified with `fstat`; regular files, sockets selected by path, reused descriptors, and absent fd 3 fail before request reservation.

Exit codes are fixed: `0` verified success; `2` invalid local/protocol input; `70` host authority unavailable; `71` exact authorization declined/expired/replayed; `72` disclosure declined; `73` provider failure; `74` outcome unknown/no retry; `75` response/result verification failure. The Pipeline adapter maps them to existing explicit Codex/failure outcomes; unknown codes are hard safe failures.

## Frozen Trust Chain

The client loads only the fixed root-owned public FIDO credential registry and daemon build trust record. The FIDO assertion binds the exact challenge plus the ephemeral result public key. The terminal result signature verifies under that ephemeral key and includes the assertion/challenge digest. Fixture trust roots carry an explicit production-ineligible domain marker.

## Exchange Golden-Vector Matrix

Create byte-exact vectors for each complete exchange, not independently retyped fragments:

| Vector | Expected terminal |
|---|---|
| one system and one user part, accepted | signed success plus response released after verification |
| Unicode, escaping, null-valued options and maximum legal lengths | byte-identical canonical body and terminal digests |
| disclosure decline | safe error 72, no content frame, no network |
| operator/FIDO decline or expiry | safe error 71, consumed transaction, no network |
| provider timeout after send start | signed outcome unknown/provider failure, no retry |
| response digest or length mismatch | client exit 75, content discarded |
| original connection closes before ack | durable cleanup/tombstone, no authorization |
| original connection closes after send start | terminal unknown/failure, no later retrieval |
| another connection reuses transaction/challenge | rejection without changing original state |
| changed daemon/scanner build or policy digest | FIDO challenge mismatch before network |

For every positive vector, store the complete request bytes, challenge bytes, consent-ack bytes, content-frame bytes, terminal bytes, signature input and expected exits. For every negative vector, store the mutation operation and stable rejection code without embedding credential, assertion, prompt, or response secrets beyond explicit harmless fixtures.

## Reservation and Flood Bounds

The contract fixes maximum pending reservations per peer, repository and daemon, maximum bytes charged before FIDO, expiry cleanup, and rate-limit diagnostics. Rejected/flooded reservations cannot allocate response buffers, invoke FIDO, or contact DNS/network. Disconnect cleanup is bounded and durable.

The transaction ID is safe to log only as a random identifier and remains useless off the original connection. It never appears in argv/environment and never reopens or retrieves state. Tests must prove possession of it grants nothing.

## Stable Frame Errors

- Header or control length exceeds the bound: `frame_too_large`.
- Part count/length differs from the manifest: `part_frame_mismatch`.
- Unknown control kind or wrong state order: `exchange_state_invalid`.
- Content arrives before successful provider terminal construction: `content_order_invalid`.
- Terminal arrives without matching response digest/count: `terminal_binding_invalid`.
- Consent ack arrives on another connection or after expiry: `consent_connection_invalid`.
- Any trailing byte after a complete frame sequence: `exchange_trailing_data`.

These identifiers are public and content-free. Implementations may retain internal causes in protected diagnostics only after redaction; arbitrary parser, OS, FIDO, or TLS text never crosses the protocol.

## Companion Skills

- `developer-essentials:auth-implementation-patterns` -- fail-closed authority and replay contract review
- `developer-essentials:error-handling-patterns` -- stable safe failures without secret-shaped diagnostics

## Acceptance Criteria

- [ ] `REQ-M0-01`: request/challenge binds protocol/mapping version, operation family, ordered parts, final body digest, method/origin/path, model order, repository, run, lane, candidate, workload, daemon/scanner build digest, policy digest, nonce, sequence, boot/session, connection nonce digest, issuance, expiry, and byte budgets.
- [ ] `REQ-M0-02`: result schema contains only request/authorization/body/response digests, byte counts, safe outcome, requested/actual model, available provider provenance, scope, sequence, timing, prior-chain digest, and cleanup; content and credentials are structurally impossible.
- [ ] `REQ-M0-03`: every dispatch request and result fixes `operation_family=external_provider_dispatch` and `substrate_authority=not_asserted`; repository-verification schemas reject these documents.
- [ ] `REQ-M0-04`: `openrouter-chat-v1` vectors freeze exact compact body bytes for Unicode, escaping, null, newlines, ordered roles, one model, and ordered model fallback.
- [ ] `REQ-M0-05`: Go-compatible signature-input vectors are domain separated and include every authority field without accepting caller-selected authorization mode or approved digest.
- [ ] `REQ-M0-06`: the fake broker binds only an injected test socket and fixture trust marker and always reports `production_ready=false`.
- [ ] `REQ-M0-07`: negative tests reject part mutation/reorder/add/remove, role/model changes, wrong scope, stale/future/replayed identifiers, wrong origin/path/method/mapping, unknown fields, malformed UTF-8, binary and bounds violations.
- [ ] `REQ-M0-08`: diagnostics contain stable codes only and never echo prompt, response, credential, authorization bytes, filesystem paths containing secrets, or arbitrary exception text.
- [ ] `REQ-M0-09`: exchange vectors freeze every byte and state transition above, including fd-3 semantics, trust verification and exit-code mapping, for Python/fake/Go consumers.
- [ ] `REQ-M0-10`: tests reject pending-request substitution, reservation flooding beyond bounds, authorization/ack from another connection, stale challenge, changed daemon/scanner build or policy, content delivery before terminal verification, and response retrieval by any non-original connection.
- [ ] `REQ-M0-11`: provider-dispatch schema v1 is explicitly distinct from public authority-envelope v2; raw HMAC/receipt-key inputs and authority-envelope v1 cannot satisfy or downgrade production dispatch.
- [ ] `CHK-M0-01`: `./tools/validate-workflow-kernel.py` passes offline.
- [ ] `CHK-M0-02`: `python3 -m unittest tests.test_provider_dispatch_contract` passes offline.
- [ ] No live socket, FIDO device, credential, DNS, TLS, or provider is contacted.

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
- Do not edit generated Codex manifests or command-skill aliases.
- Do not implement production IPC, FIDO, credential loading, HTTP transport, or installation.
- Do not make the fake broker discoverable at the production socket.
- Do not touch the read-only PR15 worktree.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.

## Research Context

The existing caller-controlled `exact-digest` and `trusted-boundary` modes are insufficient for automation because a same-UID worker can choose the mode and compute the digest. The stable replacement is an indivisible broker dispatch whose authority covers exact final wire bytes and whose result is signed but content-free.

## Required Handoff Evidence

- Record the exact schema IDs and versions introduced.
- Record the canonical digest for every positive golden vector.
- List every negative vector and its stable rejection code.
- State explicitly that the fake trust root is production-ineligible.
- Report any Go/Python byte-parity question as `NOT-COVERED`, not assumed compatibility.
