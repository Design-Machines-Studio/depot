# Selective Lane Allowlist (internal loop input)

Load this reference only when `review_lane_allowlist` input is present. Build
the normal roster first, exactly as Phase 3 requires; call it the recomputed
selected full set. The allowlist is only ever a filter over that completed
selection; `review_lane_allowlist` never participates in computing the roster.

`review_lane_allowlist` is an internal loop-to-review input passed only by
`dm-review-loop`. It is not a user-facing flag, is not an environment variable,
and cannot be set by a user. When it is absent, run the recomputed selected
full set exactly as before and record `selective_input_absent`.

Consume it only when the recomputed selected full set exactly equals the
caller's declared `selected_full_set` -- same members, no more and no fewer,
regardless of order -- and the caller's `lanes` is a non-empty subset of that
set containing only unique exact logical lane IDs. Duplicates, aliases,
unknown IDs, role IDs, and criterion aliases are invalid. `security-auditor`
is the one exact independent-family logical lane; `security-review` is its role
and is not a lane ID.
Exact equality for `selected_full_set` is mandatory: it proves the caller and
receiver agree on the full roster at this moment. If the diff changed between
the caller's computation and Phase 3 recomputation, the sets differ and the
receiver discards the input; never relax this equality check to a subset check.

For a full-mode allowlist that omits `security-auditor`, also
require the internal input to carry all three exact fields:
`verification_basis: "affected_lane_repair"`,
`prior_full_review_complete: true`, and
`security_boundary_changed: false`. Only `dm-review-loop` produces this input.
These fields prove that the integration boundary already completed and that
the repair did not touch the bounded escalation set. Missing, false, or
malformed proof discards the allowlist and runs the full roster.

Any validation failure discards the entire selective input and dispatches the unfiltered recomputed selected full set. Never drop invalid members and honor the remainder. Use only this closed reason set, applying the first matching reason in the order listed: `selective_input_absent` when no input was received; `selective_input_malformed` when the input is not an object with string-array `selected_full_set` and `lanes` members; `selected_full_set_mismatch` when the declared and recomputed full sets are unequal; `selective_lanes_empty` when `lanes` is empty; `selective_lanes_duplicated` when `lanes` contains duplicates; `selective_lanes_ambiguous_or_aliased` when `lanes` contains an alias or a criterion-level ID; `selective_lanes_not_subset` when `lanes` contains an unknown ID or a lane outside the recomputed selected full set; and `selective_lanes_omit_required_lane` when `lanes` omits a mandatory lane that the unfiltered review would require. The coverage receipt returns this exact reason, never a generic invalid-input reason.

The independent-family security sign-off, `security-auditor`, is
mandatory for the initial full review, incomplete full-review recovery, and
security-boundary repairs. It may be omitted only by the proven affected-lane
repair case above. Otherwise, if the recomputed selected full set requires it
but `lanes` omits it, discard the entire allowlist, dispatch the unfiltered
roster, and report `selective_lanes_omit_required_lane`. Never silently drop a
required lane and never silently add it back to an otherwise honored allowlist.

When the input is honored, dispatch only the exact lanes in `lanes`. Every
member of the recomputed selected full set outside `lanes` is a deliberate
selective non-dispatch, not a failed lane, and must be identified that way in
the coverage receipt. A selective affected-lane repair verification can support `CLEAN` only after an earlier complete full review, when no P1/P2/P3 findings remain and every required selected verification lane completes. It never substitutes for the initial full-review boundary.
