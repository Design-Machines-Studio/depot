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
a compact matrix that omits a task or row is drift. Discovery rejects symlinks
in every ancestor from the project root through the UX declaration and all
descendants, plus any resolved path outside the owned UX tree, before reading
it. Declaration reads are descriptor-relative and no-follow, reject hardlinks,
and revalidate file and directory identity after reading so path swaps cannot
replace validated config, index, persona, task, suite, or matrix content.
Duplicate scalar or list-section frontmatter keys and malformed scalar or
container types fail with `invalid_verification_declaration`. Task `personas:`
assignments are parsed only from that exact nested section: duplicate or unknown
keys, duplicate IDs, invalid `expected` values, invalid `required` booleans, or
missing assignments fail closed rather than being inferred from nearby text.
Selected `current`, `redirected-current`, and statusless legacy tasks expand every
persona assignment across every configured browser and viewport. Statusless tasks
record `legacy_status_defaulted=true`. `required` defaults to true; only explicit
`required: false` opts out. SUCCESS, FRICTION, and expected BLOCKED are evaluative
outcomes, not reasons to omit a case.
Explicit status filters are non-empty known-status lists and may add future or
inactive work without erasing default runnable declarations. A declared profile
with no cases is valid only with `selection_status=no_runnable_tasks`; a profile
whose cases are all optional records `selection_status=optional_cases_only`.
The discovery/source/selection/cases matrix is exact: `not_declared` requires an
absent tree and empty cases/engines; declared profiles use project-declaration
provenance and exactly one of runnable, optional-only, or proven no-runnable
selection. UI work with empty coverage blocks unless declared provenance proves
that no runnable cases exist.

Precedence is project config, task declaration, selected suite IDs, persona
device/viewport defaults, then workflow-policy defaults. Undeclared browser and
viewport values are recorded as `workflow_policy_default`. The canonical defaults
are Chromium plus Firefox, desktop `1440x900`, and mobile `375x812`.
Each normalized profile retains the ordered configured-engine set and derives a
content-addressed `profile-sha256` identity from its complete safe declaration.
The authoritative runtime origin is reduced to an opaque `origin-sha256` digest
and included in that identity; configured and runtime origins must agree. Raw
origins, credentials, query secrets, and fragments are never persisted.

Required coverage is exact set subtraction: required case IDs minus valid passing
evidence case IDs. Evidence must bind one persona, scenario, route, engine,
viewport, attempt, authentication state, and evaluation. Curl or reachability
diagnostics are never browser evidence. UI/integration work blocks on missing,
failed, unauthenticated, or non-evaluative required evidence. No UX directory is
`not_declared`; no personas are fabricated, and non-UI work remains unblocked.
Persona, scenario, role, and auth field identifiers are at most 128 characters.
Routes are at most 2048 characters, are absolute and origin-relative, contain no
query or fragment, and reject `.` or `..` traversal segments in both runtime
validation and the published schema.

Profiles retain auth field names only. Cookie values, bearer tokens, passwords,
credential usernames, fixture secrets, and URL credentials never enter profiles,
events, exceptions, stderr, snapshots, or recovery receipts.

## Browser recovery

For a required browser failure, preserve safe attempt evidence first, then:

1. quit the primary browser process or engine session (a tab/context close is not proof);
2. launch a fresh primary profile with a changed process/session identity and retry once;
3. if restart cannot be proved, record `primary_restart_unavailable` and continue;
4. launch one genuinely different configured engine and retry once; a valid
   single-engine profile instead records `secondary_engine_unavailable`;
5. if it fails or is unavailable, return blocked `human_help_required` with all
   attempts and exact missing case IDs.

The browser adapter canonically snapshots and reconstructs each sealed
`BrowserRequest` before any browser call. Mutation of its URL, target origin, or
other bound input therefore fails before an adapter can observe the request.

Quit evidence must identify the initial session, launch evidence must identify a
different fresh session, and the following attempt must identify that launched
session. The same launch-to-attempt identity proof applies to the alternate
engine. Every attempt and receipt binds `case_id`, requested engine, actual
engine, configured-engine set, verification-profile identity, validated
viewport, opaque URL digest, authoritative origin digest, opaque route digest,
and session ID. Raw targets
never enter durable attempt or receipt data. A passing alternate is explicit
`alternate_engine_recovery`: degraded browser-tooling proof for the requested
case. The coverage gate accepts only that named substitution when its complete
recovery receipt belongs to the same profile and configured-engine set and its
winning attempt is bound to the proved fresh alternate session. Generic engine
mismatch is rejected. Adapter exceptions become stable reason codes plus bounded
digested details and continue through the ladder even when exception string or
representation rendering itself fails; raw error text is never stored.
Launches with a reused/invalid session identity or `fresh_profile=false` are
recorded as `session_identity_mismatch` or `fresh_profile_unavailable`, never as
successful launches. Successful recovery lifecycle evidence persists
`fresh_profile=true`.

Injected policy documents are canonically snapshotted and revalidated at adapter
construction. Later mutation of a frozen object cannot alter discovery defaults.

Receipt constructors and schemas reject contradictory state: status and reason
must agree, attempts are ordered and retain all failures before the sole winning
attempt, action/result pairs are coherent, relaunch sessions are fresh and bind
the following attempt, recovered/clean receipts have no missing cases, and a
blocked human-help receipt names the exact missing case.

Every browser `EvidenceRef`, including clean first-pass primary evidence, carries
a complete `BrowserRecoveryReceipt`. The verification gate canonically
reconstructs the evidence and all nested receipt values at its boundary, checks
their sealed origin captures, and accepts only a browser winning attempt bound to
that evidence. A caller-mutated evidence object, receipt, attempt, URL digest, or
curl proof cannot be promoted by preserving an earlier digest. Every successful
launch has exactly one following attempt bound to its session; primary quit
evidence names the initial primary session exactly. Single-engine clean and
primary-recovered receipts remain valid, while only a blocked path lacking a
configured alternate records `secondary_engine_unavailable`.

A recovered run retains the failed attempts and is degraded, never first-pass
clean. Application/container restart is a separate diagnostic action and cannot
stand in for browser restart. Required browser work is never translated to
skipped, approved, or curl-verified.
