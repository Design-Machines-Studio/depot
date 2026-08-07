> **SUPERSEDED — NON-DISPATCHABLE HISTORICAL EVIDENCE.** This payload reviews verification-only plan revision 5 and its old eight prompts. It is not a verdict or implementation authorization for revision 6 external-provider dispatch.

# Cross-platform Workflow Authority Broker — OpenRouter Plan Adversary Payload

Review the exact artifacts below as read-only. Produce `VERDICT: APPROVED` or `VERDICT: REVISE`, prioritized findings with artifact anchors, and sprint-contract addenda assigning any required fixes to specific chunks.

The user-approved threat boundary is governing and must not be broadened:
- This is a simple two-person-team design.
- One authenticator-internal-UV FIDO approval per closed run binds a memory-only ephemeral Ed25519 run key.
- Docker/OrbStack is trusted host infrastructure.
- Candidate containers receive no Docker, broker, FIDO, credential, or service-manager surfaces.
- Deliberate developer/host-agent Docker tampering and fully compromised desktop/terminal spoofing are explicitly outside scope.
- Do not require a separate worker OS account, exclusive Docker engine, trusted-display authenticator, or approval station.
- Real systemd/launchd apply adapters must be implemented and tested against fake roots, but must not be invoked live in this task.

This is the third and final convergence review. Focus only on remaining execution blockers after the prior findings were integrated: operation admission, controlling-terminal handshake, frozen bounds, libfido2 key/version handling, legacy/v2 separation, recovery commands, shared verification, file ownership, parity, and authorization gates.

===== BEGIN plans/macos-authority-broker/original-prompt.md =====
# Original Prompt

## User Input

Implement a production-grade macOS host authority broker for Workflow Kernel repository verification as a separate Depot task.

Context and objective:
- Workflow Kernel 0.6.1 defines approve-verification-profile, plan-verification, run-verification, and record-verification-result with --receipt-key-stdin.
- The current Baseplate pipeline is blocked because no HOST_AUTHORITY_BROKER implementation is installed and DM_VERIFICATION_SUBSTRATE is unavailable.
- The broker must preserve the security boundary: repository/worker code must not read, mint, log, inherit, or pass the authority key through argv or environment.
- A chmod-600 plaintext key or same-user shell script is not acceptable.
- Target macOS with OrbStack, currently exposed at unix:///Users/trav/.orbstack/run/docker.sock.

Required work:
1. Inspect current Depot/Workflow Kernel architecture, AGENTS.md, relevant skills, schemas, CLI contracts, tests, and release/install conventions before designing.
2. Work only in the new isolated worktree; do not disturb existing Depot or Assembly/Baseplate worktrees and do not absorb unrelated changes.
3. Produce a threat model and select a practical macOS authority boundary using user-presence or equivalent host authorization (for example a native broker backed by Keychain/Secure Enclave or a narrowly scoped launchd/XPC service). Explain why repository workers cannot extract the key.
4. Implement the broker and its installation/uninstallation/status workflow. Never expose the key in stdout except the exact bounded receipt-key protocol response, or in logs, files, argv, environment, crash reports, receipts, or test fixtures.
5. Implement caller-produced DM_VERIFICATION_SUBSTRATE attestation for OrbStack/Docker, binding the actual Docker endpoint/engine, containment identity, resolved image digest, exact Go 1.26.5, generator/toolchain identity, run ID, and lifecycle cleanup. Do not accept a caller-invented opaque label as proof.
6. Integrate with Workflow Kernel’s documented HOST_AUTHORITY_BROKER pipe contract without weakening fail-closed semantics. Preserve repeated access across chunk, revision_batch, execution_level, merge_candidate, and provider-attestation operations.
7. Add adversarial tests for unauthorized invocation, same-user worker attempts, key exfiltration channels, replay/stale authorization, wrong repository/run/profile/candidate, altered substrate, symlink/path attacks, concurrent requests, cancellation, and cleanup.
8. Add operator documentation with exact setup/use/recovery/uninstall steps and a minimal Baseplate-compatible example that exports only non-secret broker/substrate handles.
9. Run all required repository validation according to Depot instructions. Use existing project skills and current documentation. Do not run release, push, PR, merge, tag, marketplace publication, or live installation without separate explicit authorization.
10. Hand off the implementation, threat-model decisions, test evidence, remaining risks, and the exact next authorization gate.

Start from the project default branch in the Codex-managed worktree.

## Date

2026-08-02

## Key Requirements Extracted

1. Inspect Depot and Workflow Kernel architecture, instructions, skills, schemas, CLI contracts, tests, and release/install conventions before design.
2. Keep all work inside the isolated Codex-managed Depot worktree based on the default branch, preserving unrelated worktrees and changes.
3. Define a macOS threat model and a practical host authority boundary with user presence or equivalent authorization that prevents repository workers from extracting the receipt key.
4. Implement broker setup, bounded receipt-key delivery, status, recovery, and uninstall without leaking the key through files, logs, argv, environment, crash reports, receipts, or fixtures.
5. Implement a caller-produced OrbStack/Docker substrate attestation bound to the real endpoint and engine, containment identity, resolved image digest, exact Go 1.26.5, generator/toolchain identity, run ID, and cleanup lifecycle.
6. Integrate with the existing fail-closed HOST_AUTHORITY_BROKER pipe contract and support repeated authority operations across all required verification boundaries and provider attestation.
7. Add adversarial coverage for authorization, same-user attacks, exfiltration, replay/staleness, binding mismatches, substrate alteration, path attacks, concurrency, cancellation, and cleanup.
8. Document exact operator setup, use, recovery, uninstall, and a Baseplate-compatible example exporting only non-secret handles.
9. Run Depot-required validation, but do not install live, release, commit, push, open a PR, merge, tag, or publish without separate authorization.
10. Hand off implementation evidence, threat-model decisions, remaining risks, and the exact next authorization gate.

## Iteration 1 Feedback

The user approved the following Phase 3 classifications without modification:

- `workflowClass`: `security`
- `decisionProfile`: `{"uncertainty":"high","consequence":"high","rationale":"The design changes the authority trust boundary, cryptographic receipt contract, native macOS service architecture, and verification substrate; mistakes could expose signing authority or falsely attest repository verification."}`

## Iteration 2 Feedback

After reviewing `plans/macos-authority-broker/plan.html`, the user responded `aspproved`. This explicitly approves the full plan, including decision D1: production uses the v2 asymmetric authority-provider contract and the public stdin HMAC pipe remains legacy compatibility only because it cannot satisfy the same-user threat model.

## Iteration 3 Feedback

The user rejected platform-specific product behavior after learning that the Swift/XPC implementation would not run on Linux:

- Linux will be the primary development platform moving forward.
- macOS and Linux must have parity; the product must not include security or workflow features that are unavailable on Linux.
- The previously approved Swift/XPC/Secure Enclave plan is superseded and no longer authorizes implementation.
- The user approved replacement planning around a Linux-first, cross-platform Go broker with a shared FIDO2/libfido2 user-presence and non-exportable-key boundary.
- Platform adapters may differ only where the operating systems require it, such as `systemd` versus `launchd` and Unix-socket peer credential APIs. User-facing operations, authorization semantics, receipt/substrate contracts, failure behavior, lifecycle commands, and adversarial coverage must remain equivalent.
- Existing partial macOS implementation work must remain paused until the replacement plan completes fresh adversarial review and receives a new explicit execution approval.

## Iteration 4 Feedback

The user approved the replacement research brief and its three decisions:

1. Production uses public FIDO-signed schema-v2 authority envelopes; raw `--receipt-key-stdin` remains explicit legacy compatibility only.
2. Authoritative Docker verification requires a separate worker OS principal denied access to the enrolled Docker socket, or a broker-exclusive engine/socket. The current same-user OrbStack endpoint is observational until this separation exists.
3. Linux and macOS use one Go core with a thin cgo adapter to pinned libfido2; only peer-credential and service-manager adapters differ.

## Iteration 5 Feedback

The user approved the corrected replacement implementation plan after its closed `decisionProfile` metadata was repaired to include the exact approved high/high rationale. This approval authorizes Phase 4 prompt and manifest generation plus adversarial plan review; it does not authorize implementation or any live, git-publication, installation, enrollment, or release action.

## Iteration 6 Feedback

After both adversarial lenses returned `REVISE`, the user explicitly selected the practical consent boundary and directed the design to avoid enterprise-scale over-hardening for the current two-person team:

- Keep the design as simple as possible while preserving the useful repository/candidate-code boundary.
- Production protects against candidate code, repository-controlled commands, accidental leakage, and unattended agent minting. A fully compromised developer desktop, deliberate developer tampering with Docker, and sophisticated consent-display spoofing are outside the supported threat boundary and must be documented honestly.
- The genuine broker displays the exact run scope in the operator-initiated terminal and requires authenticator-internal UV. The user accepts that this is not a cryptographically trusted display.
- Use one FIDO approval per closed run rather than one touch per operation. The daemon generates an ephemeral run signing key held only in root-process memory; the FIDO assertion binds its public key and run scope. Repeated operation/result/cleanup envelopes are signed by that ephemeral key. Restart or expiry destroys the run authority and requires another FIDO approval.
- Treat the enrolled Docker engine as trusted host infrastructure. Candidate containers must not receive Docker, broker, FIDO, credential, or service-manager access. The broker still measures and revalidates endpoint, engine, image, container, Go 1.26.5, generator, exact workload, and cleanup, but does not claim resistance to a developer or host agent that intentionally controls the same Docker daemon.
- Continue to implement real install/status/recovery/uninstall adapters, but do not invoke them live without a later authorization gate.
===== END plans/macos-authority-broker/original-prompt.md =====

===== BEGIN plans/macos-authority-broker/assessment.html =====
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="generator" content="depot pipeline">
  <meta name="pipeline-artifact" content="assessment">
  <title>Assessment: cross-platform Workflow Authority Broker</title>
  <style>
    :root { color-scheme: light dark; --measure: 72rem; } * { box-sizing: border-box; }
    body { margin: 0; font: 1rem/1.6 system-ui, sans-serif; background: Canvas; color: CanvasText; }
    main, header, footer { max-width: var(--measure); margin: auto; padding: 1rem; }
    h1, h2, h3 { line-height: 1.2; } code { font-family: ui-monospace, monospace; }
    table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid GrayText; padding: .5rem; text-align: left; vertical-align: top; }
    .callout { border-inline-start: .3rem solid Highlight; padding-inline-start: 1rem; }
  </style>
</head>
<body>
<header><p>Pipeline reassessment · 2026-08-02 · supersedes the macOS-only assessment</p></header>
<main>
  <h1>Assessment: cross-platform Workflow Authority Broker</h1>
  <section>
    <h2>Change in scope</h2>
    <p>The user has made Linux the primary development platform and requires feature parity with macOS. The previously approved Swift/XPC/Secure Enclave design is therefore invalid: its central security, IPC, packaging, and test paths cannot execute on Linux. Existing partial Swift work is paused historical work, not an implementation baseline.</p>
    <div class="callout"><p><strong>Selected direction:</strong> one Go broker and protocol core on Linux and macOS. One authenticator-internal-UV FIDO approval opens a closed run and binds a memory-only ephemeral signing key for its repeated operations. Platform adapters are limited to Unix peer credentials and service management; Docker is trusted host infrastructure on both systems.</p></div>
  </section>
  <section>
    <h2>Key requirements</h2>
    <ol>
      <li>Inspect Depot and Workflow Kernel architecture, schemas, CLI contracts, tests, and release/install conventions before design.</li>
      <li>Keep work isolated and preserve unrelated worktrees and the pre-existing <code>CLAUDE.md</code> Airlift marker.</li>
      <li>Deliver the same broker operations, authorization semantics, failure behavior, substrate evidence, lifecycle workflow, and adversarial coverage on Linux and macOS; Linux is primary.</li>
      <li>Use one FIDO approval per closed run to bind a memory-only ephemeral signing key so repository workers cannot extract authority or mint unattended runs.</li>
      <li>Never place secret authority material in stdout, logs, files, argv, environment, crash reports, receipts, or fixtures. Public outputs are signed bounded envelopes and non-secret handles only.</li>
      <li>Bind Docker substrate evidence to the real enrolled Unix endpoint and engine, exact containment identity, immutable image digest, Go 1.26.5, generator/toolchain identity, run/candidate/profile scope, and cleanup proof. OrbStack is the macOS adapter, not the product model.</li>
      <li>Preserve fail-closed Workflow Kernel semantics and repeated operations across chunk, revision batch, execution level, merge candidate, and provider attestation.</li>
      <li>Cover unauthorized invocation, key exfiltration, replay/staleness, binding mismatch, altered substrate, candidate control-surface access, path attacks, concurrency, cancellation, and cleanup on both operating systems.</li>
      <li>Provide parity installation, status, recovery, rotation/revocation, and uninstall workflows for <code>systemd</code> and <code>launchd</code>, plus a Baseplate example exporting only non-secret handles.</li>
      <li>Run Depot validation without live install, enrollment, release, commit, push, PR, merge, tag, or publication until separately authorized.</li>
    </ol>
  </section>
  <section>
    <h2>Current code state</h2>
    <table>
      <thead><tr><th>Area</th><th>Assessment</th></tr></thead>
      <tbody>
        <tr><td>Workflow Kernel 0.6.1</td><td>The released HMAC stdin contract and current closed repository-verification schemas are the compatibility baseline. Partial uncommitted v2 asymmetric-provider work may be audited and reused only after its operation vocabulary, verification trust root, and shared golden vectors are proven.</td></tr>
        <tr><td>Swift prototype</td><td>Six uncommitted files under <code>native/workflow-authority-macos</code> establish protocol ideas but violate the new parity requirement. The replacement plan must remove or quarantine them; no Swift-only production surface remains.</td></tr>
        <tr><td>Docker substrate</td><td>The kernel currently accepts an opaque <code>DM_VERIFICATION_SUBSTRATE</code> value. Production must instead resolve a non-secret handle to broker-signed, live-observed evidence. Linux Docker Engine and macOS OrbStack must share one attestation schema and lifecycle state machine.</td></tr>
        <tr><td>Repository state</td><td>The branch is based on the project default branch. Only task-owned partial files plus the pre-existing <code>CLAUDE.md</code> Airlift marker are present. No commit, install, or external publication has occurred.</td></tr>
      </tbody>
    </table>
  </section>
  <section>
    <h2>Security assessment</h2>
    <ul>
      <li>A same-user worker can invoke ordinary user processes and redirect pipes; a pathname, chmod-600 key, shell producer, or environment token is not an authority boundary.</li>
      <li>A single FIDO2 assertion binds the exact closed-run digest and an ephemeral public key without exporting either private key. The broker shows the run scope once; the daemon signs repeated operations with the memory-only run key until expiry, restart, or revocation.</li>
      <li>Unix peer credentials identify the local caller and support fixed-service checks. Human intent comes from the one run-opening FIDO approval; peer credentials are not treated as a separate consent ceremony.</li>
      <li>Exact parity means equivalent guarantees, not identical OS syscalls: <code>SO_PEERCRED</code>/<code>systemd</code> and <code>getpeereid</code>/<code>launchd</code> are narrow adapters behind shared acceptance tests.</li>
      <li>The enrolled Docker engine is trusted host infrastructure. Candidate containers receive no Docker, broker, FIDO, credential, or service-manager surface; deliberate developer/host-agent Docker tampering and a fully compromised desktop are documented outside scope.</li>
      <li>Hardware absence is a fail-closed availability gap on both platforms. There is no software-key or host-PIN fallback.</li>
    </ul>
  </section>
  <section>
    <h2>Classification and next phase</h2>
    <p><strong>Full mode; workflow class security; uncertainty high; consequence high.</strong> The work crosses cryptographic authorization, local IPC, service packaging, Docker lifecycle, Python/Go protocol compatibility, and two operating systems. The design intentionally protects candidate-code and accidental/unattended-agent boundaries without claiming resistance to a fully compromised developer host.</p>
  </section>
</main>
<footer><p>Pipeline planning artifact. No implementation authorization is conveyed by this assessment.</p></footer>
<script type="application/json" id="pipeline-data">{"artifact":"assessment","slug":"macos-authority-broker","revision":4,"supersedes":"macOS-only and hostile-host assessments","workflowClass":"security","decisionProfile":{"uncertainty":"high","consequence":"high","rationale":"Cross-platform cryptographic authority, local IPC, Docker attestation, and lifecycle mistakes could expose signing authority or falsely attest verification."},"keyRequirements":["Inspect Depot and Workflow Kernel architecture, schemas, CLI contracts, tests, and release/install conventions before design.","Keep work isolated and preserve unrelated worktrees and the pre-existing CLAUDE.md Airlift marker.","Deliver the same broker operations, authorization semantics, failure behavior, substrate evidence, lifecycle workflow, and adversarial coverage on Linux and macOS; Linux is primary.","Use one internal-UV FIDO approval per closed run to bind a memory-only ephemeral signing key.","Never place secret authority material in stdout, logs, files, argv, environment, crash reports, receipts, or fixtures.","Bind Docker substrate evidence to the trusted enrolled endpoint and engine, containment identity, immutable image digest, exact Go 1.26.5, generator/toolchain identity, run scope, and cleanup proof.","Preserve fail-closed Workflow Kernel semantics and repeated cadence/provider operations.","Prevent candidate containers from receiving Docker, broker, FIDO, credential, or service-manager control surfaces.","Provide parity install, status, recovery, rotation/revocation, uninstall, and Baseplate documentation.","Run validation without live install, enrollment, release, commit, push, PR, merge, tag, or publication until separately authorized."],"testPersonas":["operator","trusted host broker","unattended repository process","contained verification child","replay attacker"],"recentLessons":["Installed launcher behavior is part of release proof.","Unavailable or skipped lanes remain coverage gaps."],"baselineScreenshots":[]}</script>
</body>
</html>
===== END plans/macos-authority-broker/assessment.html =====

