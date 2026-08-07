# Chunk: Prove and gate the first safe Linux dispatch

## Context

This is workstream F, the M1 join and final serial critical-path step. It integrates the authority/FIDO, composed provider daemon, single Pipeline assessment adapter, and Linux packaging through black-box fixture tests.

This is product integration evidence, not pipeline closeout. It must not install live, enroll FIDO, provision a real credential, contact OpenRouter, mutate PR15, or publish git state. Missing live lanes remain explicit gaps.

## Task

Create an offline hostile integration harness that launches the daemon under an injected Linux root with fake FIDO, fixture-only credential, fixed test socket, pinned test scanner, and local TLS fixture server. Exercise the real public client, Pipeline adapter, daemon, WAL, provider transport, signed result verifier, disconnect/cancellation behavior, and cleanup.

Update validation expectations so production automation is available only when fixed-socket broker status and a verified same-connection exact-request terminal receipt exist. Preserve `host_authority_unavailable` and Codex fallback for every missing/mismatched state.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `tools/validate-workflow-authority.sh` | Create | M0/M1 static, secret-surface, fixture and dependency gate |
| `tests/test_workflow_authority_integration.py` | Create | Black-box Linux fixture and hostile end-to-end matrix |

## Files to Read (for context)

| File | Why |
|---|---|
| `tools/test-openrouter-runner-policy.sh` | Existing `host_authority_unavailable`, fixture and fallback assertions |
| `tools/validate-openrouter-cascade.sh` | Existing routing/cascade behavior |
| `tools/validate-routing-economics.sh` | Routing matrix invariants |
| `native/workflow-authority/packaging/linux/workflow-authority.service` | Service environment and shutdown behavior |
| `tests/test_provider_dispatch_contract.py` | Contract vectors and production-ineligible fake marker |

## Patterns to Follow

- Use temporary injected roots and fixture-only trust/credential markers. Never bind the production socket or production origin.
- Treat test doubles as local contract proof only. The harness must print real FIDO, root systemd, system TLS, and live provider lanes as `GAP`, never `PASS`.
- Run accepted request, rejected request, crash, replay, cancellation, cleanup, and concurrent cases in isolated processes so inherited environment/descriptors are observable.
- Scan process argv/env, logs, files, receipts, crash output, and sibling process visibility for sentinel prompt/response/key bytes.
- Verify zero fixture-server requests for every pre-contact rejection.
- Preserve routing and dry-run assertions; only authority availability changes.

## Companion Skills

- `developer-essentials:e2e-testing-patterns` -- deterministic black-box fixture orchestration
- `developer-essentials:auth-implementation-patterns` -- hostile boundary and downgrade cases
- `developer-essentials:error-handling-patterns` -- terminal state/fallback assertions
- `assembly:golang-patterns` -- race and subprocess test conventions

## Acceptance Criteria

