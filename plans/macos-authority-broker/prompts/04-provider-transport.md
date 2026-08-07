# Chunk: Implement broker-owned OpenRouter transport

## Context

This is workstream D and the third step on the M1 serial critical path. It plugs into the run and WAL interfaces from chunk 02 and owns the complete provider boundary: trusted scanning, exact wire construction, credential custody, pinned HTTPS, bounded response delivery, and signed content-free terminal results.

The caller remains untrusted. It reserves proposed bytes and requested routing with no send authority. Only after the daemon builds the final body does same-connection FIDO authorize that exact request; no pre-approved or reusable provider run exists.

## Task

Implement the `openrouter-chat-v1` provider package and compose the production daemon. Load the root-owned credential safely, run the compiled-in scanner over exact parts using a fixed root-owned policy, build deterministic compact JSON, obtain the exact-request FIDO authorization, rehash immediately before the first network write, send exactly once, bound the response, and commit terminal/cleanup states.

Use injectable scanner, credential reader, clock, resolver, TLS transport, and response sink interfaces for fixture-only tests. No test may contact production or contain a real-looking key.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/internal/provider/openrouter.go` | Create | Mapping, body construction, result/provenance projection |
| `native/workflow-authority/internal/provider/credential.go` | Create | Fixed-path no-follow credential custody and zeroization |
| `native/workflow-authority/internal/provider/transport.go` | Create | Pinned HTTP/TLS, bounds, cancellation and original-connection response sink |
| `native/workflow-authority/internal/provider/provider_test.go` | Create | Fixture TLS server and adversarial transport tests |
| `native/workflow-authority/cmd/workflow-authorityd/main.go` | Create | Fail-closed composition of authority, in-process scanner, credential, transport and result sink |

## Files to Read (for context)

| File | Why |
|---|---|
| `tests/test_provider_dispatch_contract.py` | Exact wire and receipt vectors |
| `native/workflow-authority/internal/authority/run.go` | Reservation, WAL, signer, and terminal interfaces |
| `plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json` | Canonical disclosure policy semantics; do not execute caller paths |
| `plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh` | Historical response/provenance behavior to replace, not call |

## Patterns to Follow

- Production credential path is `/etc/design-machines/workflow-authority/credentials/openrouter`; parent 0700, file root:root 0600, regular, single link, every parent no-follow validated.
- Scanner code is compiled into the root daemon. Production policy is fixed at `/etc/design-machines/workflow-authority/provider-policy.json`; its canonical digest and daemon build identity are bound into exact-request authority.
- Only `POST https://openrouter.ai/api/v1/chat/completions`; direct TLS with system roots, redirects and proxy environment disabled, no base override.
- Preserve each ordered UTF-8 part as one message entry. Build the final compact body once, hash it, authorize it, then rehash those exact bytes immediately before write.
- Response bytes exist only in bounded memory and the original authenticated connection sink. Durable artifacts contain digests and byte counts only.
- Treat absent required provenance, truncated JSON, oversize body, timeout, partial response, disconnect, or cleanup failure as unverified terminal outcomes.

## Companion Skills

- `assembly:golang-patterns` -- contexts, HTTP transport, memory ownership, race-safe fakes
- `developer-essentials:auth-implementation-patterns` -- credential custody and TOCTOU resistance
- `developer-essentials:error-handling-patterns` -- terminal outcome classification and redaction

## Acceptance Criteria

- [ ] `REQ-TRANSPORT-01`: production opens only the fixed credential and policy paths using descriptor-relative no-follow owner/type/mode/link checks; scanner code is in-process and caller code/path selection is impossible.
- [ ] `REQ-TRANSPORT-02`: credential bytes never reach argv, environment, logs, child processes, crash text, receipts, fixtures, public files, or caller memory; buffers are locked where supported and explicitly zeroized.
- [ ] `REQ-TRANSPORT-03`: the in-process scanner receives the exact ordered parts and fixed policy; its daemon build identity and policy digest are authorized, and rejection produces zero DNS or network activity.
- [ ] `REQ-TRANSPORT-04`: exact compact body bytes match M0 vectors and are rehashed immediately before first write; any mutation after authorization fails closed and consumes/tombstones the reservation as specified.
- [ ] `REQ-TRANSPORT-05`: HTTP transport rejects alternate scheme/host/path/method, redirects, proxy environment, userinfo, query/fragment, production credential with fixture origin, and fixture credential with production origin.
- [ ] `REQ-TRANSPORT-06`: exactly one network attempt is possible; timeout, ambiguous send, partial headers/body, client disconnect, and daemon cancellation never trigger automatic retry.
- [ ] `REQ-TRANSPORT-07`: response is limited to 8 MiB and delivered once over the original authenticated connection; no output path, retrieval token, later connection, regular-file fd, or sibling client can obtain it.
- [ ] `REQ-TRANSPORT-08`: terminal receipt signs request/authorization/body/response digests, bytes, destination, requested/actual model, available serving-provider/generation/usage provenance, fallback, scope, prior chain, outcome, and cleanup without content.
- [ ] `REQ-TRANSPORT-09`: missing required provenance is explicit and fails when installed policy requires it; code never infers provider/model identity.
- [ ] `REQ-TRANSPORT-10`: rotate/revoke primitives use atomic write/fsync/rename/parent-fsync and never leave the old or new key readable by non-root; failed rotation preserves one valid known state.
- [ ] `REQ-TRANSPORT-11`: `workflow-authorityd` composes the exact protocol, authority/FIDO, scanner, credential, transport, response sink, WAL, and signer implementations; unavailable/stub dependencies fail startup before socket readiness.
- [ ] Fixture tests prove no key-shaped bytes appear in captured env/argv/log/result/state and only the fixture TLS server receives accepted requests.
- [ ] `go test -race ./...` passes; real provider/TLS/credential lanes remain unrun and reported as gaps.

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
- No live credential, production endpoint, provider call, install, service enablement, or external transmission.
- No external scanner executable, separate proxy, signed child bearer, reusable authorization grant, caller HTTP client, or wrapper fallback.
- Invalid root-owned policy/config exits non-zero at boot; it never warns and continues.
- Shutdown drains accepted IPC, prevents new sends, resolves/tombstones transport, flushes WAL, zeroizes credentials, then closes state.
- Do not touch the read-only PR15 worktree or unrelated files.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.

## Research Context

Broker-owned transport was selected over a privileged proxy or child grant because only one process should simultaneously hold disclosure authority, the provider credential, destination policy, network send authority, and evidence signer. Splitting those roles would add a reusable capability or second privileged boundary without reducing trust.

## Required Handoff Evidence

- List every possible network-contact point and the checks that precede it.
- Record fixture-server request counts for all positive and negative cases.
- Include the exact terminal outcome table for timeout, cancel, partial, disconnect, and restart.
- Report credential/key/content sentinel scans by surface.
- State which provenance fields are verified, unavailable, or policy-required.
