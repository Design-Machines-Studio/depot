# Stable anchors audit

Loaded by promptcraft Phase 3e only when a draft prompt cites line numbers. A
prompt set that already anchors on named symbols, components, heading slugs, or
table/column names never loads this file.

### Phase 3e: Stable Anchors Audit

Line numbers are time-bounded: an interstitial chunk may rewrite the file before Phase 6 executes. Prefer the highest-ranking stable anchor available:

1. **Function / method names** (Go, Python, TS, PHP): "Edit the `SetPosition` handler in `internal/handler/position.go`" beats "Edit lines 42-68".
2. **Templ / component names**: "the `PositionChangeDialog` component in `internal/view/proposal/dialogs.templ`" beats "lines 235-259".
3. **Markdown heading slugs**: link `#section-name` rather than `docs/foo.md:42`.
4. **SQL table + column**: `003_add_votes.sql modifies proposals.vote_count`.

When line numbers are unavoidable (unnamed blocks, constants, YAML keys), annotate `// verified at HEAD <short-sha>` and add a re-verification grep acceptance criterion: `AC: lines 42-68 of path/to/file still contain the signature "<unique-string>" at execution time; if the grep fails, the chunk must stop and re-anchor.` A prompt-wide line-number count above 5 is a smell.