- [ ] `REQ-E2E-01`: an eligible peer with a fake-FIDO assertion over the exact final request sends one accepted Pipeline assessment request to the local TLS fixture and receives response content only on the original connection plus a verifiable content-free receipt.
- [ ] `REQ-E2E-02`: missing daemon/socket/run/FIDO/policy/scanner/credential, wrong peer/scope/model/body/nonce/expiry, invalid signature, or nonterminal receipt preserves `host_authority_unavailable` or explicit decline/failure and completes on Codex.
- [ ] `REQ-E2E-03`: caller-set API key, provider base, proxy, socket, broker path, authorization mode, approved digest, policy/scanner path, output path, or wrapper cannot change production behavior.
- [ ] `REQ-E2E-04`: every malformed/secret/bounds/digest/destination/scope/replay/downgrade rejection produces zero fixture-server contact.
- [ ] `REQ-E2E-05`: crash before/after each WAL fsync, restart after `send_started`, timeout, partial response, client disconnect, and cancel/send races yield one deterministic terminal or unknown result with no retry.
- [ ] `REQ-E2E-06`: two concurrent duplicate requests yield at most one send; independent authorized requests respect run concurrency/byte/operation budgets.
- [ ] `REQ-E2E-06A`: a same-UID competing process cannot substitute, race, or spend a different body after exact-request approval; a duplicate of the approved body still sends at most once.
- [ ] `REQ-E2E-06B`: another connection cannot acknowledge, authorize, cancel, resume, or retrieve a pending request; closing the original connection consumes/tombstones it and releases no response.
- [ ] `REQ-E2E-07`: response bytes cannot be retrieved by a later/sibling connection, regular output file, inherited unauthorized descriptor, stdout, log, state, receipt, or crash report.
- [ ] `REQ-E2E-08`: credential and ephemeral private-key sentinels are absent from repository, temporary artifacts after cleanup, argv, env, logs, public state, receipts, children, and sibling process reads.
- [ ] `REQ-E2E-09`: signed dispatch result is rejected by repository-verification validators and states `substrate_authority=not_asserted`; it never advances verification success.
- [ ] `REQ-E2E-10`: dry-run routing, model ladders, quality floors, economics, and direct interactive `/openrouter` remain unchanged.
- [ ] `REQ-E2E-10A`: Pipeline assessment is the only M1 automated lane; research, adversarial, execution, dm-review, Airlift, unknown and missing lanes remain `host_authority_unavailable` with explicit Codex fallback.
- [ ] `REQ-E2E-11`: symlink, hard-link, parent swap, wrong owner/mode/type, stale socket, fake service, queue saturation, credential revoke, cleanup failure, and corrupt state fail closed.
- [ ] `REQ-E2E-12`: fixture harness uses only loopback TLS and fixture credentials; production origin, DNS, root filesystem, systemd, FIDO hardware, and external worktree are untouched.
- [ ] `CHK-E2E-01`: `./tools/validate-workflow-authority.sh` passes.
- [ ] `CHK-E2E-02`: `./tools/validate-workflow-kernel.py` passes.
- [ ] `CHK-E2E-03`: `./tools/validate-dual-compat.sh`, `./tools/check-dependencies.sh`, generated manifest/command checks, and `./tools/validate-composition.sh --all` pass.
- [ ] Output separately reports unrun live lanes: real libfido2 device, root systemd install, production credential provisioning, system TLS/OpenRouter, macOS parity, Docker substrate, and repository verification. Production enablement remains blocked until the real libfido2 exact-request path passes separately authorized acceptance.
- [ ] Production `host_authority_unavailable` assertion is relaxed only behind verified fixed-broker readiness; it remains the default on an ordinary developer checkout.

## Behavioral Contract Inputs

Classify all `REQ-E2E-*` and `CHK-E2E-*` above as executable offline except the explicitly listed live lanes, which are manual and unavailable for this run. Preserve the prohibited regressions: no caller authority, no worker credential/transport, no provider receipt as repository verification, no automatic retry, no silent fallback, no mocked live pass.

The execution orchestrator—not this chunk—generates and binds the canonical behavioral contract after `run.started`. Every dispatch and completion must echo its current digest and revision.

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
- Do not hide product edits inside this integration chunk; if an upstream bug blocks acceptance, stop and report the exact owning chunk.
- Do not run provider contact, root install, systemd enablement, FIDO enrollment, credential provisioning, Docker/OrbStack, macOS services, or external worktree mutation.
- Do not weaken or delete fallback, dry-run, routing-economics, direct-interactive, disclosure, or repository-verification assertions.
- No release, generated manifest rewrite, version bump, stage, commit, push, PR, merge, tag, or publication.
- Unavailable live lanes are explicit gaps, never mocked passes.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.

## Research Context

The earliest safe production integration point is not the presence of a daemon or API key. It is the conjunction of fixed-socket broker readiness, independently approved exact run scope, broker-owned scan/credential/send, durable single-use state, and a verified terminal result. Every missing element must preserve the current Codex fallback.
