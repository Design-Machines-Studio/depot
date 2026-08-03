# OpenRouter External Payload Authorization

Pipeline has two separate OpenRouter authorization families. They must not be
mixed or treated as substitutes for one another.

Automated Pipeline dispatch uses only the fixed
`/usr/local/bin/workflow-authority` client. The root service owns disclosure
scanning, exact OpenRouter request construction, the provider credential,
network transport, replay state, and signed result receipts. Automated callers
export only non-secret repository, run, lane, candidate, workload, nonce, and
model bindings. They must not use an environment variable, API-key presence,
caller digest, plugin helper, or caller-selected socket as authority. If the
fixed client or production-ready status is unavailable, the lane fails closed
before provider contact.

Direct interactive `/openrouter` remains a distinct compatibility path. It uses
only `exact-digest` authorization: the user approves each distinct ordered
payload. `trusted-boundary` remains low-level compatibility and offline-fixture
vocabulary, but it is not production disclosure authority and callers must not
select it for either direct or automated transmission.

## Direct interactive coherent bundle

Resolve one installed OpenRouter bundle through workflow-kernel with:

```text
resolve-plugin-bundle --plugin openrouter
--minimum-version 1.8.0
--required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh
--required-asset skills/openrouter-delegate/references/delegation-security-policy.json
--required-executable skills/openrouter-delegate/references/delegation-boundary.sh
--required-executable skills/openrouter-delegate/references/payload-authorization.sh
--active-host <claude|codex>
```

Use every asset from that selected root. Never resolve one helper independently
or accept a caller-selected executable path.

## Direct interactive authorization protocol

For each direct interactive request:

1. Materialize the exact ordered system and user prompt files that would be
   sent. Artifact packs are prompt files; path lists are boundary metadata and
   are not a substitute for the exact content.
2. Run `delegation-boundary.sh --mode artifact-delegation` over every exact
   outbound file. A disclosure decline returns the lane to its trusted local
   fallback without network contact.
3. Run `payload-authorization.sh snapshot` with the exact files in send order.
4. If the user has not supplied that lane's combined digest, return `PAYLOAD
   APPROVAL REQUIRED`. On approval, rebuild the files and run
   `payload-authorization.sh verify --approved-sha256
   <user-approved-digest>`.
5. Send only successfully verified files through the wrapper and set
   `OPENROUTER_AUTHORIZATION_MODE=exact-digest` so the content-free provider
   receipt records the actual authorization boundary.

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

Do not persist `trusted-boundary` into repository files, infer authority from an
API key or successful scanner result, enable it because OpenRouter was selected
as an executor, or pass it into the automated broker client. Scanner eligibility
and byte identity are necessary controls, but neither independently authorizes
disclosure.

## Broker terminal outcomes

Automated Pipeline dispatch uses the fixed host-authority client. Its exit
classes are part of the fail-closed boundary:

- `70`, `71`, and `72` are unsigned pre-network outcomes. The cascade may use
  the existing trusted Codex fallback because the broker proves that no
  provider contact occurred.
- `73` (`provider_failure`) and `74` (`unknown`) are signed terminal outcomes
  after a provider attempt. They are not model-capacity signals. Before
  preserving the content-free receipt, the adapter must require zero response
  bytes and match its repository, run, lane, candidate, workload, ordered
  models, exact request-body digest, outcome/exit pair, chain/cleanup fields,
  and production signature shape. Selected-model, generation, serving-provider,
  usage, and fallback fields must be `null`; failure paths cannot infer
  provenance that the provider did not verify. The client has already verified
  the signature and its challenge binding, including the caller nonce.
- `75` means the post-dial outcome is unsigned or unverifiable. It carries no
  receipt and is never converted into one by Pipeline.

Pipeline normalizes all three post-dial classes to cascade exit `75`, with one
explicit terminal lane failure. That exit stops the complete external rail:
it must not try another model, contact OpenRouter again, downgrade to another
external provider, or treat an automatic Codex fallback as completion. A
validated `73`/`74` receipt may pass unchanged through the existing receipt
channel as evidence; its content is never written to stderr or mixed with a
provider response. Invalid receipts and native `75` outcomes expose no receipt.
Genuine model-ladder exhaustion is the distinct cascade exit `76` and carries
no provider terminal receipt.

Dry-run routing, direct interactive exact-digest approval, and the routing
matrix are unchanged by this terminal normalization.
