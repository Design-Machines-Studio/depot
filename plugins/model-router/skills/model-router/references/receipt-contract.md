# Private dispatch receipt

The dispatcher writes schema version 1, content-free JSON. The private surface
contains request role and effort, anonymous participant ID, requested and
effective effort, attempted candidates, served model/provider/transport,
billing mode, duration, token and cost provenance, fallback reason, matrix
snapshot, and family-independence result. It contains no prompt or model output.

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
