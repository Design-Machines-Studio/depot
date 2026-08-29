# Assembly Baseplate role cases

This catalog preserves the benchmark contracts prototyped against Assembly
Baseplate without copying private source excerpts or raw provider transcripts
into Depot. The machine-readable status and source selectors live in
`depot-role-portfolio.json`.

The cases are about the kind of work Baseplate requires, not about choosing a
model for one product feature. They represent a two-maintainer team operating
sovereign, single-binary Go installations with SQLite and embedded NATS. Each
installation serves roughly 4-50 users and may federate with other independent
installations.

## Evidence sealing

Every run materializes its evidence from an exact Baseplate Git revision into
the private result directory. The result must retain:

- the revision and clean-source proof;
- ordered source selectors and excerpt boundaries;
- prompt, task, evidence, system, and scorer SHA-256 values;
- exact requested and served model identities;
- transport, effort, provider, fallback, duration, token, and billed-cost data;
- raw output and every scorer revision.

Changing any prompt, evidence byte, fixture, assertion, or scorer creates a new
case revision. It never silently replaces earlier evidence. A scorer may be
corrected only when it contradicts the written task contract; unchanged raw
outputs are rescored and the original results remain retained.

## Scoped database implementation

Role: `builder-deep`.

The prototype supplied the first 150 lines of Baseplate `AGENTS.md`,
`internal/module/scoped_db.go`, and its visible tests. A durable revision must
ask for a patch in a disposable exact-revision worktree and close the following
gates:

1. The patch applies without repair or post-hoc extraction.
2. It changes only owned paths.
3. Go formatting and compilation pass inside Baseplate's Docker workflow.
4. Existing scoped DB tests pass.
5. Hidden tests prove that module scoping cannot be bypassed.
6. Transaction, placeholder, and error behavior remain compatible.
7. No host Go command or unrelated refactor is introduced.

The 2026-08-28 experiment retained model patches and receipts, but not one
sealed task/scorer artifact. It is therefore prototype evidence, not promotion
evidence.

## Federation architecture

Role: `architect`.

The candidate receives exact-revision excerpts covering federation identity,
protocol and capabilities, Assembly-info, trust delivery, HTTP security,
state models, and update health/handoff/orchestration. It must choose pull,
push, or a bounded hybrid for compatibility observations between sovereign
installations.

The deliverable covers:

1. current and proposed behavior with a team-size cost argument;
2. reused contracts and explicitly rejected new machinery;
3. state, persistence, ordering, staleness, and terminal conditions;
4. v1/v2 compatibility without changing the existing strict v1 payload;
5. identity, grants, nonces, SSRF, key-change, and revocation boundaries;
6. offline, retry, idempotency, and out-of-order behavior;
7. running-versus-staged update truth, failed handoff, rollback, and downgrade;
8. bounded operator UI and observability without private data leakage;
9. a two-install positive and negative verification matrix; and
10. independently revertible delivery slices with rollback criteria.

The prior run retained prompt hash
`1e749af4b2ada634f13a588b6f6435218a49826f80ebc268e57e1baf0a5345d1`
and three attempts for each admitted candidate. Its exact scorer was not
retained, so it remains a prototype until T3 seals the missing contract.

## Stack compatibility research

Role: `research-fast`.

The candidate receives Baseplate's exact Go, Templ, Datastar Go, and
NATS/JetStream pins; Docker/CI and architectural constraints; current official
documentation excerpts; and two deliberately unsupported internal claims. It
must return one JSON object with a hold/change decision, four component
findings, claim checks, risks, required validations, and unknowns.

The closed scorer requires:

1. a raw JSON object and `hold-pins` decision;
2. exactly one finding for Go, Templ, Datastar Go, and NATS/JetStream;
3. correct treatment of Baseplate's Go 1.26 pin and Datastar's documented Go
   1.24 floor;
4. Templ generation and generated-code drift controls;
5. JetStream at-least-once behavior, duplicate/idempotency responsibility, and
   the WorkQueuePolicy overlapping-consumer constraint;
6. rejection of both unsupported claims;
7. no speculative upgrade conclusion without exact-version evidence; and
8. supplied-source citations, unknowns, and bounded validation work.

The final prompt hash is
`5e4eb127192e324cccbefd13272511d3203acd3d26f9d7e0141c28090a2f7864` and
the corrected scorer hash is
`61a293015cd9278867318d0303e15dff6e5ef76a6d49932ae0a660f9ee4ef799`.
The correction broadened field placement only; it did not alter the task,
evidence, outputs, or paid calls.

## Planned role-completion cases

- `plan-critic`: critique a seeded federation plan against closed protocol,
  trust, update, rollback, operability, and scope defects.
- `review-deep`: review a seeded scoped-DB patch with hidden true findings and
  false-positive traps, then verify finding contribution.
- `security-review`: identify seeded federation trust, nonce, SSRF, grant,
  key-change, revocation, and data-minimization defects.
- `editorial`: produce an exact operator release note explaining running,
  staged, failed, rolled-back, and deliberately downgraded versions.
- `builder-deep` frontend: implement a bounded Templ, Datastar, and Live Wires
  interaction with generated-code, browser, accessibility, and validation
  gates.

The frontend case also exposes a policy gap: no current role directly owns
frontend implementation. Until a distinct routing need is proved, it is
measured under `builder-deep`; it must not silently create a new routed role.
