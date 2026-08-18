# Selective lane re-run (iteration 2+)

The caller-side selection contract for `dm-review-loop`. Loaded only from
iteration 2 onward, when a prior pass left findings to repair. Iteration 1 is
always a full fan-out in the selected mode and never loads this file. The
receiver-side validation contract is `selective-lane-allowlist.md`.

Iteration 1 is always a full fan-out in the selected mode. From iteration 2 onward the loop re-reviews only what the fixes could have affected. Before each fix step, preserve the exact owner lanes of every pending P1/P2/P3 finding so deleting a resolved todo cannot erase its verification obligation. The re-run lane set is the union of:

- **(a) Finding-owning lanes** -- every lane named in the `source_agents` frontmatter of a P1/P2/P3 finding repaired by the prior fix step, plus every lane owning a P1/P2/P3 finding that remains pending. The loop snapshots repaired owners before `dm-review-fix` deletes completed todos.
- **(b) File-trigger lanes** -- every lane whose file-trigger set matches any file the fixes touched since the prior review. `dm-review-fix` does not commit, so the touched-file set is the union of `git diff --name-only <prior-review-head>..HEAD` and the paths reported by `git status --porcelain`. A committed-range diff alone would report an empty change set for a perfectly normal uncommitted fix pass, and would then narrow on false evidence.

Before either rule may narrow coverage, recompute a non-empty `selected_full_set` containing only unique exact logical lane IDs. Every owner in every pending finding's `source_agents` must resolve to exactly one member of that set. Unknown owners, aliases, and criterion-level IDs shared by more than one logical lane are not narrowing signals; each fails open to full coverage with an explicit `fallback_reason`. The naming trap is deliberate: `security-auditor-codex-signoff` and `security-auditor-openrouter` are two logical lanes sharing one criterion, so bare `security-auditor` is ambiguous and fails open. An empty computed lane set is never dispatched.

The committed half of changed-file discovery is boundary-guarded. `prior_review_head` must be non-null. When `HEAD` advanced, `fix_head` must differ from `prior_review_head` and `git merge-base --is-ancestor <prior_review_head> <fix_head>` must succeed before the committed diff is trusted. A reset, rewritten history, null boundary, or advanced non-ancestor boundary fails open with an explicit `fallback_reason`; it must never be read as "no files changed." When `HEAD` did not advance but `git status --porcelain` reports fix paths, the committed half contributes no paths and the uncommitted half remains valid narrowing evidence. When neither half advances, selection fails open. This preserves ordinary uncommitted-only `dm-review-fix` passes while applying the ancestry guard only to the committed half.

**Which trigger source applies depends on the mode**, because the two modes run different rosters:

- **quick mode** (the default): the eligible roster is `pattern-recognition-specialist`, `code-simplicity-reviewer`, and only the applicable existing UI/build/domain verification lanes from the quick-mode contract. Security-sensitive changes escalate to full mode.
- **full mode**: the trigger sets are the Phase 3 conditional-agents table in `plugins/dm-review/skills/review/SKILL.md`, plus the quick-mode UI trigger above.

Full-mode lanes follow the same affected-lane rule. A selective full-mode input
may omit `security-auditor-codex-signoff` only when the loop records an earlier
complete full review and the touched-file set does not match the bounded
security escalation set. It passes those facts as
`verification_basis: "affected_lane_repair"`,
`prior_full_review_complete: true`, and
`security_boundary_changed: false`; the receiver validates them. If the prior
full review was incomplete or a repair changes a security-sensitive boundary,
repeat the full fan-out so independent-family full-diff security sign-off, the
authorized external security lens, `second-perspective`, and all applicable
conditionals are complete on the new tested SHA.

When both (a) and (b) come back empty there is nothing the fixes could have affected, so selection fails open to a full fan-out with `fallback_reason: empty selection` rather than running a near-empty pass that would have to be promoted to full anyway.

