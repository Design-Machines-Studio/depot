# Review Closeout Contract

Load for terminal cleanup of any full or quick review, standalone, loop, or
Pipeline-owned. The exact-run-root creator owns closeout: `dm-review` for a
standalone run, `dm-review-loop` for a root it started, and Pipeline for a
Pipeline-supplied root. Nested reviews and affected-lane rechecks return
evidence; they never finish the shared root or render its terminal report.

## Preserve Before Cleanup

Before deleting review output or a worktree containing evidence, settle
required coverage through the producer. Bind each request before inspection;
final requests name the target HEAD while lane records keep their original
source. Never rebind old output to a repaired HEAD. Keep the durable finding,
coverage, and result inputs. Call the trusted Kernel command:

Write required_browser_cases as an explicit list in the final coverage
receipt. Use an empty list when the bound request has no browser cases;
omission or null is not an empty, settled browser scope.

```text
"$WORKFLOW_KERNEL" preserve-review-evidence \
  --run-root <exact-run-root> \
  --repository-root <reviewed-repository> \
  --request <exact-run-root>/review/request.json \
  --receipts <exact-run-root>/review/authoritative-receipts.json \
  --lane-receipts <exact-run-root>/review/review-lane-receipts.json \
  --raw-lane-outputs <exact-run-root>/review/raw-lane-outputs.json \
  --raw-findings <exact-run-root>/review/raw-finding-inventory.json \
  --decisions <exact-run-root>/review/synthesis-decisions.json \
  --private-router-directory <exact-run-root>/receipts/private/router \
  --report <unified-review-report>
```

The report contains verdict, findings, and an evidence index. Local links must
resolve in the retained scope; use `review/<artifact>` or `browser/<artifact>`
and returned `evidence_path`. Only `status: complete` supports `CLEAN` or source
worktree removal. The copy contains the request, authoritative coverage,
selected outputs and literal receipts, synthesis artifacts, report, real
private router receipts, and required evidence references. Kernel bounds it to
128 files and 2 MiB outside product repositories.

Missing required lanes, browser cases, source, HEAD, or report links keep the
verdict `REVIEW INCOMPLETE`; narrative and passing CI cannot fill a gap. Search
only this exact run and retained scope for attributable evidence. If it cannot
be recovered, rerun only the genuinely missing required lanes/cases at the
same repository, HEAD, and scope. Never rerun settled lanes to rebuild
closeout. Changed source or scope requires the producer's supported recheck or non-impact chain; unsupported reuse is rejected.

If preservation or validation fails, leave the original evidence and its
worktree intact and report the exact run-root path. Do not finish the root.
After a verified copy exists, cleanup of owned processes, containers, and
registered worktrees follows their resource-specific contracts. If required
finalization then fails, retain one bounded exact-owned recovery directory and
retry from it; existing contribution receipts and settled lane outputs are
reused without duplication or redispatch. Keep resource cleanup separate from
evidence destruction.

An incomplete retained copy also fixes the authoritative receipt bytes. A
retry may append a valid closeout receipt, but changing an existing review or
coverage receipt is rejected and reported as an incomplete recovery; correct
the caller input in a new owned replay rather than rewriting the first copy.

Keep the original producer checkout, owner/state and receipts through publication.
After transfer, publish there with `--feature-branch` from the approved task or
manifest `featureBranch`; the canonical serving folder cannot adopt its state.
After owned-resource cleanup settles, update `<evidence_path>/report.md` with
the actual cleanup inventory and revalidate all local links. Write the final report to `.claude/ux-review/report.md` while its checkout remains available.
Check every used checkout after its last producer/write and before removal.
After final writes and cleanup, only explicitly selected Assembly development
checkouts run read-only `canonical-checkout.sh finish` with exact
`--delivered-head`, surviving checkouts and removed owned residue paths; no
disposable owner state is required. Other repositories compare every used
checkout against its entry baseline and verify absence of run-owned residue.
Pending cleanup means Not ready with safe paths and one agent action;
`Workspace: clean` requires the applicable final source/residue checks.
Finish once, after fresh exact-scope Docker inventory proves zero run-owned
objects:

```text
"$WORKFLOW_KERNEL" owned-run-finish --outcome succeeded --retain-diagnostics
```

The Kernel revalidates preserved evidence. On incomplete coverage, use
`--outcome failed --retain-diagnostics` and report its exact recovery path,
reason, contents, and cleanup command. If copying failed, retain the original
root instead. An abort before execution uses `review-aborted`. `SIGINT` and
`SIGTERM` use the same closeout. Never delete a feature branch under review,
retain foreign worktrees, or auto-delete `.workflow-kernel/repository-scope.json`.

Use `repo-cleanup-contract.md` for exact registered worktrees/branches,
host-created worktree release, browser artifacts, and the final repository
inventory. Compare status with the entry baseline and keep foreign refs with
their follow-up commands. For review-created Docker resources, load
`review-docker-cleanup.md`; clean only registered resources after authoritative
browser evidence and fresh dependent-node proofs. Preserve maintained previews.
Do not let evidence retention skip process/container cleanup.

