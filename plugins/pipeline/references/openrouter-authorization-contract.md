# OpenRouter Configured-Key Contract

On a trusted developer workstation, either `OPENROUTER_API_KEY` or the existing
validated `OPENROUTER_API_KEY_FILE` input is sufficient authorization for an
eligible OpenRouter payload. Provider-side per-key spending limits are the
recommended runaway-cost control.

## Coherent installed bundle

Every active caller resolves one coherent installed OpenRouter bundle and
derives its wrapper, disclosure policy, and boundary from that root. A partial
or incoherent bundle closes the provider attempt and model-router advances the
role without prompting.

## Automatic outbound boundary

Direct `/openrouter` and model-router's bounded external adapter
all follow one non-interactive protocol:

1. Materialize the exact ordered system and user files in private storage.
2. Run `delegation-boundary.sh --mode artifact-delegation` with the installed
   disclosure policy over those files.
3. On success immediately invoke `openrouter-wrapper.sh` with those same files;
   on decline contact no provider and return the closed state to role fallback.

There is no screening manifest or second hash comparison. Private copies keep
the scan-and-send path proportionate to a trusted developer workstation.

The boundary refuses unmistakable credentials, private keys, authenticated
DSNs, access/session tokens, and explicitly classified private or regulated
material. Placeholder values, variable names, paths, vendors, nationalities,
and jurisdictions are not disclosure evidence.

No OpenRouter caller asks for user approval or probes a broker. The
configured-key path has no broker dependency.

## Bounded routed execution

model-router keeps the existing workload boundary for a resolver-selected
external write attempt:

- any role-selected text task may use the rail; task kind, repository path,
  security subject matter, and native subscription availability are not
  OpenRouter eligibility gates;
- `OPENROUTER_EXEC_ALLOWED_PATHS` is mandatory;
- before contact, every allowed path must be a clean normalized repository-relative
  path naming either a regular UTF-8 text blob at `HEAD` or an absent new file;
- the outbound task includes the exact allowlist and exact committed `HEAD`
  contents for those files only, with absent files marked explicitly and file
  contents delimited as untrusted data;
- symlinked, escaping, dirty, binary, unreadable, unsupported, or duplicate
  allowed paths close the attempt before contact;
- the complete user prompt is capped at 256 KiB; larger bounded contexts close
  the attempt before contact rather than truncating committed file contents;
- the model must return a non-empty unified diff;
- every output path must be in the complete owned-path allowlist;
- disclosure/output validation occurs before patch application;
- `git apply --check`, allowlist-only staging, and staged `git diff --check`
  remain mandatory;
- later correctness and project verification remain caller-owned workflow work.

The adapter uses the wrapper's content-free schema-v2 receipt as evidence. It
may report requested/response model, generation ID, serving provider and its
provenance, usage, fallback, and request-envelope digest. It must not claim a
broker signature, host attestation, repository verification, prompt/response
content, API key, or secret content.

## Failure and origin rules

Missing/invalid credentials, provider unavailability, or an automatic payload
decline returns to model-router without an approval question. Primary and
fallback slugs beginning with `anthropic/` are rejected before provider
contact; this prevents a provider API call from masquerading as native Claude
subscription use. Existing independent-family and consequential-security
verification rules remain unchanged; neither rule makes OpenRouter secondary
or permission-gated.

No dormant provider broker implementation is retained by this contract.
