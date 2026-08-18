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

The airlift `dm-review-findings` checkpoint is not fired here: it protects the default `todos/*-pending-*.md` artifacts, so it lives on the text-file tracking path in the review skill's Phase 6, not on this GitHub-Issues route.

---

## Ecosystem Integration

