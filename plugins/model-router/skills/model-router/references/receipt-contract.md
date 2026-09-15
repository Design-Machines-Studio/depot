# Private dispatch receipt

The dispatcher writes schema version 1, content-free JSON. The private surface
contains request role and effort, anonymous participant ID, requested,
transport-normalized, and transmitted effort, attempted candidates, served
model/provider/transport,
billing mode, duration, token and cost provenance, fallback reason, matrix
snapshot, and family-independence result. It contains no prompt or model output.
Availability/fallback reasons are limited to router-authored content-safe codes,
including `rate_limit_probe_no_response`, `rate_limit_response_malformed`,
`rate_limit_shape_unsupported`, `rate_limit_mapping_unknown`,
`required_window_missing`, `rate_limit_exhausted`,
`workflow_kernel_unavailable`, `provider_bundle_unavailable`,
`provider_credential_unavailable`, `provider_availability_unknown`,
`provider_boundary_declined`, `provider_transport_failed`,
`provider_model_unavailable`, `provider_model_identity_unavailable`,
`provider_model_substitution`, `organization_monthly_budget_exceeded`,
`insufficient_credits`, `rate_limited`, `unknown_provider_failure`,
`provider_receipt_missing`, `provider_receipt_malformed`,
`provider_receipt_publication_failed`, `provider_receipt_preservation_failed`,
`provider_adapter_rejected`,
`browser_transport_unavailable`, and
`model_participant_unavailable`, and
`provider_effort_evidence_unavailable`. They
never contain raw CLI/provider output, account identity, quota balances,
credentials, prompts, or private paths.

The ordinary caller sees only role, normalized capabilities, requested,
transport-normalized, and transmitted effort, the closed transmission status,
anonymous participant ID, disposition, fallback state, and output destination.
`effectiveEffort` is retained as a compatibility alias for a confirmed
`transmittedEffort`; it is null when transmission is unavailable. A transport
stub is fixture-only evidence and cannot confirm provider transmission.
Historical receipts without `effortTransmission` remain readable, but the
terminal renderer reports their transmitted effort as `unavailable` rather
than inferring it from the old `effectiveEffort` field. A transmitted setting
records request-envelope or native-CLI evidence only; it is never a measurement
of the model's internal reasoning process. Concrete receipt fields must never
be copied into peer prompts or ordinary orchestration summaries.

Write attempts may also retain a bounded `providerFailureEvidence` object in
the private attempt receipt. The sibling `providerReceiptStatus` is the
attempt-level status, one of `valid-provider-failure`,
`valid-provider-success`, `missing`, `malformed-or-unsupported`,
`publication-failed`, `preservation-failed`, `adapter-local-rejection`, or
`not-requested`. A valid failure object contains only closed failure
kind/reason values, HTTP status (`http_error` only), timeout kind, transmitted
effort, process exit status, and usage/cost values when the provider reports
them. Missing, malformed, unsupported, or publication evidence never becomes a
provider diagnosis or a zero-cost claim. `processExitStatus` is retained as a
sibling field on every failed attempt.

After every model-dependent decision has settled, the terminal workflow may
load `terminal-report-contract.md` and pass one exact run-private ordered index
to `render-terminal-report.sh`. That renderer projects only its closed field
allowlist into operator JSON and Markdown. It never exposes prompts, outputs,
provider bodies, arbitrary errors, credentials, endpoints, environments, or
family-independence internals. No model dispatch may follow the projection.
