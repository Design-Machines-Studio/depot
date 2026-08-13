# OpenRouter Configured-Key Contract

On a trusted developer workstation, either `OPENROUTER_API_KEY` or the existing
validated `OPENROUTER_API_KEY_FILE` input is sufficient authorization for an
eligible OpenRouter payload. Provider-side per-key spending limits are the
recommended runaway-cost control.

## Coherent installed bundle

Every active caller resolves one coherent installed OpenRouter bundle and
derives its wrapper, disclosure policy, and boundary from that root. A partial
or incoherent bundle makes OpenRouter unavailable and the
caller falls back to native Codex without prompting.

## Automatic outbound boundary

Direct `/openrouter`, eligible dm-review lanes, and the bounded Pipeline adapter
all follow one non-interactive protocol:

1. Materialize the exact ordered system and user files in private storage.
2. Run `delegation-boundary.sh --mode artifact-delegation` with the installed
   disclosure policy over those files.
3. On success immediately invoke `openrouter-wrapper.sh` with those same files;
   on decline contact no provider and use the native fallback where applicable.

There is no screening manifest or second hash comparison. Private copies keep
the scan-and-send path proportionate to a trusted developer workstation.

The boundary refuses unmistakable credentials, private keys, authenticated
DSNs, access/session tokens, and explicitly classified private or regulated
material. Placeholder values, variable names, paths, vendors, nationalities,
and jurisdictions are not disclosure evidence.

No OpenRouter caller asks for user approval, probes Workflow Authority, or
treats broker status as availability. A fake, ready, broken, or absent
`/usr/local/bin/workflow-authority` has no effect on configured-key dispatch.

## Bounded Pipeline execution

Pipeline keeps its existing workload boundary:

- only the already-routed non-sensitive config/docs/mechanical workload;
- `OPENROUTER_EXEC_ALLOWED_PATHS` is mandatory;
- the model must return a non-empty unified diff;
- every output path must be in the complete owned-path allowlist;
- disclosure/output validation occurs before patch application;
- `git apply --check`, allowlist-only staging, and staged `git diff --check`
  remain mandatory;
- later correctness and project verification remain native Codex work.

The adapter uses the wrapper's content-free schema-v2 receipt as evidence. It
may report requested/response model, generation ID, serving provider and its
provenance, usage, fallback, and request-envelope digest. It must not claim a
broker signature, host attestation, repository verification, prompt/response
content, API key, or secret content.

## Failure and origin rules

Missing/invalid credentials, provider unavailability, or an automatic payload
decline returns to native Codex without an approval question. Primary and
fallback slugs beginning with `anthropic/` are rejected before provider
contact; Anthropic remains native-Claude-only. Existing independent-family and
consequential-security sign-off rules remain unchanged.

Workflow Authority remains optional dormant code and is not part of
configured-key development.
