# Baseplate #1190 evidence-size repair

Workflow Kernel 0.30.1 raises required retention and the assembly workspace from
128 MiB to **192 MiB (201,326,592 bytes)**. The consumer's audited closure is
858 files / 157,818,269 bytes. Restoring its 91 verified archive members makes
the physical assembly workspace 820 files / 147,994,776 bytes.

Assembly still permits 4,096 files; required retention permits 2,048 files.
Disposable diagnostics still permit 416 files / 9 MiB. Existing file reads,
router copying, aggregate partitions, projection and terminal validation use
the same finite required allowance. Scope, digest, path containment, ownership,
immutable history, provenance and coverage checks are unchanged.

dm-review 1.89.2 and Pipeline 1.74.3 change only their repeated contracts and
Kernel dependency floors to >=0.30.1. No other plugin is bumped. Canonical
Claude manifests generate the Codex adapter manifests; command aliases and
the search index are refreshed through their generators.

## Verification and evidence

The focused suite covers a valid package above 128 MiB through assembly,
copying, preservation and terminal validation, plus exact 192 MiB boundaries,
excess bytes, unchanged file/diagnostic limits and failed digest/path/ownership
checks. Failed sealing preserves original bytes. Existing closeout, retention,
cleanup and historical compatibility tests also run.

Private command evidence is retained on NED at:
`/home/ned/ai/depot-worktrees/evidence-size-1190-evidence/`.
`canary-results.json` distinguishes baseline and candidate assembly, projection
and preservation. `consumer-original-before.json` inventories the entire
original run; the canary verifies it again after replay. Private receipts are
copied in full and unchanged, never filtered or published.

The canary follows the existing `tests/replay_issue178.py` procedure: create
fresh real ownership through `owned-run-start` / `owned-run-create`, verify all
copied bytes, restore only digest-verified archive members into that copy, use
an isolated checkout at the authentic consumer head, then invoke normal
launcher commands. It reuses the committed coverage input and does not
redispatch consumer reviews. Original metadata is never transplanted or edited.
The detailed results are separate from size measurements; a size pass cannot
be reported as complete coverage or installed proof.

The retained Depot worktree `/home/ned/ai/depot-worktrees/evidence-size-1190`
supports owner review and release preparation. Remove it only after owner
merge and release/install handoff. Retain the canary root recorded in
`canary-root.txt` through installed verification; it contains authentic history
and a registered isolated source checkout. The original consumer run remains
owned by Baseplate and must not be cleaned by Depot.

## Release and normal installation (not executed here)

After an authorized merge, create a clean detached release worktree from freshly
fetched `origin/main`. Confirm the actual merge includes the reviewed repair
and inspect any intervening changes; stop on a conflicting tag or version.
Use that trusted checkout for all commands below. The dirty primary Depot
checkout is not a release checkout.

```sh
rtk proxy git fetch origin main --tags
rtk proxy git worktree add --detach /home/ned/ai/depot-worktrees/evidence-size-1190-release origin/main
rtk proxy git -C /home/ned/ai/depot-worktrees/evidence-size-1190-release status --short
cd /home/ned/ai/depot-worktrees/evidence-size-1190-release
rtk proxy ./tools/validate-workflow-kernel.py
rtk proxy ./tools/validate-composition.sh --all
rtk proxy ./tools/generate-codex-manifests.py --check
rtk proxy ./tools/generate-codex-command-skills.py --check
rtk proxy ./tools/check-release-preflight.sh --source-only
RELEASE_HEAD=$(rtk proxy git rev-parse HEAD)
rtk proxy git tag -a workflow-kernel-v0.30.1 "$RELEASE_HEAD" -m 'Workflow Kernel 0.30.1'
rtk proxy git tag -a dm-review-v1.89.2 "$RELEASE_HEAD" -m 'dm-review 1.89.2'
rtk proxy git tag -a pipeline-v1.74.3 "$RELEASE_HEAD" -m 'Pipeline 1.74.3'
rtk proxy git push origin refs/tags/workflow-kernel-v0.30.1 refs/tags/dm-review-v1.89.2 refs/tags/pipeline-v1.74.3
rtk proxy git ls-remote origin 'refs/tags/workflow-kernel-v0.30.1*' 'refs/tags/dm-review-v1.89.2*' 'refs/tags/pipeline-v1.74.3*'
```

Require annotated tag objects and their peeled commits to match `RELEASE_HEAD`.
Never overwrite tags. A source-only preflight defers installation proof.

```sh
rtk proxy claude plugin marketplace update depot
rtk proxy claude plugin update workflow-kernel@depot
rtk proxy claude plugin update dm-review@depot
rtk proxy claude plugin update pipeline@depot
rtk proxy codex plugin marketplace list
rtk proxy codex plugin marketplace upgrade depot
rtk proxy codex plugin add workflow-kernel@depot --json
rtk proxy codex plugin add dm-review@depot --json
rtk proxy codex plugin add pipeline@depot --json
```

Restart Claude and start a fresh Codex/T3 session. Desktop/Cowork installations
need their own normal update and restart. Do not copy source into caches.
Verify both hosts' selected manifest versions, canonical dependency floors and
complete plugin-file SHA256 inventories against the tagged source. Run the
full installed `tools/check-release-preflight.sh` and report every SKIP.

Resolve each exact installed launcher through the host's dependency bundle;
use `resolve-plugin-bundle --plugin workflow-kernel --minimum-version 0.30.1
--required-executable skills/workflow-kernel/references/workflow-kernel-launcher.sh
--active-host claude` (and `codex`) to verify selected versions and roots.
Repeat the canary with those installed launchers before touching original data.

Baseplate then owns restoration of the verified archive members and normal
`project-review-evidence` / `preserve-review-evidence` on its original run,
using `review/producer-input.json`, the canonical `review/request.json`, its
current clean source and the newly resolved installed launcher. Capture actual
receipts, require strict `status: complete`, verify every original hash/private
receipt, and finish only through the consumer's existing ownership procedure.
Projection alone never clears this dependency. Baseplate still owns dm021b,
PR creation, T3 linking, final-head CI and issue #1190; keep that issue open.

## SIMPLICITY-CHECK

Two existing constants change. No exception registry, new permission file,
service, framework, history pruning, receipt filtering or coverage bypass is
introduced. The finite bound fits the demonstrated package with about 41.5 MiB
headroom. Candidate proof does not unblock the installed consumer.

## NOT-COVERED

This task does not merge, tag, publish, install, update caches, rerun consumer
review/browser lanes, create a Baseplate PR or establish its final-head CI.
Source fixture tests do not authenticate native host delivery. There is no
rendered UI change in Depot. Installed consumer preservation remains pending.
