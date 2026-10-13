# Evidence headroom for the continuing Baseplate review

Kernel 0.30.3 raises both assembly and required-retention byte ceilings from
192 MiB to 1 GiB. File counts stay at 4,096 workspace / 2,048 required files;
diagnostics stay at 416 files / 9 MiB. dm-review 1.89.4 and Pipeline 1.74.5
update their repeated contracts and dependency floors. Generated manifests,
dependency graph and search index follow canonical sources.

The earlier 192 MiB repair fit the original 157,818,269-byte / 858-file audit,
but continued source integration and review evidence exceeded it. The board
records 204,796,090 bytes / 1,111 files before all final evidence was complete.
A practical ceiling replaces incremental cap increases; it does not waive
coverage, ownership, digest, path, immutable-history or cleanup validation.

## Validation

The focused suite passes 15 tests. It exercises a valid 257 MiB package through
assembly, copy, preservation and terminal cleanup, plus exact 1 GiB boundaries,
one byte over, failed-seal preservation, file/diagnostic limits and integrity
failures. The first direct unittest command omitted PYTHONPATH and failed before
loading; the documented runtime path invocation passed.

Read-only inspection of the current e5mkyptn consumer workspace found 1,110
files / 200,603,110 bytes. This is a physical workspace count, not the final
required closure. Candidate size-policy checks also accept the original audit
and the board's larger 1,111-file / 204,796,090-byte measurement. The original
audit hash was unchanged. No consumer run was written, copied or cleaned, and
no consumer reviews were rerun. These checks are size-policy proof only;
consumer coverage and final preservation remain to be verified after installation.

The final Kernel release validator passes all 13 checks, including its full
unit suite. Initial validation found stale version assertions and an unchanged
runtime version tuple; these were corrected and rechecked. The full composition
invocation completed with those earlier failures; final dependency and Codex
perspective rechecks pass, with a complete composition recheck recorded in the PR.

Command logs are retained under
/home/ned/.local/state/design-machines/depot/evidence-headroom-1190/.

## Publication handoff

After owner-authorized merge, verify trusted main contains the tested tree,
run tools/check-release-preflight.sh --source-only, and publish annotated tags
workflow-kernel-v0.30.3, dm-review-v1.89.4 and pipeline-v1.74.5 at that commit.
Use the normal Claude and Codex marketplace/plugin update commands documented
in .claude/skills/plugin-cache-sync/SKILL.md; do not edit cache files. Verify
selected versions and byte inventories against the tagged source, then run the
installed-cache release preflight. Source validation is not installed proof.

Reply to board exchange d2094fd74d164c9281edbfd3d175c8f0 with publication and
installation evidence. Baseplate owns the original run and PR #1200. It should
resume its existing assembly, projection and preservation sequence, report
separate coverage failures accurately, and keep #1190 open. No merge, release,
deployment or shared data change is authorized in that consumer by this repair.

## SIMPLICITY-CHECK

Two existing byte constants and their contracts change. No new override,
service, registry, schema, exception workflow or dependency is introduced.

## NOT-COVERED

Installed-consumer preservation, final-head Baseplate coverage and CI, and
merge/tag/cache synchronization are separate from this source PR. One Codex
session performed the work; token totals and billing were not exposed.

## COMMANDS-RUN

Authenticated GitHub and board reads; isolated Git worktree; manifest/index/
dependency generation; focused unittest with repository PYTHONPATH; full
composition validation; read-only consumer workspace/size-policy checks;
git diff --check. Final validation and PR head are recorded in the PR body.
