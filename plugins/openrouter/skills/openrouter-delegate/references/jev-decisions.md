# Jev Decisions adapter

Use this path for Jev typed decisions; the existing chat runner stays unchanged.
Jev classifies supplied state; it does not generate prose or watch videos.

For an installed bundle, follow the OpenRouter command's coherent kernel bundle
resolution and additionally require the executable
`skills/openrouter-delegate/references/openrouter-decisions.sh`, with minimum
OpenRouter version 1.21.1. Do not mix credential, boundary or adapter files from
different bundles. An explicitly selected, inspected development checkout is
also supported for fixture testing and user-authorized bounded trials, without
installing or publishing that checkout. Derive all assets from that same root.

Supply UTF-8 JSON on stdin with exactly `model`, `state`, and `questions`.
Pin the model to `typesafe/jev-1.13`. Each question contains `type`, text
`instructions`, and `criteria`: label-description mapping for `choice`, 2–10
ordered descriptions for `score`, or `true`/`false` descriptions for `noul`.
State is text, an object, or an array. Question names are identifiers, not
instructions: put the judgment in `instructions`.

```sh
bash "$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-decisions.sh" \
  --receipt ./jev-receipt.json --timeout 20 < ./jev-request.json
```

`jev-request.json` must exist and `jev-receipt.json` must not; the adapter
creates the receipt with mode 0600.

This is one client request with no automatic retry or model substitution. The
adapter reuses the bundle's
credential-file policy and structural boundary. It caps requests at 32,000 UTF-8
bytes and 32 questions, enforces a hard overall timeout (default 20 seconds,
maximum 60), rejects redirects and ambient proxies, validates answer
distributions, and reserves a new 0600 receipt before network access. JSON
answers go to stdout. Error messages omit remote bodies and credentials.
Chat-only privacy/provider/reasoning/web overrides, including an explicit
`OPENROUTER_ALLOW_FALLBACKS` setting, are rejected before sending;
the alpha Decisions contract cannot silently satisfy a requested ZDR policy.

On failure stop, report the safe receipt when one was created; otherwise report
the safe stderr failure. Do not retry automatically. An interrupted request may
have been billed. Exit codes: 0 success, 1 transport or credential failure, 2
schema/configuration failure, 28 timeout, 130 interrupted.

Report generation ID, response model/provider with provenance, usage and request
digest from the content-free receipt. Missing identity stays unknown: a pinned
request does not prove returned identity. Present model interpretations apart
from measured data and human reference labels. Recommend provider-side per-key
spend limits; do not add a second approval or billing service.

Use fixtures by default; this capability does not itself authorize live calls.
For bounded research trials, send only the user-authorized metadata and profile
context, not private review notes or credentials. Metadata classification does
not establish video quality, audience demand, causal performance or accuracy.

API: https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request
Model: https://openrouter.ai/typesafe/jev-1.13
