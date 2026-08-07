# Expanded Plan Adversarial Review

## Scope

- Plan: `plans/macos-authority-broker/plan.html`, revision 6
- Lens: independent local Codex reviewer
- Date: 2026-08-03
- Mode: read-only; no OpenRouter transmission, credentials, provider calls, live validation, implementation, or external-worktree mutation

## Verdict

`REVISE`

The selected broker-owned transport architecture is retained. The review found eight contract gaps that must be closed in planning before post-review approval:

1. **P0 — Fixed installation boundary:** literal Linux/macOS binary, admin, socket, state, credential, scanner, policy, service, and public-ledger paths plus owner/group/mode requirements were not frozen.
2. **P0 — OpenRouter wire mapping:** the plan bound ordered input parts but did not freeze the exact HTTP method/path/headers/body mapping version or make the final body digest part of the signed pre-send authorization.
3. **P1 — Lifecycle ownership:** daemon, admin client, and service manager responsibilities for install/recover/rotate/revoke/uninstall/purge and failure ordering were ambiguous.
4. **P1 — Status/doctor ownership:** public content-free transport status and privileged lifecycle diagnostics were conflated.
5. **P1 — Controlling-terminal custody:** end-to-end `/dev/tty` preservation, non-TTY rejection, and exclusion of provider credentials from Python/plugin memory were not explicit.
6. **P1 — Credential-at-rest contract:** directory/file validation, atomic rotation, fsync, dump/swap/backup handling, zeroization, revoke, and purge semantics were incomplete.
7. **P1 — Response confidentiality:** result delivery was not bound to the original connection, later retrieval was not forbidden, and fixed-client response sink/disposal behavior was unspecified.
8. **P1 — Durable linearization:** persisted replay fields, fsync points, cancel-vs-send ordering, pre-send rejection accounting, and crash budget reconciliation were not frozen.

## Required chunk addenda

- **Chunk 01:** freeze the wire mapping/version, method/path/semantic headers, final body-digest placement, durable operation schema, cancellation linearization, and separate public-status/privileged-doctor schemas.
- **Chunk 02:** add Go/Python exact wire-body vectors, Unicode/escaping/null vectors, restart tombstones, and response framing vectors.
- **Chunk 03:** define durable reservation, sequence, attempt/budget, cancel/send, and restart state transitions and fsync points.
- **Chunk 05:** own credential-file lifecycle, no-dump/locked-memory behavior, exact response-connection binding/disposal, and pre-write body rehash.
- **Chunk 06:** freeze client response sinks; prohibit response paths and accidental persistence.
- **Chunk 08:** add literal platform paths/modes, daemon/admin/service-manager ownership, exact lifecycle semantics, and controlling-terminal tests through the fixed-client invocation path.
- **Chunk 09:** attack every fixed path; redirected/non-TTY provisioning; same-UID response retrieval; cancellation races; crash boundaries; rotation/purge; and OS parity.
- **Chunk 10:** document plaintext-at-rest residuals and retain separate live/git/release gates.

## Disposition

Plan revision 7 incorporates these addenda. This review does not approve implementation or prompt generation. Replacement prompts remain blocked until the user explicitly approves the post-review plan.
