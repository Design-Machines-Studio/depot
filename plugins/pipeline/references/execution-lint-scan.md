# Live Wires lint and anti-pattern scan

Load at Step 3e.5 when modified files match `.html`, `.templ`, `.twig`, or `.css`, and at Step 3f before review.

## Live Wires lint

```bash
LW_ROOT=""
for CACHE in "$HOME/.claude/plugins/cache/depot/live-wires" "$HOME/.codex/plugins/cache/depot/live-wires"; do
  LW_ROOT=$(ls -td "$CACHE"/*/ 2>/dev/null | head -1)
  [ -n "$LW_ROOT" ] && break
done
```

Read `${LW_ROOT}/references/lint-rules.md`. Hard-fail (block commit, fix, re-run; max 2 iterations then P1):

- **LW-INLINE:** `grep -n 'style="' <files>` on .html/.templ/.twig
- **LW-BASELINE:** `grep -nE '(margin|padding|gap):\s*[0-9]+(px|rem|em)' <files> | grep -vE ':\s*1px'` on .css
- **LW-BEM:** `grep -nE '__' <files>` on .css/.html/.templ/.twig
- **LW-LAYER:** CSS rules outside `@layer` on .css

Warning (receipt only):

- **LW-STATE:** `grep -nE '\.(is-|active|disabled)' <files>`
- **LW-HARDCODED-COLOR:** `grep -nE '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(' <files>` on .css
- **LW-LOGICAL:** `grep -nE '(margin|padding|border)-(top|bottom|left|right):' <files>` on .css

## Anti-pattern scan

Datastar:

```bash
grep -rn 'data-on:.*\.window\|data-on:.*\.debounce\|data-on:.*\.throttle' .worktrees/pipeline/<feature>/<chunk-id>/backend/ --include="*.templ" || echo "clean"
grep -rn 'data-signals=' .worktrees/pipeline/<feature>/<chunk-id>/backend/ --include="*.templ"
```

Go:

```bash
grep -rn 'err\s*=' .worktrees/pipeline/<feature>/<chunk-id>/backend/ --include="*.go" | grep -v 'if err' | grep -v '_ =' | head -10
grep -rn 'fmt.Sprintf.*SELECT\|fmt.Sprintf.*INSERT\|fmt.Sprintf.*UPDATE' .worktrees/pipeline/<feature>/<chunk-id>/backend/ --include="*.go" || echo "clean"
```

Assembly mutation handlers:

- Classify each POST/PUT/PATCH/DELETE handler as a protected user/operator write or trusted internal maintenance. A protected write without concrete action/resource authorization before the write is P1. Trusted maintenance must name and enforce its trust boundary; an unproved maintenance claim is P1.
- Grep `Publish(` inside transaction scope. Events must fire after commit. `Publish()` between `Begin()` and `Commit()` is P1.
- Grep fixtures for raw `*sql.DB`: `grep -rn '\*sql\.DB' .worktrees/pipeline/<feature>/<chunk-id>/ --include="*_test.go" --include="*fixture*"`. Fixtures must use `ScopedDB`. P1.

All projects:

```bash
grep -rn "LIKE '%.*%'" .worktrees/pipeline/<feature>/<chunk-id>/ --include="*.go" --include="*.py" --include="*.ts" || echo "clean"
```

Fix anti-patterns before the review loop.
