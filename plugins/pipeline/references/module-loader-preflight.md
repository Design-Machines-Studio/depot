# Extracted conditional reference

## Step 0c: Module-Loader Pre-Flight

Some frameworks maintain a dev-mode module loader separately from the production bundle. When chunks touch JS modules, the dev-mode loader must be updated in lockstep or the new module will not load in the browser (silent failure -- tests pass, nothing renders).

### 1. Detect applicability

If NO chunk's `filesToModify` includes a path under `src/js/`, `assets/js/`, `static/js/`, or `public/js/`, log `module-loader pre-flight: not applicable` and skip to Step 1.

### 2. Locate the loader routing file

Search the repository root for a likely module-map handler:

```bash
grep -rn "moduleMap\|module-map\|moduleRoutes\|/js/.*\\.js" cmd/ src/ internal/ app/ 2>/dev/null | grep -iE "handler|routes|main\\.go|app\\.py|server" | head -20
```

For Assembly (Go + Templ + Datastar), the canonical location is `cmd/api/main.go` -- grep for the import map or `/js/<name>` route handlers.

### 3. Annotate filesToModify

For every chunk that touches a JS module, append the loader routing file to its `filesToModify` list in memory (do not rewrite the manifest). Log:

```text
module-loader pre-flight: chunk <chunk-id> touches src/js/<module>.js. Loader routing file <path>:<line> added to filesToModify. Chunk prompts must update both the module AND its loader entry.
```

If the chunk prompt does not already mention the loader routing file, flag it as IMPORTANT and proceed -- the prompt-writer likely missed it. The subagent must handle both files atomically.

### 4. Negative case

If no loader routing file is found (e.g. a framework that auto-discovers modules), log `module-loader pre-flight: no dev-mode loader detected -- assuming auto-discovery` and continue. This is the common case for modern bundlers.

