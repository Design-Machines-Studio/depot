# Behavioral contract readiness gate

Loaded by promptcraft Phase 3l.5 only when the run binds a behavioral
verification contract -- a repository with a workflow-kernel verification
profile. A run with no such profile never loads this file.

### Phase 3l.5: Behavioral Contract Readiness Gate

Prepare deterministic contract inputs from the approved Key Requirements and
the final acceptance criteria. Assign stable `REQ-*` and `CHK-*` IDs, preserve
explicit prohibited regressions, and classify every requirement as executable
or manual per
`plugins/workflow-kernel/skills/workflow-kernel/references/behavioral-verification-contract-schema.json`.
For work with `renderedSurface: required`, resolve selected persona and browser case IDs from the
authoritative declarations described by `verification-contract.md`; generated
coverage matrices and invented sample personas are not authority, and any unresolved
persona, scenario, route binding, browser, viewport, auth fixture, or case ID
blocks handoff.

For validated `renderedSurface: not_applicable` chunks, contribute no persona or
browser case IDs to the run-wide contract and preserve the rationale in the
manifest and receipts. If the run has zero `required` chunks, use the contract's
explicit no-profile/null pair and empty case arrays; otherwise the bound profile
and arrays contain only the union selected for `required` chunks. Do not create
placeholder cases, fake routes, or `not_declared` browser evidence to satisfy a
kind-based heuristic.

Promptcraft does not bind or pre-authorize the contract: the execution
orchestrator generates the canonical JSON from these approved inputs only after
`run.started`, then validates and binds it before the first builder dispatch;
every dispatch and builder completion must echo the current contract digest and
revision exactly.

Repository verification evidence stays bounded across model prompts. A passing current-invocation result appears once as selected check IDs, status, and plan digest; raw passing stdout/stderr and repeated result copies never enter builder repair or reviewer prompts. Before model review, a failure reaches the repair attempt as bounded canonical failing check IDs, a stable failure signature, and a trusted profile-derived reproduction instruction. Never include raw logs, secrets, environment, arbitrary host paths, or unbounded output.
