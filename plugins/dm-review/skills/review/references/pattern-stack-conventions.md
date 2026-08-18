# Stack-specific naming conventions (pattern review)

Loaded by `pattern-recognition-specialist` only for the stacks the changed files
actually use -- Go, Templ, Twig/Craft, or Live Wires CSS. A diff touching none
of them never loads this file.

## Naming Convention Checks

### Go
- Exported names are PascalCase, unexported are camelCase
- Interfaces named with -er suffix for single-method interfaces
- Package names are lowercase, single-word, no underscores
- Test files end in `_test.go`
- Error variables prefixed with `Err`, error types suffixed with `Error`

### Templ
- Component names are PascalCase
- Component files match their primary component name
- CSS class references use kebab-case

### Twig / Craft
- Template names are kebab-case
- Macro names are camelCase
- Variable names are camelCase

### CSS (Live Wires)
- Custom properties use `--lw-` prefix for framework, `--` for project
- Utility classes use functional naming (what they do, not what they look like)
- Component classes match the component name
