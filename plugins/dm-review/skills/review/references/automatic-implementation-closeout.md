# Automatic implementation closeout

Supported direct implementation tasks and Pipeline continue through review and
repair before their implementation session finishes. Implementation authorization
includes this closeout; no second operator prompt or human-started thread is
required. This contract authorizes reviewed PR creation, but no merge, tag, release
publication, cache update, or global hook. Arbitrary GitHub PR creation outside
an active supported task has no event trigger and remains uncovered.

## Select review before entering

Automatic closeout is not a mandatory full model roster. Pipeline selects the
smallest sufficient workflow; ordinary bounded changes use quick review,
consequential/security boundaries and explicit full requests retain full.
A direct settled low-impact change may omit model review only when actual
repository policy permits it. Existing publication producer requirements remain
binding: do not invent an exemption or claim passing coverage without its
required evidence. Tests, UI/prototype checks, all retained findings and source
preservation remain required. A changed sensitive boundary escalates before
review, regardless of whether a quick reviewer finds a defect.

## Enter once, preserve the owner

After plan/prompt approval, implement, commit and push the candidate branch,
and verify its remote head against the local candidate. Perform applicable independent review,
repair, recheck and preserve candidate source/browser evidence before opening
a PR. An existing draft stays draft. PR-only CI is pending until a PR exists;
it cannot be claimed passed from candidate checks. Record the repository/branch
and PR when present, base/head, entry dirty-state boundary, approved requirements,
verification evidence, and current review owner in the existing workflow
receipts. Apply `repo-cleanup-contract.md` for selected Assembly inactive source; preserve
active work, ignored evidence, refs and maintained previews.

Use the existing workflow state, run lease, exact-owned root and review-source
binding. Resume an attributable existing owner instead of creating another
owner for the same repository/PR/head. A live conflicting owner blocks only
the conflicting dispatch; continue independent authorized work. Never adopt an
unattributed run or infer ownership from a latest-file search. The repair push
is a transition inside this owner, never a new implementation trigger.

Pipeline's existing final review/repair/affected-recheck sequence owns closeout;
workers return evidence, never start another loop or publish. Full `/pipeline`
defers create/ready to its parent after mandatory caller verification;
standalone `/pipeline-run` publishes after corresponding checks.
Pre-PR feedback is `not_applicable`, never settled. Collect/settle post-PR
authenticated feedback independently. Unchanged covered HEAD plus zero findings
waits for CI/feedback without review dispatch. Only actual source coverage,
new supported finding or rendered automation gaps invoke `review-next-action.sh`.
Bind flags to inspected source, validated producer coverage and supported findings;
use actual base/head/dirty boundary:

<!-- review-gap-direct:start -->
```bash
if [ "$SOURCE_COVERAGE_GAP" = true ] || [ "$SUPPORTED_RETAINED_FINDING" = true ] || [ "$RENDERED_AUTOMATION_GAP" = true ]; then
  "$DM_REVIEW_BUNDLE_ROOT/skills/review/references/review-next-action.sh" "$REVIEW_ACTION_INPUT"
else
  printf '%s\n' 'Review coverage unchanged; settle CI and feedback without reviewer dispatch.'
fi
```
<!-- review-gap-direct:end -->

Execute a needed action within the current logical owner. A new review uses
one `dm-review-loop`; quick/full commands already
delegate to that loop before lane dispatch. Existing passing coverage at an
unchanged head means no duplicate model work. A rendered-only gap uses the
existing visual path; a repository-permitted settled low-impact exemption still runs
mandatory repository checks and reports the exemption accurately.

`awaiting_ui` is nonterminal: provisional handoff retains the same owner,
checkout, root/state and unfinished evidence/private index. Requested repairs
resume executing/checking; acceptance and actual ready precede terminal
model/cost generation and destructive cleanup. Complete preservation still
gates publication and destroying review resources; owner alone merges.

## Native session pointer (root owner only)

When checking native hook activation, load `review-hook-activation.md`.
Run final workspace checks before marking the owner complete/clearing its pointer.

Load `review-owner-context.sh` from the same coherent dm-review bundle as the
publication helper. The thin SessionStart handler initializes an unbound
planning marker and supplies its exact path as `additionalContext`; a matching
resume preserves it. The existing private per-session hook-state convention
stores one `review-owner.json`, keyed by SHA256 of the canonical repository,
physical worktree identity and native `session_id`. Store exactly `session_id`,
`repository`, `workflow`, `run_id`, `run_root`, `state_dir`, `phase`, and
`change_boundary`. This is a session pointer, not a discovery registry or
review receipt. Native SessionStart/Stop inputs are the only hook authority.

The root owner retains the host-supplied native input and exact SessionStart
context ref, and binds only after plan/prompt approval with the actual logical
owner's workflow, run ID, exact-owned run root, state directory and canonical
repository. `REVIEW_CHANGE_BOUNDARY` is the helper's `review_change_boundary`
for the actual checkout, never a caller guess. With that native input on stdin:

