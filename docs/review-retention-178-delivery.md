# Issue 178 delivery and consumer retry

Candidate versions: **Workflow Kernel 0.28.0**, **dm-review 1.88.1**.
The dm-review dependency floor becomes `>=0.28.0` because its instructions use
the new projection command and separate retention policy. Other consumers keep
their supported floors. This source task does not merge, tag, publish, install,
edit caches or finish either live consumer root. Issue #178 stays open.

## Release and synchronize after owner approval

Use a clean release checkout of approved merged main; preserve the dirty primary
checkout. Confirm that the reviewed changes are in that checkout and both
canonical plugin/marketplace versions equal the versions above. Refresh both
marketplaces from that approved source. Local CLI help verified these commands;
they are future operator steps, not commands executed by this repair:

```sh
rtk git fetch origin main
rtk git worktree add --detach /home/ned/ai/depot-worktrees/release-retention-178 origin/main
cd /home/ned/ai/depot-worktrees/release-retention-178
rtk proxy ./tools/validate-composition.sh --all
rtk proxy claude plugin marketplace update depot
rtk proxy claude plugin update workflow-kernel@depot
rtk proxy claude plugin update dm-review@depot
rtk proxy codex plugin marketplace upgrade depot
rtk proxy codex plugin add workflow-kernel@depot --json
rtk proxy codex plugin add dm-review@depot --json
rtk proxy claude plugin list --json
rtk proxy codex plugin list --marketplace depot --json
rtk proxy ./tools/check-release-preflight.sh
```

The existing preflight requires installed Codex versions to match canonical
marketplace versions. Therefore synchronize the approved merged main before
tagging, then run preflight without `--no-net`; require actual cache `OK` with no
unexplained SKIP. Restart both harness sessions to load the new bundles. Compare
all shipped files in each exact manifest-selected Claude/Codex Kernel and
dm-review bundle with the merged plugin source, excluding only generated
cache-private bookkeeping. A listed version alone does not prove file equality.
Resolve each harness's trusted Kernel launcher from its selected dependency root
per `runtime-resolution.md`; require 0.28.0 and the projection CLI.

After successful preflight and file comparison, create annotated tags at that
same approved release commit. Refuse an existing conflicting tag; do not move it:

```sh
RETENTION_RELEASE_HEAD=$(rtk git rev-parse HEAD)
rtk git tag -a workflow-kernel-v0.28.0 "$RETENTION_RELEASE_HEAD" -m 'Workflow Kernel 0.28.0: separate validated review retention'
rtk git tag -a dm-review-v1.88.1 "$RETENTION_RELEASE_HEAD" -m 'dm-review 1.88.1: required retention policy and projection guidance'
rtk git push origin refs/tags/workflow-kernel-v0.28.0 refs/tags/dm-review-v1.88.1
rtk git ls-remote origin 'refs/tags/workflow-kernel-v0.28.0*' 'refs/tags/dm-review-v1.88.1*'
```

Verify both peeled tag revisions equal `RETENTION_RELEASE_HEAD`. Refresh both
marketplaces again if necessary; confirm selected bundle versions and bytes after
restart. Only then record published and installed proof. Run the installed
projection and isolated replay before touching the live consumer. Keep #178 open
until that delivery and live closeout evidence is recorded.

## Terminal-only consumer retry after installation

Refresh PR #1162's head/checks/feedback first. The recorded head is
`362b2207d9801193d179a4a8599df73c45aedfa5`. Use its clean producer checkout,
`/home/ned/assembly/assembly-baseplate-worktrees/widget-w00-1160`, whose source
inventory matches the sealed review. The serving checkout has six baseline
screenshots and cannot stand in for that clean source inventory. If source/head
has changed, preserve the existing identity and use the supported affected-recheck
or non-impact chain; do not relabel old evidence or rerun settled lanes for storage.

Set `WORKFLOW_KERNEL` to the exact trusted **installed** 0.28.0 launcher selected
by the active host. Never use a cache glob, edit a cache or choose the source
checkout runtime as installed proof. Then use the original supported recovery:

```sh
WORKFLOW_KERNEL=/home/ned/.codex/plugins/cache/depot/workflow-kernel/0.28.0/skills/workflow-kernel/references/workflow-kernel-launcher.sh
rtk proxy "$WORKFLOW_KERNEL" kernel-info --minimum-version 0.28.0
RETAINED_RUN_ROOT=/home/ned/.local/state/design-machines/depot/runs/dm-review-pr1162-20261009-resume-n1hi98w6
REVIEWED_REPOSITORY=/home/ned/assembly/assembly-baseplate-worktrees/widget-w00-1160
RETENTION_ARGS=(
  --run-root "$RETAINED_RUN_ROOT"
  --repository-root "$REVIEWED_REPOSITORY"
  --request "$RETAINED_RUN_ROOT/review/request-with-native.json"
  --receipts "$RETAINED_RUN_ROOT/review/authoritative-receipts.json"
  --lane-receipts "$RETAINED_RUN_ROOT/review/review-lane-receipts.json"
  --raw-lane-outputs "$RETAINED_RUN_ROOT/review/raw-lane-outputs.json"
  --raw-findings "$RETAINED_RUN_ROOT/review/raw-finding-inventory.json"
  --decisions "$RETAINED_RUN_ROOT/review/synthesis-decisions.json"
  --private-router-directory "$RETAINED_RUN_ROOT/receipts/private/router"
  --report "$RETAINED_RUN_ROOT/report-final.md"
)
rtk proxy "$WORKFLOW_KERNEL" project-review-evidence "${RETENTION_ARGS[@]}"
rtk proxy "$WORKFLOW_KERNEL" preserve-review-evidence "${RETENTION_ARGS[@]}"
```

The assignment above is for the manifest-selected NED Codex bundle after restart.
For Claude, use its verified selected root at
`/home/ned/.claude/plugins/cache/depot/workflow-kernel/0.28.0/` instead; keep the
same `skills/workflow-kernel/references/workflow-kernel-launcher.sh` suffix.
`kernel-info` must confirm the compatible installed runtime before the retry.

Require a complete preservation result. Update the provisional report with actual
preservation status and fresh CI/feedback, retain its evidence index, then repeat
projection/preservation for those final report bytes and links. Do not overwrite
any sealed request, history, literal output or receipt. Keep the maintained
producer branch/preview and predecessor roots. Confirm run-owned resource cleanup
from fresh inventory and then finish **only this exact root**:

```sh
rtk proxy "$WORKFLOW_KERNEL" owned-run-finish \
  --run-root "$RETAINED_RUN_ROOT" --outcome succeeded --retain-diagnostics
rtk proxy "$WORKFLOW_KERNEL" owned-run-finish \
  --run-root "$RETAINED_RUN_ROOT" --outcome succeeded --retain-diagnostics
```

The second terminal call returns the existing cleanup receipt after revalidation.
That finishes review storage only. Baseplate #1166 is a separate CI blocker;
preserved complete review evidence does not establish overall PR readiness or
authorize ready/merge. No browser checks or settled review lanes are redispatched.

Project 1: **None**. The bounded native Project 1 read found no existing relevant
item; no item was created or changed.
