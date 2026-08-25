# Full review role dispatch

This reference is the authoritative full-mode lane dispatcher. dm-review owns
the roster and review criteria; model-router owns every concrete participant,
availability, billing, family, transport, fallback, and payload invocation.
For every lane that requires separation from implementation, load
`independent-family-lanes.md` and pass only its opaque receipt identifiers.

## Fixed role mapping

| Lane | Role | Capabilities | Effort |
|---|---|---|---|
| security auditor | `security-review` | `read-repository`, `long-context`, `structured-output`, `independent-family` | `high` |
| architecture | `review-deep` | `read-repository`, `long-context`, `structured-output` | `high` |
| patterns | `review-deep` | `read-repository`, `structured-output` | `high` |
| simplicity | `review-deep` | `read-repository`, `structured-output` | `high` |
| documentation | `review-fast` | `read-repository`, `structured-output` | `medium` |
| tests/build | `review-fast` | `read-repository`, `tool-use`, `structured-output` | `medium` |
| second perspective | `plan-critic` | `read-repository`, `long-context`, `structured-output`, `independent-family` | `high` |
| triggered domain/UI lane | `review-deep` | explicit required capabilities only | `high` |

Keep the complete selected roster. Role mapping does not drop a required lane.
Quick mode keeps its existing smaller roster but uses the same role mapping.

## Dispatch

Resolve one coherent model-router bundle with Workflow Kernel and require
`skills/model-router/references/role-dispatch.sh`, the request schema, and role
policy. For each selected lane:

1. Build the common reviewer prompt from `reviewer-prompt-template.md`.
   Inline `reviewer-output-contract.md` exactly once. Resolve every trusted
   `${CLAUDE_SKILL_DIR}/references/<name>.md` pointer host-side; no token may
   remain unresolved in the materialized prompt.
2. Use a stable lane label and anonymous participant ID. Do not add a runtime
   model/provider tag or disclose another participant's concrete identity.
3. Materialize a fresh output file, private receipt file, and complete
   repository-evidence file. Pass the evidence path with
   `--repository-evidence-file`; a prompt-only candidate is ineligible without
   it.
4. Build `role-dispatch` argv as an array from the table above.
5. Store every live implementation and repair receipt under
   `<exact-run-root>/receipts/private/router/`, named by its opaque receipt ID.
   For independent lanes, pass that directory with
   `--independence-receipt-dir` and append each opaque implementing receipt ID
   with `--independence-receipt-id`; dm-review never receives family names. For
   a verified human-authored diff with no model-authored contribution, pass
   `--human-authored` instead. Any subsequent model repair invalidates that
   claim; register its live implementer receipt and use receipt IDs alone. If
   repair provenance is unavailable, the independent lane remains unavailable.
   The two origin forms are mutually exclusive.
6. Launch selected lanes in parallel when the host supports it.

Outside an explicit repository test harness, accept `disposition: completed`
only when the companion also reports `evidenceSource: live` and
`transportStub: false`; simulated evidence never settles production coverage.
The public lane companion records lane, requested role/capabilities/effort,
anonymous participant, disposition, fallback state, diff scope, and output
reference. The private router receipt remains outside reviewer prompts and
ordinary reports.

## Provider-neutral input eligibility

The router applies the same request-shape and workload rules to native and
OpenRouter candidates. Its external boundary validates UTF-8, paths, and diff
structure; it never rejects, redacts, splits, or holds content because it looks
credential-shaped, classified, security-sensitive, or deployment-related.
There is no approval prompt. Transport failure or structurally invalid evidence
falls through within the same role; the complete roster and every required diff
section must still settle.

## Diff scoping per lane

A scoped lane's `## Diff` section contains only files selected by its complete
Phase 3 trigger condition; the lane may still read any project file it needs.
Always include the whole-diff path list (names only) under `## Files to Review`.
Slice from the full trigger, not file extensions alone.

Only the lanes named scoped below may be sliced. Every other lane receives the
full diff. A lane in neither list is a classification gap: give it the full diff
and record `diff_scope: full` with `slice_status: unclassified`.

Scoped lanes: `a11y-html-reviewer`, `a11y-css-reviewer`, `css-reviewer`,
`a11y-dynamic-content-reviewer`, `voice-editor`, `go-build-verifier`,
`craft-reviewer`, `migration-validator`, `visual-browser-tester`,
`ux-quality-reviewer`, and `ui-standards-reviewer`.

Full-diff lanes (closed list): `security-auditor`, `architecture-reviewer`,
`second-perspective`, `pattern-recognition-specialist`,
`code-simplicity-reviewer`, `doc-sync-reviewer`, `test-coverage-reviewer`,
`governance-domain`, and `openrouter-bulk-analyst`.

Every lane records `diff_scope` (`full` or `scoped(<n> files of <total>)`),
`full_diff_override`, and `slice_status` (`sliced`, `not_sliced`,
`unclassified`, `slice_failed`, or `full_diff_override`).
`DM_REVIEW_FULL_DIFF=1` disables slicing and records the override. The switch
fails open: an unparseable diff, empty trigger result, or any slice-construction
error sends that lane the full diff with `slice_status: slice_failed`.
Uncertainty always widens input; a lane is never dispatched against an
unverifiable slice or skipped because its slice is empty.

## Security independence

The full-diff security lane is always required and passes every implementing
receipt ID. A supplementary eligible-section security result may coexist, but
cannot replace the independent full-diff lane. Missing private family evidence,
no eligible independent family, or incomplete held-section coverage keeps the
review incomplete. Never fall back to an implementing family.

## Receipts

Use model-router's public disposition in the lane coverage receipt. Exact
model/provider/transport/billing/token/cost identity remains in its content-free
private receipt and may be consumed only by operator metrics. Preserve current
Workflow Kernel attempt recording without asking it to choose a role or model.
