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

## One synthesis

Compare project-goal alignment, assumptions, ownership, sequence, dependencies,
scope cuts, collision risk, development speed, token/cost exposure, demonstrated
current consumers, and rejected complexity. Perform one bounded synthesis and
recommend exactly one next chunk. High consequence strengthens the recommended
verification seam; it does not add another opinion.

If the architect is unavailable, synthesize from current evidence and the
remaining valid opinion. If an explicit comparison cannot obtain Plan B, state
that limitation plainly. Routine planning never blocks on model-router.
