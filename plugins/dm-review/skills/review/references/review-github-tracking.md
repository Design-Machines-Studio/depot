# GitHub issues for external blockers

Load only for a concrete external dependency under `issue-tracking.md`.
Search the owning repository's existing issues before creating one. Reuse a
matching issue; otherwise create it with `gh issue create --repo <owner/repo>`
and a body file containing the finding evidence, reviewed head, dependency,
unblock condition, and acceptance criteria. Use existing labels when available.
Never create new labels just to satisfy a template.

Keep the pending todo and issue URL in the review report until the dependency
is available and the affected verification passes. Creating an issue does not
resolve the finding. Continue independent local repairs. Report permission or
API failures with prepared issue details; do not claim creation without a URL.
