# Implementation origin for independent review

Resolve provenance only when a selected lane requires family independence.
Prefer every supplied live implementation and repair receipt ID. Otherwise
accept one truthful plain declaration about the exact diff: entirely
human-authored, authored in Codex, authored in Claude, mixed known origins, or
unknown. Never infer prior authorship from the host currently running review,
and never ask an operator to fabricate an internal receipt ID.

Materialize the declaration with model-router's private
`implementation-origin.sh create` interface. Keep the resulting file under the
mode-`0700` exact-run private router directory. Pass only its path to
`role-dispatch.sh --origin-file`; do not read or project its contributing-family
field into a reviewer prompt, synthesis input, lane companion, or public report.

The declaration binds repository identity, exact base, exact HEAD, exact diff
digest, origin class, contributing families, and declaration source. A changed
HEAD or diff rejects it. A model-authored repair invalidates an earlier
human-authored declaration. Preserve every known original and repair origin in
the replacement mixed record, or prefer the complete set of live receipts.

## Proportional unknown handling

For an ordinary trusted first-party diff outside the bounded sensitive paths,
unknown provenance is one transparent nonblocking limitation. Run the selected
review roster without claiming family independence, consolidate one provenance
coverage cause, and allow an otherwise complete review to finish.

For a security-sensitive path, release-integrity boundary, authorization
boundary, credential boundary, destructive operation, or high-consequence
decision, unknown provenance keeps the required independent lanes incomplete.
Do not emit one failure per candidate or reviewer. Ask exactly one next action:
"Was this exact diff authored in Codex, authored in Claude, or entirely
human-authored?" After a truthful answer, create the exact-diff record, reuse
completed deterministic and review evidence bound to the unchanged HEAD, and
rerun only the affected independent lanes.