```bash
"$DM_REVIEW_BUNDLE_ROOT/skills/review/references/review-owner-context.sh" bind \
  --repository-root "$REVIEW_ROOT" --context "$REVIEW_OWNER_CONTEXT" \
  --workflow "$REVIEW_WORKFLOW" --run-id "$REVIEW_RUN_ID" \
  --run-root "$REVIEW_RUN_ROOT" --state-dir "$REVIEW_STATE_DIR" \
  --change-boundary "$REVIEW_CHANGE_BOUNDARY" < "$REVIEW_NATIVE_HOOK_INPUT"
```

Use `phase` at actual boundaries: `awaiting_plan_approval` before the plan gate,
`executing` after binding or resuming repairs, `checking` for verification,
`awaiting_ui` for required designer browser acceptance, `awaiting_merge` for
owner merge, `blocked` for an actual blocker, and `complete` at terminal
closeout. Pass the exact ref and fresh change boundary on each bound update:

```bash
"$DM_REVIEW_BUNDLE_ROOT/skills/review/references/review-owner-context.sh" phase \
  --repository-root "$REVIEW_ROOT" --context "$REVIEW_OWNER_CONTEXT" \
  --phase "$REVIEW_PHASE" --change-boundary "$REVIEW_CHANGE_BOUNDARY" \
  < "$REVIEW_NATIVE_HOOK_INPUT"
```

Only the root owner clears its own completed binding before exact-owned cleanup:

```bash
"$DM_REVIEW_BUNDLE_ROOT/skills/review/references/review-owner-context.sh" clear \
  --repository-root "$REVIEW_ROOT" --context "$REVIEW_OWNER_CONTEXT" \
  --run-id "$REVIEW_RUN_ID" --run-root "$REVIEW_RUN_ROOT" \
  < "$REVIEW_NATIVE_HOOK_INPUT"
```

Rebind only a completed prior owner. Workers receive the exact SessionStart
context ref solely as read-only context and never bind/update/clear the parent
session. The helper validates private ownership, single-link containment,
matching native session/repository and actual exact-owned metadata. Missing,
foreign or conflicting context cannot be adopted. Never parse transcripts,
search newest runs, invent a session ID, rewrite evidence or add a Kernel API.
When native hooks are disabled/unavailable or no exact SessionStart context
exists, report `hook activation unavailable`, omit binding honestly and still
run the mandatory pre-PR producer gate below.

## Publish only the reviewed candidate

Resolve a coherent dm-review bundle containing `publish-reviewed-pr.sh`,
`review-owner-context.sh` and `operator-handoff.sh`. Retain the trusted
`WORKFLOW_KERNEL` launcher. `REVIEW_ROOT` is the physical reviewed checkout;
`REVIEW_RUN_ROOT` is the current owner's exact-owned root.
`REVIEW_PRODUCER_INPUT` is the closed map of absolute existing producer file
arguments: `request`, `receipts`, `lane-receipts`, `raw-lane-outputs`,
`raw-findings`, `decisions`, `private-router-directory`, `report`.
`REVIEW_READINESS_INPUT` contains `approvedBase`, `owner`, `readiness`, `uiNonImpact`, plus `feedback` for ready;
copy `approvedBase` from the approved task/plan (`baseBranch` for Full/Lean),
never GitHub's default. The publication helper resolves local/origin branch
names, passes explicit `--base` and rejects a different actual PR base.
Keep original source-bound review base/head unchanged.
`owner` contains canonical `repository`, `workflow`, `run_id`, `run_root`,
`state_dir`. Read `operator-handoff.sh` for its closed readiness shape; use
actual candidate-stage source/build/verification checks; PR-only rows do not
prove candidate verification. Leave PR checks pending and `feedbackSettled=false`
until the PR exists. UI acceptance is an explicit owner fact, bound to the
final head or supported bounded UI non-impact proof. No missing source packet
can be called inspected; the existing producer is the only coverage authority.

`feedback` is the closed `{intake, decisions}` map of absolute current-run
files from `external-finding-intake.sh` and `external-finding-settlement.sh`.
Ready requires matching repository/PR/head, complete source artifacts and all
source judgments. The helper recollects once and compares all source content,
identity and metadata, excluding collection timestamps and the body filename.
Only identical sources permit cutoff-only decision revalidation; changed/new
sources remain blocked for host evaluation under the same owner. Production
ignores intake test overrides; only the validated disposable source fixture
uses the existing collector seam. Thread and aggregate decision checks remain.

Publish after independent review, repair, recheck and preservation; Full requires
parent verification. Bind `FEATURE_BRANCH` from the approved direct task's
`featureBranch` (Full: manifest; Lean: approved plan). Retain that authoritative
binding and `$REVIEW_ROOT` after transfer; never rediscover from detached HEAD.
Never bypass with bare `gh`:

