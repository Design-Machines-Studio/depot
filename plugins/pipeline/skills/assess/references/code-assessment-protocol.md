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

## Step 5: Project History Check

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
