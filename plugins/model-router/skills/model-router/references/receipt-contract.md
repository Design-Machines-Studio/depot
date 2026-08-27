# Private dispatch receipt

The dispatcher writes schema version 1, content-free JSON. The private surface
contains request role and effort, anonymous participant ID, requested and
effective effort, attempted candidates, served model/provider/transport,
billing mode, duration, token and cost provenance, fallback reason, matrix
snapshot, and family-independence result. It contains no prompt or model output.
Availability/fallback reasons are limited to router-authored content-safe codes,
including `rate_limit_probe_no_response`, `rate_limit_response_malformed`,
`rate_limit_shape_unsupported`, `rate_limit_mapping_unknown`,
`required_window_missing`, `rate_limit_exhausted`,
`workflow_kernel_unavailable`, `provider_bundle_unavailable`,
`provider_credential_unavailable`, `provider_availability_unknown`,
`provider_boundary_declined`, `provider_transport_failed`,
`provider_model_unavailable`, `organization_monthly_budget_exceeded`,
`insufficient_credits`, `rate_limited`, `unknown_provider_failure`,
`browser_transport_unavailable`, and
`model_participant_unavailable`. They
never contain raw CLI/provider output, account identity, quota balances,
credentials, prompts, or private paths.

The ordinary caller sees only role, normalized capabilities, requested and
effective effort, anonymous participant ID, disposition, fallback state, and
output destination. Concrete receipt fields must never be copied into peer
prompts or ordinary orchestration summaries.

After every model-dependent decision has settled, the terminal workflow may
load `terminal-report-contract.md` and pass one exact run-private ordered index
to `render-terminal-report.sh`. That renderer projects only its closed field
allowlist into operator JSON and Markdown. It never exposes prompts, outputs,
provider bodies, arbitrary errors, credentials, endpoints, environments, or
family-independence internals. No model dispatch may follow the projection.