The restriction is passed as the internal loop-to-review input `review_lane_allowlist`, carrying both `selected_full_set` (the loop's recomputed full lane set) and `lanes` (the narrowed subset). It is not a public flag. Review Phase 3 recomputes its own selected full set and consumes the input only when that set exactly equals `selected_full_set` and `lanes` is a unique subset of exact logical lane IDs. Otherwise the receiver discards the input, runs the original unfiltered review, and returns the exact fallback reason in its authoritative coverage receipt. An absent or invalid input always means the original unfiltered review, never an empty or partially inferred lane set.

**Current state of the receiving interface -- read this before claiming a saving.** Review Phase 3 now receives `review_lane_allowlist` under the validation contract above. The loop still never assumes that a restriction was honored: after every pass it consumes the authoritative coverage receipt and derives attempted and skipped lanes from that evidence. If the receiver reports the input absent, invalid, or not applied, the loop sets `selective_rerun` to false and persists the receiver's exact fallback reason. Input-byte savings may be claimed only from a receipt proving the narrowed input was applied.

#### Selective Re-run Receipt

Skipped lanes get no kernel `record-attempt` call, because nothing ran. That is exactly why every iteration report must name them: without the skip list, a `lanes: m/n` coverage delta in `run-cost-summary.json` is indistinguishable from a lane that silently failed. These fields are additions beside per-lane recording, not replacements for it.

Receipts are **per pass, not per iteration**. If an incomplete prior full review or a security-boundary repair requires a new full fan-out, report that pass separately so the affected-lane verification history remains recoverable.

The ordinary pass artifact is `.workflow-kernel/runs/<run-id>/dm-review-loop/iterations/<iteration>/iteration-receipt.json`. The last-iteration verification atomically emits `max-iterations-verification-receipt.json` beside it with artifact reason `max_iterations_affected_lane_verification`. Emit each artifact only AFTER its nested coverage receipt validates, then append it to `authoritative-receipts.json` BEFORE the corresponding `observe-review` invocation.

Each pass report carries:

- `selective_rerun: true` on a pass whose coverage receipt proves a narrowed lane set was applied; `selective_rerun: false` on iteration 1, on any full fan-out, on any fail-open fallback, and whenever a passed selective input was absent, invalid, or not applied. The value describes the pass that emitted it, never a sibling pass.
- `promoted_to_full` and `full_fanout_override` are explicit booleans on every pass, including `false`; they are never omitted as present-when-true fields.
- `promoted_to_full: true` only when an incomplete prior full review or a security-boundary repair requires another full fan-out.
- `lanes_rerun` -- the exact logical lane IDs from the coverage receipt's ATTEMPTED rows, not the loop's intended set. A receiver that silently drops an intended lane therefore cannot falsely report it as re-run.
- `lanes_skipped` -- for a proven selective pass only, `coverage_selected_set` minus the applied allowlist: the lanes deliberately omitted by narrowing. Each skipped lane records `no_rule_a_or_b_match` and receives no kernel `record-attempt` call. Every non-selective full fan-out reports an empty skip set. A lane selected or allowlisted but missing from ATTEMPTED because dispatch never began is neither re-run nor skipped; the nested review reports `REVIEW INCOMPLETE`.
- `rerun_reasons` -- a per-lane map using only `a_prior_unresolved_finding`, `b_fix_file_trigger`, `initial_full_fanout`, and `selection_fail_open`. The stable `a_prior_unresolved_finding` receipt value covers a prior P1/P2/P3 finding owner whether the finding was repaired or remains unresolved. A lane selected by more than one rule records every applicable reason. Full fan-outs use `initial_full_fanout`; fail-open full fan-outs use `selection_fail_open`.
- `selection_fallback_reason: <reason>` whenever selection failed open to a full fan-out or the receiver rejected or ignored selective input, and `full_fanout_override: true` whenever `DM_REVIEW_LOOP_FULL_FANOUT=1` disabled selection. `selection_fallback_reason` is the persisted receipt field for the loop-local `fallback_reason`. The local variable resets at the start of every iteration so a fail-open on one iteration never leaks into the next iteration's receipt.

Example (affected-lane verification):

```
Iteration 2, pass 1: selective_rerun: true
Lanes re-run:
- code-simplicity-reviewer -- a_prior_unresolved_finding
- a11y-css-reviewer -- b_fix_file_trigger
Lanes skipped (no_rule_a_or_b_match):
- architecture-reviewer, second-perspective, doc-sync-reviewer, pattern-recognition-specialist, security-auditor-openrouter
```
