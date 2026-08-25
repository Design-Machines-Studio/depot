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
3. Materialize a fresh output file and private receipt file.
4. Build `role-dispatch` argv as an array from the table above.
5. For independent lanes, append each opaque implementing receipt ID with
   `--independence-receipt-id`; dm-review never receives the family names.
6. Launch selected lanes in parallel when the host supports it.

The public lane companion records lane, requested role/capabilities/effort,
anonymous participant, disposition, fallback state, diff scope, and output
reference. The private router receipt remains outside reviewer prompts and
ordinary reports.

## Disclosure and partial coverage

The router invokes the existing OpenRouter disclosure boundary automatically
for any external attempt. There is no approval prompt. A full disclosure
decline falls through within the same role. When the provider boundary returns
partial eligible coverage, retain that result and complete only held sections
with another role attempt. The complete roster and every required diff section
must still settle.

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
