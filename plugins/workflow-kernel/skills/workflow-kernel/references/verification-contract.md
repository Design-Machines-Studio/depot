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
The matrix must represent the complete authoritative task and assignment set;
a compact matrix that omits a task or row is drift. Discovery rejects symlinked
UX directories and files, plus any resolved path outside the owned UX tree,
before reading it.
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
Each normalized profile retains the ordered configured-engine set and derives a
content-addressed `profile-sha256` identity from its complete safe declaration.

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
engine, configured-engine set, verification-profile identity, validated
viewport, opaque URL digest, opaque route digest, and session ID. Raw targets
never enter durable attempt or receipt data. A passing alternate is explicit
`alternate_engine_recovery`: degraded browser-tooling proof for the requested
case. The coverage gate accepts only that named substitution when its complete
recovery receipt belongs to the same profile and configured-engine set and its
winning attempt is bound to the proved fresh alternate session. Generic engine
mismatch is rejected. Adapter exceptions become stable reason codes plus bounded
digested details and continue through the ladder even when exception string or
representation rendering itself fails; raw error text is never stored.

Receipt constructors and schemas reject contradictory state: status and reason
must agree, attempts are ordered and retain all failures before the sole winning
attempt, action/result pairs are coherent, relaunch sessions are fresh and bind
the following attempt, recovered/clean receipts have no missing cases, and a
blocked human-help receipt names the exact missing case.

A recovered run retains the failed attempts and is degraded, never first-pass
clean. Application/container restart is a separate diagnostic action and cannot
stand in for browser restart. Required browser work is never translated to
skipped, approved, or curl-verified.
