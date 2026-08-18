# Assembly federation and release security checks

Deep P1/P2 checks for two Assembly Baseplate surfaces. The `security-auditor`
agent loads this file only when the changed files touch one of them; a diff that
touches neither never loads it.

- **Federation / cross-install trust** -- when the diff touches `internal/federation/**`,
  well-known fetch clients, key pinning or trust-state code, signed-push handlers,
  federated SSE fan-out, share-grant paths, or federation-reachable asset serving.
- **Updater / release supply chain** -- when the diff touches `internal/updater/`,
  release CLI commands, manifest fetch/parse, archive extraction, signature or
  checksum verification, `.goreleaser.yaml`, `internal/config/` loaders, shutdown
  ordering, or release workflows.

## Assembly production architecture checks

When reviewing Go code in Assembly projects (detected by `internal/fixtures/` or `internal/baseplate/` directory structure):

The severity labels below are candidates only after the security-auditor's current-evidence gate (retain a finding only when direct evidence establishes an observable current defect) is satisfied. Trusted first-party Fixture code is not an attacker by default; identify the reachable boundary and harm rather than escalating from a path name or API use alone.

### NATS Subject ACL Violations (P1)

Flag fixtures publishing to NATS subjects outside their `ScopedEventBus` prefix. Each fixture is scoped to its own subject namespace (e.g., governance publishes to `assembly.gov.*` only).

**Look for:** `Publish()` calls with subjects not matching the fixture's scope prefix. Direct `nats.Conn` usage in fixture code.

### SSE Session Validation (P1)

Flag SSE handlers that don't validate the session before starting a KV Watch or streaming data. All SSE endpoints must verify authentication and extract member ID before streaming.

**Look for:** SSE handler functions that call `datastar.NewSSE()` or `kv.Watch()` without a preceding auth check.

### Object-Level Authorization (P1)

Flag protected user/operator mutation handlers (POST, PUT, PATCH, DELETE) that
do not authorize the concrete action/resource before modifying it. Trusted
internal maintenance must instead name and enforce an explicit trust boundary;
do not demand a fake user authorization call. Read-only GET handlers may skip
object-level auth if route-level middleware covers the permission and the data
is not privileged.

**Look for:** Protected user/operator handler methods containing `db.Exec`,
`db.ExecContext`, `service.Create`, `service.Update`, or `service.Delete` without
concrete action/resource authorization before the write; maintenance entry
points with no explicit trust-boundary proof.

### Federation Security (P1)

Check federation-related code for security requirements:
- Link tokens must include TTL (max 5 minutes), single-use nonce, and audience (`aud`) field
- `return_url` / `callback` must be validated with exact host match (not suffix match)
- HTTPS must be enforced on all federation endpoints in production
- Rate limiting: 10 link requests/hour per source, 5 callbacks/hour

**Look for:** Code in `federation/`, `/.well-known/assembly` handler, link token generation/validation.

### Hardcoded Member IDs (P2)

Flag literal member ID strings (e.g., `"mem_001"`, `"mem_009"`) in non-test, non-seed code. These are prototype carryovers that must be replaced with dynamic lookups.

**Look for:** String literals matching `mem_\d+` pattern outside `*_test.go`, `*_seed.go`, `seeds/`, and `testdata/` files.

### Input Validation (P2)

Flag handlers that accept form input, URL parameters, or request body data without calling a validation function on the request DTO. All user input must be validated for type, length, and format before use.

**Look for:** `r.FormValue()`, `r.URL.Query()`, `json.Decode()` without a subsequent `Validate()` or validation call on the parsed data.

### Authorizer Pattern Validation (P1)

For protected user/operator writes, flag handlers/services that call
`deps.Auth.Authorize()` with the wrong action string, resource, or scope. This
strengthens the missing-authorization check above. For trusted maintenance,
validate the named trust boundary instead.

**Look for:** `Authorize()` calls where the action string doesn't match the handler's purpose (e.g., `proposal.view` in an update handler), or where the `Resource` struct is missing `AuthorID` or `Status` fields needed for ownership checks.

### Dynamic SQL Detection (P2)

Flag SQL queries built with `fmt.Sprintf` or string concatenation. Prefer static SQL with conditional predicates (`WHERE 1=1` + append). Dynamic SQL triggers gosec G202 and risks injection even when values appear controlled.

**Look for:** `fmt.Sprintf` with SQL keywords (`SELECT`, `INSERT`, `UPDATE`, `DELETE`), string concatenation (`+`) adjacent to SQL query strings.

### Destructive Confirmation (P2)

Flag DELETE, archive, or reset handlers that execute the destructive action without requiring a server-verified confirmation token. Client-only `confirm()` dialogs are insufficient -- the server must verify the user confirmed.

