# Evidence source fallback

Loaded at Phase 1b only when reviewer threads and PR comments come back empty,
or no PR exists. A review whose PR threads already yielded evidence never loads
this file.

**Absence of threads is never absence of findings.** When reviewer threads and
PR comments come back empty, or no PR exists, fall through these in order and
use the first that yields evidence: (1) **checked-in receipts** --
`plans/*/receipt.md`, Auth Boundary Map receipts in the PR body or `docs/`,
JSON and screenshot receipts under `.claude/ux-review/`; (2) **merge-commit
bodies** -- `git log --merges --format='%B' <base>..HEAD`; (3) **closed issues
in range** -- `git log <base>..HEAD --format=%B | grep -oE '#[0-9]+'`, then
`gh issue view <n>`; (4) **verification files** -- `tests/`, `tests/ux/`,
`docs/runbooks/`, and conformance-harness cases the diff added.

Record the source in the report header:

```text
**Evidence source:** PR threads | receipts | merge bodies | closed issues | verification files | none found
```

If every source is empty, say so explicitly and review the diff alone -- a valid but *reported* state. A review that found no prior evidence and stays quiet about it is indistinguishable from one that never looked.
