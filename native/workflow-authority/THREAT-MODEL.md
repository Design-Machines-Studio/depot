# Workflow Authority provider-dispatch threat model

## First safe milestone

The first milestone authorizes one broker-mediated OpenRouter request on Linux.
The root service owns the FIDO ceremony, provider credential, disclosure scan,
exact request construction, network transport, replay ledger, and signed
content-free terminal receipt. The repository process supplies bounded content
and scope fields but never receives reusable authority or provider credentials.

This milestone does not attest repository execution or Docker containment.
Every provider artifact carries `substrate_authority: not_asserted`. A caller
label, `DM_VERIFICATION_SUBSTRATE`, Docker socket path, or engine description is
not accepted as proof. Deferring substrate attestation therefore cannot grant
authority, weaken provider credential custody, or turn a provider receipt into
repository-verification evidence.

## Protected assets and decisions

- FIDO private keys remain inside the authenticator. Root-private credential IDs
  and device selectors remain in the root-owned enrollment record.
- The OpenRouter credential remains in a root-owned regular file and daemon
  memory. It is not placed in argv, environment, child processes, receipts, or
  repository-controlled transport.
- The daemon binds the exact ordered payload, fixed HTTPS origin/method/path,
  model list, repository, run, lane, candidate, workload, caller nonce,
  allocation sequence, boot/session identity, issuance, expiry, scanner/policy
  digests, and result signer.
- Send authority is consumed durably before the first provider byte. A
  post-send failure is a signed non-retryable terminal outcome or an unsigned
  ambiguity that also stops the external rail.
- Verified response bytes return only on the original authenticated connection.
  Receipts contain digests and provenance, never prompt or response content.

## Trust boundary

The trusted computing base is the host kernel, systemd, fixed root-owned
binaries and configuration, the Workflow Authority daemon, libfido2, the
authenticator, and the installed public client verifier. Root compromise,
kernel compromise, malicious authenticator firmware, and compromise of the
OpenRouter service are outside this local boundary. Provider compromise is
still bounded by response provenance validation and cannot mint a locally valid
terminal signature.

Linux peer credentials authenticate the connecting OS UID/PID and a fixed
root-owned group limits eligible UIDs. This is not a same-UID executable
identity: code running as an eligible user can connect to the socket and can
trigger authorization pressure. It still cannot mint authority silently,
because every dispatch requires a fresh UP+UV assertion for the exact
daemon-generated challenge. No secret shared with that UID is an authority
factor.

For stronger isolation, run repository workers under a different UID that is
not a member of `workflow-authority`. The first milestone does not require this
for a two-person trusted workstation, but operators must treat unexpected FIDO
prompts as hostile and decline them.

## User-presence limitation

An ordinary FIDO authenticator does not display the canonical request. UP+UV
proves that a person approved the cryptographic challenge; it does not prove
that hardware displayed the repository, run, lane, candidate, or models. The
client renders the exact scope on the controlling terminal, but a compromised
same-user desktop can spoof that display. Hardware with a trusted display or an
external approval station is required to close that residual risk.

## Fail-closed and deferral proof

- No enrolled FIDO credential, provider credential, policy, durable state,
  allowed peer, exact installed daemon identity, or activated fd 3 means no
  production-ready socket.
- Wrong scope, stale time, replayed nonce/sequence, mutated payload, destination
  change, model downgrade, disclosure-policy match, mixed failure provenance,
  cancellation, or terminal-delivery failure cannot yield a successful result.
- Linux is the first production runtime. macOS shares protocol schemas,
  canonical receipt validation, the public trust format, the client-side peer
  verification interface, and the fixed response-pipe contract. It does not yet
  have the production FIDO adapter, root platform/admin composition,
  peer-authenticated daemon runtime, launchd socket activation, or service
  packaging; production use therefore fails closed.
- Broader Pipeline, dm-review, research, assessment, adversarial-review, Airlift,
  and direct interactive migration can follow without changing the shared
  protocol. Until each caller is migrated, it retains its existing fail-closed
  Codex fallback or exact-digest interactive gate.
- Live root/systemd installation, libfido2 hardware, worker-separated accounts,
  provider contact, and credential provisioning are acceptance evidence gates;
  local fixture tests cannot satisfy them.

## Interim operator-batch authorization (temporary, sunset-bound)

The broker's production runtime is Linux/systemd/libfido2 and the Linux host is
unavailable for about two weeks from 2026-08-08. Until then the only working
OpenRouter path on macOS is interactive exact-digest approval per payload,
which is too much friction for automated lanes. The interim operator-batch mode
takes one interactive approval per run over a digest-bound payload set. This is
a deliberate, owner-authorized loosening with a sunset, not a quiet hole, and
it is documented here because honesty is the price of the mode existing.

**What it weakens.** Two things, stated plainly.

