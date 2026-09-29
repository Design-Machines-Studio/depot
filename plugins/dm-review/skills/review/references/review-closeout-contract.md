# Review Closeout Contract

Load for terminal cleanup of any full or quick review, standalone, loop, or
Pipeline-owned. The exact-run-root creator owns closeout: `dm-review` for a
standalone run, `dm-review-loop` for a root it started, and Pipeline for a
Pipeline-supplied root. Nested reviews and affected-lane rechecks return
evidence; they never finish the shared root or render its terminal report.

## Preserve Before Cleanup

Before deleting review output or a worktree containing evidence, settle
required lane and browser-case coverage, then bind `request.json` to the exact
repository, HEAD, selected lanes, and browser cases. Keep the durable finding,
coverage, and result inputs. Call the trusted Kernel command:

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

The report contains the verdict, findings, and evidence index. Every local
link must resolve inside the retained copy; use its returned `evidence_path`
for stable report links. Only `status: complete` supports `CLEAN` or source
worktree removal. The copy contains the request, authoritative coverage,
selected outputs and literal receipts, synthesis artifacts, report, real
private router receipts, and required evidence references. Kernel bounds it to
128 files and 2 MiB outside product repositories.

Missing required lanes, browser cases, source, HEAD, or report links keep the
verdict `REVIEW INCOMPLETE`; narrative and passing CI cannot fill a gap. Search
only this exact run and retained scope for attributable evidence. If it cannot
be recovered, rerun only the genuinely missing required lanes/cases at the
same repository, HEAD, and scope. Never rerun settled lanes to rebuild
closeout. Changed source or scope rejects reuse.

If preservation or validation fails, leave the original evidence and its
worktree intact and report the exact run-root path. Do not finish the root.
After a verified copy exists, cleanup of owned processes, containers, and
registered worktrees follows their resource-specific contracts. If required
finalization then fails, retain one bounded exact-owned recovery directory and
retry from it; existing contribution receipts and settled lane outputs are
reused without duplication or redispatch. Keep resource cleanup separate from
evidence destruction.

After owned-resource cleanup settles, update `<evidence_path>/report.md` with
the actual cleanup inventory and revalidate all local links. Write the final report to `.claude/ux-review/report.md` while its checkout remains available.
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

Use `review-next-action.sh` against the base/final-head diff, policy, required
cases, coverage, retained findings, and settled PR feedback. Follow its exact
Review, Action, Why, and Reuse lines; invoke `operator-recommendation.sh` only
when it reports `modelWork: true`. Append the existing terminal model report
only for its declared owner. A standalone owner preserves the already-rendered
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
terminal verdict only; do not pair a formal status with an informal clean
approval.