===== BEGIN plans/macos-authority-broker/research.html =====
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="generator" content="depot pipeline">
  <meta name="pipeline-artifact" content="research">
  <title>Research: cross-platform Workflow Authority Broker</title>
  <style>
    :root { color-scheme: light dark; --measure: 74rem; } * { box-sizing: border-box; }
    body { margin: 0; font: 1rem/1.6 system-ui, sans-serif; background: Canvas; color: CanvasText; }
    main, header, footer { max-width: var(--measure); margin: auto; padding: 1rem; }
    h1, h2, h3 { line-height: 1.2; } code, pre { font-family: ui-monospace, monospace; }
    pre { overflow: auto; padding: .75rem; border: 1px solid GrayText; }
    table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid GrayText; padding: .5rem; text-align: left; vertical-align: top; }
    .critical { border-inline-start: .35rem solid #c33; padding-inline-start: 1rem; }
    .selected { border-inline-start: .35rem solid Highlight; padding-inline-start: 1rem; }
    a { color: LinkText; }
  </style>
</head>
<body>
<header><nav><a href="assessment.html">Assessment</a> · Research</nav><p>Replacement research brief · 2026-08-03</p></header>
<main>
  <h1>Research: Linux-first, cross-platform Workflow Authority Broker</h1>
  <section>
    <h2>Executive conclusion</h2>
    <p>Linux and macOS can share the same security and product contract through one Go broker core, a thin cgo adapter to libfido2, pathname Unix-domain sockets, canonical public authority envelopes, and direct Docker Engine API attestation. Only peer-credential calls and service-manager packaging differ.</p>
    <div class="critical">
      <p><strong>Raw-key impossibility:</strong> a public <code>HOST_AUTHORITY_BROKER | workflow-kernel --receipt-key-stdin</code> producer cannot defend against a malicious same-UID worker. The worker can invoke, redirect, interpose on, or debug the consumer. Production must never export a receipt key; it must verify public FIDO-signed envelopes. The stdin-HMAC path may remain only as explicit schema-v1 compatibility.</p>
      <p><strong>Practical Docker boundary:</strong> Docker-daemon access is powerful host authority, so the broker never mounts or forwards the Docker socket into candidate containers. For this two-person deployment the enrolled host engine is trusted infrastructure. Deliberate developer or host-agent control of that engine is outside scope and must not be represented as a hostile-host guarantee.</p>
    </div>
  </section>

  <section>
    <h2>Selected cross-platform architecture</h2>
    <table>
      <thead><tr><th>Layer</th><th>Shared contract</th><th>Platform adapter</th></tr></thead>
      <tbody>
        <tr><td>Core binaries</td><td>Go module producing <code>workflow-authorityd</code> and <code>workflow-authority</code>; common protocol, policy, canonical JSON, FIDO verification, replay ledger, Docker client, redaction, and lifecycle.</td><td>None.</td></tr>
        <tr><td>Authority</td><td>CTAP2 ES256 credential, fixed domain-separated RP ID, explicit credential allow-list, signed UP and UV flags, request-bound challenge, enrolled public key and revocation generation only. Private key remains in the authenticator.</td><td>libfido2 uses the native HID transport on both systems.</td></tr>
        <tr><td>IPC</td><td>Root-owned pathname <code>SOCK_STREAM</code> socket, bounded length-prefixed frames, closed schemas, no ancillary descriptors, mutual server/client checks, fixed installation path, no repository-selected provider command.</td><td>Linux <code>SO_PEERCRED</code>; macOS <code>getpeereid</code> plus peer-PID evidence where available.</td></tr>
        <tr><td>Service lifecycle</td><td>Identical commands and exit/status model: <code>install</code>, <code>enroll-key</code>, <code>enroll-endpoint</code>, <code>status</code>, <code>doctor</code>, <code>rotate-key</code>, <code>revoke-key</code>, <code>uninstall</code>, and explicit <code>uninstall --purge</code>.</td><td>systemd socket/service units on Linux; launchd socket activation on macOS.</td></tr>
        <tr><td>Substrate</td><td>Direct Docker Engine API over an enrolled Unix socket; live engine/image/container/toolchain measurements; exact broker-owned execution and cleanup state machine; one signed attestation schema.</td><td>Linux Docker/rootless Docker endpoint or OrbStack on macOS; both are trusted host infrastructure and are never exposed inside candidate containers.</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>FIDO authorization ceremony</h2>
    <p>Enrollment requires CTAP2, ES256, a non-discoverable credential, fixed RP identity, user presence, user verification, and verified enrollment output. Root-owned state stores only the credential reference, public key, algorithm, generation, policy, and revocation metadata.</p>
    <pre>clientDataHash = SHA-256(
  "workflow-kernel-authority-v2\0" || canonical_authority_request
)</pre>
    <p>One run-opening assertion verifies the fixed RP hash, enrolled credential, signed UP/UV flags, assertion signature, canonical closed-run digest, server nonce, issuance/expiry, and exact repository/run/profile/candidate/substrate bindings. It also binds a newly generated ephemeral Ed25519 public key. The daemon then signs the run's plan, execution, result, provider, cleanup, and receipt envelopes with that memory-only key and destroys it on restart, revocation, or expiry.</p>
    <p><strong>Consent limitation:</strong> ordinary security keys do not display the canonical request. The genuine client renders the exact closed run scope before requesting authenticator-internal UV; there is no host PIN input path. A fully compromised desktop could spoof that terminal display, which is an accepted residual risk for this small-team deployment rather than a feature the broker claims to solve.</p>
  </section>

  <section>
    <h2>Authority-provider contract</h2>
    <p>The partial schema-v2 provider work is directionally correct but must be audited rather than accepted wholesale. The response needs FIDO evidence: stable credential reference, authenticator data, client-data hash, assertion signature, RP ID hash, algorithm, public-key generation, signed UP/UV flags, and optional counter evidence. Python verifies this public envelope against the root-owned enrolled public-key registry and the exact request it generated.</p>
    <p>The shared operation vocabulary is fixed across Go, Python, schemas, golden fixtures, and documentation: <code>approve_profile</code>, <code>plan_verification</code>, <code>run_verification</code>, <code>record_result</code>, <code>provider_attestation</code>, <code>verify_envelope</code>, substrate lifecycle operations, key lifecycle operations, <code>status</code>, and <code>doctor</code>. Unknown operations and schema/mode mixing fail closed.</p>
    <p>No production API returns secret bytes. The bounded stdout response is public signed JSON only. Legacy HMAC tests remain deliberately separate and cannot be selected by fallback.</p>
  </section>

  <section>
    <h2>IPC, replay, and concurrency</h2>
    <ul>
      <li>The service-manager owns the socket parent and socket; symlinks, parent swaps, wrong owner/mode, oversized frames, unknown fields, descriptor passing, environment overrides, and caller executable paths are rejected.</li>
      <li>Peer credentials are eligibility evidence, not human intent. Direct same-user invocation cannot open a run without the one FIDO ceremony, and cannot extend the resulting closed scope.</li>
      <li>The run assertion and each ephemeral envelope use fresh nonces, a strictly increasing sequence, and bounded expiry. Idempotency reuse with different content fails; exact duplicate committed requests may return the same public result.</li>
      <li>Authenticator access is serialized; queues and per-peer/repository prompt rates are bounded; state transitions use per-run locks; cancellation propagates through FIDO I/O, Docker execution, and cleanup.</li>
      <li>Core dumps are disabled, diagnostic codes are closed and redacted, and secrets/PINs/request bodies never enter logs, argv, environment, fixtures, or crash metadata.</li>
    </ul>
  </section>

  <section>
    <h2>Docker substrate evidence</h2>
    <table>
      <thead><tr><th>Stage</th><th>Required observations and controls</th></tr></thead>
      <tbody>
        <tr><td>Endpoint enrollment/use</td><td>Normalized no-follow Unix socket; opened-descriptor identity, owner and mode; daemon connection; <code>/_ping</code>; negotiated API; <code>/version</code>; <code>/info</code>; stable engine ID, OS/architecture, runtime/security facts. Ignore <code>DOCKER_HOST</code>.</td></tr>
        <tr><td>Image</td><td>Resolve caller reference to immutable <code>sha256:</code> image ID and available repository/manifest digest; create by immutable ID; inspect actual container <code>.Image</code> and reject drift.</td></tr>
        <tr><td>Containment</td><td>Broker-generated ID/name/nonce and root-ledger ownership; non-root user; no privileged mode or Docker socket; network off unless approved; read-only root; all capabilities dropped; no-new-privileges; controlled mounts; CPU/memory/PID/output/time limits; exact argv without shell.</td></tr>
        <tr><td>Toolchain/workload</td><td>Trusted pre-workload probe requires <code>go version</code> exactly <code>go1.26.5</code>, Go env identity, generator path/version/SHA-256, canonical argv, image and container IDs, repository/run/profile/candidate scope, and authority-request digest.</td></tr>
        <tr><td>Cleanup</td><td>Stop/kill and remove container/anonymous volumes after success, failure, timeout, cancellation, or recovery; verify absence; record cleanup result. Reconcile only exact IDs in the root ledger. Unverified cleanup makes the attestation non-passing.</td></tr>
      </tbody>
    </table>
    <p><code>DM_VERIFICATION_SUBSTRATE</code> exports only a non-secret broker handle. The kernel resolves and validates the signed attestation; a caller-invented label, Docker context name, image tag, or forged ownership label is never proof.</p>
  </section>

  <section>
    <h2>Adversarial proof required on both platforms</h2>
    <ul>
      <li>Unauthorized peer/server, direct same-user invocation, prompt flooding, missing UP/UV, wrong credential/RP/signature, revoked generation.</li>
      <li>Stale/future/replayed/duplicate/reordered/cross-boot requests and wrong repository/run/profile/candidate/lane/provider/substrate.</li>
      <li>Unicode and maximum-boundary canonical vectors shared by Go and Python; stdout/stderr/log/argv/environment/core/crash exfiltration scans.</li>
      <li>Symlink, parent, socket, and repository path races; concurrent assertions; cancellation at every lifecycle stage.</li>
      <li>Mutable image race, engine/API/toolchain/generator/container drift, worker attach/exec/kill attempts, daemon restart, cleanup failure, forged labels, and exact-ID reconciliation.</li>
      <li>Install/status/recovery/rotation/revocation/uninstall idempotence and identical protocol/status/exit behavior on Linux and macOS CI.</li>
      <li>Candidate containers are tested to receive no Docker socket, broker socket, FIDO device, host credential, or service-manager surface.</li>
    </ul>
  </section>

  <section>
    <h2>Primary references</h2>
    <ul>
      <li><a href="https://developers.yubico.com/libfido2/index.html">Yubico libfido2</a>: Linux/macOS support and credential/assertion API role.</li>
      <li><a href="https://fidoalliance.org/specs/fido-v2.2-ps-20250714/fido-client-to-authenticator-protocol-v2.2-ps-20250714.html">FIDO Alliance CTAP 2.2</a>: UP/UV, authenticator-held credentials, assertions, cancellation, and counters.</li>
      <li><a href="https://man7.org/linux/man-pages/man7/unix.7.html">Linux unix(7)</a>: <code>SO_PEERCRED</code>.</li>
      <li><a href="https://keith.github.io/xcode-man-pages/getpeereid.3.html">macOS getpeereid(3)</a>: peer effective UID/GID.</li>
      <li><a href="https://man7.org/linux/man-pages/man5/systemd.socket.5.html">systemd.socket(5)</a> and <a href="https://keith.github.io/xcode-man-pages/launchd.plist.5.html">launchd.plist(5)</a>: socket activation.</li>
      <li><a href="https://docs.docker.com/engine/security/">Docker daemon attack surface</a>, <a href="https://docs.docker.com/engine/install/linux-postinstall/">Docker non-root access warning</a>, and <a href="https://docs.docker.com/reference/api/engine/">Docker Engine API</a>.</li>
    </ul>
  </section>

  <section class="selected">
    <h2>User-approved practical threat boundary</h2>
    <p>Iteration 6 narrows the production goal to the current two-person team: prevent candidate/repository code, accidental leakage, and unattended agents from exporting or silently minting authority. A fully compromised developer desktop, deliberate developer Docker control-plane tampering, and cryptographically trusted consent display are outside scope and are documented residual risks.</p>
    <p>One authenticator-internal-UV FIDO assertion authorizes a closed run and binds an ephemeral run-signing public key. The root daemon holds the ephemeral private key in memory only and uses it for exact operation, observed-result, provider, and cleanup envelopes. Restart or expiry discards the key and requires a new FIDO approval. The enrolled Docker engine is trusted host infrastructure; candidate containers receive none of its control surfaces.</p>
  </section>

  <section class="selected">
    <h2>Research gate recommendations</h2>
    <ol>
      <li>Approve schema-v2 public FIDO authority envelopes as the only production contract. Retain raw receipt-key stdin solely for explicit legacy compatibility tests.</li>
      <li>Approve the enrolled Docker/OrbStack engine as trusted host infrastructure. Require candidate containers to receive no Docker or broker control surface, and document deliberate developer/host-agent engine tampering as outside scope.</li>
      <li>Approve a thin cgo adapter to pinned libfido2 rather than a Swift implementation or an immature pure-Go CTAP stack.</li>
    </ol>
  </section>
</main>
<footer><p>Pipeline research artifact. No live service, key, endpoint, package, or installation was changed.</p></footer>
<script type="application/json" id="pipeline-data">{"artifact":"research","slug":"macos-authority-broker","revision":4,"selectedArchitecture":{"language":"Go","fido":"libfido2 via thin cgo adapter","productionAuthority":"one FIDO-authorized ephemeral run key and public schema-v2 envelopes","ipc":"pathname Unix SOCK_STREAM","linuxAdapters":["SO_PEERCRED","systemd socket activation"],"macosAdapters":["getpeereid and peer PID evidence","launchd socket activation"],"substrate":"direct Docker Engine API with trusted host engine and candidate control surfaces excluded"},"criticalConstraints":["Never export a production receipt key or ephemeral run private key to a repository worker.","Never expose Docker, broker, FIDO, credential, or service-manager surfaces inside candidate containers.","Require the same protocol, operations, authorization, lifecycle, failures, and tests on Linux and macOS."],"researchGate":["Approve one FIDO authorization per closed run with public ephemeral-key envelopes.","Approve the enrolled Docker engine as trusted host infrastructure.","Approve Go plus libfido2 cgo."],"sources":["https://developers.yubico.com/libfido2/index.html","https://fidoalliance.org/specs/fido-v2.2-ps-20250714/fido-client-to-authenticator-protocol-v2.2-ps-20250714.html","https://man7.org/linux/man-pages/man7/unix.7.html","https://keith.github.io/xcode-man-pages/getpeereid.3.html","https://man7.org/linux/man-pages/man5/systemd.socket.5.html","https://keith.github.io/xcode-man-pages/launchd.plist.5.html","https://docs.docker.com/engine/security/","https://docs.docker.com/engine/install/linux-postinstall/","https://docs.docker.com/reference/api/engine/"]}</script>
</body>
</html>
===== END plans/macos-authority-broker/research.html =====

===== BEGIN plans/macos-authority-broker/plan.html =====
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="generator" content="depot pipeline">
  <meta name="pipeline-artifact" content="plan">
  <title>Plan: cross-platform Workflow Authority Broker</title>
  <style>
    :root { color-scheme: light dark; --measure: 76rem; } * { box-sizing: border-box; }
    body { margin: 0; font: 1rem/1.58 system-ui, sans-serif; background: Canvas; color: CanvasText; }
    main, header, footer { max-width: var(--measure); margin: auto; padding: 1rem; }
    h1, h2, h3 { line-height: 1.2; } code { font-family: ui-monospace, monospace; }
    table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid GrayText; padding: .5rem; text-align: left; vertical-align: top; }
    .callout { border-inline-start: .35rem solid Highlight; padding-inline-start: 1rem; }
    .warning { border-inline-start: .35rem solid #c33; padding-inline-start: 1rem; }
    a { color: LinkText; }
  </style>
</head>
<body>
<header><nav><a href="assessment.html">Assessment</a> · <a href="research.html">Research</a> · Plan</nav><p>Replacement implementation plan · 2026-08-03</p></header>
<main>
  <h1>Plan: Linux-first, cross-platform Workflow Authority Broker</h1>
  <section>
    <h2>Outcome</h2>
    <p>Replace the paused Swift/XPC direction with one Go authority companion that behaves identically on Linux and macOS. One authenticator-internal-UV FIDO approval binds a closed run scope and an ephemeral run-signing public key. The root daemon holds the private run key in memory only, signs every operation/result/cleanup envelope, and destroys it on restart or expiry. No production authority key is exported.</p>
    <div class="callout">
      <p><strong>Authorized after the later execution gate:</strong> task-owned source, schemas, tests, packaging definitions, documentation, and non-mutating/offline validation in this worktree.</p>
      <p><strong>Still excluded:</strong> live installation, root service registration, real FIDO enrollment, endpoint enrollment, release, commit, staging, push, PR, merge, tag, marketplace publication, or changes to Assembly/Baseplate worktrees.</p>
    </div>
  </section>

  <section>
    <h2>Production trust boundary</h2>
    <ol>
      <li><strong>Fixed Go companion:</strong> a root-owned <code>workflow-authorityd</code> and fixed-path <code>workflow-authority</code> client implement closed, length-bounded JSON over a root-owned pathname Unix socket. Repository configuration carries only a non-secret provider handle; it cannot select an executable or socket path.</li>
      <li><strong>FIDO run authorization:</strong> the operator initiates approval in the genuine client, which displays the exact run/repository/profile/candidate/expiry scope in its terminal. libfido2 1.17.0 requires CTAP2 ES256 plus authenticator-internal UP/UV; host PIN entry is unsupported. The FIDO assertion binds the closed run scope and ephemeral signing public key. Terminal spoofing by a compromised developer desktop is an accepted documented residual risk.</li>
      <li><strong>Consent and admission:</strong> protocol stdin/stdout remain machine-only. When a run is not active, the client renders the daemon challenge and reads one confirmation from its controlling terminal; no terminal fails closed. Key rotation, revocation, enrollment, and Docker endpoint enrollment remain UID-0 root-console operations unreachable from Workflow Kernel.</li>
      <li><strong>Ephemeral evidence chain:</strong> the daemon signs each plan, execution authorization, observed result, provider attestation, substrate observation, cleanup result, and final receipt with the in-memory run key using fresh nonces/sequences. Historical verification checks the recorded FIDO run authorization, public run key, and complete signature/digest chain without live daemon trust.</li>
      <li><strong>Kernel verification:</strong> the fixed Go client verifies FIDO and ephemeral signatures; Python independently reconstructs and compares every canonical binding and chain digest. Absence, substitution, removal, reordering, mismatch, downgrade, or ambiguity fails closed.</li>
      <li><strong>Candidate containment:</strong> candidate code and repository-controlled commands execute only inside the broker-created container, which receives no broker socket, Docker socket, FIDO device, host credential, authority state, or service-management interface.</li>
      <li><strong>Docker authority:</strong> the daemon alone opens the enrolled endpoint and derives engine, immutable image, exact container, Go 1.26.5, generator, workload, run, and cleanup evidence from live Engine API responses. Passing status requires exact-ID absence proof after cleanup.</li>
      <li><strong>Parity:</strong> Linux <code>SO_PEERCRED</code>/systemd and macOS <code>getpeereid</code>/launchd adapters implement one shared interface and contract suite. There are no macOS-only authority, substrate, lifecycle, recovery, or operator features.</li>
    </ol>
    <div class="warning"><p>The enrolled Docker engine is trusted host infrastructure. The broker attests what it observes and prevents candidate containers from receiving Docker/broker/FIDO access, but it does not claim resistance to a developer or host agent deliberately controlling the same daemon. That narrower boundary is intentional for the current two-person team.</p></div>
  </section>

  <section>
    <h2>Chunk decomposition</h2>
    <table>
      <thead><tr><th>ID</th><th>Scope</th><th>Acceptance evidence</th><th>Depends on</th></tr></thead>
      <tbody>
        <tr><td>01<br><code>authority-contract-reset</code></td><td>Define the FIDO-authorized ephemeral run-key chain: run authorization, operation envelope, observed substrate/result, cleanup result, and final receipt roles; freeze vocabulary/golden vectors; preserve explicit v1 read compatibility.</td><td>Every artifact identifies exact signed bytes and prior digest; historical verification works offline; HMAC/v2 mixing, altered/reordered/missing chain elements, wrong bindings, and unknown operations fail.</td><td>—</td></tr>
        <tr><td>02<br><code>go-core-foundation</code></td><td>Create the Go 1.26.5 shared core plus a digest-pinned <code>golang:1.26.5-trixie</code> test image, canonical protocol, ephemeral-key interfaces, fakes, and thin binaries. Remove the Swift prototype.</td><td>Pinned container tests and cross-language vectors pass; malformed/secret surfaces fail; no OS-only semantic path remains.</td><td>01</td></tr>
        <tr><td>03<br><code>fido-ipc-authority</code></td><td>Implement pinned libfido2 1.17.0, internal-UV run approval, terminal scope display, in-memory ephemeral run signer, enrollment/rotation/loss recovery, replay state, IPC, and OS peer adapters.</td><td>One FIDO approval creates only a closed expiring in-memory run authority; repeated operation signatures chain correctly; restart/expiry/revocation invalidate it; no host PIN or exported key exists.</td><td>02</td></tr>
        <tr><td>04<br><code>docker-substrate</code></td><td>Implement enrolled trusted-engine observations, immutable image/container execution, exact Go/generator measurement, candidate control-surface exclusion, signed result/cleanup chain, and exact-ID recovery.</td><td>Endpoint/image/toolchain/cleanup drift fails; candidate receives no Docker/broker/FIDO access; deliberate host-daemon tampering remains explicitly outside the threat model.</td><td>03</td></tr>
        <tr><td>05<br><code>kernel-cadence-integration</code></td><td>Wire the complete FIDO run authorization → ephemeral operation/result → cleanup → final receipt chain through every cadence boundary; finish both Go composition roots and the daemon-independent historical verifier. Retain stdin HMAC as explicit legacy-only.</td><td>Python and Go verify the full chain offline; real binaries select production backends; repeated operations require no extra touch but cannot exceed the closed run scope.</td><td>01, 04</td></tr>
        <tr><td>06<br><code>cross-platform-packaging</code></td><td>Implement real injectable Linux/systemd and macOS/launchd apply adapters for install/status/recovery/uninstall plus staging, rollback, libfido2 1.17.0 preflight, and shared admin commands. Test against temporary/fake roots; do not invoke live.</td><td>Real code paths exist for both OSes, parity tests cover every lifecycle state, rollback is atomic, and no live privileged mutation runs.</td><td>03, 04</td></tr>
        <tr><td>07<br><code>parity-adversarial-harness</code></td><td>Add shared protocol/chain fixtures, Linux/macOS adapter harnesses, scoped same-user/candidate attacks, cancellation/concurrency/recovery tests, and validator inventories.</td><td>Tests prove unattended minting/key extraction and candidate control-surface access fail; deliberate developer desktop/Docker tampering is documented outside scope; unavailable native hardware/service lanes remain gaps.</td><td>05, 06</td></tr>
        <tr><td>08<br><code>docs-metadata-validation</code></td><td>Migrate canonical Pipeline/Assembly consumers to v2 handles, then document the practical threat model, evidence chain, parity lifecycle, trusted-host Docker assumption, Baseplate example, versions, and repository conventions.</td><td>Canonical consumers no longer prescribe production raw-key stdin or opaque substrate labels; dependencies, generated surfaces, docs, and validators agree; no release occurs.</td><td>07</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>Stable file ownership</h2>
    <ul>
      <li><strong>Chunks 01/05:</strong> <code>plugins/workflow-kernel/skills/workflow-kernel/references/*authority*</code>, repository-verification schemas, <code>workflow_kernel/authority_provider.py</code>, receipt/CLI/planning/execution/provider modules, and focused Python tests.</li>
      <li><strong>Chunks 02–04/06:</strong> new <code>native/workflow-authority/</code> Go module, internal protocol/FIDO/IPC/state/Docker/platform packages, commands, fixtures, service resources, packaging metadata, and Go tests. The obsolete Swift directory is removed in chunk 02.</li>
      <li><strong>Chunk 07:</strong> top-level validation scripts and shared hostile/parity tests. It does not own consumer documentation or modify external Assembly/Baseplate repositories.</li>
      <li><strong>Chunk 08:</strong> canonical Pipeline/Assembly consumers, Workflow Kernel and Depot docs including the Baseplate example, dependency checks, <code>AGENTS.md</code>/<code>CLAUDE.md</code> convention changes, canonical plugin/marketplace versions, generated aliases/manifests, and validation evidence.</li>
    </ul>
  </section>

  <section>
    <h2>Decisions and tradeoffs</h2>
    <table>
      <thead><tr><th>ID</th><th>Decision</th><th>Reason / rejected alternative</th></tr></thead>
      <tbody>
        <tr><td>D1</td><td>One Go core plus pinned libfido2 cgo on Linux and macOS.</td><td>Provides a mature shared CTAP implementation. Swift/XPC and Secure Enclave are rejected because Linux cannot run them; a new pure-Go CTAP implementation is too risky for this boundary.</td></tr>
        <tr><td>D2</td><td>Public FIDO schema-v2 envelopes are production; stdin HMAC is legacy-only.</td><td>A same-UID worker can capture or debug raw-key consumers. No automatic fallback is allowed.</td></tr>
        <tr><td>D3</td><td>One FIDO assertion authorizes a closed run and binds an ephemeral in-memory signing key.</td><td>This keeps repeated cadence usable without exporting a bearer or stable host key. Restart/expiry requires reauthorization.</td></tr>
        <tr><td>D4</td><td>Require authenticator-internal UP/UV; do not implement host PIN handling.</td><td>This is the simplest parity policy. Hardware that cannot perform internal UV is unavailable.</td></tr>
        <tr><td>D5</td><td>Fixed root-owned provider/socket identity and bidirectional peer checks.</td><td>Peer UID alone cannot identify human intent or trusted code. Repository-selected provider paths and environment overrides are rejected.</td></tr>
        <tr><td>D6</td><td>Trust the enrolled host Docker engine and exclude its control surfaces from candidate containers.</td><td>The product defends against candidate code and unattended minting, not deliberate developer/host-agent daemon tampering. This is proportionate for the current team.</td></tr>
        <tr><td>D7</td><td>Direct Docker Engine API with immutable image/container IDs and cleanup as validity.</td><td>CLI contexts, tags, opaque labels, and best-effort cleanup do not bind actual execution.</td></tr>
        <tr><td>D8</td><td>Equivalent contract tests on both OSes; Linux is the primary full lane.</td><td>Cross-compilation alone does not prove peer credentials or service lifecycle. Platform gaps are explicit acceptance gaps.</td></tr>
        <tr><td>D9</td><td>Default uninstall preserves public verification/revocation/audit metadata; purge is explicit root-console recovery and uses FIDO when available.</td><td>Historical receipts remain verifiable while lost-authenticator recovery stays possible.</td></tr>
        <tr><td>D10</td><td>No live install, hardware enrollment, endpoint enrollment, release, or git publication in this task without a later gate.</td><td>Those mutate privileged or external state beyond the current authorization.</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>Verification strategy</h2>
    <ol>
      <li>Focused schema/Python tests after chunk 01.</li>
      <li>Pinned Go 1.26.5 Linux container tests, race tests where supported, static analysis, golden-vector comparison, and secret-surface scans after Go chunks.</li>
      <li>macOS build/unit adapter proof using the same Go version and pinned libfido2 ABI; signed launchd/hardware acceptance remains a separately authorized host gate.</li>
      <li>Fake Engine/libfido2 tests for deterministic failure injection plus separately gated real-device and live-service acceptance.</li>
      <li>Workflow Kernel focused and full offline gate, dual-compat generation checks, dependency checks, and full composition validation.</li>
      <li>Final full adversarial review binds its conclusion to the exact worktree diff and reports all unavailable external lanes.</li>
    </ol>
  </section>

  <section>
    <h2>Residual risks and exact later gates</h2>
    <ul>
      <li>The operator-initiated terminal display is not a cryptographically trusted display. Fully compromised desktop/session spoofing is outside the supported boundary.</li>
      <li>Hardware and libfido2 availability become fail-closed operational prerequisites on both platforms.</li>
      <li>Root/service-manager and real authenticator acceptance cannot be proven by unit mocks or cross-compilation. The enrolled Docker engine is trusted host infrastructure.</li>
      <li>The first gate after plan approval is prompt/adversarial-plan approval. After implementation, separate gates remain for commit/stage, live install/enrollment, publication/release, and external Baseplate adoption.</li>
    </ul>
  </section>
</main>
<footer><p>Pipeline plan artifact. Execution remains paused pending prompt generation, adversarial review, and explicit approval.</p></footer>
<script type="application/json" id="pipeline-data">{"artifact":"plan","slug":"macos-authority-broker","revision":5,"title":"Linux-first cross-platform Workflow Authority Broker","workflowClass":"security","decisionProfile":{"uncertainty":"high","consequence":"high","rationale":"Cross-platform cryptographic authority, local IPC, Docker attestation, and lifecycle mistakes could expose signing authority or falsely attest verification."},"chunks":[{"id":"01-authority-contract-reset","dependsOn":[]},{"id":"02-go-core-foundation","dependsOn":["01-authority-contract-reset"]},{"id":"03-fido-ipc-authority","dependsOn":["02-go-core-foundation"]},{"id":"04-docker-substrate","dependsOn":["03-fido-ipc-authority"]},{"id":"05-kernel-cadence-integration","dependsOn":["01-authority-contract-reset","04-docker-substrate"]},{"id":"06-cross-platform-packaging","dependsOn":["03-fido-ipc-authority","04-docker-substrate"]},{"id":"07-parity-adversarial-harness","dependsOn":["05-kernel-cadence-integration","06-cross-platform-packaging"]},{"id":"08-docs-metadata-validation","dependsOn":["07-parity-adversarial-harness"]}],"decisions":["Go plus libfido2 1.17.0 on Linux and macOS","Public FIDO-authorized ephemeral run-key envelopes production and stdin HMAC legacy-only","One internal-UV FIDO approval per closed run","Controlling-terminal confirmation with documented spoofing residual","Root-console-only key and endpoint lifecycle operations","Fixed root-owned socket/provider","Trusted host Docker engine with candidate control surfaces excluded","Direct Engine API and exact cleanup","Equivalent OS contract tests with Linux primary","Public audit state retained on uninstall","No live or publication mutations without separate gate"],"excludedActions":["live install","FIDO enrollment","Docker endpoint enrollment","commit or stage","push or PR","merge or tag","marketplace publication","external worktree changes"]}</script>
</body>
</html>
===== END plans/macos-authority-broker/plan.html =====

===== BEGIN plans/macos-authority-broker/manifest.json =====
{
  "feature": "macos-authority-broker",
  "description": "Replace the macOS-only prototype with a simple Linux-first Go broker: one FIDO-approved ephemeral run key, equivalent macOS behavior, and trusted-host Docker substrate evidence.",
  "workflowClass": "security",
  "decisionProfile": {
    "uncertainty": "high",
    "consequence": "high",
    "rationale": "Cross-platform cryptographic authority, local IPC, Docker attestation, and lifecycle mistakes could expose signing authority or falsely attest verification."
  },
  "executionMode": "codex_native",
  "baseBranch": "main",
  "featureBranch": "ai/macos-authority-broker",
  "generatedAt": "2026-08-02T22:52:01Z",
  "overlapRisk": "high",
  "noMergeOnCompletion": true,
  "campaignSlug": null,
  "chunks": [
    {
      "id": "01-authority-contract-reset",
      "title": "Reset the Authority Provider Contract for FIDO2",
      "prompt": "prompts/01-authority-contract-reset.md",
      "level": 0,
      "parallelGroup": null,
      "dependsOn": [],
      "filesToModify": [
        "plugins/workflow-kernel/skills/workflow-kernel/references/authority-provider-schema.json",
        "plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-substrate-schema.json",
        "plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-approval-schema.json",
        "plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-profile-schema.json",
        "plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-provider-attestation-schema.json",
        "plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification-receipts-schema.json",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_receipts.py",
        "tests/fixtures/workflow-authority-v2-golden.json",
        "tests/test_authority_provider.py",
        "tests/test_repository_verification.py"
      ],
      "companionSkills": [
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns"
      ],
      "estimatedComplexity": "large",
      "kind": "logic",
      "executor": "codex"
    },
    {
      "id": "02-go-core-foundation",
      "title": "Build the Shared Go Protocol Foundation",
      "prompt": "prompts/02-go-core-foundation.md",
      "level": 1,
      "parallelGroup": null,
      "dependsOn": ["01-authority-contract-reset"],
      "filesToModify": [
        "native/workflow-authority/go.mod",
        "native/workflow-authority/Dockerfile.test",
        "native/workflow-authority/README.md",
        "native/workflow-authority/cmd/workflow-authority/main.go",
        "native/workflow-authority/cmd/workflow-authorityd/main.go",
        "native/workflow-authority/internal/protocol/types.go",
        "native/workflow-authority/internal/protocol/canonical.go",
        "native/workflow-authority/internal/protocol/framing.go",
        "native/workflow-authority/internal/protocol/redaction.go",
        "native/workflow-authority/internal/protocol/protocol_test.go",
        "native/workflow-authority/internal/platform/platform.go",
        "native/workflow-authority/internal/fido/fido.go",
        "native/workflow-authority/internal/dockerapi/docker.go",
        "native/workflow-authority-macos/Package.swift",
        "native/workflow-authority-macos/README.md",
        "native/workflow-authority-macos/Sources/AuthorityProtocol/AuthorityProtocol.swift",
        "native/workflow-authority-macos/Sources/AuthorityClientCore/AuthorityClientCore.swift",
        "native/workflow-authority-macos/Sources/AuthorityClient/main.swift",
        "native/workflow-authority-macos/Tests/AuthorityProtocolTests/AuthorityProtocolTests.swift"
      ],
      "companionSkills": [
        "assembly:golang-patterns",
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns"
      ],
      "estimatedComplexity": "large",
      "kind": "integration",
      "executor": "codex"
    },
    {
      "id": "03-fido-ipc-authority",
      "title": "Implement FIDO2 Authority and Cross-Platform IPC",
      "prompt": "prompts/03-fido-ipc-authority.md",
      "level": 2,
      "parallelGroup": null,
      "dependsOn": ["02-go-core-foundation"],
      "filesToModify": [
        "native/workflow-authority/internal/fido/libfido2.go",
        "native/workflow-authority/internal/fido/libfido2_stub.go",
        "native/workflow-authority/internal/fido/fake.go",
        "native/workflow-authority/internal/fido/fido_test.go",
        "native/workflow-authority/internal/state/replay.go",
        "native/workflow-authority/internal/state/replay_test.go",
        "native/workflow-authority/internal/ipc/client.go",
        "native/workflow-authority/internal/ipc/server.go",
        "native/workflow-authority/internal/ipc/socket.go",
        "native/workflow-authority/internal/ipc/peer_linux.go",
        "native/workflow-authority/internal/ipc/peer_darwin.go",
        "native/workflow-authority/internal/ipc/ipc_test.go",
        "native/workflow-authority/internal/authority/service.go",
        "native/workflow-authority/internal/authority/service_test.go"
      ],
      "companionSkills": [
        "assembly:golang-patterns",
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns",
        "developer-essentials:e2e-testing-patterns"
      ],
      "estimatedComplexity": "large",
      "kind": "logic",
      "executor": "codex"
    },
    {
      "id": "04-docker-substrate",
      "title": "Implement Authoritative Docker Substrate Attestation",
      "prompt": "prompts/04-docker-substrate.md",
      "level": 3,
      "parallelGroup": null,
      "dependsOn": ["03-fido-ipc-authority"],
      "filesToModify": [
        "native/workflow-authority/internal/dockerapi/client.go",
        "native/workflow-authority/internal/dockerapi/endpoint.go",
                "native/workflow-authority/internal/dockerapi/substrate.go",
                "native/workflow-authority/internal/dockerapi/cleanup.go",
                "native/workflow-authority/internal/dockerapi/substrate_test.go",
                "native/workflow-authority/internal/authority/service.go"
      ],
      "companionSkills": [
        "assembly:golang-patterns",
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns",
        "developer-essentials:e2e-testing-patterns"
      ],
      "estimatedComplexity": "medium",
      "kind": "logic",
      "executor": "codex"
    },
    {
      "id": "05-kernel-cadence-integration",
      "title": "Integrate FIDO Authority Across Workflow Kernel Cadence",
      "prompt": "prompts/05-kernel-cadence-integration.md",
      "level": 4,
      "parallelGroup": "A",
      "dependsOn": ["01-authority-contract-reset", "04-docker-substrate"],
      "filesToModify": [
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_authority.py",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_planning.py",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_orchestrator.py",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_execution.py",
        "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_provider.py",
                "plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_repository.py",
                "plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md",
                "native/workflow-authority/cmd/workflow-authority/main.go",
                "native/workflow-authority/cmd/workflow-authorityd/main.go",
                "native/workflow-authority/internal/authority/composition.go",
                "native/workflow-authority/internal/authority/offline.go",
                "native/workflow-authority/internal/authority/offline_test.go",
                "tests/test_runtime_cli.py",
        "tests/test_repository_verification.py",
        "tests/test_authority_provider.py"
      ],
      "companionSkills": [
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns",
        "developer-essentials:e2e-testing-patterns"
      ],
      "estimatedComplexity": "large",
      "kind": "integration",
      "executor": "codex"
    },
    {
      "id": "06-cross-platform-packaging",
      "title": "Add Parity Packaging and Operator Lifecycle",
      "prompt": "prompts/06-cross-platform-packaging.md",
      "level": 4,
      "parallelGroup": "A",
      "dependsOn": ["03-fido-ipc-authority", "04-docker-substrate"],
      "filesToModify": [
        "native/workflow-authority/cmd/workflow-authority-admin/main.go",
        "native/workflow-authority/internal/admin/admin.go",
        "native/workflow-authority/internal/admin/apply_linux.go",
                "native/workflow-authority/internal/admin/apply_darwin.go",
                "native/workflow-authority/internal/admin/filesystem.go",
                "native/workflow-authority/internal/admin/admin_test.go",
        "native/workflow-authority/packaging/systemd/workflow-authority.socket",
        "native/workflow-authority/packaging/systemd/workflow-authority.service",
        "native/workflow-authority/packaging/launchd/studio.designmachines.workflow-authority.plist"
      ],
      "companionSkills": [
        "assembly:golang-patterns",
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns",
        "developer-essentials:e2e-testing-patterns"
      ],
      "estimatedComplexity": "large",
      "kind": "integration",
      "executor": "codex"
    },
    {
      "id": "07-parity-adversarial-harness",
      "title": "Prove Linux and macOS Security Parity",
      "prompt": "prompts/07-parity-adversarial-harness.md",
      "level": 5,
      "parallelGroup": null,
      "dependsOn": ["05-kernel-cadence-integration", "06-cross-platform-packaging"],
      "filesToModify": [
        "native/workflow-authority/internal/adversarial/adversarial_test.go",
        "native/workflow-authority/internal/admin/admin_test.go",
        "tests/test_authority_provider.py",
        "tools/validate-workflow-authority.py",
        "tools/validate-workflow-kernel.py"
      ],
      "companionSkills": [
        "assembly:golang-patterns",
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns",
        "developer-essentials:e2e-testing-patterns"
      ],
      "estimatedComplexity": "medium",
      "kind": "logic",
      "executor": "codex"
    },
    {
      "id": "08-docs-metadata-validation",
            "title": "Migrate Consumers, Document, Version, and Validate",
      "prompt": "prompts/08-docs-metadata-validation.md",
      "level": 6,
      "parallelGroup": null,
      "dependsOn": ["07-parity-adversarial-harness"],
      "filesToModify": [
        "docs/workflow-authority.md",
        "docs/workflow-kernel.md",
                "plugins/workflow-kernel/skills/workflow-kernel/SKILL.md",
                "plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md",
                "plugins/pipeline/agents/workflow/execution-orchestrator.md",
                "plugins/assembly/commands/assembly-build.md",
                "plugins/assembly/skills/assembly-build/SKILL.md",
                "plugins/assembly/agents/workflow/go-test-runner.md",
                "plugins/assembly/references/repository-verification-profile.example.json",
                "AGENTS.md",
                "CLAUDE.md",
                "docs/dependency-graph.md",
                "tools/check-dependencies.sh",
                "plugins/workflow-kernel/.claude-plugin/plugin.json",
                "plugins/pipeline/.claude-plugin/plugin.json",
                "plugins/assembly/.claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                "plugins/workflow-kernel/.codex-plugin/plugin.json",
                "plugins/pipeline/.codex-plugin/plugin.json",
                "plugins/assembly/.codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json"
      ],
      "companionSkills": [
        "developer-essentials:auth-implementation-patterns",
        "developer-essentials:error-handling-patterns"
      ],
      "estimatedComplexity": "large",
      "kind": "config",
      "executor": "openrouter"
    }
  ],
  "executionPlan": {
    "levels": [
      {"level": 0, "strategy": "sequential", "chunks": ["01-authority-contract-reset"]},
      {"level": 1, "strategy": "sequential", "chunks": ["02-go-core-foundation"]},
      {"level": 2, "strategy": "sequential", "chunks": ["03-fido-ipc-authority"]},
      {"level": 3, "strategy": "sequential", "chunks": ["04-docker-substrate"]},
      {"level": 4, "strategy": "parallel", "groups": {"A": ["05-kernel-cadence-integration", "06-cross-platform-packaging"]}},
      {"level": 5, "strategy": "sequential", "chunks": ["07-parity-adversarial-harness"]},
      {"level": 6, "strategy": "sequential", "chunks": ["08-docs-metadata-validation"]}
    ],
    "totalChunks": 8,
    "parallelChunks": 2,
    "sequentialChunks": 6,
    "maxConcurrency": 2
  }
}
===== END plans/macos-authority-broker/manifest.json =====

===== BEGIN plans/macos-authority-broker/prompts/01-authority-contract-reset.md =====
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
===== END plans/macos-authority-broker/prompts/01-authority-contract-reset.md =====

===== BEGIN plans/macos-authority-broker/prompts/02-go-core-foundation.md =====
# Chunk: Build the Shared Go Protocol Foundation

## Context

This chunk replaces the paused Swift/macOS-only prototype with the shared implementation foundation.
Linux is the primary development platform, but macOS must expose the same operations, protocol, errors, lifecycle semantics, and evidence.
No native security or workflow feature may exist on only one platform.

## Task

Create `native/workflow-authority` as a Go 1.26.5 module.
Implement closed protocol types, canonicalization, bounded framing, redaction, platform interfaces, and thin client/daemon entry points.
Consume the shared Python golden fixture produced by chunk 01.
Create interfaces for FIDO and Docker without implementing real device or engine access yet.
Delete every file under the paused `native/workflow-authority-macos` Swift prototype listed below.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/go.mod` | Create | Module and exact Go 1.26.5 requirement; no third-party Go packages |
| `native/workflow-authority/Dockerfile.test` | Create | Pinned Linux test toolchain image |
| `native/workflow-authority/README.md` | Create | Developer-only build/test overview and parity rules |
| `native/workflow-authority/cmd/workflow-authority/main.go` | Create | Thin client entry point; no business logic |
| `native/workflow-authority/cmd/workflow-authorityd/main.go` | Create | Thin daemon entry point; no business logic |
| `native/workflow-authority/internal/protocol/types.go` | Create | Closed request/response and stable reason-code types |
| `native/workflow-authority/internal/protocol/canonical.go` | Create | Canonical UTF-8 JSON and SHA-256 digest |
| `native/workflow-authority/internal/protocol/framing.go` | Create | Length-bounded stream framing and depth/field enforcement |
| `native/workflow-authority/internal/protocol/redaction.go` | Create | Allowlist diagnostics and secret-value suppression |
| `native/workflow-authority/internal/protocol/protocol_test.go` | Create | Golden, boundary, redaction, and malformed-frame tests |
| `native/workflow-authority/internal/platform/platform.go` | Create | Minimal peer/socket/service abstraction shared by OS adapters |
| `native/workflow-authority/internal/fido/fido.go` | Create | FIDO run-approval and ephemeral signer interfaces |
| `native/workflow-authority/internal/dockerapi/docker.go` | Create | Docker interface and observation structures |
| `native/workflow-authority-macos/Package.swift` | Delete | Superseded Swift package |
| `native/workflow-authority-macos/README.md` | Delete | Superseded Swift documentation |
| `native/workflow-authority-macos/Sources/AuthorityProtocol/AuthorityProtocol.swift` | Delete | Superseded protocol |
| `native/workflow-authority-macos/Sources/AuthorityClientCore/AuthorityClientCore.swift` | Delete | Superseded client core |
| `native/workflow-authority-macos/Sources/AuthorityClient/main.swift` | Delete | Superseded client |
| `native/workflow-authority-macos/Tests/AuthorityProtocolTests/AuthorityProtocolTests.swift` | Delete | Superseded tests |

## Files to Read

| File | Why |
|---|---|
| `tests/fixtures/workflow-authority-v2-golden.json` | Canonical cross-runtime source of truth |
| `plugins/workflow-kernel/skills/workflow-kernel/references/authority-provider-schema.json` | Exact operations and public evidence fields |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Python validation and digest semantics |
| `AGENTS.md` | Depot executable and validation conventions |

## Architecture Rules

Use package boundaries rather than build-tagging the product model.
Only OS syscall adapters may use `_linux.go` or `_darwin.go` later.
Protocol types, status values, error codes, FIDO ceremony inputs, Docker evidence, admin operations, and lifecycle state machines are shared.
The Go core must not import repository-controlled plug-ins or execute arbitrary hooks.
The command packages parse arguments, invoke an internal API, write a bounded public result, and translate stable exit codes.
They do not contain policy.

The run-authority interface generates an ephemeral Ed25519 key, binds its public key into one FIDO-approved closed run scope, retains the private key in daemon memory only, and signs repeated operation/result/cleanup envelopes until expiry or restart.
The interface never serializes, persists, or returns the ephemeral private key.

## Canonicalization Rules

- Import the frozen limits from chunk 01: 1,048,576-byte frame, 4,096-byte UTF-8 string, 256-entry collection, and nesting depth 16; do not choose new values.
- UTF-8 only.
- Closed JSON objects.
- Deterministic object-key ordering.
- No insignificant whitespace.
- No NaN, infinities, floats, duplicate keys, or implicit numeric coercion.
- Explicit integer and string length bounds.
- Explicit collection-size and nesting-depth bounds.
- SHA-256 over exact canonical bytes.
- Domain separation remains part of the FIDO layer, not generic JSON canonicalization.
- Do not copy Go's default map encoding behavior as an undocumented protocol promise.

If exact compatibility with Python requires a custom encoder, implement the smallest deterministic encoder for the closed protocol value set.
Reject values outside that set before encoding.

## Framing Rules

Use pathname Unix `SOCK_STREAM` semantics.
Define a fixed protocol header/version and enforce chunk 01's 1,048,576-byte maximum payload.
Read exactly one request and write exactly one response per connection.
Reject trailing frames, truncation, integer overflow, overlong lengths, excessive depth, duplicate fields, unknown fields, and ancillary descriptors.
Cancellation and deadlines must be carried through context.
Never include request JSON in an error.

## Redaction Rules

Diagnostics use an allowlist of stable reason codes and safe scalar metadata.
Never log or echo:

- PINs
- environment values
- argv beyond a safe operation name
- repository file content
- authenticator data
- signatures
- credential references
- raw Docker responses
- tokens, cookies, connection strings, or key-shaped bytes
- full canonical request bodies

Public signed envelopes are protocol output, not log content.

## Test Doubles

The FIDO interface must support deterministic enrollment and assertion fakes without embedding a real key.
The Docker interface must support deterministic endpoint, engine, image, container, execution, and cleanup observations.
The platform interface must support peer identity, socket ownership, boot identity, clock, cancellation, and service status fakes.
No fake may be automatically selected in a production build.

## Client Entry-Point Contract

The `workflow-authority` binary is a narrow adapter.
It accepts one operation from the fixed shared vocabulary.
It reads one bounded public request from isolated stdin or the fixed IPC layer selected internally.
It never accepts a receipt key.
It never accepts a PIN.
It never accepts a caller-selected executable.
It never accepts a caller-selected socket in production mode.
It never shells out.
It never reads repository configuration to find the daemon.
It writes one bounded public JSON response on stdout.
Human diagnostics go to stderr as closed safe reason codes.
JSON mode never interleaves prose with protocol output.
Cancellation and deadline are propagated through `context.Context`.
Exit codes are stable and defined from shared result categories.

Define result categories for at least:

- success
- denied
- cancelled
- unavailable
- invalid request
- protocol mismatch
- peer rejected
- stale or replayed request
- substrate non-authoritative
- internal failure

Do not map multiple security-distinct failures to success-like exit zero.
Do not expose internal Go errors as protocol strings.

## Daemon Entry-Point Contract

The `workflow-authorityd` binary is also a narrow adapter.
It loads only fixed installed configuration through an injected platform layer.
It does not read `.env` files.
It does not scan the repository.
It does not accept plug-ins.
It does not accept arbitrary listen addresses.
It does not daemonize itself when service managers own lifecycle.
It handles shutdown through context cancellation and explicit ordering.
It rejects positional arguments not part of the closed service surface.
It disables or requests disabling core dumps through the later platform implementation seam.

Shutdown order must be expressible as:

1. stop accepting new IPC requests
2. cancel queued authorization work
3. cancel active operations
4. allow bounded cleanup/recovery hooks
5. flush crash-consistent state
6. close the socket/listener
7. exit with a stable reason

This chunk defines the interfaces and orchestration skeleton only.
Real FIDO, Docker, persistence, and service-manager behavior arrives later.

## Platform Interface Design

Keep the shared interface small enough that both operating systems can implement it without semantic branching.
It may expose:

- fixed runtime/state/install roots
- boot identity
- peer identity retrieval
- socket ownership and no-follow operations
- clock and randomness dependencies
- core-dump policy request
- service status abstraction
- context-aware shutdown signal

It must not expose:

- XPC connections
- Secure Enclave or Keychain types
- LocalAuthentication
- systemd-specific unit objects
- launchd-specific dictionary objects
- Docker context lookup
- arbitrary subprocess execution
- repository file reads

Platform-specific structs stay inside adapter packages.
The protocol never serializes an OS-specific peer credential structure.
Normalize only the minimum shared peer facts needed by policy.

## Protocol Versioning

Define one explicit protocol version for the new companion.
Requests and responses carry schema version and artifact role.
Unknown future versions fail closed.
Do not accept missing version as v1.
Do not negotiate down to the HMAC protocol.
Compatibility is an explicit fixed range checked by both client and daemon.
Version mismatch returns a closed public error with no request echo.

## Survivor Audit

After deleting the Swift prototype, search the worktree for:

- `workflow-authority-macos`
- `AuthorityProtocol.swift`
- `AuthorityClientCore`
- `Package.swift` references tied to this broker
- XPC service identifiers
- Secure Enclave authority instructions
- Swift-specific build validation

Any remaining reference must either be historical planning evidence under `plans/` or be removed by an owned file in this chunk.
The six listed paths are the verified current inventory; do not delete a surprise unrelated file silently, and report it as an ownership conflict.
Do not edit unrelated historical artifacts outside owned paths.
Report any survivor requiring a later documentation chunk as `Noted, not fixed` with its exact path.

Search new Go definitions for zero callers after implementation.
Inline or remove unused helpers inside owned files.
Do not retain abstraction scaffolding that only mirrors the deleted Swift design.

## Integration Test Matrix

The protocol test file should exercise client/daemon core interaction in memory:

- minimal valid request round trip
- Unicode golden request round trip
- maximum-boundary request round trip
- operation mismatch
- protocol version mismatch
- unknown request field
- unknown response field
- duplicate JSON key
- invalid UTF-8
- truncated frame
- overlong frame
- extra trailing frame
- cancellation before write
- cancellation during read
- responder unavailable
- safe denied response
- safe internal failure response
- forbidden diagnostic value redaction

These tests use fakes and in-memory connections only.
They do not open a production socket or device.

## Build and Portability Evidence

Before writing `Dockerfile.test`, verify the pinned digest with a read-only registry query and confirm the resolved image reports `go1.26.5`.
The planning pass observed multi-architecture digest `sha256:4ee9ffa999b4583ce281939cdff828763083610292f252279a0cee77473bd9a7`; do not trust that observation if the registry has drifted.
On mismatch, stop, record the observed digest under `NOT-COVERED`, and surface the drift through the Ambiguity Protocol rather than silently substituting another digest.

Use build constraints only for files that truly require OS or cgo behavior.
The shared foundation must build with `CGO_ENABLED=0` on Linux and macOS targets because real libfido2 is not implemented yet.
Chunk 03 may introduce cgo-specific builds without changing protocol semantics.
Check at least:

- native Linux build/test under Go 1.26.5
- `GOOS=darwin` compile of shared packages under Go 1.26.5 where cgo-free
- `GOOS=linux` compile of shared packages under Go 1.26.5
- no platform build produces a different operation list or JSON fixture

Cross-compilation is portability evidence only.
It is not native peer/service acceptance evidence.

`Dockerfile.test` must use the official multi-platform image exactly as:

`docker.io/library/golang:1.26.5-trixie@sha256:4ee9ffa999b4583ce281939cdff828763083610292f252279a0cee77473bd9a7`

The validator must reject tag-only, version drift, or digest drift.
The pinned image is used for Linux unit, race, vet, and cross-compilation lanes; it is not a production runtime image.

## Companion Skills

Load:

- `assembly:golang-patterns` for Go package, context, error, and testing patterns.
- `developer-essentials:auth-implementation-patterns` for protocol and authority boundaries.
- `developer-essentials:error-handling-patterns` for stable failure taxonomy and redaction.

## Acceptance Criteria

- [ ] AC-01 `go.mod` declares the exact approved Go 1.26.5 toolchain policy and introduces no third-party Go module dependency.
- [ ] AC-01A `Dockerfile.test` pins the exact approved Go 1.26.5-trixie multi-architecture digest and later validation uses only that definition.
- [ ] AC-02 Both binaries are thin; policy, canonicalization, framing, and redaction live in importable internal packages.
- [ ] AC-03 The exact 16 operation values match chunk 01 and no Swift-era aliases remain.
- [ ] AC-04 Go consumes all three shared golden vectors directly and matches Python canonical UTF-8 bytes and SHA-256 digests.
- [ ] AC-05 Unicode, maximum boundaries, duplicate fields, unknown fields, invalid UTF-8, floats, excessive nesting, oversized frames, truncation, and trailing data have negative tests.
- [ ] AC-06 One connection accepts one request and returns one bounded public response; it cannot stream arbitrary data or request raw key output.
- [ ] AC-07 Error and logging tests prove forbidden secret-shaped fields never appear on stdout, stderr, formatted errors, or injected log sinks.
- [ ] AC-08 FIDO, Docker, clock, boot identity, peer identity, filesystem, and cancellation interfaces have deterministic fakes.
- [ ] AC-08A Interface-contract tests against fakes prove the ephemeral run private key is never serialized or returned, is invalidated by restart/expiry, and signs only operations allowed by the FIDO-bound run scope; the production security proof remains chunk 03 AC-17A.
- [ ] AC-09 Production command construction cannot select a fake backend through argv or environment.
- [ ] AC-10 The shared platform interface contains only unavoidable OS primitives; no macOS-only product operation appears in an interface.
- [ ] AC-11 Linux and darwin compile-time assertions can implement the same platform interface without conditional protocol fields.
- [ ] AC-12 Client and daemon ignore authority-related environment overrides and do not resolve executables or sockets through `PATH`.
- [ ] AC-13 All six listed Swift files are deleted, `find native/workflow-authority-macos -type f` returns no survivors, and no Swift/XPC/Secure Enclave production instructions remain in the new module.
- [ ] AC-14 The module README states Linux-primary parity, hardware fail-closed behavior, and the prohibition on raw receipt-key output without claiming installation is complete.
- [ ] AC-15 Pinned Go 1.26.5 container tests run `go test ./...`; if the image/toolchain is unavailable, record the exact gap rather than using another version.
- [ ] AC-16 The Go race suite is run under the pinned toolchain where supported and any unsupported host/toolchain condition is explicit.
- [ ] AC-17 `go vet ./...` or the repository-approved equivalent passes under the pinned container; no bare host-Go proof is substituted for a missing pinned lane.
- [ ] AC-18 `git diff --check` passes and only owned files change.
- [ ] AC-19 Go constants match chunk 01's frozen frame/string/collection/depth values; exact-limit frames pass and max-plus-one frames fail.

## Behavioral Contract Inputs

- `REQ-003`: identical Linux/macOS product contract.
- `REQ-004`: authority private key is structurally absent from the host protocol.
- `REQ-005`: no secret output channels.
- `REQ-008`: shared adversarial fixtures.
- `CHK-004`: Python/Go canonical vector equality.
- `CHK-005`: frame and diagnostic negative matrix.
- `CHK-006`: Swift production surface removed.

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

- Only modify the listed files.
- Do not implement real libfido2, service-manager, peer-credential, Docker Engine, installer, or Workflow Kernel integration in this chunk.
- Do not keep a Swift compatibility target.
- Do not introduce a pure-Go CTAP stack.
- Do not add a raw-key, general-signing, shell-execution, plugin-loading, or arbitrary-socket API.
- Do not include secrets or authentic device artifacts in source or fixtures.
- Do not stage, commit, push, install, enroll, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

libfido2 is the approved shared FIDO implementation for Linux and macOS.
The thin cgo adapter arrives in the next chunk.
This foundation makes platform parity testable by putting all semantic decisions above the OS adapter boundary.
===== END plans/macos-authority-broker/prompts/02-go-core-foundation.md =====

===== BEGIN plans/macos-authority-broker/prompts/03-fido-ipc-authority.md =====
# Chunk: Implement FIDO2 Authority and Cross-Platform IPC

## Context

The shared Go protocol exists after chunk 02.
This chunk implements the actual host authority boundary used identically by Linux and macOS.
The private credential remains in a FIDO2 authenticator; one public assertion authorizes a closed run and binds an ephemeral in-memory run-signing key.
Peer credentials admit a caller but never substitute for user presence or user verification.

## Task

Implement a thin cgo adapter pinned to libfido2 1.17.0.
Implement verified credential enrollment, rotation, revocation, loss recovery, and one assertion ceremony per closed run.
Display the exact scope in the operator-initiated client terminal before assertion.
Generate and retain an ephemeral Ed25519 run key in daemon memory, then sign repeated closed operation/result/cleanup envelopes without additional touches.
Implement crash-consistent replay state, bounded prompt queues, rate limits, cancellation, and one-request Unix-socket IPC.
Add Linux `SO_PEERCRED` and macOS `getpeereid`/peer-PID adapters behind the shared platform interface.
Keep every user-facing operation, status, error, and test contract identical across operating systems.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/internal/fido/libfido2.go` | Create | cgo CTAP2 device/enrollment/assertion adapter |
| `native/workflow-authority/internal/fido/libfido2_stub.go` | Create | Explicit unavailable build, never a software-key fallback |
| `native/workflow-authority/internal/fido/fake.go` | Create | Deterministic test backend only |
| `native/workflow-authority/internal/fido/fido_test.go` | Create | Ceremony, verification, cancellation, and redaction tests |
| `native/workflow-authority/internal/state/replay.go` | Create | Atomic nonce/session/sequence/consumption ledger |
| `native/workflow-authority/internal/state/replay_test.go` | Create | Crash/replay/idempotency/time tests |
| `native/workflow-authority/internal/ipc/client.go` | Create | Fixed-socket run-scoped client |
| `native/workflow-authority/internal/ipc/server.go` | Create | Bounded server, admission, queue, deadline, response |
| `native/workflow-authority/internal/ipc/socket.go` | Create | Root-owned no-follow pathname socket policy |
| `native/workflow-authority/internal/ipc/peer_linux.go` | Create | `SO_PEERCRED` implementation |
| `native/workflow-authority/internal/ipc/peer_darwin.go` | Create | `getpeereid` and available peer-PID evidence |
| `native/workflow-authority/internal/ipc/ipc_test.go` | Create | Shared and adapter-negative tests |
| `native/workflow-authority/internal/authority/service.go` | Create | Policy orchestration and closed authority result |
| `native/workflow-authority/internal/authority/service_test.go` | Create | End-to-end fake authority tests |

## Files to Read

| File | Why |
|---|---|
| `native/workflow-authority/internal/protocol/types.go` | Exact operation and message types |
| `native/workflow-authority/internal/protocol/framing.go` | One-operation framing contract |
| `native/workflow-authority/internal/platform/platform.go` | Required adapter interface |
| `tests/fixtures/workflow-authority-v2-golden.json` | Canonical request digests |
| `/usr/include/fido.h` or the resolved pinned libfido2 headers | Verify exact C API names and result semantics |

## libfido2 Boundary

Require libfido2 exactly 1.17.0 for the initial production artifact and preflight; document its OpenSSL 3/libcbor/zlib requirements.
Resolve current API behavior from official Yubico documentation and installed headers.
Build/package preflight requires `pkg-config --modversion libfido2` to report exactly `1.17.0`, verifies the linked shared-library dependency and required symbols, and records the package identity in private install state.
libfido2 exposes no documented public runtime version query; daemon startup therefore performs a required-symbol and minimal allocation/self-test and reports a version-integrity gap if the package identity cannot be established rather than inventing a runtime version check.
Use device manifest/discovery APIs with deterministic selection policy.
Require CTAP2 and ES256.
Enrollment uses a fixed domain-separated RP ID.
Use a non-discoverable credential with an explicit allow-list.
Require user presence and authenticator-internal user verification.
Reject authenticators that require a host-entered PIN; there is no PIN input or IPC path.
Verify enrollment output before persisting public metadata.
Persist only the public stable credential reference, the root-only raw allow-list credential ID required to request assertions for a non-discoverable credential, the enrolled public key, algorithm, generation, policy, and revocation data.
The raw credential ID never appears in signed evidence, logs, status, argv, environment, or fixtures.
For ES256, read the libfido2-normalized 64-byte `x || y` value through `fido_cred_pubkey_ptr`/`fido_cred_pubkey_len`, require the expected credential type and exact length, and persist canonical 65-byte SEC1 uncompressed form (`0x04 || x || y`).
Do not parse authenticator-controlled COSE/CBOR in Go; malformed type/length/point-on-curve enrollment output fails before persistence, and the retained SEC1 point is verifiable with the Go standard library.
Never persist or return PINs, private keys, assertion scratch buffers, or raw device diagnostics.
Zero sensitive mutable buffers where the API permits.

The unavailable build returns a stable `fido_unavailable` status.
It does not generate a software key.
It does not downgrade UV.
It does not call an external CLI.

## Run Authorization Ceremony

The daemon performs all libfido2 device I/O.
The client's only roles are rendering the canonical scope to its controlling terminal, collecting explicit operator confirmation, and transporting bounded IPC frames; the client never opens a FIDO device.

For every closed run:

1. Validate the closed request and recompute canonical bytes.
2. Generate a fresh ephemeral Ed25519 run key in daemon memory.
3. Bind its public key, exact repository/run/profile/base/candidate/boundary/allowed-operation scope, boot identity, session, issuance, and expiry.
4. Render that exact canonical scope and expiry to the operator-initiated client's controlling terminal and require explicit confirmation.
5. Allocate a server-generated 256-bit nonce and compute `SHA-256("workflow-kernel-authority-v2\0" || canonical_run_authorization)`.
6. Request one assertion restricted to the enrolled credential and RP.
7. Require signed UP and internal UV bits.
8. Verify the signature, client-data hash, and active public-key generation.
9. Atomically consume the challenge and activate the in-memory run signer.
10. Return the public run-authorization envelope and non-secret run handle.

This implements chunk 01's challenge flow: the first cadence request receives `authorization_required`, confirmation is read only from the controlling terminal, one resubmission performs the assertion, and absence of a terminal returns `authority_unavailable`.

Each later operation uses a fresh nonce and strict sequence, checks the allowed run scope, and signs the canonical operation/result/cleanup envelope with the ephemeral key.
The private run key never crosses IPC, never persists, and is zeroed/discarded on expiry, cancellation, revocation, daemon shutdown, or restart.
The non-secret handle cannot broaden scope and is useless after signer loss.

Cancellation, timeout, denial, and device removal consume the challenge.
No FIDO assertion is reused for another run.
No run-wide secret or bearer is exported.
The ephemeral key is a bounded run signer, not a stable host key.

The terminal is not a cryptographically trusted display.
The supported guarantee is that candidate/repository code and unattended agents cannot mint a run without operator confirmation plus internal UV.
Fully compromised desktop/session spoofing is an accepted documented residual risk.

## Replay and Idempotency

Use root-owned, no-follow, crash-consistent state.
Persist a boot marker, daemon-instance session UUID, next sequence, outstanding challenges, consumed challenges, committed result digest, and revocation generation.
State transitions are monotonic.
An exact duplicate committed request with the same idempotency key may return the same public result.
Reusing an idempotency key with different canonical content fails.
Future, stale, reordered, replayed, cross-session, and cross-boot requests fail.
Authenticator counters are recorded as optional clone evidence but never become the sole replay mechanism.
Use atomic replace plus fsync policy appropriate to security state.
Failure injection tests must cover every persistence boundary.
Persist only public run authorization and sequence/consumption metadata; never persist the ephemeral private key.
After daemon restart, historical envelopes remain verifiable but new operations require a new FIDO-approved run.

## Enrollment, Rotation, and Loss

First enrollment is a root-console administrative action plus authenticator credential-creation UP/internal-UV; it does not require an existing credential.
Rotation authorizes enrollment of a new generation, verifies it, activates it, then revokes the prior generation for issuance while retaining its public verification record.
Lost-authenticator recovery is an explicit root-console flow that revokes the missing generation and enrolls a replacement; it never creates a software FIDO credential or recovers a private key.
Default uninstall preserves public verification/revocation state.
Explicit purge uses FIDO when available and permits the documented root-console lost-key recovery path.

## IPC Admission

Use a root-owned pathname socket directory.
Reject symlinks and parent-directory swaps with descriptor-relative/no-follow checks.
Verify owner and mode before bind/connect.
Reject caller-supplied socket paths in production.
Linux reads kernel-provided `SO_PEERCRED`.
macOS reads kernel-provided effective UID/GID using `getpeereid` and peer PID where supported.
The client verifies it reached the fixed service identity/path.
The server rejects unauthorized UID/GID/session policy before parsing sensitive request content.
Enforce chunk 01's operation-admission matrix before mutation: UID-0 root-console peers alone may invoke key or endpoint lifecycle operations; cadence operations require the exact active run permission; read-only verification/status/doctor cannot mutate or issue authority.
Add negative tests for each lifecycle operation from a same-UID non-root repository peer and prove rejection occurs before handler dispatch.
Reject ancillary file descriptors.
Ignore `HOST_AUTHORITY_BROKER`, provider, FIDO, socket, and executable environment overrides.

## Concurrency and Prompt Flooding

Serialize authenticator access.
Bound the global queue.
Bound requests per peer and repository.
Use per-run locks for state transitions.
Do not hold global locks while waiting for user presence.
Cancellation propagates through queued, active FIDO I/O, persistence, and response stages.
Every terminal path releases locks and consumes or invalidates its challenge.
Errors remain bounded and secret-free.

## Companion Skills

Load:

- `assembly:golang-patterns` for contexts, concurrency, build tags, and test seams.
- `developer-essentials:auth-implementation-patterns` for FIDO, replay, and revocation boundaries.
- `developer-essentials:error-handling-patterns` for fail-closed error translation.
- `developer-essentials:e2e-testing-patterns` for IPC and cancellation scenarios.

## Acceptance Criteria

- [ ] AC-01 Linux and macOS compile the same protocol/authority packages with only peer/system adapters build-tagged.
- [ ] AC-02 The cgo adapter uses verified libfido2 1.17.0 APIs and production preflight rejects other versions for this release.
- [ ] AC-03 Enrollment requires CTAP2, ES256, fixed RP, explicit credential, UP, authenticator-internal UV, and verified output before public metadata persistence; host-PIN authenticators fail unavailable.
- [ ] AC-04 The unavailable build fails with `fido_unavailable` and contains no software-key or CLI fallback.
- [ ] AC-05 Each run creates one fresh domain-separated FIDO authorization binding exact scope and ephemeral Ed25519 public key; each later operation creates a fresh nonce/sequence and ephemeral signature within that scope.
- [ ] AC-06 Missing UP/UV, wrong RP, wrong credential, invalid signature, wrong client hash, revoked generation, and unsupported algorithm fail closed.
- [ ] AC-07 PINs, authenticator data, signatures, request bodies, raw libfido2 diagnostics, and real or authenticator-derived credential references are absent from logs, errors, argv, environment, and fixtures; synthetic placeholder public references are permitted in fixtures.
- [ ] AC-07A No host PIN input or transport path exists; PIN-requiring authenticators fail before authority activation.
- [ ] AC-07B Terminal consent displays exact operation allowance, repository scope, run, profile, base, candidate, boundary, and expiry derived from the same canonical bytes signed by FIDO.
- [ ] AC-07C Tests prove unattended direct invocation cannot activate a run without explicit terminal confirmation and internal UV; desktop display spoofing is documented outside scope.
- [ ] AC-08 Replay state rejects stale/future/reordered/replayed/cross-session/cross-boot challenges and consumes cancelled/time-out/device-removed challenges.
- [ ] AC-09 Idempotency returns only an exact previously committed public result; same key with altered content fails.
- [ ] AC-10 Crash/failure injection around write, fsync, rename, and response cannot resurrect or double-consume authority.
- [ ] AC-11 Linux peer tests verify `SO_PEERCRED`; macOS tests verify `getpeereid` semantics and available PID evidence without changing admission outcomes.
- [ ] AC-12 Socket symlinks, parent swaps, wrong owner/mode, replacement after inspection, arbitrary path, and ancillary descriptors are rejected.
- [ ] AC-13 Client and server mutually enforce fixed identity/path and ignore authority environment overrides.
- [ ] AC-14 Authenticator requests are serialized, queues/rates are bounded, prompt floods do not starve cancellation, and locks are released on every path.
- [ ] AC-15 Cancellation works before queue admission, while queued, before touch, during FIDO I/O, during persistence, and before response.
- [ ] AC-16 The same stable reason codes and exit-status mapping are asserted for Linux and macOS adapters.
- [ ] AC-17 Tests prove a public envelope contains no receipt key, private key, PIN, reusable bearer, or general-signing capability.
- [ ] AC-17A Tests prove the ephemeral private key is memory-only, cannot sign outside allowed scope, dies on expiry/restart/revocation, and leaves historical public verification intact.
- [ ] AC-17B Bootstrap enrollment, two-generation rotation, cancellation, authenticator loss, root-console recovery, and purge have parity state-machine tests.
- [ ] AC-18 Pinned Go 1.26.5 container tests and race tests pass where supported; macOS compilation/adapter tests use the same Go version or report the exact unavailable lane.
- [ ] AC-19 `git diff --check` passes and only owned files change.
- [ ] AC-20 Tests prove the root-only raw allow-list credential ID is used for assertion requests but absent from every signed envelope, log/status surface, argv, environment, and fixture.
- [ ] AC-21 Tests prove the client never opens a FIDO device and the stored raw P-256 public point is verifiable with the Go standard library alone.
- [ ] AC-22 Fake-IPC tests exercise `authorization_required` → controlling-terminal confirmation → one FIDO assertion → activation; missing terminal returns `authority_unavailable`, forged confirmation and a second assertion fail.
- [ ] AC-23 Non-root peers cannot invoke key or endpoint lifecycle handlers, while cadence and read-only operations follow the frozen admission matrix exactly.
- [ ] AC-24 Enrollment rejects wrong public-key type, wrong length, and off-curve points; ES256 public-key persistence uses the documented libfido2 64-byte output to SEC1 conversion without a Go CBOR parser.
- [ ] AC-25 Build/package preflight proves libfido2 1.17.0 via pkg-config and linked symbols; startup self-test is explicit about the absence of a public runtime version API.

## Behavioral Contract Inputs

- `REQ-003`: same security and product semantics on Linux and macOS.
- `REQ-004`: FIDO user presence/verification and non-exportability.
- `REQ-005`: no secret exfiltration channels.
- `REQ-007`: repeated fresh authority operations.
- `REQ-008`: unauthorized, replay, concurrency, cancellation, and path attacks.
- `CHK-007`: FIDO negative ceremony matrix.
- `CHK-008`: IPC peer and filesystem attack matrix.
- `CHK-009`: replay crash-consistency matrix.

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
- Do not implement Docker substrate, packaging, Workflow Kernel wiring, or docs here.
- Do not weaken UP or UV based on device availability.
- Do not accept caller assertions as verified without libfido2/public-key verification.
- Do not expose a host-entered PIN through argv, environment, logs, fixtures, or response data.
- Do not add a raw-key, general signing, long-lived bearer, plugin, or arbitrary-command endpoint.
- Do not stage, commit, push, install, enroll a real device, release, tag, publish, or modify external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

libfido2 supports Linux and macOS device discovery, credential creation, assertion retrieval, UP/UV enforcement, verification, cancellation, and timeouts.
Ordinary security keys do not display the canonical request, so trusted broker presentation remains a documented residual risk.
Peer credentials identify the kernel-reported process account, not human intent; FIDO remains mandatory.
===== END plans/macos-authority-broker/prompts/03-fido-ipc-authority.md =====

===== BEGIN plans/macos-authority-broker/prompts/04-docker-substrate.md =====
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
===== END plans/macos-authority-broker/prompts/04-docker-substrate.md =====

===== BEGIN plans/macos-authority-broker/prompts/05-kernel-cadence-integration.md =====
# Chunk: Integrate FIDO Authority Across Workflow Kernel Cadence

## Context

Chunks 01 through 04 establish the public FIDO provider contract and authoritative Docker substrate.
This chunk connects those components to every Workflow Kernel repository-verification command and cadence boundary.
Production must never invoke or receive a receipt key.
The existing `--receipt-key-stdin` behavior remains an explicit legacy path for schema-v1 compatibility and tests only.

## Task

Add an explicit authority-provider mode to Workflow Kernel CLI and runtime APIs.
Resolve only the fixed installed `workflow-authority` client and non-secret provider/substrate handles.
Construct one closed FIDO run authorization, then fresh ephemeral-key-signed requests/results for every approve, plan, run, record, provider-attestation, cleanup, and receipt operation.
Verify the complete public FIDO → run key → ordered operation/result/cleanup chain through the fixed Go verifier and independently compare all bindings in Python.
Resolve `DM_VERIFICATION_SUBSTRATE` as a non-secret broker handle to an authoritative signed document.
Preserve current fail-closed planning, execution, receipt, provider, mutation, cache, and cadence behavior.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Modify | Explicit provider flags/handles, mode exclusion, stable exit codes |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_authority.py` | Modify | Approval issuance/validation through provider abstraction |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_planning.py` | Modify | Provider and substrate binding in plans/reuse |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_orchestrator.py` | Modify | Fresh provider calls, broker execution, cleanup validity |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_execution.py` | Modify | Prevent production host-side candidate execution and inheritance |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_provider.py` | Modify | Exact remote-provider evidence and broker attestation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_repository.py` | Modify | Closed profile/provider/substrate handle admission |
| `plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md` | Modify | Fixed installed authority companion resolution contract |
| `native/workflow-authority/cmd/workflow-authority/main.go` | Modify | Final client composition root and offline verification command |
| `native/workflow-authority/cmd/workflow-authorityd/main.go` | Modify | Final daemon composition root with production backends |
| `native/workflow-authority/internal/authority/composition.go` | Create | Explicit production backend assembly with no fake/stub fallback |
| `native/workflow-authority/internal/authority/offline.go` | Create | Daemon-independent public-chain historical verifier |
| `native/workflow-authority/internal/authority/offline_test.go` | Create | Binary-facing offline verification and composition tests |
| `tests/test_runtime_cli.py` | Modify | CLI selection, mutual exclusion, resolution, exit tests |
| `tests/test_repository_verification.py` | Modify | Full cadence, execution, cache, mutation, provider tests |
| `tests/test_authority_provider.py` | Modify | Cross-process verifier and handle integration tests |

## Files to Read

| File | Why |
|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/authority_provider.py` | Provider request/response validation from chunk 01 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_receipts.py` | Versioned receipt authority abstraction |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md` | Released command and cadence behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/runtime_resolution.py` | Existing trusted launcher/bundle resolution patterns |
| `native/workflow-authority/internal/protocol/types.go` | Shared operation and handle vocabulary |

## Production Mode Selection

Introduce one explicit production authority-provider selection.
Use a fixed installed client resolved by trusted runtime policy.
The repository may carry only a non-secret logical handle or fixed provider-mode declaration.
It may not carry:

- executable paths
- socket paths
- command strings
- shell fragments
- environment-variable names used for secrets
- raw public-key registry paths outside the installed root
- receipt keys
- PINs
- bearer tokens

Production provider mode and `--receipt-key-stdin` are mutually exclusive.
If neither is supplied where authority is required, fail closed.
If both are supplied, fail closed.
If the provider is unavailable, malformed, stale, untrusted, or version-incompatible, fail closed.
Never fall back from provider mode to HMAC.

## Fixed Companion Resolution

Follow the existing runtime resolution principles:

1. Resolve an installed, root-owned authority companion from a fixed policy root.
2. Reject repository-relative, worktree-relative, cache-relative, `PATH`, symlink, and environment-selected binaries.
3. Verify regular-file type, ownership, permissions, no-follow path components, expected version, protocol version, and trusted distribution identity metadata.
4. Invoke exact argv without a shell.
5. Spawn the fixed root-owned `workflow-authority` client with exact argv, supply one closed request through isolated stdin, and capture one bounded public JSON response on stdout. The client opens the controlling terminal directly for the single `authorization_required` confirmation flow; stdin remains protocol-only. Without a controlling terminal it returns `authority_unavailable`. Python never opens the broker socket directly.
6. Capture only a bounded public JSON response.
7. Use minimal environment and isolated stdin/HOME rules consistent with the kernel.
8. Verify exit code and closed response together; neither alone is authority.

Interpretation pre-selected: Python always uses the fixed client process.
Rejected: a direct Python socket client, because it duplicates framing and bypasses the Go client verification boundary.

Tests inject a fake verifier through an internal Python dependency seam.
Production never accepts the test seam from user input.

## Fresh Operation Mapping

Map each Workflow Kernel action to exactly one shared operation:

| Kernel action | Authority operation |
|---|---|
| Approve verification profile | `approve_profile` |
| Create or refresh plan | `plan_verification` |
| Admit/execute verification lane | `run_verification` |
| Record local result/receipt | `record_result` |
| Import remote provider evidence | `provider_attestation` |
| Validate historical public envelope | `verify_envelope` |
| Prepare run-owned containment | `substrate_prepare` |
| Inspect/revalidate containment | `substrate_inspect` |
| Execute exact contained argv | `substrate_execute` |
| Finalize cleanup/absence evidence | `substrate_cleanup` |
| Read status/doctor | `status` / `doctor` read-only operations |

Do not alias old names.
Do not reuse a response for a different operation.
Workflow Kernel never invokes `key_enroll`, `key_rotate`, `key_revoke`, or `substrate_enroll_endpoint`; those are root-console admin operations only.

## Request Closure

Every request includes all applicable fields, and Python recomputes them from trusted local inputs:

- schema/protocol version
- operation
- repository scope digest
- canonical repository descriptor/root identity
- run ID
- profile ID and profile digest
- trusted base commit
- candidate commit or snapshot digest
- changed-path closure
- boundary and cadence value
- lane ID and command digest
- provider name and provider request/result digest
- authority files/environment digest
- substrate handle and signed substrate digest
- previous receipt/event prefix digest
- nonce/sequence/timestamps supplied by the service challenge flow

Do not accept caller-provided digests without recomputing the underlying trusted value.
The Go result must echo the exact request digest.
Python compares each expected field after cryptographic verification.

## Cadence Semantics

Preserve repeated access at these boundaries:

- `chunk`
- `revision_batch`
- `execution_level`
- `merge_candidate`
- provider attestation operations

Each boundary receives a fresh nonce/sequence and ephemeral-key signature within the FIDO-approved run scope.
No cross-process grant is serialized.
No run-wide bearer is placed in environment or files.
Cache reuse does not reuse signing authority.
Cache reuse remains bound to exact command, source closure, toolchain/container, authority/substrate, environment profile, and source digest.
Receipt-only successor commits do not broaden authority.
Revision-batch changes force the appropriate new plan/run/result operations.

## Approval Integration

`approve-verification-profile` in provider mode:

1. Loads and validates the closed profile.
2. Resolves repository scope/base/candidate/authority closure.
3. Resolves the non-secret provider handle.
4. Resolves and validates authoritative substrate capability policy.
5. Constructs `approve_profile` request.
6. Obtains or validates the FIDO run authorization and a fresh ephemeral-key-signed approval operation.
7. Verifies and independently compares it.
8. Writes a v2 approval containing public evidence/provenance only.

The approval contains no receipt key, PIN, credential secret, environment secret, or reusable capability.
Cancelled/denied/unavailable authority writes no approved artifact.

## Planning Integration

`plan-verification` in provider mode:

- validates v2 approval and its public evidence
- recomputes repository/profile/base/candidate closure
- revalidates provider identity/version
- revalidates authoritative substrate handle/document freshness
- requests fresh `plan_verification` evidence
- binds exact cadence/boundary and cache identity
- emits only a v2 plan

Legacy approval cannot authorize v2 plan issuance.
V2 approval cannot be consumed by legacy HMAC plan mode.
Missing, stale, mismatched, or incomplete substrate evidence cannot produce an executable verified plan.

## Execution Integration

Production provider mode must not execute repository commands directly on the host.
For each admitted lane:

1. Revalidate plan, candidate, repository, authority, and substrate closure.
2. Request fresh ephemeral-key-signed `run_verification` authority within the active run scope.
3. Ask the broker to prepare and inspect the exact run-owned container.
4. Send exact contained argv and declared environment through `substrate_execute`.
5. Receive bounded outputs and public execution evidence.
6. Reinspect image/container/toolchain/generator identity.
7. Receive an ephemeral-key-signed `observed_result` over the exact execution/substrate evidence.
8. Request cleanup and require a distinct ephemeral-key-signed `cleanup_result` over exact-ID absence evidence.
9. Request `record_result`/final-receipt authority over the ordered run-authorization, execution, observation, cleanup, and provider digests.
10. Publish a passing receipt only if the complete chain validates.

Host runner behavior remains for explicit legacy/unit-test modes only.
No production child inherits provider socket, Docker socket, FIDO devices, authority state, HOME credentials, receipt key, or verifier handles.

## Provider Attestation Integration

Remote evidence is not trusted merely because a provider name appears.
The kernel must:

- validate exact declared provider and lane
- bind exact head/candidate and request digest
- validate provider-origin evidence under existing policy
- obtain a fresh `provider_attestation` FIDO operation
- compare the returned provider/lane/head/result/substrate bindings
- record provider provenance in the receipt
- reject altered, replayed, cross-run, cross-lane, cross-provider, stale, or incomplete evidence

The broker is not allowed to invent a successful provider result.
It authorizes a caller-supplied result only after exact evidence validation inputs are present.

## Substrate Handle Resolution

In v2/provider mode, `DM_VERIFICATION_SUBSTRATE` is a non-secret logical handle only.
Do not hash the handle string as proof.
Resolve it through the fixed companion.
Require a valid signed schema-v2 substrate document.
Require authoritative status.
Require candidate-container endpoint access denial: the contained workload receives no Docker, broker, FIDO, credential, or service-manager surface.
Require exact endpoint/engine/image/container/toolchain/generator/run/candidate/lane bindings.
Require freshness before and after execution.
Require verified cleanup for a passing receipt.
An opaque label, Docker context, tag, socket pathname, stale document, incomplete evidence, or tombstone cannot pass.
Explicit schema-v1 legacy mode retains the released opaque-substrate semantics and cannot enter provider mode; tests keep that behavior separate and prove no cross-mode reuse.

## Production Composition and Offline Verification

Replace the chunk-02 binary skeleton wiring with explicit production composition after FIDO, IPC, state, and Docker packages exist.
The daemon binary rejects unavailable or stub libfido2 and cannot silently select fake backends.
The client exposes a stable offline verification invocation that accepts only recorded public enrollment, revocation, FIDO authorization, ephemeral public key, and ordered signed-chain artifacts.
Offline verification does not connect to the daemon, Docker, or a FIDO device; it returns stable exit codes for valid, malformed, incomplete, revoked-at-issuance, reordered, substituted, and unknown-generation evidence.
Binary-level tests prove the real mains select production backends and historical verification remains usable after daemon shutdown or uninstall with retained public state.
Daemon `verify_envelope` and client offline verification call one shared internal chain verifier rather than duplicating signature/binding logic.

## Mutation and Concurrency

Retain existing repository mutation detection.
If candidate inputs change, invalidate or refresh according to current policy and require fresh authority.
Receipt append/merge remains lock-protected.
Concurrent lanes may execute only when their dependency/cadence policy permits.
Authority calls remain independent and uniquely sequenced.
Cancellation propagates to broker execution and cleanup.
If the client dies after execution but before receipt publication, recovery cleanup runs and no passing receipt appears without revalidation.

## Stable Error Semantics

Add closed errors for:

- provider required
- provider/legacy mode conflict
- provider unavailable
- provider identity invalid
- provider version incompatible
- provider response malformed
- provider verification failed
- authority denied
- authority cancelled
- authority stale/replayed
- substrate handle invalid
- substrate evidence incomplete
- candidate control surface exposed
- substrate drifted
- cleanup unverified

Errors must not embed request bodies, signatures, raw credential IDs, paths outside safe installed roots, Docker bodies, environment values, or repository content. Stable public credential references may appear only inside signed v2 evidence, never logs, diagnostics, status output, argv, environment, or fixtures.

## Companion Skills

Load:

- `developer-essentials:auth-implementation-patterns` for mode separation and exact authorization bindings.
- `developer-essentials:error-handling-patterns` for stable fail-closed error translation.
- `developer-essentials:e2e-testing-patterns` for CLI/cadence/cancellation coverage.

## Acceptance Criteria

- [ ] AC-01 All four repository-verification CLI commands support explicit provider mode and retain explicit legacy `--receipt-key-stdin` compatibility.
- [ ] AC-02 Provider mode and legacy mode are mutually exclusive and neither automatically falls back to the other.
- [ ] AC-03 Production resolves only the fixed root-owned companion with version/protocol/ownership/mode/no-follow checks; repository, `PATH`, environment, cache, and symlink selections fail.
- [ ] AC-04 The exact operation mapping table is implemented with no aliases or reused response across operations.
- [ ] AC-05 Python reconstructs and compares every applicable repository/run/profile/base/candidate/lane/provider/authority/substrate/result binding after public verification.
- [ ] AC-06 A forged verifier success, altered response, altered request digest, wrong verifier identity, or untrusted registry generation fails.
- [ ] AC-07 One FIDO run authorization binds the ephemeral public key and closed scope; `approve_profile`, `plan_verification`, `run_verification`, observed result, cleanup result, `record_result`, and `provider_attestation` each require a fresh nonce/sequence/ephemeral signature.
- [ ] AC-08 Chunk, revision-batch, execution-level, merge-candidate, and provider-attestation cadence tests prove repeated scoped authority without repeated touch or an exported bearer.
- [ ] AC-09 V1 approval/plan/receipt cannot authorize v2 issuance and v2 artifacts cannot silently enter legacy mode.
- [ ] AC-10 Production provider mode never sends a receipt key to Python or a child process and never executes candidate commands through the host runner.
- [ ] AC-11 Candidate execution occurs in the exact broker-measured container with exact argv and no provider/Docker/FIDO/authority/credential inheritance.
- [ ] AC-12 In v2/provider mode `DM_VERIFICATION_SUBSTRATE` resolves to an authoritative signed document and opaque labels/hashing the handle fail; explicit schema-v1 mode retains its released substrate semantics with no cross-mode fallback or artifact reuse.
- [ ] AC-13 Unenrolled endpoint, stale document, engine/image/toolchain drift, missing candidate isolation, or cleanup tombstone cannot produce a passing plan or receipt; trusted-host daemon tampering is explicitly outside scope.
- [ ] AC-14 Engine/image/container/Go 1.26.5/generator/run/candidate/lane evidence is checked before and after execution.
- [ ] AC-15 Passing receipts require signed exact-ID cleanup absence evidence; execution success with cleanup failure is non-passing.
- [ ] AC-15A Python and the fixed Go verifier validate the complete FIDO run authorization → ephemeral operation → observed result → cleanup result → final receipt chain offline; missing/reordered/substituted elements fail.
- [ ] AC-16 Cache reuse remains bound to exact command, source closure, toolchain/container, authority/substrate, environment profile, and source digest.
- [ ] AC-17 Repository mutation and revision-batch paths invalidate stale authority and request fresh operations without corrupting concurrent receipt suffixes.
- [ ] AC-18 Provider evidence binds exact provider, lane, candidate/head, request, result, authority, and substrate provenance.
- [ ] AC-19 Wrong repository, run, profile, base, candidate, boundary, lane, provider, substrate, result, nonce, sequence, timestamp, or operation fails.
- [ ] AC-20 Cancellation/timeout/client death invokes broker cleanup and cannot publish a pass without fresh revalidation.
- [ ] AC-21 Errors and CLI output remain bounded/redacted and contain no secret-shaped values, assertions, Docker bodies, environment values, or repository content.
- [ ] AC-22 Focused CLI, authority-provider, repository-verification, planning, execution, provider, mutation, cache, and concurrency tests pass.
- [ ] AC-23 `./tools/validate-workflow-kernel.py` passes or reports only an exact later-owned inventory gap; no expected red is called green.
- [ ] AC-24 `git diff --check` passes and only owned files change.
- [ ] AC-25 Tests assert no Python Workflow Kernel module opens the broker socket path directly.
- [ ] AC-26 Both final Go mains use explicit production composition with real FIDO/IPC/state/Docker implementations and no fake, stub, or environment-selected fallback.
- [ ] AC-27 The fixed client provides daemon-independent offline historical verification with stable exit codes and rejects every missing, reordered, altered, revoked-at-issuance, or unknown-generation chain element.
- [ ] AC-28 Binary-facing tests prove production backend wiring and offline verification after daemon shutdown using retained public state only.
- [ ] AC-29 Static and runtime tests prove Workflow Kernel cannot reach key/endpoint lifecycle operations and follows `authorization_required`/`authority_unavailable` retry semantics without prompt loops.
- [ ] AC-30 The same vector corpus produces identical verdicts through daemon `verify_envelope` and client offline verification because both use one shared internal verifier.

## Behavioral Contract Inputs

- `REQ-001`: preserve inspected Workflow Kernel conventions.
- `REQ-003`: identical Linux/macOS authority semantics through one provider contract.
- `REQ-004`: FIDO authority without exported key.
- `REQ-005`: no secret inheritance or output.
- `REQ-006`: authoritative substrate binding.
- `REQ-007`: fail-closed repeated cadence and provider operations.
- `REQ-008`: binding, replay, cancellation, concurrency, and cleanup adversaries.
- `CHK-013`: CLI mode and resolution matrix.
- `CHK-014`: cadence fresh-authority matrix.
- `CHK-015`: contained execution and cleanup matrix.
- `CHK-016`: provider evidence provenance matrix.

## Verification Commands

Use repository-sanctioned Python 3.12 execution.
Run focused unit modules first.
Run the offline Workflow Kernel validator after focused convergence.
Run `git diff --check`.
Do not use a live broker, authenticator, installed service, or external repository.
Do not call a missing lane a pass.

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
- Do not modify Go internal packages other than the five listed composition-root files; do not modify `internal/admin/`, `packaging/`, or any file owned by chunk 06, which runs in parallel.
- Do not edit external Assembly/Baseplate worktrees.
- Do not expose a raw key, PIN, raw FIDO credential ID, general signing capability, socket path override, or reusable bearer. Stable public credential references may appear only inside signed v2 evidence and receipts; never in logs, diagnostics, status output, environment, argv, or fixtures.
- Do not trust caller digests, opaque substrate labels, Docker contexts, or provider names without recomputation/evidence.
- Do not weaken legacy validation to make new tests pass.
- Do not stage, commit, push, install, enroll, release, tag, publish, or run live services.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

The production raw-key pipe is impossible to protect from same-UID worker interception.
FIDO public evidence avoids key export, while Python binding checks prevent a confused-deputy verifier result.
The enrolled Docker engine is trusted host infrastructure; candidate containers receive none of its control surfaces.
Cleanup is part of receipt validity.
===== END plans/macos-authority-broker/prompts/05-kernel-cadence-integration.md =====

===== BEGIN plans/macos-authority-broker/prompts/06-cross-platform-packaging.md =====
# Chunk: Add Parity Packaging and Operator Lifecycle

## Context

This chunk runs in parallel with Workflow Kernel integration after the Go authority and Docker substrate exist.
It packages the same broker operations for Linux and macOS without introducing platform-only features.
Real apply adapters are implemented and tested against temporary/fake roots, but never invoked against live root/service state in this task.

## Task

Implement the shared admin command dispatcher, real injectable filesystem/service apply adapters, and deterministic staged lifecycle operations.
Add systemd socket/service resources for Linux and a launchd socket-activation plist for macOS.
Expose identical commands, status fields, reason codes, safety checks, state retention, rollback, and uninstall semantics.
Keep service-manager mechanics behind platform adapters.
Leave the consolidated hostile matrix to chunk 07, but implement and unit-test the actual install/rollback/status/recover/uninstall/purge behavior here without live invocation.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/cmd/workflow-authority-admin/main.go` | Create | Thin stable admin CLI and exit mapping |
| `native/workflow-authority/internal/admin/admin.go` | Create | Shared lifecycle state machine and dry-run/staging implementation |
| `native/workflow-authority/internal/admin/apply_linux.go` | Create | Real injectable systemd/filesystem apply adapter |
| `native/workflow-authority/internal/admin/apply_darwin.go` | Create | Real injectable launchd/filesystem apply adapter |
| `native/workflow-authority/internal/admin/filesystem.go` | Create | No-follow atomic install/rollback/remove primitives |
| `native/workflow-authority/internal/admin/admin_test.go` | Create | Focused fake-root lifecycle and rollback tests for both real adapters |
| `native/workflow-authority/packaging/systemd/workflow-authority.socket` | Create | Root-owned pathname socket activation |
| `native/workflow-authority/packaging/systemd/workflow-authority.service` | Create | Hardened Linux service policy |
| `native/workflow-authority/packaging/launchd/studio.designmachines.workflow-authority.plist` | Create | Equivalent macOS socket/service activation |

## Files to Read

| File | Why |
|---|---|
| `native/workflow-authority/cmd/workflow-authority/main.go` | Thin command conventions |
| `native/workflow-authority/internal/platform/platform.go` | Shared service-manager boundary |
| `native/workflow-authority/internal/authority/service.go` | Runtime identity and state requirements |
| `native/workflow-authority/internal/state/replay.go` | Public enrollment/revocation/audit retention |
| `native/workflow-authority/internal/dockerapi/cleanup.go` | Exact-ID ledger, cleanup, and recovery state |
| `native/workflow-authority/internal/dockerapi/endpoint.go` | Enrolled endpoint identity and revalidation state |

## Shared Command Surface

Implement exactly:

- `install`
- `enroll-key`
- `enroll-endpoint`
- `status`
- `doctor`
- `rotate-key`
- `revoke-key`
- `recover`
- `uninstall`
- `uninstall --purge`

Do not add platform-specific commands.
The same command on both platforms accepts the same logical options and returns the same public JSON/status/reason schema.
Platform-specific paths may appear only as redacted/safe installed identity metadata where operator documentation requires them.

CLI to protocol mapping:

| CLI command | Protocol operation |
|---|---|
| `enroll-key` | `key_enroll` |
| `enroll-endpoint` | `substrate_enroll_endpoint` |
| `rotate-key` | `key_rotate` |
| `revoke-key` | `key_revoke` |
| `status` | `status` |
| `doctor` | `doctor` |
| `install`, `recover`, `uninstall`, `uninstall --purge` | Local lifecycle operations; no authority protocol frame |

`uninstall --purge` is one command plus a flag, not a separate protocol operation.

Lost-authenticator recovery is exactly:

1. From a UID-0 root console, run `workflow-authority-admin revoke-key --lost <generation>`; this records the lost generation as issuance-revoked without requiring the missing authenticator and preserves its public historical-verification record.
2. Run `workflow-authority-admin enroll-key`; require the replacement authenticator's credential-creation UP/internal-UV ceremony and atomically activate the new generation.
3. Run `workflow-authority-admin doctor`; it must report an active replacement generation and no software-key fallback, without printing credential identifiers.

No repository-context client or Workflow Kernel operation may invoke this sequence.

## Dry-Run and Staging Boundary

Every mutating command supports an injected filesystem/service manager and a non-mutating dry-run plan.
This chunk may build a deterministic staging tree under a test temporary directory.
It must not write `/usr`, `/etc`, `/Library`, `/var`, service-manager state, FIDO devices, or a live Docker endpoint.
The CLI contains the real live-apply path, but tests inject temporary roots/fake service managers and this task never invokes live apply.
Dry-run output contains actions and safe destinations but no keys, PINs, credential references, assertions, raw endpoint responses, or repository content.

## Installation Policy

Define root-owned fixed destinations for:

- client binary
- daemon binary
- admin binary
- service-manager resource
- root state directory
- root run/socket directory
- public trust/enrollment metadata
- audit/revocation metadata

Every path is absolute, normalized, no-follow, and below an approved installation root.
Reject symlinks, hard-link surprises where detectable, wrong owner/mode, writable parents, non-regular binaries, and destination replacement races.
Use a staging directory, verify all candidate files, fsync as appropriate, and atomically install.
Do not trust repository-side scripts as installer authority.

## Candidate Preflight

Before replacement, validate the candidate:

- closed distribution inventory
- exact filenames and roles
- SHA-256 checksums
- Go companion version
- protocol version
- libfido2 exactly 1.17.0 via `pkg-config --modversion libfido2`, linked-library/required-symbol inspection, plus required OpenSSL 3/libcbor/zlib dependencies; because libfido2 has no documented public runtime version query, runtime startup uses the chunk-03 symbol/allocation self-test and reports unverifiable package identity as unavailable
- expected target OS/architecture
- no unexpected writable/executable files
- no secret material
- service resource syntax/closed fields
- version ordering and downgrade policy

Because real distribution signing/notarization is outside this task, model signature/trust verification as an injected required policy.
Never call an unsigned staged artifact production-ready.
Failure leaves the prior installation intact.

## Linux Service Policy

The systemd socket unit owns a pathname Unix socket in a protected runtime directory.
Set explicit user/group/mode and `RemoveOnStop=true`; launchd removal/uninstall implements the equivalent explicit socket cleanup.
The service unit consumes socket activation rather than accepting arbitrary `--socket` input.
Apply applicable hardening:

- no new privileges
- private temporary directory
- protected system/home/control groups/kernel tunables/modules where compatible
- restrictive address families
- explicit device access needed for FIDO only
- bounded file descriptors/processes/memory
- working/state/runtime directories with fixed ownership
- disabled core dumps
- restart and timeout policy that does not loop prompt floods
- minimal environment

Document any hardening directive omitted because it conflicts with required HID/Docker Unix-socket access.
Omission must be explicit and tested later, not silent.

## macOS Service Policy

The launchd plist uses socket activation with a fixed pathname and root service label.
Set fixed program arguments and service identity.
The LaunchDaemon performs libfido2 HID device I/O for the authenticator; document any macOS device-access constraint explicitly and keep the real internal-UV hardware lane gated rather than substituting a client-side device path.
Do not use `PATH`, shell commands, user-selected sockets, LaunchAgent-only authority, or repository paths.
Use equivalent keepalive/throttle/resource/core-dump controls available in launchd.
The daemon still enforces peer credentials and FIDO authorization; launchd identity alone is not approval.
Do not add XPC, Secure Enclave, LocalAuthentication, Swift, app-bundle, or GUI-only behavior.

## Enrollment and Key Lifecycle

`enroll-key` invokes the shared FIDO ceremony and persists public enrollment only.
`rotate-key` enrolls a new generation, verifies it, atomically activates it, and retains prior public verification material.
`revoke-key` prevents new authority under the generation while preserving historical verification.
Key loss never triggers a software-key fallback.
No operation prints credential identifiers or assertions.
Real device operations remain unavailable in dry-run/unit mode.

`enroll-endpoint` derives endpoint/engine evidence through the broker.
It never trusts `DOCKER_HOST` or a context label.
Enrollment records the actual endpoint and engine identity; the engine is trusted host infrastructure, and status reports whether candidate-control-surface exclusion checks are configured.
Endpoint rotation retains audit history and invalidates active substrate state.

## Status and Doctor

Expose safe parity fields:

- installed/staged version
- protocol compatibility
- service configured/running/reachable state
- socket ownership/mode validity
- FIDO availability and enrollment generation state without credential reference
- libfido2 ABI compatibility
- endpoint enrolled/reachable/identity-matched state
- candidate-control-surface policy state
- cleanup/recovery backlog counts without object IDs
- public audit/revocation health
- last safe error code

Do not print raw config, paths containing private user data unless required and safe, device serials, credential references, signatures, Docker bodies, container IDs, repository identifiers, or environment values.

## Recovery and Uninstall

`recover` reconciles only exact substrate IDs in root-owned state and reports safe counts/reasons.
Default `uninstall` stops/disables service, removes binaries/socket/resources, and preserves public enrollment, revocation, historical verification, and audit state.
It reports the exact recovery command if rollback/uninstall cannot finish.
`uninstall --purge` requires explicit root-console confirmation. It attempts FIDO UV when the enrolled authenticator is available, but root-console lost-authenticator recovery must remain possible.
Lost-authenticator recovery permits the documented root-console path, records revocation of the lost generation, and never recovers or generates a software private credential.
It uses the exact `revoke-key --lost <generation>` → `enroll-key` → `doctor` sequence above on both platforms.
Purge never follows symlinks or removes outside exact approved roots.
Every step is idempotent and rollback-aware.

## Platform Parity Matrix

For each shared command, define:

- identical input validation
- identical logical state transition
- identical public response schema
- identical success/failure reason codes
- identical preservation/destruction policy
- OS-specific service-manager calls hidden behind one interface
- explicit unsupported-environment status only when a required dependency is absent on both product paths

Hardware or libfido2 absence is fail-closed availability, not a reduced feature mode.

## Companion Skills

Load:

- `assembly:golang-patterns` for Go CLI/state interfaces.
- `developer-essentials:auth-implementation-patterns` for enrollment, rotation, revocation, and purge confirmation.
- `developer-essentials:error-handling-patterns` for rollback and actionable recovery messages.
- `developer-essentials:e2e-testing-patterns` for injectable lifecycle seams.

## Acceptance Criteria

- [ ] AC-01 Both platforms expose exactly the ten shared commands and identical logical options/status/reason schemas.
- [ ] AC-02 Real Linux and macOS apply/service/filesystem paths are implemented behind injected interfaces; tests execute them only against temporary/fake roots and this task performs no live mutation.
- [ ] AC-03 Fixed installation roots, ownership, modes, no-follow components, writable-parent checks, and atomic replacement are enforced.
- [ ] AC-04 Candidate preflight verifies inventory, checksums, version ordering, OS/arch, protocol, libfido2 exactly 1.17.0/dependencies, and injected distribution trust before replacement; unavailable/stub builds are rejected.
- [ ] AC-05 Failed preflight or any install step leaves the prior installation usable and returns an actionable recovery command.
- [ ] AC-06 systemd socket/service units use fixed socket activation, root ownership, minimal environment, core-dump suppression, and documented hardening exceptions.
- [ ] AC-07 launchd uses fixed socket activation and program identity with equivalent resource/throttle/core policy and no XPC/Swift/GUI-only features.
- [ ] AC-07A systemd and launchd packaging declare the daemon-owned HID access intent required by libfido2; platform-specific constraints remain explicit native-lane gaps.
- [ ] AC-08 Key enrollment/rotation/revocation persist no private material; prior public keys remain for historical verification and revoked generations cannot issue.
- [ ] AC-09 Endpoint enrollment derives live endpoint/engine evidence and reports candidate-control-surface policy without claiming resistance to deliberate host-engine tampering.
- [ ] AC-10 Status/doctor output passes a closed safe-field allowlist and excludes credential/device/object/repository/secret/raw-response data.
- [ ] AC-11 Recovery acts only on exact root-ledger IDs and never expands authority from labels or names.
- [ ] AC-12 Default uninstall preserves public enrollment/revocation/audit state; purge is explicit, uses FIDO when available, and supports documented root-console lost-authenticator recovery.
- [ ] AC-13 Install, status, doctor, recover, rotate, revoke, uninstall, and purge plans are idempotent under repeated calls and partial-failure injection.
- [ ] AC-14 Invalid config fails before service start and never warns-then-continues with permissive defaults.
- [ ] AC-15 The same parity state-transition table is consumable by chunk 07 tests for both platform adapters.
- [ ] AC-16 No live installation, service registration, FIDO operation, endpoint enrollment, or privileged write occurs during verification.
- [ ] AC-17 Pinned Go 1.26.5 build/vet for `./cmd/workflow-authority-admin` and `./internal/admin` passes; injected filesystem/service/FIDO/endpoint fakes are constructible from an external test package.
- [ ] AC-17A Tests prove install, rollback, status, recover, uninstall, and purge execute real adapter logic against temporary/fake roots while leaving live host state unchanged.
- [ ] AC-17B Chunk-local tests execute each real apply adapter through injected fake service managers and temporary roots; cross-compilation alone is not native adapter proof.
- [ ] AC-18 `git diff --check` passes and only owned files change.
- [ ] AC-19 Linux and macOS parity tests execute the exact lost-authenticator command sequence and reject it from non-root/repository peers.
- [ ] AC-20 Fake-root tests assert every write remains under the injected root and run each mutating command twice to prove idempotent end state.

## Behavioral Contract Inputs

- `REQ-003`: parity install/status/recovery/uninstall semantics.
- `REQ-004`: non-exportable FIDO enrollment lifecycle.
- `REQ-005`: safe operator output.
- `REQ-009`: systemd/launchd parity and Baseplate prerequisites.
- `REQ-010`: no live install/enrollment/publication without another gate.
- `CHK-017`: parity admin state-transition table.
- `CHK-018`: install rollback and no-follow safety.
- `CHK-019`: public-state retention and explicit root-console purge, including lost-authenticator recovery.

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
- Do not modify Workflow Kernel files; chunk 05 runs in parallel.
- Do not add platform-only commands or reduced-security fallback modes.
- Do not perform a live privileged mutation.
- Do not expose credential references, assertions, PINs, Docker bodies/object IDs, repository identities, or environment values.
- Do not stage, commit, push, install, enroll, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

systemd and launchd both support socket activation, enabling one daemon/client protocol with narrow packaging adapters.
Public enrollment and revocation state must outlive ordinary uninstall so historical receipts remain verifiable.
The real privileged, hardware, and endpoint acceptance suite remains a separate authorization gate.
===== END plans/macos-authority-broker/prompts/06-cross-platform-packaging.md =====

===== BEGIN plans/macos-authority-broker/prompts/07-parity-adversarial-harness.md =====
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
===== END plans/macos-authority-broker/prompts/07-parity-adversarial-harness.md =====

===== BEGIN plans/macos-authority-broker/prompts/08-docs-metadata-validation.md =====
# Chunk: Migrate Consumers, Document, Version, and Validate

## Context

This final product chunk migrates the canonical Pipeline and Assembly consumers, documents the implemented Linux-first broker, records the repository convention expansion, updates canonical metadata, regenerates Codex shims, and runs Depot validation.
It must describe real evidence and gaps without performing a release or live installation.

## Task

Write one cross-platform operator and threat-model guide.
Update Workflow Kernel documentation and skill contracts for public FIDO provider mode, legacy HMAC separation, non-secret substrate handles, and repeated cadence.
Document systemd and launchd workflows with identical semantics.
Document the current OrbStack socket as trusted host infrastructure and state precisely that deliberate developer/host-agent engine tampering is outside scope.
Migrate the canonical Pipeline orchestrator and Assembly build/test/profile surfaces from production `--receipt-key-stdin` use to fixed v2 provider and substrate handles, preserving legacy HMAC only as an explicit compatibility path.
Update canonical plugin/marketplace versions, regenerate derived Codex manifests, and run repository validation.

## Files to Modify

| File | Action |
|---|---|
| `docs/workflow-authority.md` | Create |
| `docs/workflow-kernel.md` | Modify |
| `plugins/workflow-kernel/skills/workflow-kernel/SKILL.md` | Modify |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md` | Modify |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Modify canonical production consumer |
| `plugins/assembly/commands/assembly-build.md` | Modify canonical command consumer |
| `plugins/assembly/skills/assembly-build/SKILL.md` | Regenerate command-skill alias only |
| `plugins/assembly/agents/workflow/go-test-runner.md` | Modify canonical agent consumer |
| `plugins/assembly/references/repository-verification-profile.example.json` | Modify canonical handle/profile example |
| `AGENTS.md` | Modify |
| `CLAUDE.md` | Modify while preserving the pre-existing Airlift marker |
| `docs/dependency-graph.md` | Modify minimum-version edges |
| `tools/check-dependencies.sh` | Modify dependency assertions |
| `plugins/workflow-kernel/.claude-plugin/plugin.json` | Modify canonical version |
| `plugins/pipeline/.claude-plugin/plugin.json` | Modify dependency/version only as required by consumer migration |
| `plugins/assembly/.claude-plugin/plugin.json` | Modify dependency/version only if implementation requires it |
| `.claude-plugin/marketplace.json` | Modify canonical versions |
| `plugins/workflow-kernel/.codex-plugin/plugin.json` | Regenerate only |
| `plugins/pipeline/.codex-plugin/plugin.json` | Regenerate only |
| `plugins/assembly/.codex-plugin/plugin.json` | Regenerate only |
| `.agents/plugins/marketplace.json` | Regenerate only |

## Documentation Requirements

Include:

- threat actors, protected assets, trust assumptions, and residual trusted-display risk
- identical Linux/macOS architecture and the narrow adapter differences
- compatible FIDO2 authenticator requirements, UP/UV policy, enrollment, rotation, revocation, loss, and recovery
- daemon-owned libfido2 device I/O, root-only raw allow-list credential ID handling, and raw uncompressed P-256 public-key storage for offline verification
- libfido2 and exact Go 1.26.5 prerequisites
- candidate-container exclusion from Docker, broker, FIDO, credential, and service-manager control surfaces
- exact install, status, doctor, endpoint enrollment, use, recovery, uninstall, and purge steps for both service managers
- explicit distinction between staged/offline proof and separately gated live acceptance
- exact Baseplate-compatible example exporting only fixed non-secret provider and substrate handles
- explicit legacy `--receipt-key-stdin` compatibility with no production fallback
- exact historical verification chain: FIDO run authorization to ephemeral public key to ordered operation, observed-result, cleanup-result, and final-receipt signatures
- cadence examples for chunk, revision batch, execution level, merge candidate, and provider attestation
- failure/recovery reason codes and zero-residue cleanup requirement
- uninstall preservation of public enrollment/revocation/audit state
- remaining risks and exact next authorization gates

Never print or demonstrate a real PIN, credential reference, assertion, receipt key, Docker object ID, user-specific socket path, token, or repository secret.
Use placeholders that cannot be mistaken for credentials.

## Canonical Consumer Migration

Update the Pipeline execution orchestrator, Assembly command and agent, and Assembly verification-profile example to use only the fixed non-secret provider and substrate handles in production v2 mode.
Preserve the complete repeated cadence across chunk, revision batch, execution level, merge candidate, result recording, and provider attestation.
Remove production instructions that pipe `HOST_AUTHORITY_BROKER` bytes to `--receipt-key-stdin`; retain that flag only in clearly named legacy schema-v1 compatibility documentation/tests with no automatic fallback.
Set exact minimum Workflow Kernel dependencies based on the implemented unreleased version, update the dependency graph and dependency validator, then regenerate the Assembly command-skill alias and Codex manifests from canonical sources.
Add validator coverage that fails if canonical Pipeline/Assembly production surfaces still prescribe raw-key stdin, an opaque substrate label, or Workflow Kernel `>=0.6.1` when the new provider contract requires a later version.

## Required Execution Order

This large final chunk follows a fixed order to avoid a half-migrated repository:

1. Inspect current canonical versions and record chosen unreleased versions plus rationale.
2. Migrate Pipeline/Assembly canonical consumers and dependency assertions.
3. Update canonical manifests, then regenerate aliases and Codex manifests.
4. Write operator/threat-model/repository-convention documentation from the implemented behavior.
5. Run the complete validation suite last against the converged tree.

If the tool budget prevents completion, do not describe the feature as complete; `NOT-COVERED` must enumerate every unwritten document, unmigrated consumer, ungenerated artifact, and unrun validator exactly.

## Repository Convention Update

Depot previously allowed one sanctioned executable exception: stdlib-only Python 3.12 Workflow Kernel.
Update `AGENTS.md` and canonical `CLAUDE.md` to describe the new separately built Go host companion, its non-shipping source/tests, Go 1.26.5/libfido2 validation, and Linux/macOS packaging.
Do not weaken the Python stdlib-only rule.
Do not imply the native companion is automatically installed with the plugin cache.

## Metadata and Generation

Choose the next coherent unreleased versions based on current canonical manifests and actual compatibility changes.
Update Claude manifests first.
Regenerate Codex manifests; never hand-edit generated JSON.
Regenerate command-skill aliases only if canonical command sources changed.
Keep Assembly dependency changes minimal and evidence-based.
Do not create tags, releases, marketplace publications, installs, or cache updates.

## Validation

Run:

- focused Python and Go validator suites
- `./tools/validate-workflow-authority.py`
- `./tools/validate-workflow-kernel.py`
- `./tools/generate-codex-manifests.py --check`
- `./tools/generate-codex-command-skills.py --check`
- `./tools/validate-dual-compat.sh`
- `./tools/check-dependencies.sh`
- `./tools/validate-composition.sh --all`
- `git diff --check`

Record exact commands, outcomes, unavailable external lanes, and the worktree diff scope.
Do not call hardware, live root-service, or real-engine acceptance green unless it actually ran.

## Companion Skills

Load:

- `developer-essentials:auth-implementation-patterns` for accurate threat/runbook wording.
- `developer-essentials:error-handling-patterns` for recovery guidance.

## Acceptance Criteria

- [ ] AC-01 Documentation states identical Linux/macOS features and names only systemd/launchd and peer-credential syscalls as adapters.
- [ ] AC-02 Threat model explains why no production receipt key exists, why the enrolled Docker engine is trusted host infrastructure, and what deliberate-host threats are excluded.
- [ ] AC-03 Setup/use/recovery/rotation/revocation/uninstall/purge steps are exact for both platforms and distinguish offline from live gates.
- [ ] AC-04 Baseplate example exports only non-secret fixed provider/substrate handles and uses all repeated cadence operations.
- [ ] AC-04A Documentation explains how historical verification validates the recorded FIDO-to-ephemeral-key-to-result/cleanup/receipt chain without a live daemon.
- [ ] AC-05 Current OrbStack is documented as a trusted host endpoint whose socket is never exposed inside candidate containers.
- [ ] AC-06 Residual terminal-spoofing, deliberate host-engine tampering, hardware availability, and privileged-service risks are explicit.
- [ ] AC-07 Repository executable conventions describe the Go companion without weakening Workflow Kernel’s stdlib-only Python rule.
- [ ] AC-08 Canonical versions/dependencies are coherent and Codex manifests are regenerated rather than hand-edited.
- [ ] AC-09 All listed validators pass or report exact environmental gaps; unavailable lanes are not promoted to proof.
- [ ] AC-10 No install, enrollment, release, tag, push, PR, publication, or external worktree mutation occurs.
- [ ] AC-11 The handoff lists implementation decisions, test evidence, remaining risks, and the exact next authorization gate.
- [ ] AC-12 `git diff --check` passes and only owned files plus the preserved Airlift marker remain.
- [ ] AC-13 Canonical Pipeline and Assembly execution surfaces use fixed non-secret v2 provider/substrate handles across every repeated cadence operation with no production HMAC fallback.
- [ ] AC-14 Pipeline/Assembly minimum Workflow Kernel versions, dependency graph, manifests, generated aliases/shims, and dependency checks agree exactly.
- [ ] AC-15 Validation fails on any remaining canonical production `--receipt-key-stdin`, opaque-substrate, or stale `>=0.6.1` instruction.
- [ ] AC-16 Operator docs match the implementation: the daemon owns device I/O, the raw allow-list credential ID remains root-only, and the retained public key uses the documented stdlib-verifiable P-256 format.
- [ ] AC-17 Documentation names the controlling-terminal run-open flow, root-only lifecycle admission matrix, one-retry behavior, and exact lost-authenticator command sequence.
- [ ] AC-18 Work follows the required order, all validators run last, and any budget truncation produces an exact `NOT-COVERED` inventory rather than a completion claim.

## Behavioral Contract Inputs

- `REQ-001` through `REQ-010` receive documentation and final validation traceability.
- `CHK-023`: operator parity/documentation review.
- `CHK-024`: canonical/generated metadata and full Depot validation.
- `CHK-025`: prohibited live/publication actions remain absent.

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
- Preserve unrelated changes and the existing Airlift marker.
- Do not hand-edit generated Codex manifests.
- Do not disclose secret/authenticator/Docker/repository values.
- Do not stage, commit, push, install, enroll, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

FIDO2 authorizes one closed run and binds its memory-only ephemeral signing key.
Docker is trusted host infrastructure; candidate containers must receive none of its control surfaces.
Linux is primary, but macOS must satisfy the same contract and tests.
===== END plans/macos-authority-broker/prompts/08-docs-metadata-validation.md =====
