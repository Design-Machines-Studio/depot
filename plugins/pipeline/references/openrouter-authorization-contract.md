# OpenRouter External Payload Authorization

Apply this contract before every Pipeline workflow sends prompt or artifact
content bytes to the OpenRouter service, including read-only research,
assessment, and adversarial review lanes. General OpenRouter permission, an API
key, and an orchestrator's decision are not disclosure authority.

## Coherent bundle

Resolve one installed OpenRouter bundle through workflow-kernel with:

```text
resolve-plugin-bundle --plugin openrouter
--minimum-version 1.7.0
--required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh
--required-asset skills/openrouter-delegate/references/delegation-security-policy.json
--required-executable skills/openrouter-delegate/references/delegation-boundary.sh
--required-executable skills/openrouter-delegate/references/payload-authorization.sh
--active-host <claude|codex>
```

Use every asset from that selected root. Never resolve one helper independently
or accept a caller-selected executable path.

## Two-pass protocol

For each external lane:

1. Materialize the exact ordered system and user prompt files that would be
   sent. Artifact packs are prompt files; path lists are boundary metadata and
   are not a substitute for the exact content.
2. Run `delegation-boundary.sh --mode artifact-delegation` over every exact
   outbound file. A disclosure decline returns the lane to its trusted local
   fallback without network contact.
3. Run `payload-authorization.sh snapshot` with the exact files in send order.
4. If the user has not supplied that lane's combined digest, return
   `PAYLOAD APPROVAL REQUIRED` with the content-free combined digest. Do not
   call the wrapper. The root collects all distinct lane digests and asks the
   user once whether those exact content payloads may be sent. For a batch,
   present a content-free mapping of logical lane, requested/fallback model,
   and digest so the approvals are distinguishable.
5. On approval, rebuild the identical files, take a fresh snapshot, and run
   `payload-authorization.sh verify --approved-sha256 <user-approved-digest>`
   with the exact files in the same order immediately before network contact.
6. Send those verified files through the wrapper. Any content byte, order,
   membership, system-prompt, or artifact change requires a new approval.

The digest authorizes disclosure of those exact ordered content bytes to the
OpenRouter service. It does not bind model, fallback, endpoint order, sorting,
ZDR, or other routing metadata. Those controls remain independently constrained
by routing policy, native-vendor rejection, and provider/model provenance
receipts. A routing-only change does not reuse the digest to send different
content.

A child lane cannot ask the user, copy its own digest into the approval input,
or treat a per-file hash list as authority. A user decline is recorded as
`host_disclosure_declined` and is never retried or routed around. Missing or
mismatched approval is a preparation state, not provider failure and not a
clean review result.
