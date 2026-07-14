# Verification Contract

## Declared coverage

The kernel discovers `tests/ux/personas/_index.md`, persona frontmatter,
`tests/ux/tasks/**/*.md`, optional `suites/*.md`, and optional
`tests/ux/verification.json`. Task frontmatter is authoritative;
`coverage-matrix.md` is a generated index and never changes required coverage.
The persona index must exactly name the available persona files, and a present
coverage matrix must agree with task/persona/outcome declarations; index drift
fails closed rather than changing task authority. An existing incomplete
`tests/ux/` tree is invalid. Only an absent declaration tree is `not_declared`.
Selected `current`, `redirected-current`, and statusless legacy tasks expand every
persona assignment across every configured browser and viewport. Statusless tasks
record `legacy_status_defaulted=true`. `required` defaults to true; only explicit
`required: false` opts out. SUCCESS, FRICTION, and expected BLOCKED are evaluative
outcomes, not reasons to omit a case.
Explicit status filters are non-empty known-status lists and may add future or
inactive work without erasing default runnable declarations. A declared profile
with no cases is valid only with `selection_status=no_runnable_tasks`; a profile
whose cases are all optional records `selection_status=optional_cases_only`.

Precedence is project config, task declaration, selected suite IDs, persona
device/viewport defaults, then workflow-policy defaults. Undeclared browser and
viewport values are recorded as `workflow_policy_default`. The canonical defaults
are Chromium plus Firefox, desktop `1440x900`, and mobile `375x812`.

Required coverage is exact set subtraction: required case IDs minus valid passing
evidence case IDs. Evidence must bind one persona, scenario, route, engine,
viewport, attempt, authentication state, and evaluation. Curl or reachability
diagnostics are never browser evidence. UI/integration work blocks on missing,
failed, unauthenticated, or non-evaluative required evidence. No UX directory is
`not_declared`; no personas are fabricated, and non-UI work remains unblocked.

Profiles retain auth field names only. Cookie values, bearer tokens, passwords,
credential usernames, fixture secrets, and URL credentials never enter profiles,
events, exceptions, stderr, snapshots, or recovery receipts.

## Browser recovery

For a required browser failure, preserve safe attempt evidence first, then:

1. quit the primary browser process or engine session (a tab/context close is not proof);
2. launch a fresh primary profile with a changed process/session identity and retry once;
3. if restart cannot be proved, record `primary_restart_unavailable` and continue;
4. launch one genuinely different configured engine and retry once;
5. if it fails or is unavailable, return blocked `human_help_required` with all
   attempts and exact missing case IDs.

Quit evidence must identify the initial session, launch evidence must identify a
different fresh session, and the following attempt must identify that launched
session. The same launch-to-attempt identity proof applies to the alternate
engine. Every attempt and receipt binds `case_id`, requested engine, actual
engine, and session ID. A passing alternate is explicit
`alternate_engine_recovery`: degraded browser-tooling proof for the requested
case. The coverage gate accepts only that named substitution and rejects generic
engine mismatch. Adapter exceptions become stable reason codes plus bounded
digested details and continue through the ladder; raw error text is never stored.

A recovered run retains the failed attempts and is degraded, never first-pass
clean. Application/container restart is a separate diagnostic action and cannot
stand in for browser restart. Required browser work is never translated to
skipped, approved, or curl-verified.
