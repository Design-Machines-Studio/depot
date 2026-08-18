# Assembly production architecture checks

Assembly-specific structural checks (fixtures, ScopedDB, service boundaries,
Templ/Datastar placement, Auth Boundary Map receipts). The `architecture-reviewer`
agent loads this file only when the detected project type is Go+Templ+Datastar
(Assembly); other project types never load it.

When reviewing Assembly production code (`internal/fixtures/` or `internal/baseplate/`):

**File Size Heuristic:** Handler files above 200 lines and service files above 500 lines deserve inspection, but the number alone is not a finding. Report only a concrete current defect such as an unsafe boundary, untestable coupling that caused a regression, or an execution failure. Do not create P3 work for file size or a general maintainability preference alone.

**Reorg-Only PR Verification (P2):** When a PR's stated purpose is decomposing an oversized file (the fix for a File Size Limits finding), hold it to the behavior-preserving reorg contract:

- The diff must be **move-only** -- code relocated between files with no logic edits. Flag any PR that mixes decomposition with behavior changes; the behavior change hides in the move noise and must ship separately.
- File-size targets are stated up front in the PR body (which files, target line counts), so reviewers can verify the split achieved its goal.
- Behavior proof is the **existing test suite green via the Docker-backed run** (assembly go-test-runner pattern), not new tests. A reorg-only PR that needs new tests to pass was not reorg-only. State the no-behavior-change acceptance criterion explicitly in the PR body: "same test suite, same pass set, before and after."
- **Stable public contracts:** the package's exported symbol set and signatures are unchanged after the split. Flag any decomposition that renames, removes, or re-signatures an exported symbol -- that is a breaking change that ships as its own tracked PR, not smuggled into a reorg.
- **Narrow DTOs at new boundaries:** when a split introduces a new interface or DTO between the extracted pieces, it must expose only the fields the caller actually uses -- no whole-struct ("God-struct") passing across the new seam just because it is convenient. Stamp coupling reintroduced by a decomposition defeats the point.
- Security-sensitive modules (auth, federation, **share, repair, membership**) get extra scrutiny: confirm package visibility and import boundaries are unchanged after the move, and that no privileged path becomes reachable from a wider scope post-split.

Open Baseplate exercises for this check: **#258** (decompose the federation file) and **#234** (split the membership service + admin handler files). The trust/share/repair services touched by PR #271 (trust hardening/delivery) and PR #275 (data-sharing permissions) are the same decomposition class -- when they grow past the file-size limits, split them under this contract. A good next exercise is executing #258 as a strict reorg-only PR with the Docker test suite as the behavior proof.

**Service Boundary Bypass (P2):** Use `assembly:development`'s Mutation
Applicability Matrix. Flag a handler that calls `ScopedDB` directly when domain
logic, transaction ownership, or a second real caller requires a service. Do
not flag a one-use handler merely for one low-consequence `ScopedDB` statement
when it has no domain logic or transaction ownership. Every other applicable
control still applies, including concrete action/resource authorization for a
protected user or operator write.

**Module Boundary Violations:** A fixture importing another fixture's package is a heuristic. Report it only when the import creates a concrete current data, authorization, lifecycle, execution, or bounded maintainability defect. For example, inspect `internal/fixtures/governance/` importing `internal/fixtures/documents/`, but do not infer hostile code or report coupling merely because another layer would look cleaner.

**ScopedDB Bypass:** Raise P1/P2 when fixture code importing `database/sql` or using `*sql.DB` exposes a reachable cross-prefix read/write, authorization bypass, or corruptible state that `ScopedDB` currently prevents. Mere direct access in trusted first-party Fixture code is not automatically a finding. Exception: baseplate code (`internal/baseplate/`) and test utilities may use raw `*sql.DB`.

**Handler Thickness (P2):** Flag handler functions that own domain rules,
transaction scope, or behavior shared by another caller. Do not flag ordinary
request parsing, input validation, rendering, or the narrow one-statement
direct `ScopedDB` case allowed by the applicability matrix. Suggest a service
when a real boundary exists.

**Shared Component Isolation:** An `internal/components/` file importing fixture-specific types is a heuristic. Report it only when direct evidence shows a current boundary regression or other observable defect; do not mandate primitive props or a new abstraction by default.

**Module-Owned Model Placement:** DTO or model placement outside `internal/fixtures/{name}/model/` is not a finding without a demonstrated current defect. Do not require a move solely for architectural consistency.

