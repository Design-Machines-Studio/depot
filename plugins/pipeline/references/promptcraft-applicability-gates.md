# Promptcraft trigger-conditional gates

Five gates that apply only when a chunk hits their trigger. Promptcraft loads
this file when at least one trigger fires and skips it entirely otherwise.

| Gate | Trigger |
|---|---|
| Assembly Mutation Applicability | the chunk is an Assembly mutation, or alters an auth boundary, membership, settings, or permissions surface |
| Visual Acceptance Criteria | the chunk is `renderedSurface: required` |
| Fixture SDK Conformance | the chunk touches `internal/fixtures/`, the `Module` interface, or a fixture SDK path |
| Production Readiness Preflight | the chunk touches config loading, the updater, release tooling, shutdown, or key rotation |
| Datastar-First | the project is Go + Templ + Datastar and the chunk is `renderedSurface: required` |

## Phase 3h: Assembly Mutation Applicability Gate

For each Assembly mutation chunk, consult `assembly:development`'s Mutation Applicability Matrix. Record only applicable authorization, validation/invariant, transaction, audit, event, SSE, service-abstraction, and test criteria, each with a one-line reason tied to a present behavior, current consumer/contract, or realistic consequence; omit inapplicable controls without `N/A` ceremony. A mutation verb or SQL statement alone never proves that every control applies; any required event still publishes strictly after commit.

**Auth Boundary Map gate:** mandatory when a change actually alters authentication, middleware, an Authorizer action/resource, a privileged read/write, a role/member/account/install/module permission, or a privileged UI capability; path names such as `auth/`, `admin/`, `account/`, `install/`, `member/`, and module-permission paths are review hints, not proof. The receipt enumerates mapped surfaces, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases addressed, test files, and residual risk; without it an actual boundary-changing chunk is incomplete.

**Data-integrity receipt (membership and settings chunks):** when a chunk adds, edits, clones, or reorders rows in a membership, settings, or permissions surface, its acceptance criteria must include:

1. **Stable row identity.** Every row carries a server-issued ID -- never an array index, DOM order, or client-generated key; reordering or filtering must not change which record a mutation targets.
2. **Cloned rows regenerate their ID** -- a duplicated row inheriting the source identifier silently overwrites the original on submit.
3. **Validation fails closed.** Unknown and missing required fields are rejected; a zero-value enum is invalid rather than defaulting to the first option.
4. **Async mutations announce.** Row-level loading and completion states are announced through a live region, not a spinner alone.

## Phase 3i: Visual Acceptance Criteria Gate

Every chunk with `renderedSurface: required` must include at least 2 visual acceptance criteria describing rendered impressions, not just structural class names, in a `### Visual Acceptance Criteria` subsection. "Uses `.button--accent` class" is structural; "Primary action button is visually dominant over secondary actions" is visual; both types are required. A chunk marked `not_applicable` must not fabricate rendered impressions.

**Shared-component parity:** when one Templ component renders on two or more routes -- a shared editor, form, or dialog -- the chunk must carry a **Visual Parity Criterion** even when the prompt never says "visually identical": sharing a component is itself the parity claim, and a route-specific wrapper or stale override quietly breaks it. Detect by grepping the plan's `filesToModify` for a component invoked from more than one page package; for each, add these two **P1** criteria:

1. `Screenshot of <component> at /route-a and /route-b at the same viewport shows identical rendering.`
2. `getComputedStyle on <selector> matches across both routes for: font-size, font-weight, color, padding, margin, background-color, border.`

A shared component that renders differently per route is the component failing to be shared, not polish.

## Phase 3m: Fixture SDK Conformance Gate

**Trigger:** the chunk touches `internal/fixtures/`, the `Module` interface, or a fixture SDK path.

Every such chunk carries **negative-test** acceptance criteria -- proof the invalid case is rejected, not just that the valid case works. The prompt must include an acceptance criterion for each invariant the chunk touches, written as the negative case:

| Invariant | Required AC (negative form) |
|---|---|
| Table-prefix enforcement | An unprefixed table name, or another fixture's prefix, is rejected by `ScopedDB` |
| Zero-value auth | A zero-value `Authorizer` or nil/zero actor **denies**. An uninitialized auth struct never allows |
| Stream subject validation | A subject outside the fixture's own prefix is rejected at registration |
| Reserved scopes | Registering under `gov`, `doc`, `eq`, `health`, `member`, `system`, `audit`, or `federation` from a fixture that does not own that scope is rejected |
| Disabled-module route leakage | A disabled fixture's routes return 404 -- not 200, not 500, not a redirect |
| Module lifecycle | `register -> enable -> disable -> teardown` runs clean, and a second `enable` reattaches routes and streams |
| All-or-nothing stream preflight | A stream set with one invalid subject registers **none** of them |

Plus: **a new case is added to the conformance harness in the same chunk** -- a happy-path-only harness proves nothing. Fail-closed is the theme: any invariant that defaults to permissive on absent input (zero value, empty string, unset flag, missing module) is a P1 and the prompt says so.

## Phase 3n: Production Readiness Preflight Gate

**Trigger:** the chunk touches config loading, the updater, release tooling, shutdown, or key rotation. The prompt must carry acceptance criteria for each applicable item:

1. **Config validation is fail-closed at boot.** Invalid config exits non-zero; it never defaults through or warns and continues.
2. **Update candidate is preflighted before replacement.** Checksum, signature, and version ordering are verified against the *candidate* before any file is swapped; a "verified" claim with no actual verify call is a BLOCKER.
3. **Update-failure recovery copy is actionable.** The message names the recovery command, not "an error occurred".
4. **Shutdown ordering is explicit.** Drain HTTP -> stop consumers -> flush -> close DB; an unordered `defer` stack is not a shutdown sequence.
5. **Key rotation covers both sides.** Email and federation key checks are fair on the responder side (a rotated key is detected, not silently rejected as forged) and old keys have a stated grace window.
6. **Critical forms are double-submit protected server-side.** An idempotency token, not a disabled button -- repair and recovery forms run when the system is already unhealthy.
7. **A release receipt exists**, enumerating active-install monitoring and beta-finalization proof.
8. **Runbooks and docs are updated in the same chunk**, not deferred to a follow-up.

## Phase 3o: Datastar-First Gate

**Trigger:** the project is Go + Templ + Datastar and the chunk has `renderedSurface: required`.

Agents reach for hand-rolled JS by default, and a Datastar Pro attribute whose plugin is missing from the bundle is **inert** -- a silent no-op that looks correct in review. The prompt must:

1. **Name the attribute per interaction.** For each interactive behavior, state which Datastar attribute or action implements it (`data-persist`, `data-query-string__history`, `data-match-media:signal`, `@clipboard`, `@intl`, ...). See the substitution table in `plugins/assembly/skills/development/datastar-pro.md`.
2. **Carry a bundle-presence check** for every Pro attribute it prescribes -- a grep of the vendored bundle for the plugin's **registered name** (`grep -c "'query-string'" web/static/vendor/datastar.js`), not the `data-` attribute. If the plugin is absent, the chunk adds "regenerate the bundle including `<plugin>`" as an explicit step or falls back to the free tier. Prescribing a Pro attribute into a bundle that lacks it is a BLOCKER.
3. **Include the no-new-JS acceptance criterion:** "No new `<script>` block or `.js` file is introduced. If one is unavoidable, the prompt names the interaction and states why the substitution table has no entry for it."
4. **List `assembly:development` in `companionSkills`** so the substitution table travels with the prompt.