## Report and Optional Observations

Keep the unified report provisional until authoritative repository and Docker
cleanup results are known. Preserve both the final report and its machine
companions before terminal delivery. The compact handoff links the established
`.claude/ux-review/report.md` and retained `report.md`, names blocked cleanup,
and contains no expanded report or private provider data.

Keep `review-next-action.sh` internal. Use it against the base/final-head diff, policy, required
cases, coverage, retained findings, and settled PR feedback. Follow its exact
Review, Action, Why, and Reuse lines; invoke `operator-recommendation.sh` only
when it reports `modelWork: true`. Append the existing terminal model report
only for its declared owner. Deliver `operator-handoff.sh` readiness to the
designer after validating final-head facts; never ask for backend inspection
or another dm-review command. A standalone owner preserves the already-rendered
model report and accepted observation index; a nested owner returns its private
index without rendering. Preserve bounded PR intake and decision artifacts.

One owner renders the terminal model report from its private index. A nested
review returns evidence to its owner without a second terminal render. Model
report failure records the contract's closed unavailable line and does not
change coverage or cleanup.

Contribution economics, cost summaries, shadow comparison, and observation
indexes are optional observations. Their absence or export failure produces a
concise unavailable diagnostic only; it cannot downgrade otherwise supported
required coverage. Missing lane output, literal lane receipt, required browser
evidence, or invalid source binding remains `REVIEW INCOMPLETE`. Report one
mechanical verdict in the complete report. The designer's readiness status
also accounts for current PR CI/feedback and UI acceptance; CLEAN alone does
not authorize publication, readiness or merge.

## Candidate publication gate

Supported owners use `publish-reviewed-pr.sh` before creating a PR or marking
a draft ready. The host resolves and exports its exact trusted
`WORKFLOW_KERNEL` launcher once using `runtime-resolution.md`. Invoke:

```text
publish-reviewed-pr.sh --operation create|ready \
  --repository-root <original-producer-checkout> --run-root <exact-current-owned-root> \
  --producer-input <absolute-producer-arguments.json> \
  --readiness-input <absolute-owner-readiness.json> \
  [--feature-branch <approved-short-branch>] [--pr <URL-for-ready-only>]
```

The producer JSON map contains exactly `request`, `receipts`,
`lane-receipts`, `raw-lane-outputs`, `raw-findings`, `decisions`,
`private-router-directory` and `report`. Values are absolute paths for the
preserve command. Except `report`, inputs stay in the current owned root;
`report` may use the reviewed checkout. Quoted argv invokes the real producer;
complete coverage, settled decisions and clean HEAD remain mandatory before gh.
Detached HEAD requires explicit `--feature-branch`. Its exact local branch ref
and remote SHA must match reviewed HEAD; an attached branch must match too.
Recheck before mutation. Missing, unsafe or moved branches block. No state or
source-proof relocation, caller coverage flags or new Kernel API is accepted.

Helpers use fixed PATH, Bash 3.2 arrays, GNU/BSD stat and SHA256/shasum.
Source tests alone may set
`DM_REVIEW_DEVELOPMENT_TEST_ROOT` to a private, canonical disposable
`publish-reviewed-pr-test.*` directory. It must contain the exact
`repository` checkout with real `Fixture/consumer` identity and the run under
`runs/`; only explicit `bin/git` and `bin/gh` mocks are used. Only Depot source
with its fixture runner accepts mocks; installed/live consumers cannot. The real Kernel rejects synthetic/incomplete coverage. Assembly transfer
and detached Fixture publication are separate composed fixtures, with unchanged
identities; neither proves live review or installed enforcement.