**Look for:** HTTP DELETE handlers or archive/reset service methods that proceed directly to `db.Exec` without checking a confirmation token or nonce parameter from the request.

### Raw Error Exposure (P2)

Flag `err.Error()` output passed directly to HTTP responses. Internal error details leak implementation information to attackers.

**Look for:** `http.Error(w, err.Error(), ...)`, `fmt.Fprintf(w, ... err.Error())`, or error strings included in JSON response bodies.

### Admin Form Input Validation (P2)

Flag admin-facing forms that skip length/format validation because "only admins use them." Admin interfaces are still attack surfaces -- compromised admin accounts or CSRF attacks can exploit unvalidated inputs.

**Look for:** Form handlers in admin routes (`/admin/`, `RequireAdmin` middleware) that parse input without calling validation functions.

### Auth Boundary Map Gap (P2)

Flag PRs touching `auth/`, `admin/`, `account/`, `install/`, `member/`, or
`module`-level permission paths that rely only on
`RequireAdmin`/`RequireSuperAdmin` middleware for protected mutations without
explicit concrete action/resource authorization before the write. Middleware is
necessary but insufficient: it proves a coarse route precondition, not an
authorization decision. Put the check in the service when the applicability
matrix selects a service boundary; the narrow permitted direct handler must
authorize for itself.

**Note:** This check subsumes Object-Level Authorization (above) for auth-surface
paths. If both trigger on the same protected write, report under Auth Boundary
Map Gap only. Retain P1 severity when neither the applicable service nor the
permitted direct handler performs concrete authorization. The P2 severity
applies when coarse route auth exists but the fine-grained boundary is misplaced
or incomplete.

**Look for:** Protected handler or service methods in `auth/`, `admin/`,
`account/`, `install/`, `member/`, or `module`-level paths containing `db.Exec`,
`db.ExecContext`, `service.Create`, `service.Update`, or `service.Delete` without
concrete action/resource authorization before the write, even when
`RequireAdmin` is present on the route; trusted maintenance paths without a
named and enforced trust boundary.