<!-- reviewed-pr-direct:start -->
```bash
"$DM_REVIEW_BUNDLE_ROOT/skills/review/references/publish-reviewed-pr.sh" \
  --operation create --repository-root "$REVIEW_ROOT" --run-root "$REVIEW_RUN_ROOT" \
  --feature-branch "${FEATURE_BRANCH:?approved featureBranch required}" \
  --producer-input "$REVIEW_PRODUCER_INPUT" --readiness-input "$REVIEW_READINESS_INPUT"
```
<!-- reviewed-pr-direct:end -->

Start PR checks after source validation:

<!-- reviewed-pr-direct-request:start -->
```bash
"$DM_REVIEW_BUNDLE_ROOT/skills/review/references/publish-reviewed-pr.sh" \
  --operation request-review --repository-root "$REVIEW_ROOT" --run-root "$REVIEW_RUN_ROOT" \
  --feature-branch "${FEATURE_BRANCH:?approved featureBranch required}" \
  --producer-input "$REVIEW_PRODUCER_INPUT" --readiness-input "$REVIEW_READINESS_INPUT" \
  --pr "$REVIEW_PR_URL"
```
<!-- reviewed-pr-direct-request:end -->

Wait for actual CI, approvals, feedback and UI acceptance before readiness:

<!-- reviewed-pr-direct-ready:start -->
```bash
"$DM_REVIEW_BUNDLE_ROOT/skills/review/references/publish-reviewed-pr.sh" \
  --operation ready --repository-root "$REVIEW_ROOT" --run-root "$REVIEW_RUN_ROOT" \
  --feature-branch "${FEATURE_BRANCH:?approved featureBranch required}" \
  --producer-input "$REVIEW_PRODUCER_INPUT" --readiness-input "$REVIEW_READINESS_INPUT" \
  --pr "$REVIEW_PR_URL"
```
<!-- reviewed-pr-direct-ready:end -->

Register the returned PR with the host when supported. Collect actual PR CI/
feedback; fix supported defects, push and recheck affected source/browser under
this owner. Keep merge readiness blocked while CI, feedback or designer acceptance remains;
unchanged UI acceptance needs bounded non-impact proof. Deliver dm-review's
`operator-handoff.sh`: tested behavior, checks, preview tasks/acceptance and owner
merge. Never ask for backend-code review or create-PR approval. Preserve
planning/material-scope approvals. Missing/false legacy controls grant no merge.

## Invoke the supported protocol

Use the current harness's skill entry point. Claude's Skill tool invokes the
command skill; Codex resolves and reads `dm-review:dm-review-loop` (or its
generated command alias), then executes that exact protocol with the review
skill and references. A missing slash-command UI is not plugin unavailability.
Resolve a coherent compatible plugin bundle through the trusted Kernel when
needed. Missing/incompatible skill assets are a precise review blocker; do not
replace them with informal review or launch the entire workflow in another
harness. Candidate source execution must be labeled separately from installed
consumer proof.

Select modes and conditional lanes through existing review policy, retaining
sensitive-path full review and required rendered interaction/persona cases.
Independent participants receive fresh sessions and sufficient bounded source,
diff, requirements and verification context. Preserve the current origin-neutral
eligibility and provenance contract: an authoring-session coordinator is allowed,
but its self-review cannot replace the selected independent lanes.

## Repair, recheck, retain

Follow `dm-review-loop` and `dm-review-fix`: consolidate supported findings,
reject unsupported findings with a concise evidence-backed reason, repair every
retained in-scope P1/P2/P3, commit and push the batch, and verify the remote head.
Run affected repository checks and lanes on the repaired head. Reuse unaffected
evidence only under `selective-lane-allowlist.md` and existing source validity
rules; never restamp old evidence. Repeat broad review only for incomplete prior
coverage or a changed sensitive boundary. Preserve the existing bounded retry,
stalled-convergence and explicit iteration-cap rules.

Applicable UI/UX judgment and front-facing design repair drafting request
`design-consultant` under model-router's `design-consultation.md`. The host
integrates its bounded patch/decision and verifies functionality, security,
accessibility and prototype parity. A required unavailable design participant
is a design coverage blocker; browser/tool availability is a separate cause.

For verified external dependencies, use `issue-tracking.md`: search the owning
repository for an existing Issue before creating one, link it to the affected
PR, retain the incomplete coverage, and name the exact unblock condition. Do
not create Issues for repairable findings, speculative enhancements or routine
transient limits. Never implement in another repository without authority.

After final report writes, apply `canonical-checkout.sh finish` when using a
selected Assembly development checkout; pending cleanup yields Not ready.
Before terminal delivery, validate final-head selected lane outputs, literal
receipts, required cases and authoritative coverage through
`review-closeout-contract.md`. Contribution exports retain their existing
observation-only status; they cannot replace required receipts. Preserve
evidence before cleanup, finalize once, and report `CLEAN` only when every
required gate passes. Otherwise retain recoverable work and report the exact
head, unresolved condition, Issue when applicable, evidence/recovery path and
owned resources with purpose and removal condition. Interruption uses the same
preservation and resume path; it never rewrites sealed evidence. Fixed companion
conflicts use a supported exact-owned replay under the same logical owner;
never overwrite preserved history or finish an enclosing owner from a worker.
