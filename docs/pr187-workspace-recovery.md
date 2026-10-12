# PR 187: workspace recovery and release handoff

PR 187 removes the approval-record and PR-URL prerequisite from ordinary review
assembly. Kernel 0.30.0 allows a finite assembly workspace of 4,096 files /
128 MiB and separately retains at most 2,048 required files / 128 MiB.
Diagnostics remain 416 files / 9 MiB. Every run, repository, source, ownership,
literal, receipt and reference-integrity check remains required.

## Candidate evidence

The task-owned evidence directory on NED is:

```text
/home/ned/.local/state/design-machines/depot/pr187-continuation-20261012
```

The original Governance run remains untouched:

```text
/home/ned/.local/state/design-machines/depot/runs/pipeline-gov-documents-b-20261011-794fe816-exec-cua1w93o
```

The real failed input is
`review/independent-batch-source-assignment-adc2674c/security-auditor-current-input.json`.
Its run ID remains `gov-documents-b-20261011-794fe816-exec`; repository remains
`github.com/Design-Machines-Studio/assembly-governance`; review head remains
`adc2674c4a6ba484f5c477040d467b57d00782c0`.

The final candidate recovery root is:

```text
/home/ned/.local/state/design-machines/depot/pr187-continuation-20261012/pipeline-gov-documents-b-20261011-794fe816-exec-77xuvz34
```

Source is isolated at `pr187-continuation-20261012/governance-source`. Original
inputs were copied byte-for-byte into a new exact-owned run using supported
`owned-run-start` and `owned-run-create`. Source identity was verified through
an isolated Git checkout. No maintained checkout, producer install, dm027,
shared data or installed cache was changed.

The complete first Governance closure measured 1,754 required files /
89,773,652 bytes with no missing evidence. It failed the original final
1,024-file allowance despite fitting 128 MiB. That distinct measurement is the
basis for the finite 2,048-file retention repair. Assembly success alone was
insufficient. Replaying the original failed input added one authentic committed
record. The final measured and strictly preserved closure is 1,755 files /
89,780,566 bytes. Repeated preservation adds no files and preserves identical
bytes. The measurement and preservation receipts are in the task evidence
directory.

All sixteen original controls remain selected. New linked records correct
older extraction selections' missing receipt-envelope fields and inconsistent
selective/pending flags. Run/source/dispatch/output bindings come from authentic
records; reconstruction timestamps describe the current recovery, not original
execution. The original stream and malformed/partial seals remain intact.
Twenty-six historical findings have linked verification/repair resolutions.
Two optional P3 progress suggestions remain raw and are explicitly discarded
using the retained independent adjudication.

Browser/build execution stays at `06a6d99c2e016070adddcd3302f8b0b5eeb8f1aa`.
A new caller-owned browser carry receipt binds the target review to those nine
actual cases after checking complete mode/blob identities: only four task
checkpoint Markdown files changed. Its linked artifact retains the execution
head, target head, original case/journal/artifact hashes and actual diff.
Neither journals nor old execution receipts are restamped. The existing host
command variant uses the authentic `independent-batch-final-source-direct.json`
receipt and excludes those four later checkpoint files. No passing model
review, Docker suite or browser case was rerun.

Live Wires' original final package is replayed separately with its original run
ID and `ddc9c90e28c338065eb0e04f07ac25a54a5da918` source. Its 1,055-file workspace
assembles through the ordinary CLI. Its historical owner report is unchanged;
a new linked report uses contained relative references to the same original
four evidence files. The actual projection and strict preservation receipts
are retained separately from Governance: 1,721 required files / 46,266,789 bytes,
plus one diagnostic file / 2,423 bytes. Strict preservation retains 1,722 files /
46,269,212 bytes; repetition adds no files and preserves identical bytes.
Before/after hashes match all 7,336 original Governance files and all 1,821
original Live Wires files. No product approval or publication is inferred from
these storage checks.