**Page Template Placement:** A page-level Templ template outside `internal/fixtures/{name}/pages/` is not a finding without a demonstrated current defect. Clear direct placement is valid.

**Fixture Ownership Boundary:** Flag fixture access to baseplate internals as P1/P2 only when it exposes a reachable authorization, credential, destructive-data, or corruptible-state path. Otherwise treat `Dependencies` interfaces as the existing preferred mechanism, not proof that direct trusted code is hostile.

**Note:** Missing NATS events after mutations are checked by the `nats-reviewer` agent (assembly plugin), not this agent. Do not duplicate that check here. Authorizer call *presence* is checked by the `security-auditor` agent; this agent checks *structural* placement (logic in handler vs service layer).

**Auth Boundary Violation (P2):** When a protected mutation has a service
boundary, flag an `Authorize()` call that lives only in the handler. A different
caller could otherwise bypass authorization. The service method owns the
concrete action/resource check. A direct handler allowed by the applicability
matrix must authorize before its protected write.

**Look for:** `Authorize()` calls inside `func (h *Handler)` or `func (h *handler)` methods that precede `h.service.Foo()` calls -- the Authorize should be inside `service.Foo()`, not the handler.

**Auth Boundary Map Receipt:** When reviewing changes that touch `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths, check whether the PR description, a commit body, or a checked-in receipt includes an Auth Boundary Map receipt. Its absence is a coverage note, not a product finding or proof of an auth defect. Report a finding only for a concrete reachable authorization failure in the code.

The receipt enumerates: mapped surfaces, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases addressed, test files, and residual risk. See the assembly development skill for the template.

The receipt helps a reviewer learn which surfaces were considered, but no repository is required to create a new threat-model document solely to satisfy review. Inspect the actual diff and reachable routes.

If Phase 1b located the receipt somewhere other than the PR body (a merge-commit body, `plans/*/receipt.md`), that satisfies this check -- cite where you found it.

**Fixture SDK Conformance Gap:** When approved scope changes an SDK trust boundary or a current reachable input can violate an existing invariant, verify the smallest relevant negative case. Trusted first-party Fixture code does not imply a hostile marketplace. Raise P2 only when the missing proof permits a concrete current regression or realistic reachable harm; otherwise omit broader conformance coverage from findings.

- An unprefixed or foreign table prefix is rejected by `ScopedDB`
- Stream subjects outside the fixture's own prefix are rejected at registration
- Reserved scopes (`gov`, `doc`, `eq`, `health`, `member`, `system`, `audit`, `federation`) cannot be claimed by a fixture that does not own them
- A disabled module's routes return 404 -- a 200 or a 500 both disclose that the module exists
- The `register -> enable -> disable -> teardown` lifecycle is exercised, including a second `enable` reattaching routes and streams
- A stream set containing one invalid subject registers **none** of them

Escalate to **P1** for a fail-open default: a zero-value `Authorizer`, a nil or zero actor, an empty enum, or a missing module that **allows** rather than denies. Absent input must deny.

A change that makes a verification claim must prove the specific reachable invariant it claims. Do not require an unrelated conformance-harness family.

**Hand-Rolled JS Where Datastar Suffices:** In Go + Templ + Datastar projects, a new `<script>` block or `.js` file whose behavior maps to `${CLAUDE_PLUGIN_ROOT}/plugins/dm-review/skills/review/references/datastar-pro.md` is a framework heuristic. Report it only for a demonstrated current behavior, security, accessibility, or bounded maintainability defect; otherwise do not require a declarative rewrite.

#### Craft CMS Projects
Expected layers:
1. **Templates** (Twig) -- Presentation only
2. **Modules/Plugins** -- Business logic, custom functionality
3. **Config** -- Environment and Craft configuration
4. **Migrations** -- Database schema changes

Violations:
- Templates executing complex Element Queries that should be in modules
- Business logic in template `{% set %}` blocks
- Modules directly rendering HTML instead of returning data

#### CSS Framework Projects
Expected layers:
1. **Tokens** -- Design tokens (custom properties)
2. **Reset/Base** -- Element defaults
3. **Layout Primitives** -- Grid, stack, cluster, etc.
4. **Components** -- Scoped component styles
5. **Utilities** -- Single-purpose classes

Violations:
- Components overriding tokens directly instead of using them
- Utilities with more than one property
- Layout primitives containing visual styling (colors, fonts)
