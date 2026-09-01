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
