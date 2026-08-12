# OpenRouter Configured-Key Contract

On a trusted developer workstation, either `OPENROUTER_API_KEY` or the existing
validated `OPENROUTER_API_KEY_FILE` input is sufficient authorization for an
eligible OpenRouter payload. Provider-side per-key spending limits are the
recommended runaway-cost control.

## Coherent installed bundle

Every active caller resolves one coherent installed OpenRouter bundle and
derives its wrapper, disclosure policy, boundary, and authorization helper from
that root. A partial or incoherent bundle makes OpenRouter unavailable and the
caller falls back to native Codex without prompting.

## Automatic outbound boundary

Direct `/openrouter`, eligible dm-review lanes, and the bounded Pipeline adapter
all follow one non-interactive protocol:

1. Materialize the exact ordered system and user files.
2. Run `payload-authorization.sh snapshot` on those files.
3. Immediately run `payload-authorization.sh verify-trusted-boundary` with the
   installed disclosure policy and the unchanged files.
4. On success invoke `openrouter-wrapper.sh` with
   `OPENROUTER_AUTHORIZATION_MODE=trusted-boundary`; on decline contact no
   provider and use the native fallback where applicable.

The boundary refuses unmistakable credentials, private keys, authenticated
DSNs, access/session tokens, and explicitly classified private or regulated
material. Placeholder values, variable names, paths, vendors, nationalities,
and jurisdictions are not disclosure evidence.

No active caller emits `approval_required`, asks for a digest, creates or reads
an operator-batch artifact, probes Workflow Authority, or treats broker status
as availability. A fake, ready, broken, or absent
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

The old exact-digest and interim operator-batch helpers remain dormant
compatibility code for now. Workflow Authority remains optional dormant code.
Neither is part of normal configured-key development.
