# Bounded Assembly planning opinions

Load only for an explicit comparison/second-opinion/architect-challenge request
or approved high uncertainty.

## Evidence packet

Prepare one compact, immutable packet containing the project goal, exact current
repository/PR/Project evidence, ownership, required evidence levels, current
dependencies, approved decision profile, current consumers, scope boundaries,
and candidate next chunks. Do not include participant identity, candidate
rankings, reputational claims, or one participant's output.

## Blind requests

1. Request `architect` with `read-repository`, `long-context`, and
   `structured-output` at `high` effort. Label its returned work `Plan A`.
2. Request at most one `plan-critic` with `read-repository`, `long-context`,
   `structured-output`, and `independent-family` at `high` effort. Pass the
   architect's opaque private receipt ID, not its family or identity. Label its
   returned work `Plan B`.

Send the evidence packet independently. Neither request receives the other's
output. Do not run debate, rebuttal, convergence, or a third opinion.

## Dispatch mechanics

Resolve one coherent installed model-router bundle through Workflow Kernel and
bind its `role-dispatch.sh`, request schema, and policy. Materialize Plan A and
Plan B prompts separately, use the same immutable evidence packet as each
request's `--repository-evidence-file`, and allocate fresh private output and
receipt paths in one run-private directory.

Dispatch Plan A with `--role architect`, the three capabilities above, and
`--effort high`. Dispatch Plan B with `--role plan-critic`, the four
capabilities above, `--effort high`, `--independence-receipt-dir` set to that
private directory, and Plan A's opaque `--independence-receipt-id`. Preserve
only role-level public dispositions in planning output. The private receipts
remain content-free evidence and never disclose model or family identity to
the other participant.

## One synthesis

Compare project-goal alignment, assumptions, ownership, sequence, dependencies,
scope cuts, collision risk, development speed, token/cost exposure, demonstrated
current consumers, and rejected complexity. Perform one bounded synthesis and
recommend exactly one next chunk. High consequence strengthens the recommended
verification seam; it does not add another opinion.

If the architect is unavailable, synthesize from current evidence and the
remaining valid opinion. If an explicit comparison cannot obtain Plan B, state
that limitation plainly. Routine planning never blocks on model-router.