## Exact release and installation preflight

This continuation does **not** merge, tag, publish or synchronize installations.
A separately authorized release must first confirm the reviewed PR head and
merged main tree, refresh active version ownership, and use a clean isolated
release checkout. Do not switch or clean the dirty primary checkout.

The only affected release tags are:

```text
workflow-kernel-v0.30.0
dm-review-v1.89.1
pipeline-v1.74.2
```

Kernel keeps the version reserved by this owned PR. dm-review and Pipeline
bump only for their closeout contract/dependency-floor updates. Both require
Kernel >=0.30.0. Generated Codex surfaces come from canonical Claude manifests;
no cache patch supplies the capability.

In the verified, clean release checkout, before creating tags:

```sh
./tools/generate-codex-manifests.py --check
./tools/generate-codex-command-skills.py --check
./tools/check-release-preflight.sh --source-only
```

Require the source/tag/remote-collision/authentication gates to pass. A source-only
receipt explicitly defers installation proof. After separate merge/publication
authorization and exact merged-tree verification:

```sh
git tag -a workflow-kernel-v0.30.0 -m 'Workflow Kernel 0.30.0'
git tag -a dm-review-v1.89.1 -m 'dm-review 1.89.1'
git tag -a pipeline-v1.74.2 -m 'Pipeline 1.74.2'
git push origin workflow-kernel-v0.30.0 dm-review-v1.89.1 pipeline-v1.74.2
git ls-remote origin 'refs/tags/workflow-kernel-v0.30.0*' \
  'refs/tags/dm-review-v1.89.1*' 'refs/tags/pipeline-v1.74.2*'
```

Verify annotated tag objects and peeled commits against the approved release
commit. Existing tags must never be overwritten.

Use official host operations for synchronization:

```sh
claude plugin marketplace update depot
claude plugin update workflow-kernel@depot
claude plugin update dm-review@depot
claude plugin update pipeline@depot
codex plugin marketplace list
codex plugin marketplace upgrade depot
codex plugin add workflow-kernel@depot
codex plugin add dm-review@depot
codex plugin add pipeline@depot
```

Codex marketplace upgrade may need an interactive terminal. Confirm the actual
marketplace root from `marketplace list`; do not assume an installation path.
If a native refresh fails, follow the repository's
[official synchronization instructions](../.claude/skills/plugin-cache-sync/SKILL.md).
Never copy candidate files into installed caches. Verify both host manifests
and bytes against the released plugin trees, then run:

```sh
./tools/check-release-preflight.sh
```

Every installation coverage gap or SKIP remains explicit. The release has not
proven Governance's installed path until the commands below run successfully
against the actually selected installed bundle.

## Complete installed Governance continuation

Keep the original run unchanged. Use the tested recovery context below, whose
registered retention directory is `preserved` and whose source remains isolated.
The task owns this recovery; the original run and maintained source are foreign.

Resolve the launcher from the exact manifest-validated dependency bundle selected
by the host, following the shared
[runtime-resolution contract](../plugins/workflow-kernel/skills/workflow-kernel/references/runtime-resolution.md).
Confirm Kernel >=0.30.0 and both official installations. Set `WORKFLOW_KERNEL`
to that installed bundle's `skills/workflow-kernel/references/workflow-kernel-launcher.sh`,
never to the candidate checkout or an arbitrary globbed cache executable.