**Direct-request / stale-install rejection (Baseplate PR #278):** baseplate-only install endpoints must reject direct, out-of-band, or stale requests not originating from the gated install flow -- default-deny on a POST that arrives without the expected install-flow precondition (install not started, already completed, or wrong step). A stale install-wizard session must fail closed, not resume a privileged flow. Flag install/setup handlers that proceed on any well-formed request without checking install state, and flag install completion that does not invalidate the wizard session.

### UI Capability Flag Mismatch (P2)

Flag template conditionals that gate admin/mutation UI using role-string comparisons (`member.Role == "admin"`, `member.IsSuperAdmin`) instead of delegating to `Authorize(ctx, action, resource)` with the same action/resource pairs used by the corresponding handler.

**Look for:** `.templ` files with role-string comparisons or boolean role checks adjacent to mutation buttons, admin-only sections, or privileged controls, where the handler uses `deps.Auth.Authorize()` with a different gating mechanism.

### Nil ContextMember Guard (P1)

Flag handler or service code that accesses fields on `auth.ContextMember(ctx)` (`.ID`, `.Role`, `.Email`, etc.) without a nil check. A nil `ContextMember` occurs when middleware is misconfigured, when internal service calls bypass the HTTP layer, or when session hydration fails silently.

**Look for:** Direct field access on the return value of `ContextMember()` without a preceding `if member == nil` or `if member := auth.ContextMember(ctx); member != nil` guard.

### Stale Operator Session (P2)

Flag operator privilege mutations (role changes, member removal, permission updates, super-admin revocation) that do not invalidate or revalidate the affected member's session. Stale operator sessions must fail closed.

**Look for:** Service methods that update `member.role`, `member.status`, or remove super-admin privileges without a subsequent `session.Destroy()`, session invalidation, or role revalidation call for the affected member.

### PII-Safe Logging (P2)

Flag error responses or structured log calls that include raw email addresses or member IDs in user-facing HTTP responses, or that distinguish between "user not found" and "password wrong" in login flows (account-existence oracle). Logs should use stable non-PII identifiers when available.

**Look for:** `slog.String("email", ...)`, `http.Error(w, ... member.Email ...)`, login handlers with distinct user-facing error messages for missing-account vs wrong-password. For raw `err.Error()` in responses, see Raw Error Exposure above.

### Unvalidated Redirect / gosec G710 (P2)

Flag `http.Redirect` (or `Location` header writes) whose destination is derived from request input -- query params, form values, referer -- without a validating guard. This is the open-redirect vector gosec reports as **G710**.

A redirect already constrained by a `safeRelativeRedirect`-style guard (rejects absolute URLs, `//host` targets, and non-local paths) is **compliant** -- do not flag it; a gosec G710 hit on a guarded path is a false positive resolved with a justified `#nosec G710` naming the guard (see the golang-patterns "CI Security Scanner Diagnosis" section), not a code change.

**Look for:** `http.Redirect(w, r, X, ...)` or `w.Header().Set("Location", X)` where `X` comes from `r.URL.Query()`, `r.FormValue()`, or `r.Referer()` with no preceding local-only validation. If a `safeRelativeRedirect`-style helper already constrains `X`, treat it as safe.

### Cross-Install Trust Choreography (P1)

The federation backend (Assembly Baseplate PR #252, Session 2.9a) introduced cross-install link/trust/consent flows. Review any code touching those flows against these checks. The open Baseplate issues cited are the live threat-model exercises -- treat them as open work, not solved patterns.

- **Ingress endpoint hardening:** a receiving install's trust-request ingress endpoint must validate the sender, rate-limit, and emit an alert/audit/event for every inbound trust request -- silent acceptance is a finding (Baseplate #259, mutual-trust handshake).
- **TOFU pinning:** the first-seen key for an install is pinned. A *known* install presenting a new key must enter a TOFU-pending state requiring explicit re-verification; flag any path that silently re-trusts a changed key (Baseplate #259).
- **Server-side fingerprint attestation:** fingerprint verification must be recorded as an explicit attestation enforced server-side. Flag flows where verification status is client-asserted or inferable from UI state alone (Baseplate #254).
- **Replay + SSRF controls:** handshake exchanges need nonce/timestamp replay protection; outbound well-known fetches need SSRF guards (scheme/host allowlisting, no redirects to private address ranges) (Baseplate #259).
- **Key-rotation detection:** background well-known re-fetch should detect rotated keys proactively. A detected rotation is a flagged event requiring re-verification, never an auto-accept. A rotated key also invalidates any in-flight signed pushes still pending under the old key -- flag a delivery path that keeps applying old-key payloads after rotation is detected (Baseplate #255).
- **Default-deny trust boundaries:** no resource is federation-accessible unless explicitly granted. Flag any handler reachable by a federated peer that does not check an explicit grant.
- **Signed push delivery (Baseplate PR #271, #275):** inbound trust/share/co-op-stats push payloads must be signature-verified against the *pinned* sender key BEFORE any processing or state write -- a handler that parses or applies before verifying is a P1 finding. Delivery must be idempotent: a replayed or duplicate push must not double-apply. Flag push handlers lacking a nonce/timestamp or idempotency key, and flag stale-response handling that returns a success path where a 409 (already-applied / superseded) is correct (stale-response 409 cleanup, PR #275).
- **Notification SSE fan-out (Baseplate #273, #277):** cross-install state changes (share grants, signed co-op stats, live trust notifications) that drive live SSE updates must re-authorize each subscriber per fan-out and scope each event to the granted resource. A federated SSE stream must not broadcast ungranted data to a peer who lost (or never held) the grant. Flag fan-out loops that resolve authorization once at subscribe time and never re-check on emit.
- **Share-grant authorization (Baseplate PR #275):** data-sharing permission grants are explicit, revocable, and re-checked on every cross-install read -- not cached at link time. Super-admin trust controls gate grant creation/revocation. Flag any cross-install read path that serves shared data without re-checking a live grant, or grant mutation reachable below super-admin.

- **Public/Private URL Boundary (P1, Baseplate PR #447):** an install has an internal base URL (container address, LAN hostname, `localhost:port`) and a public federation URL. They are never interchangeable. Flag: any internal URL serialized into a federated payload (a remote install cannot resolve `http://app:8080/uploads/logo.png`, and emitting it discloses internal topology); any cross-install asset URL derived from the inbound `Host` header rather than from configuration; and any fallback to the internal address when the public URL is unset -- that path must **refuse to emit the payload**, fail-closed. A `Host`-derived URL is attacker-controlled.
- **Responder-side share transport (P1, Baseplate PR #447):** federation work is routinely built and verified only from the requester's side. Review the **responder**: serving shared assets (install logo, document preview) re-checks the share grant on **every fetch**, not once at link time; the requesting key is checked fairly (a rotated key is detected and flagged, not silently treated as a forgery); and a signed inbound fetch is validated against the grant that actually covers the target resource. A valid signature proves *identity*, never *authorization*. Flag any asset-serving path reachable by a federated peer whose only check is signature validity.

**Look for:** ingress/handshake handlers in `federation/`, well-known fetch clients, key pinning/storage code, trust-state transitions, signed-push delivery/ingest handlers, federated SSE fan-out emitters, share-grant create/revoke/read paths, federated asset/logo/preview serving handlers, URL-building helpers that read `r.Host`, and any federation-reachable handler missing an explicit grant check.

**Acceptance bar:** cross-install behavior is proven by a real **two-install** exercise (live sender + receiver, PR #275 two-install proof) covering **both directions** -- requester and responder. Flag federation work whose only verification is a same-process stub, or that exercises the requester alone -- note it as insufficient evidence for the trust claim.

### Release / Update Supply-Chain (P1/P2)

The Baseplate update system (PR #279: updater CLI, release manifests, pre-apply snapshots, release workflow, ADR-008/ADR-014) introduced a software supply chain. Review any updater, release, or manifest code against these controls. The trust boundary is "code we built" vs "bytes fetched from a network" -- everything crossing it must be verified before it runs.

- **Manifest + artifact URL boundaries (P1):** the release manifest and every artifact URL it names must be fetched over HTTPS from a pinned/allowlisted origin. Flag manifests that accept an attacker-influenced base URL, follow redirects to an unvalidated host, or take the download URL from untrusted input.
- **Checksum + signature honesty (P1):** the artifact checksum AND signature must be verified BEFORE the archive is extracted or the new binary is executed. A code path that *claims* verification (logs "verified", sets a flag) without an actual cryptographic check against a pinned key is a P1 finding -- verification theater is worse than none.
- **Archive extraction safety (P1):** extraction must guard against zip-slip / path traversal (reject entries resolving outside the target dir), reject symlinks, and bound total size/entry count. See the path-traversal item under Input Validation; an updater extracting a remote archive is the highest-stakes instance of it.
- **Snapshot / handoff semantics (P2):** a snapshot of the current install is taken before apply; a partial-success apply leaves a recoverable state (not a half-written binary or migrated-but-unrunnable DB); rollback restores the snapshot. Flag apply paths with no snapshot, or a handoff to the new binary that is not atomic (rename-into-place, not truncate-then-write).
- **GoReleaser dry-run constraint (P2):** release config is validated via dry-run (`--snapshot` / `--skip-publish`) in CI; flag CI or test paths that perform a real publish or signing operation, or that bake real signing keys into a non-release job.
- **Provider-agnostic (P2):** no hardcoded single registry/host/provider in updater code or release docs -- the manifest origin is configurable. Flag provider lock-in that would prevent self-hosting the update channel.

**Look for:** `internal/updater/`, release CLI commands (`assembly update`/`assembly version`), manifest fetch/parse, archive extract (`archive/tar`, `archive/zip`, `io.Copy` into a path joined from archive entry names), signature/checksum verify calls, `.goreleaser.yaml`, and release GitHub Actions workflows.

### Update / Release Preflight (P1)

Beyond the supply chain, the *operational* preflight. Baseplate PRs #399, #438, #436/#437.

- **Update candidate preflighted before replacement (P1, #438):** checksum, signature, AND version ordering are verified on the candidate **before any file is swapped**. Flag an apply path that begins replacing files and validates afterward, or that permits a downgrade or same-version reapply without an explicit force flag. "We verify it during extraction" means a partially-replaced install on a failed check.
- **Config validation fails closed at boot (P1, #399):** invalid configuration exits non-zero. Flag any loader that logs a warning and continues, substitutes a default for a required secret or URL, or treats an empty string as an unset-and-therefore-fine value. A server that boots with half a config is a server that fails at 3am.
- **Shutdown ordering is explicit (P2, #399):** drain HTTP -> stop consumers -> flush -> close DB. Flag an incidental `defer` stack standing in for a shutdown sequence, and any path that closes the DB while consumers may still write.
- **Key rotation, responder side (P2, #399):** email and federation key checks must treat a rotated key as *detected and flagged*, not as a forgery, and must state an old-key grace window. Flag rotation logic with no grace period -- it drops in-flight messages signed moments before the rotation.
- **Double-submit protection on repair forms (P2, #399):** recovery and repair endpoints are idempotent server-side via a token. A disabled submit button is not protection -- these forms run precisely when the system is unhealthy and users double-click.
- **Update-failure recovery copy (P2, #399):** the failure message names the recovery command. "An error occurred" during a half-applied update is a support ticket.
- **Release receipt (P2, #436/#437):** a release enumerates active-install monitoring and beta-finalization proof. Flag a release claimed complete with no receipt naming what was monitored and for how long.

**Look for:** `internal/config/` loaders and their `Validate()` methods, `internal/updater/` apply/preflight ordering, `Shutdown(ctx)` implementations and `defer` stacks in `cmd/`, key-rotation handlers for email and federation, repair/recovery form handlers, and release workflow receipts.
