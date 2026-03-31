# Code Assessment Protocol

Systematic evaluation of current codebase state for a specific area. This is not a diff review -- it evaluates what exists now.

## Step 1: File Discovery

Starting from the scope (directory or file list):

1. List all files in the area
2. Categorize by role:
   - **Entry points:** handlers, controllers, routes, main files
   - **Domain logic:** models, services, business rules
   - **Data layer:** migrations, queries, repositories
   - **Presentation:** templates, views, components
   - **Configuration:** env files, config structs, docker
   - **Tests:** test files, fixtures, helpers
3. Note file count and approximate line count per category

## Step 2: Architecture Analysis

Read entry points and trace the request/data flow:

1. How do requests enter? (HTTP handlers, CLI commands, event handlers)
2. What layers exist? (handler -> service -> repository -> database)
3. Are layers cleanly separated or tangled?
4. What patterns are used? (MVC, hexagonal, event-driven, etc.)
5. Are there clear boundaries between modules?

Produce a 1-2 paragraph architecture summary.

## Step 3: Pattern Inventory

Scan for recurring patterns (both positive and negative):

**Positive patterns to note:**
- Consistent naming conventions
- Clean error handling
- Proper use of interfaces/abstractions
- Good test coverage
- Clear separation of concerns

**Negative patterns (tech debt) to flag:**
- Inconsistent naming
- God objects (files >500 lines with mixed responsibilities)
- Missing error handling or swallowed errors
- Hardcoded values that should be configuration
- Duplicated logic across files
- Dead code (unused functions, commented-out blocks)
- TODO/FIXME/HACK comments
- Band-aid fixes (workarounds instead of proper solutions)
- Missing tests for critical paths

## Step 4: Dependency Mapping

1. **Internal dependencies:** What other packages/modules does this area import?
2. **External dependencies:** What third-party libraries are used?
3. **Reverse dependencies:** What depends on this area? (grep for imports of this package)
4. **Circular dependencies:** Any bidirectional imports?

## Step 5: Route Tracing (web projects)

For every user-visible route in the affected area, trace the full chain end-to-end:

1. **Nav link** -- What URL does the user click? (grep sidebar/nav templates for `href`)
2. **Route registration** -- Find the route in main.go/routes.go: `r.Get("/members", ...)`
3. **Handler** -- Which handler function does the route call?
4. **Template import** -- Which template file does the handler render? (check the import path)
5. **Template file** -- Does the file at that import path actually exist?

**Search for ALL matches, not just the first.** If you find `pages/people/members/index.templ`, also search for `pages/members/index.templ` -- duplicate files serving different routes is a common source of bugs.

Document the trace:

```
/members -> r.Get("/members", h.PageMembers) -> handlers/members.go -> pages/members/index.templ
/admin/members -> r.Get("/admin/members", h.AdminMembers) -> handlers/admin.go -> pages/people/members/index.templ
```

## Step 5b: Live State Verification (data-dependent features)

For features that touch module gating, settings, permissions, or data-dependent behavior, do NOT trust config files or code comments. Query the actual live state:

1. **Database state:** Run queries to check actual data. For example:
   - Module slugs: `sqlite3 data/assembly.db "SELECT slug FROM modules"`
   - Config values: `sqlite3 data/assembly.db "SELECT key, value FROM settings"`
   - Seed data: Check that referenced IDs actually exist
2. **Runtime behavior:** If a dev server is running, hit the actual endpoints to verify responses
3. **Package.json scripts:** Read the actual build commands -- don't assume "Vite" or "webpack"

```bash
# Verify actual build toolchain
cat package.json | python3 -c "import json,sys; scripts=json.load(sys.stdin).get('scripts',{}); [print(f'{k}: {v}') for k,v in scripts.items()]"
```

## Step 5c: Runtime Injection Audit (when removing/replacing components)

When the assessment involves removing or replacing a web component, JS module, or framework feature, audit what it injects at runtime beyond what appears in templates:

1. Read the component's source (JS/TS file)
2. Search for `connectedCallback`, `render()`, `setAttribute`, `classList.add`, `innerHTML` -- anything that modifies the DOM
3. List every attribute, class, or element the component adds that doesn't appear in the template source
4. Each injected behavior needs explicit migration -- it won't happen automatically

```
Runtime injection audit for popup-dialog.js:
- Adds aria-haspopup="dialog" to trigger elements (line 178)
- Adds role="dialog" to content wrapper (line 203)
- Manages focus trap on open (lines 210-230)
Migration required: All three behaviors must be replicated in replacement approach
```

## Step 6: Project History Check

Load the `ai-memory` skill from ned and search for:

1. The project entity -- any recent observations about this area
2. Known bugs or incidents related to these files
3. Architectural decisions that affect this area
4. Prior review findings that may still be relevant

If ai-memory is unavailable, check git log for recent changes:
```bash
git log --oneline -20 -- <paths>
```

## Step 6: Produce Report

Structure the Current State Report as:

```markdown
## Architecture
[1-2 paragraph summary of how code is organized]

## Key Files
| File | Role | Lines | Notes |
|------|------|-------|-------|
| path/to/file.go | HTTP handler | ~120 | Entry point for /api/v1/... |

## Patterns
### What's Working
- [Pattern]: [Where observed]

### Tech Debt
- [Issue]: [Location] -- [Impact]

## Dependencies
- Internal: [list]
- External: [list]
- Reverse: [what depends on this]

## Project History
- [Relevant observations from ai-memory or git log]
```
