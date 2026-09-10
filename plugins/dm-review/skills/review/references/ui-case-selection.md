# Proportional UI case selection

Use this contract once per review target before application/browser readiness.
It selects browser cases; it does not decide whether a browser is required.

## Ordinary PR review

Start from changed rendered files and their concrete routes. Add matching
prototype-parity case IDs and explicitly named acceptance case IDs. Keep only
the personas, states, engines, and viewports directly affected by those
surfaces. Add at most one explicitly identified baseline case, and only when it
can expose a realistic adjacent regression.

### Host route-mapping preflight

The full, quick, and visual review hosts own route mapping before request
materialization. For each changed rendered file, use only an exact route named
by a verification profile or case, a prototype/acceptance mapping, or a
framework route declaration that directly binds that file. Record the resolved
file-to-route pair in `renderedRouteMappings` with `status: "resolved"`. Keep
`changedRenderedFiles` as the complete changed-file inventory; the helper
requires exactly one mapping outcome for every listed file. Do not scan
localhost, guess a fallback route, or ask a reviewer participant to discover
it.

When no bounded source resolves a changed rendered file, record
`status: "unresolved"` and `route: null` for that file. This is the
`unresolved-rendered-route` outcome. Source-capable review may continue, but
rendered-required coverage remains incomplete until the host receives an exact
route.

The presence of `tests/ux/verification.json`, persona/task files, a coverage
matrix, or supported engine/viewport declarations makes cases discoverable; it
does not make their Cartesian product mandatory. Task frontmatter and explicit
verification profiles remain authoritative over generated indexes.

Materialize the explicit candidate set and inputs, then run
`ui-review-contract.sh select-cases --request <file>`. The helper performs only
this closed filter. It does not score changes, infer an impact graph, discover
routes, or plan tests.

## Existing prototype tasks and personas

For a declared Assembly counterpart, resolve `Design-Machines-Studio/assembly`
by canonical remote and exact reviewed commit (local discovery hint:
`/home/ned/assembly/assembly`). Read `tests/ux/README.md`,
`tests/ux/coverage-matrix.md`, applicable `tests/ux/tasks/**/*.md`,
`tests/ux/personas/_index.md`, selected persona profiles, and heuristics named
by selected tasks. Individual task frontmatter and steps override the generated
coverage matrix. These are content-defined browser scenarios: do not invent a
CLI runner or copy the suite into Depot.

Select affected existing task IDs and persona/role/state/device combinations,
including handler-only Datastar changes. Carry source paths/commit, task IDs,
preconditions, steps, success criteria and screenshot points through Pipeline
prompts into the existing candidate cases and browser evidence. Use stable case
IDs for each selected combination; keep the detailed task context in the
existing prompt/evidence packet, not new helper fields or another ledger.

Actually execute selected scenarios in both prototype and application with
comparable designated demo accounts, permissions and initial data. Explicitly
map differing routes, account IDs and record IDs without weakening the scenario
or production authorization. For each case record prototype result, application
result and observed difference in existing interaction observations/artifacts.
Exercise save/autosave, reload/revisit, validation, cancel and keyboard/focus
where applicable; capture designated screenshot points. Reading tasks or
imagining persona experiences is not execution or real-user research.

An expected permission denial is a successful boundary check when verified,
not unavailable infrastructure. Expected FRICTION is a hypothesis to assess,
not an automatic finding. Record stale task/source conflicts and approved
production differences. Unimplemented out-of-scope areas do not become feature
requirements; missing setup for a selected required case is an honest coverage
gap. Do not run the entire task/persona cross-product for an ordinary change.

## Full matrix

Select the complete declared matrix only for one of these closed reasons:

- the user explicitly requested a sweep;
- `/dm-review-visual --all` or equivalent full mode is active;
- a release/readiness profile explicitly requires the full matrix at this
  cadence; or
- changed shared shell, authentication, global layout, or an equivalent shared
  surface genuinely affects the complete set.

Record one of `explicit-sweep`, `release-profile`, or `shared-surface` as the
full-matrix reason. A list of supported browsers or viewports is not a
full-matrix reason.

Every selected rendered-required case must still complete or produce the one
shared rendered-evidence gap. Proportional selection narrows unrelated cases;
it never converts a selected required case to optional.