First, approval granularity. An operator now confirms a SET of exact payload
digests once at run start instead of confirming each payload immediately before
its own transmission. The window between approval and transmission widens from
one payload to one run, so a same-user process that can rewrite a lane's bytes
after the snapshot has a longer opportunity to try. Rewriting bytes does not
by itself get them transmitted: the wrapper recomputes the canonical
exact-ordered-content digest over ALL message contents in the request body it
is about to POST -- system, developer, assistant, and user turns, in
transmission order -- and refuses unless that digest is already a member of the
validated batch file's `payload_digests`. That check is at the point of
disclosure, over the content bytes actually sent, and it does not depend on the
lane having run `verify-batch` first. "Actually sent" is enforced by
construction, not asserted: the private copy of the request body is opened on a
dedicated file descriptor and its path is unlinked immediately, so no name
resolves to those bytes any more; the contents are read once through that
descriptor into process memory; and both the digest and curl are driven from
that single in-memory copy, with curl fed the bytes on stdin
(`--data-binary @-`) rather than any path. The per-message content parts the
digest frames are extracted from the same in-memory copy and never written to
disk. There is no second open of anything between the digest and the POST.
Message content that is not a plain
string (array-typed or otherwise structured content parts) has no framing that
agrees with what `payload-authorization.sh snapshot` records, so the wrapper
refuses it under interim mode rather than hash something different.

**What the binding does NOT cover.** It covers ordered message CONTENT bytes
and nothing else. The model slug, the fallback slug, the provider order, the
`sort` preference, and every other routing field are caller-selected and sit
outside the approved digest set; the batch schema records digests only, so
covering them would require a schema change. Honestly assessed, routing
metadata is a weak content-exfiltration channel -- the fields are constrained
to short, validated slugs and orderings by routing policy, native-vendor
rejection, and provider-order validation, so their capacity is a handful of
bytes per request rather than an arbitrary payload -- but it is a real
destination-selection channel: a lane that cannot change WHAT is sent can still
influence WHERE approved content goes, within the set routing policy permits.
Do not read the digest binding as approval of the route.

The residual weakening is that the operator's attention is spent once on
a summary (lane IDs, per-lane byte totals, grand total, digest count) rather
than repeatedly on each payload -- the same user-presence limitation described
above, applied to a batch.

Second, and more seriously: **the batch artifact is procedural and
unauthenticated.** `plans/<feature>/openrouter-batch-authorization.json` is bare
JSON with no signature, no MAC, and no user-presence binding. Nothing in it
proves that `batch-approve` -- or its `/dev/tty` confirmation -- ever ran. A
process running as the same user, including the very agent this gate is meant
to constrain, can hand-write a batch file carrying its own payload digests and
the known run id, and enter interim mode with zero interactive approval. The
run id, expiry, and sunset checks all validate data that such a forger supplies.
The interactive confirmation is a control against ACCIDENTAL and AUTOMATED
entry by this tooling; it is NOT a technical barrier against a same-user
process that forges the artifact. What the mode still binds, even against a
forger, is disclosure of message content to digests recorded in the file at
transmission time -- it does not bind who wrote the file, and it does not bind
routing metadata.

Closing that same-user gap is precisely what an out-of-process privileged
broker exists to provide, and re-implementing a weak imitation in Bash (a
Keychain ACL, an HMAC with a secret the same user can read) would be security
theatre. It is deliberately not attempted. The gap is the primary reason this
mode carries a sunset.

**What it does not weaken.** Credential custody is unchanged. The OpenRouter
API key stays exactly where the existing interactive path already puts it, in
the caller's environment, read only by the wrapper's `Authorization` header. No
change here places the key in argv, a receipt, a batch file, a new file, or a
new process. If any future change to this mode would move the key, stop.

**What it preserves.** Disclosure stays digest-bound: only exact ordered
content bytes recorded in the batch file may be sent, the wrapper enforces that
membership over the bytes it transmits, and a non-matching payload falls back
to the per-payload interactive path or fails closed. Consent stays interactive
for every entry that goes through this tooling: the confirmation is read from
`/dev/tty` and nothing else, no environment variable substitutes for the
interactive confirmation, and an unavailable terminal fails closed -- with the
same-user forgery limitation above as the honest boundary of that claim.
Receipts stay content-free and name the mode
explicitly (`authorization_mode: interim_operator_batch` on lane receipts,
`interim-operator-batch` plus the batch file digest in the wrapper's
schemaVersion-2 receipt). The default remains unavailable: with no broker and
no batch file the rail is closed and the reason is `host_authority_unavailable`.
The mode never sits above broker authority in the resolution order.

**Two-part sunset.** The primary reason for a sunset at all is the same-user
forgery gap above: only the out-of-process broker closes it. First,
capability-triggered: interim mode is forbidden the moment a broker probe on
the host reports `ready`. Both `batch-approve` and `verify-batch`, and the
wrapper itself, refuse with `broker available; interim mode retired on this
host`. No migration step, no flag, no grace period. A broker client that is
installed but does not probe ready is an UNKNOWN state, not a brokerless host:
it withholds interim mode as well, with reason `broker_present_not_ready`.
Absence of the client is the only state that leaves interim mode available.
Second, calendar-triggered: every batch file carries `program_sunset`, set to
2026-09-07 (about four weeks). After that date batch files fail validation, and
extending the program requires changing the sunset constant in
`payload-authorization.sh` -- a commit, which is a reviewed decision, not a
runtime choice. The window is four weeks because the darwin broker milestone is
scheduled inside it; the intent is that the broker retires this mode before the
calendar does.
