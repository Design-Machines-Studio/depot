# OpenRouter External Payload Authorization

Apply this contract before every Pipeline workflow sends prompt or artifact
content bytes to the OpenRouter service, including read-only research,
assessment, and adversarial review lanes. Pipeline supports two explicit
authorization modes:

- `exact-digest` (default): the user approves each distinct ordered payload.
- `trusted-boundary`: the user opts into automatic authorization for the run;
  immediately before every send, the canonical disclosure scanner must accept
  the exact bytes and the authorization helper must verify they are unchanged.

Enable the low-friction mode for a trusted local run with:

```bash
export OPENROUTER_PAYLOAD_AUTHORIZATION=trusted-boundary
```

This setting authorizes policy-accepted payloads, not arbitrary disclosure. It
does not bypass credential detection, exact-byte verification, owned-path
restrictions, native-vendor rejection, or provider provenance checks.

## Coherent bundle

Resolve one installed OpenRouter bundle through workflow-kernel with:

```text
resolve-plugin-bundle --plugin openrouter
--minimum-version 1.7.2
--required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh
--required-asset skills/openrouter-delegate/references/delegation-security-policy.json
--required-executable skills/openrouter-delegate/references/delegation-boundary.sh
--required-executable skills/openrouter-delegate/references/payload-authorization.sh
--active-host <claude|codex>
```

Use every asset from that selected root. Never resolve one helper independently
or accept a caller-selected executable path.

## Authorization protocol

For each external lane:

1. Materialize the exact ordered system and user prompt files that would be
   sent. Artifact packs are prompt files; path lists are boundary metadata and
   are not a substitute for the exact content.
2. Run `delegation-boundary.sh --mode artifact-delegation` over every exact
   outbound file. A disclosure decline returns the lane to its trusted local
   fallback without network contact.
3. Run `payload-authorization.sh snapshot` with the exact files in send order.
4. Read `OPENROUTER_PAYLOAD_AUTHORIZATION`:
   - `exact-digest` or unset: if the user has not supplied that lane's combined
     digest, return `PAYLOAD APPROVAL REQUIRED`. On approval, rebuild the files
     and run `payload-authorization.sh verify --approved-sha256
     <user-approved-digest>`.
   - `trusted-boundary`: run `payload-authorization.sh
     verify-trusted-boundary --policy <canonical-policy>` with the manifest and
     exact files. This command reruns the canonical scanner immediately before
     transmission and verifies the ordered bytes still match the snapshot.
5. Send only successfully verified files through the wrapper and set
   `OPENROUTER_AUTHORIZATION_MODE` so the content-free provider receipt records
   `exact-digest` or `trusted-boundary`.

The digest authorizes disclosure of those exact ordered content bytes to the
OpenRouter service. It does not bind model, fallback, endpoint order, sorting,
ZDR, or other routing metadata. Those controls remain independently constrained
by routing policy, native-vendor rejection, and provider/model provenance
receipts. A routing-only change does not reuse the digest to send different
content.

A child lane cannot silently switch authorization modes, copy its own digest
into the `exact-digest` approval input, or treat a per-file hash list as
authority. A boundary decline is recorded as `host_disclosure_declined` and is
never retried or routed around. Missing or mismatched exact approval is a
preparation state, not provider failure and not a clean review result.

`trusted-boundary` is run-scoped authority supplied by the user or trusted host
environment. Do not persist it into repository files, infer it from an API key,
or enable it merely because OpenRouter was selected as an executor.