```sh
EVIDENCE_BASE=/home/ned/.local/state/design-machines/depot/pr187-continuation-20261012
RECOVERY_ROOT="$EVIDENCE_BASE/pipeline-gov-documents-b-20261011-794fe816-exec-77xuvz34"
REVIEW_ROOT="$EVIDENCE_BASE/governance-source"
REQUEST="$RECOVERY_ROOT/review/independent-batch-source-assignment-adc2674c-request.json"
RECEIPTS="$RECOVERY_ROOT/review/workspace-recovery-v6/receipts-with-browser-carry.json"

# Replay the real original rejection without changing its historical identities.
"$WORKFLOW_KERNEL" assemble-review-evidence \
  --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
  --request "$REQUEST" --receipts "$RECEIPTS" \
  --input "$RECOVERY_ROOT/review/independent-batch-source-assignment-adc2674c/security-auditor-current-input.json"

# Reuse the completed linked metadata and settled literal judgments.
"$WORKFLOW_KERNEL" assemble-review-evidence \
  --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
  --request "$REQUEST" --receipts "$RECEIPTS" \
  --input "$RECOVERY_ROOT/review/workspace-recovery-v6/coverage-accounted-input.json"

# Measure the complete closure, including the actual final report's links.
"$WORKFLOW_KERNEL" project-review-evidence \
  --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
  --request "$REQUEST" --receipts "$RECEIPTS" \
  --lane-receipts "$RECOVERY_ROOT/review/review-lane-receipts.json" \
  --raw-lane-outputs "$RECOVERY_ROOT/review/raw-lane-outputs.json" \
  --raw-findings "$RECOVERY_ROOT/review/raw-finding-inventory.json" \
  --decisions "$RECOVERY_ROOT/review/synthesis-decisions.json" \
  --private-router-directory "$RECOVERY_ROOT/router" \
  --report "$RECOVERY_ROOT/review/workspace-recovery-v6/report.md"

"$WORKFLOW_KERNEL" preserve-review-evidence \
  --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
  --request "$REQUEST" --receipts "$RECEIPTS" \
  --lane-receipts "$RECOVERY_ROOT/review/review-lane-receipts.json" \
  --raw-lane-outputs "$RECOVERY_ROOT/review/raw-lane-outputs.json" \
  --raw-findings "$RECOVERY_ROOT/review/raw-finding-inventory.json" \
  --decisions "$RECOVERY_ROOT/review/synthesis-decisions.json" \
  --private-router-directory "$RECOVERY_ROOT/router" \
  --report "$RECOVERY_ROOT/review/workspace-recovery-v6/report.md"
```

Require complete assembly, projection with no missing inputs and within limits,
and strict preservation returning `status: complete`. Repeat preservation and
compare retained hashes to prove idempotence. Compare original hashes again.
Record the installed manifest/runtime identity and exact returned closure.
These are the installed-consumer proof steps, not a request to rerun settled work.

Only after installed proof is retained and the owner no longer needs the task's
raw inputs may it finish this **recovery copy**:

```sh
"$WORKFLOW_KERNEL" owned-run-finish --run-root "$RECOVERY_ROOT" \
  --outcome succeeded --retain-diagnostics \
  --reason 'Installed Governance evidence recovery verified' \
  --contains 'Source-bound review closure and authentic linked recovery evidence'
```

This revalidates retained evidence before deleting task-owned sources. It does
not finish or remove the original Governance root. A later original-owner
closeout must retain the new linked recovery result through its existing
workflow, reconcile current source/producer acceptance, and use the supported
PR publisher if all remaining gates pass. This task creates, readies and merges
no Governance PR. Keep #184 and unrelated issues unchanged.

## Retained state and removal conditions

Retain `pipeline-gov-documents-b-20261011-794fe816-exec-rku8dhoe`, the incomplete
exploratory recovery context, until installed proof verifies the final context
and its original-input hash inventory. It contains authentic failed/interrupted
assembly and correction history; it grants no terminal coverage. Remove it only
when the owner has confirmed that its unique investigation evidence is copied
into the durable handoff and the final installed proof is retained. Never prune
its records merely to fit a package.

Retain the final Governance context, Live Wires recovery context, isolated source
copies and the PR's existing owned worktree until the installed checks above
complete and their unique evidence is retained. The candidate worktree must
remain available until the separate reviewed release is complete. Remove only
these task-owned resources at that point; no cleanup condition covers the dirty
primary checkout, original consumer runs, maintained sources, dm027 or shared data.