The readiness file contains `approvedBase`, `owner`, `readiness`, `uiNonImpact`, plus `feedback` for ready.
Copy `approvedBase` from the approved task/plan branch, including manifest
`baseBranch` for Full/Lean. The wrapper resolves existing local or origin branch
names to the GitHub base; missing, ambiguous, tag/SHA or foreign-remote input
blocks. Never infer approval from GitHub's default or rewrite original
source-bound base/head. Create passes explicit `--base`; ready rejects a
different actual PR base before mutation.
`owner` has exactly canonical `repository` (`owner/repository`), `workflow`
(`pipeline|dm-review|dm-review-loop`), `run_id`, `run_root`, `state_dir` (the
checkout's `.workflow-kernel/runs/<run_id>`). Exact-owned metadata must match.
`readiness` is the formatter object described in `output-format.md`. Producer
coverage, HEAD and dirty state replace caller projections. The owner supplies
current candidate checks, retained findings, PR feedback settlement and actual
designer acceptance. These judgments do not substitute for required code cases.

`create` requires complete candidate source/browser/test coverage and actual
candidate-stage source/build/verification results; PR-only rows cannot replace
them. Missing results give Not ready and one agent action, never a PR.
Pending PR-only CI and PR feedback settle after draft creation. `ready` validates
caller shape, refreshes actual PR metadata/checks/feedback before the final merge
gate, and retains strict candidate/source/owner checks and designer acceptance.
Cached failed/pending PR projections cannot block that refresh; actual missing,
failed, pending or unsettled facts block mutation. More than 100 threads is an explicit
feedback coverage gap; settle through the owner's supported feedback intake
before retrying. Both operations recheck clean local/remote candidate HEAD
immediately before mutation. Neither merges or approves planning/UI for the
owner. Opening a draft does not finish the current review root.

`feedback` is the closed `{intake, decisions}` map of absolute current-run
files from `external-finding-intake.sh` and `external-finding-settlement.sh`.
Ready requires matching repository/PR/head, complete source artifacts and all
source judgments. The helper recollects once and compares all source content,
identity and metadata, excluding collection timestamps and the body filename.
Only identical sources permit cutoff-only decision revalidation; changed/new
sources remain blocked for host evaluation under the same owner. Production
ignores intake test overrides; only the validated disposable source fixture
uses the existing collector seam. Thread and aggregate decision checks remain.

`uiNonImpact` is normally null. To carry actual designer acceptance across an
unaffected source change, supply `fromHead`, `toHead`, the complete UI/dependency
`paths` selected by the owner, and a contained `evidence` file with the owner's
source-bound non-impact judgment (exact `fromHead`, `toHead`, `paths`, and
nonempty `reason`). The wrapper verifies matching proof fields, ancestry and actual
unchanged bytes/modes for those paths. A Boolean claim alone is rejected.
The owner must include every relevant UI dependency; the helper does not infer
UI semantics from extensions. Any changed behavior requires fresh acceptance.

`awaiting_ui` is nonterminal: provisional handoff retains the same owner,
checkout, root/state and unfinished evidence/private index. Requested repairs
resume executing/checking; acceptance and actual ready precede terminal
model/cost generation and destructive cleanup. Complete preservation still
gates publication and destroying review resources; owner alone merges.

## Session owner pointer

`review-owner-context.sh` extends the existing
`$TMPDIR/claude-hook-state` convention with one private
`review-<sha256>/review-owner.json`. The key hashes canonical repository,
canonical checkout/worktree and native `session_id`. This pointer is not a
registry, review receipt or coverage marker. It stores exactly `session_id`,
`repository`, `workflow`, `run_id`, `run_root`, `state_dir`, `phase` and
`change_boundary`.

Every mode reads native SessionStart/Stop JSON on stdin. Pass the canonical
`--repository-root`; never parse transcripts, invent a session ID or select a
newest run. `init` requires SessionStart, creates an unbound planning marker
and returns the exact context reference as SessionStart `additionalContext`.
Matching resume preserves it. Private account ownership, single-link regular
files, contained non-symlink paths, native session/repository and actual
exact-owned metadata are checked before using a bound marker.

Only the root owner binds after plan/prompt approval, using `bind --context
<exact-reference> --workflow <workflow> --run-id <id> --run-root <root>
--state-dir <state> --change-boundary <digest>`. A worker's native agent fields
are rejected; workers never bind the parent session. The host must deliver the
root's native input to root operations, not let workers impersonate it. There
is no independent authentication rail in this same-account pointer helper.

The sourceable `review_change_boundary <checkout>` function returns SHA256 of
HEAD, actual binary working diff and untracked paths/content/modes. Pass that
digest at each actual boundary with `phase --context <reference> --phase
<phase> --change-boundary <digest>`. Phases are `planning`,
`awaiting_plan_approval`, `executing`, `checking`, `awaiting_ui`,
`awaiting_merge`, `blocked`, `complete`. Approval advances via bind to
executing; checking may return to executing, wait on UI/merge, block or finish.
UI waits may return to checking/executing or advance to merge; merge waits may
return to checking or complete; blocked may resume executing/checking. Phase
is lifecycle context only and never settles checks or designer acceptance.

Only a completed prior owner can be rebound. At closeout the root calls
`clear --context <reference> --run-id <id> --run-root <root>` with its native
input, after marking complete. A completed marker can be cleared after exact
cleanup removes its disposable root. Active, missing, foreign or conflicting
markers cannot be adopted. When no SessionStart reference exists, report
`hook activation unavailable`; continue the mandatory workflow code gate.
This chunk supplies the helper and source fixtures. Hook installation, native
host activation and Stop continuation are separate integration work.


## Source-bound repair and retry

Before preservation, invoke `assemble-review-evidence` operation `coverage`
with explicit committed record selection. Rechecks append new attempts linked
to predecessors and applied selection/repair evidence. Reuse retains original
records plus every intervening actual changed-path/source/non-impact proof.
Equal HEAD with changed dirty bytes and ancestry alone both fail coverage.
Keep earlier findings and synthesis; clean rechecks need explicit resolutions.
Use Kernel's `review-evidence-contract.md` closed producer schema.

The stream identifies the committed snapshot; missing derived companions can
be reconstructed without redispatch. Conflicting retained companions require
a new owned replay carrying the original stream/history. Preservation locks
that snapshot and retains all referenced records and bindings within existing
bounds. Missing/unsafe inputs produce closed stage/reason diagnostics; lexical
containment and symlinks are checked before absence. Preserve safe available
inputs and all originals on failure. Nested reviews return evidence; only the
existing creator finishes the root.
