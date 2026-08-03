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
- Linux is the first production runtime. macOS shares the canonical protocol,
  receipt verification, public trust format, FIDO adapter, and client peer
  verification, but the daemon intentionally fails closed until launchd socket
  activation and macOS service packaging are implemented and tested.
- Broader Pipeline, dm-review, research, assessment, adversarial-review, Airlift,
  and direct interactive migration can follow without changing the shared
  protocol. Until each caller is migrated, it retains its existing fail-closed
  Codex fallback or exact-digest interactive gate.
- Live root/systemd installation, libfido2 hardware, worker-separated accounts,
  provider contact, and credential provisioning are acceptance evidence gates;
  local fixture tests cannot satisfy them.
