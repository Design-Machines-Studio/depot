# Stack-specific simplicity checks

Loaded by `code-simplicity-reviewer` only for the stacks the changed files
actually use -- Go, Templ, Twig (Craft CMS), or CSS. A diff touching none of
them never loads this file.

## Stack-Specific Checks

### Go
- Unnecessary interfaces -- only create interfaces at consumption sites, not declaration sites
- Over-use of channels when a mutex or sync.WaitGroup would be simpler
- Wrapping errors without adding context (`fmt.Errorf("failed: %w", err)` where the wrapper adds no info)
- `any` or `interface{}` when a concrete type is known

### Templ
- Component prop bloat -- components taking more than 5 props should probably be split
- Inline styles or scripts that belong in CSS/JS files
- Repeated markup patterns that should be extracted to components
- Complex Go expressions in templates -- extract to a function

### Twig (Craft CMS)
- Deep include/extend chains (more than 3 levels)
- Complex logic in templates that belongs in a module or service
- Repeated query patterns that should be in a Twig extension
- Inline CSS/JS that belongs in asset bundles

### CSS
- Selectors that are more specific than necessary
- Duplicate property declarations
- Media queries that could be replaced with container queries
- Custom properties declared but never used
- Redundant resets (resetting properties to their default/inherited values)
