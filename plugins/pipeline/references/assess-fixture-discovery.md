# Fixture and verification-profile discovery

Loaded by the assess phase only when the project ships fixtures or a `tests/ux/`
verification declaration -- dev-time auth bypasses, persona-switching helpers,
or a declared browser coverage matrix. A project with neither never loads it.

Many codebases ship with dev-time auth bypasses or persona-switching helpers. Discovering these up-front saves the prompt-writer from having to re-derive them from handler code.

For projects with `tests/ux/`, emit a sanitized declared verification profile
using `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md`.
Include every selected task/persona/route/browser/viewport case and provenance,
not a representative sample. Task frontmatter overrides the generated coverage
matrix. Record auth field names only; never copy cookie, bearer, password,
username, or fixture-secret values into assessment HTML or its data islands.

Protocol:

1. **Auth middleware scan:** grep the project's auth middleware (common locations: `internal/handlers/middleware.go`, `backend/auth/*.go`, `app/Http/Middleware/*.php`, `config/authentication.*`) for keywords: `cookie`, `X-Test-User`, `Bearer`, `session`, `impersonate`. **Extract the header/cookie NAME only. Redact values.** If a matched line contains `=<literal>`, `: "<literal>"`, `Bearer <literal>`, or any hardcoded token, flag the file for manual review and record only the field name in the Assessment Brief. Never copy raw matched lines into `plans/<feature-slug>/assessment.html` (neither the rendered Test Personas section nor the `testPersonas` data island) -- dev-mode middleware sometimes hardcodes bearer tokens or session secrets that must not propagate downstream.
2. **Seed data scan:** grep seed files (`seeds/`, `fixtures/`, `db/seed.*`, `internal/fixtures/*/seed.go`) for user/member IDs and role names. Collect 2-3 representative personas per role.
3. **Test helper scan:** grep `tests/`, `_test.go`, `spec/` for patterns like `loginAs(`, `asUser(`, `setCurrentUser(` to find helper functions that scripts/tests use to switch identity.

Report findings in the Assessment Brief under a `## Test Personas` heading:

```markdown
## Test Personas

**Auth-switching mechanism:** `coop_member` cookie (fake auth middleware at internal/handlers/middleware.go:42)

| Persona | ID | Role | Use for |
|---------|-----|------|---------|
| Aisha Williams | mem_005 | Member, no position | Verify empty-state and unprivileged views |
| David Chen | mem_012 | Member with position | Verify authored-content views |
| Maria Rodriguez | mem_001 | Director | Verify privileged actions and approvals |

To switch identity: set `coop_member=<id>` cookie before navigating.
```

The prompt-writer reuses this instead of re-discovering the mechanism per chunk.

If no auth-bypass mechanism is found, log `fixture discovery: no dev-mode auth bypass detected` and continue.
