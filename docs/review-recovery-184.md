# Depot #184: consumer recovery and release handoff

This repair adds truthful host verification and deterministic retained-evidence
recovery in Workflow Kernel **0.29.0**. dm-review **1.89.0** requires that version
and tells new runs to use the supported host literal. Model Router is unchanged;
Kernel owns this deterministic derivation, not dispatch or model selection.
Refs [#184](https://github.com/Design-Machines-Studio/depot/issues/184).

## Evidence boundaries

The original run remains byte-for-byte intact:

```text
/home/ned/.local/state/design-machines/depot/runs/pipeline-capacity-1135-20261007-a-9u1cjg4x
```

Its entry inventory contains **79 files / 205,988 bytes**. The task's independent
hash inventory and primary-checkout baseline are at
`/home/ned/ai/depot-worktrees/host-review-recovery-184-evidence/`.

Historical source identities remain request `264acc490a2b0727e94e82274a215a3b7c4c391a`,
full review `0ddf3b2828e6cedd502c83e6d55d75868867c34a`, and pattern recheck
`7eabdc66c399859937a08c1e5f31ebb72813a07f`. Their commit trees/diffs are
reconstructed now. Their original source assignments and working-tree
observations remain unknown. Later clean delivery never supplies those facts.
Three authentic dispatch/output pairs yield deterministic anonymous companions;
old lane-name/`not_reported` rows stay unchanged and diagnostic.

The retained host import uses the actual `go-focused` command from the original
`connection-cleanup-plan.json` / `connection-cleanup-result.json` at
`fcb541c2642f61caae8d036e61732a88ccece4e8`. It covers only the four byte-equal Go
workload files at consumer head
`fbc5728c1c69e9e60022cf4bf15116714231c48a`. The race log is supplemental.
It supplies no code judgment, current application verification, standalone
build/vet result, reproduction-script execution or capacity claim.

The only fresh consumer judgment is bounded source confirmation by
`pattern-recognition-specialist` and `code-simplicity-reviewer` over the exact
14-file scope in `review/confirmation-scope.json`. It reuses prior findings,
discarded simplicity decisions and repairs. New live outputs are distinct from
the historical ones; fresh repair resolutions name the original inventories.
This is source confirmation, not a repeated workload review.

Measurement9 stays frozen beta.3: 1,000 stored members, 50 sessions and short
warm traffic. It is not current-main or sustained-capacity proof. The separate
`activity()` observer limitation remains unresolved. No Baseplate source,
preview, shared data or Docker service changes are part of this repair.

## Candidate replay

The task-owned replay is retained for installed consumer verification:

```sh
RECOVERY_ROOT=/home/ned/.local/state/design-machines/depot/runs/dm-review-host-recovery-184-canary-20261012b-83yl1t_4
REVIEW_ROOT=/home/ned/ai/depot-worktrees/host-review-recovery-184-consumer
CONSUMER_HEAD=fbc5728c1c69e9e60022cf4bf15116714231c48a
```

Original files are copied under `history/original/`. Reconstructed/derived
records live in `review/evidence/`; original requests/receipts are not rebound.
All run inputs and outputs remain private on NED. No private model identities
belong in GitHub or peer prompts.

The first task replay, `dm-review-host-recovery-184-canary-20261012-pufdkhgz`,
is retained only for its timestamp-correction audit and original fresh
confirmation locations. Its placeholder recovery/coverage times were wrong;
it is superseded by the correctly timed `20261012b` replay. Original historical
bytes and actual fresh outputs were not rewritten. No extra model call was
made for this correction. Its `TIMESTAMP-CORRECTION.md` gives the removal
condition; do not use the superseded replay as recovery proof.

The disposable consumer checkout may be removed after complete candidate
preservation. Recreate it for installation verification with exactly:

```sh
rtk proxy git -C /home/ned/assembly/assembly-baseplate-2 worktree add \
  --detach "$REVIEW_ROOT" "$CONSUMER_HEAD"
rtk proxy git -C "$REVIEW_ROOT" rev-parse HEAD
rtk proxy git -C "$REVIEW_ROOT" status --short
```

If it already exists, inspect its head/status instead of recreating it. A dirty
or different checkout is a blocker; never reset it or use a serving checkout.

## Release and official installation (not performed by this task)

Leave the repair PR open and unmerged for owner approval. After it is merged,
use a clean task-owned Depot main checkout and verify the actual merged source.
Do not release or sync from the dirty primary checkout.

```sh
rtk proxy git fetch origin main --tags
rtk proxy git checkout main
rtk proxy git pull --ff-only origin main
rtk proxy ./tools/validate-workflow-kernel.py
rtk proxy ./tools/validate-composition.sh --all
rtk proxy ./tools/check-release-preflight.sh --source-only
RELEASE_HEAD=$(rtk proxy git rev-parse HEAD)
rtk proxy git tag workflow-kernel-v0.29.0 "$RELEASE_HEAD"
rtk proxy git tag dm-review-v1.89.0 "$RELEASE_HEAD"
rtk proxy git push origin refs/tags/workflow-kernel-v0.29.0 refs/tags/dm-review-v1.89.0
```

Stop on a failed preflight, existing/conflicting tag or changed source. Do not
retag. The source-only preflight explicitly defers installed proof.

Official Claude Code CLI refresh/install commands, verified against local help:

```sh
rtk proxy claude plugin marketplace update depot
rtk proxy claude plugin update workflow-kernel@depot
rtk proxy claude plugin update dm-review@depot
```

Restart Claude Code afterward. Desktop/Cowork has a separate installation;
refresh its marketplace and plugins through its own plugin settings and restart.
CLI cache verification cannot establish Desktop/Cowork installation.

Codex refresh is documented in
[OpenAI's marketplace guidance](https://developers.openai.com/plugins/build/plugins).
The local CLI's `plugin add --help` confirms installation syntax:

```sh
rtk proxy codex plugin marketplace list
rtk proxy codex plugin marketplace upgrade depot
rtk proxy codex plugin add workflow-kernel@depot --json
rtk proxy codex plugin add dm-review@depot --json
```

Start a fresh Codex/T3 session so its skills/dependencies are reloaded. Do not
copy source files into either installed cache. Verify each exact manifest:

```sh
rtk proxy jq -e '.name=="workflow-kernel" and .version=="0.29.0"' \
  /home/ned/.claude/plugins/cache/depot/workflow-kernel/0.29.0/.claude-plugin/plugin.json
rtk proxy jq -e '.name=="dm-review" and .version=="1.89.0" and .pluginDependencies["workflow-kernel"]==">=0.29.0"' \
  /home/ned/.claude/plugins/cache/depot/dm-review/1.89.0/.claude-plugin/plugin.json
rtk proxy jq -e '.name=="workflow-kernel" and .version=="0.29.0"' \
  /home/ned/.codex/plugins/cache/depot/workflow-kernel/0.29.0/.codex-plugin/plugin.json
rtk proxy jq -e '.name=="dm-review" and .version=="1.89.0"' \
  /home/ned/.codex/plugins/cache/depot/dm-review/1.89.0/.codex-plugin/plugin.json
rtk proxy ./tools/check-release-preflight.sh
```

Generated Codex metadata need not repeat dependency fields. Verify its canonical
dependency from the same installed package. A missing manifest or skipped
preflight cache gate is an explicit installation gap.

## Installed consumer continuation

Use the exact installed dependency launcher, not the candidate checkout:

```sh
WORKFLOW_KERNEL=/home/ned/.codex/plugins/cache/depot/workflow-kernel/0.29.0/skills/workflow-kernel/references/workflow-kernel-launcher.sh
rtk proxy "$WORKFLOW_KERNEL" recover-review-evidence --help
rtk proxy "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin dm-review \
  --minimum-version 1.89.0 --active-host codex \
  --required-asset skills/review/references/host-verification-evidence.md
rtk proxy "$WORKFLOW_KERNEL" recover-review-evidence \
  --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
  --input "$RECOVERY_ROOT/review/reconstruct-input.json"
for stem in final-pattern-recognition-specialist final-code-simplicity-reviewer final-pattern-recheck; do
  rtk proxy "$WORKFLOW_KERNEL" recover-review-evidence \
    --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
    --input "$RECOVERY_ROOT/review/recover-$stem.json"
done
for input in host/lane confirm-pattern-recognition-specialist-lane confirm-code-simplicity-reviewer-lane coverage-input; do
  rtk proxy "$WORKFLOW_KERNEL" assemble-review-evidence \
    --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
    --request "$RECOVERY_ROOT/review/request.json" \
    --receipts "$RECOVERY_ROOT/review/authoritative-receipts.json" \
    --input "$RECOVERY_ROOT/review/$input.json"
done
for operation in project-review-evidence preserve-review-evidence; do
  rtk proxy "$WORKFLOW_KERNEL" "$operation" \
    --run-root "$RECOVERY_ROOT" --repository-root "$REVIEW_ROOT" \
    --request "$RECOVERY_ROOT/review/request.json" \
    --receipts "$RECOVERY_ROOT/review/authoritative-receipts.json" \
    --lane-receipts "$RECOVERY_ROOT/review/review-lane-receipts.json" \
    --raw-lane-outputs "$RECOVERY_ROOT/review/raw-lane-outputs.json" \
    --raw-findings "$RECOVERY_ROOT/review/raw-finding-inventory.json" \
    --decisions "$RECOVERY_ROOT/review/synthesis-decisions.json" \
    --private-router-directory "$RECOVERY_ROOT/receipts/private/router" \
    --report "$RECOVERY_ROOT/review/report.md"
done
rtk proxy python3 /home/ned/ai/depot-worktrees/host-review-recovery-184-evidence/inventory.py
```

Retain every command's actual status/output. Require all three lanes and strict
`status: complete` preservation at `fbc5728c`; projection alone is not proof.
The original 79 hashes must still match. Identical retry uses committed evidence
without model dispatch, builds, traffic or CI. Changed consumer source requires
the existing affected-recheck/unaffected-transition proof, not relabelling.

Only after installed recovery succeeds may the owning consumer settle its
review blocker and report installation proof. Keep Depot #184 open until that
released installation and consumer recovery are verified. No Baseplate merge,
release or deployment is authorized here. Keep originals indefinitely; retain
this replay until installed verification and consumer handoff are complete.
Never terminal-clean an incomplete authoritative recovery. Project 1: None.
