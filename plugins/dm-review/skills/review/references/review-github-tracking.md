# GitHub Issues finding tracking

Loaded at Phase 6 only when the user selects GitHub Issues tracking. A project
with a `todos/` directory uses text-file tracking and never loads this file.

For each retained P1, P2, and P3 finding, create a GitHub Issue using `gh issue create`:

```bash
gh issue create --title "[P1] Finding title" \
  --body "$(cat <<'EOF'
## Problem
Description from the review finding.

## Location
`path/to/file.ext:line`

## Fix
Remediation steps.

## Reference
OWASP/WCAG/pattern reference.

---
*From dm-review ([Full] mode, DATE)*
EOF
)" --label "review,p1"
```

Use labels `review` + `p1`/`p2`/`p3` for severity. Create the labels first if they don't exist.

**Airlift checkpoint (`dm-review-findings`):** After the pending todo files are written, fire a tier-1 airlift checkpoint so the `todos/*-pending-*.md` findings survive a usage cap, rate limit, or model switch. This is a guarded resolve-from-cache: it is tier-1 deterministic (pure local file + git work, NO model budget, no agent call, no network) and is skipped silently when airlift is absent (OPTIONAL dependency). On an early-warning trip (e.g. a budget threshold crossed mid-run), do not wait for the next phase boundary -- flush this checkpoint immediately so the pending findings are not lost.

```bash
ENGINE=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ENGINE=$(ls -t "$CACHE"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)
  [ -n "$ENGINE" ] && break
done
if [ -n "$ENGINE" ] && [ -x "$ENGINE" ]; then bash "$ENGINE" write --phase dm-review-findings; fi
```

The `[ -n "$ENGINE" ]` guard covers "airlift not installed"; the `[ -x "$ENGINE" ]` guard covers "resolved a path but not executable." Both guards sit within 3 lines of the `airlift-engine.sh` invocation.

---

## Ecosystem Integration

