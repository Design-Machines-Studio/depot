# Role-unavailable scheduling gate

Load this reference only after model-router returns the closed `unavailable`
disposition for a required role. It is never consulted while an eligible
candidate remains, and it never selects, approves, or reveals a provider,
model, transport, family, subscription, or billing source.

Pause the run instead of discarding resumable work. Offer only “wait until
capacity changes” or “park this run.” A context that cannot reach the operator
parks resumably. This is a scheduling decision after automatic fallback has
finished, not a routing or billing approval.

Headless behavior is deterministic: an unavailable interaction surface, an
interaction error, a non-operator response, a timeout, or
`PIPELINE_EXHAUSTION_ASK=0` parks the run. Record `wait_category: human_gate`,
the role-level unavailable state, the reset time when known, and the exact
resume instruction. Keep private router receipt identity out of this receipt.

Waiting or parking never weakens owned-path, disclosure, sensitive-path,
verification, independent-family, or final-review requirements. The gate never
launches or relaunches the orchestrator.
