# Review directory recovery

Playwright removed and recreated Kernel-registered output directories in the
retained livewires-templ issue #12 run. All nine mismatched paths retain results
whose project `outputDir` names the registered parent. The consumer's
`examples/gallery/playwright.config.mjs` selects `GALLERY_EVIDENCE` directly;
the original shell wrapper is missing. This establishes the effective output
configuration, but does not prove every historical command or exclude another
replacement cause. Consumer source remains unchanged.

Kernel 0.30.0 failed before coverage validation because `_diagnostic` raised a
plain ValueError on the changed directory. The generic public exception digest
hid the cause; the reviewed-PR publisher correctly exited 3 before GitHub
mutation. Kernel 0.30.2 returns `owned_directory_changed` with a recovery action.

The authoritative retained inputs for reviewed head
`63898f3846642a5f1275ece6c393a4a5a248512e` are explicitly located by
`review/pre-pr-producer-input-final.json`: `terminal-request.json`,
`authoritative-receipts-before-iteration.json`, the four Kernel-produced
companions, `private-router-publication`, and `pre-pr-report-final.md`.
The early `pre-pr-report.md` describes older incomplete source and remains intact.

## Supported repair

Read the [recovery contract](../plugins/workflow-kernel/skills/workflow-kernel/references/review-evidence-contract.md#changed-preservation-directory-0302).
Use its `preservation-destination` envelope with the existing diagnostic
registration and the final source-bound request. Retry projection and strict
preservation with those exact final producer inputs. Recovery appends a fresh
registration under the existing owner, retains every old registration, and
never trusts a replacement based on its pathname. Review coverage and sealed
source digests still have to validate. Cleanup of the containing run remains
blocked while any still-present registration has changed identity.

Use `owned-run-browser-output` to select the `playwright` child of a stable
registered raw-output parent. Feed that child to the actual harness's output
configuration and reporter. Retain separate attempt parents when previous output
is required evidence. The shared dm-review browser-target contract is the single
configuration handoff; no consumer source or installed cache change is included.

## Candidate proof and limits

An isolated canary copies the retained run and verifies all 1,274 copied files
against original bytes before and after the operation. It creates genuine
Pipeline ownership through `owned-run-start`, with the same logical run ID,
then reproduces the observed replacements through real directory operations.
The original metadata is retained separately as historical evidence; it is never
edited into active ownership metadata. A separate clone supplies the exact
reviewed Git tree. No original run, consumer branch, preview or installed cache
is modified.

The canary reproduces the directory failure, retries recovery to the same active
destination, and preserves 48 required files / 1,457,535 bytes with complete
source-bound coverage. Existing sealed digests validate the required package.
Copy hashes for other historical artifacts prove copy fidelity only; absent
historical digests and the missing shell wrapper remain unverified. This is
candidate proof, not tagged or installed consumer proof, and does not claim the
consumer is CLEAN. Real IME, screen-reader testing, owner UI acceptance,
final-head CI and post-PR feedback remain separate work; issue #12 stays open.

## Release and installation handoff — prepared only

After authorized PR merge, validate the merged tree and run
`./tools/check-release-preflight.sh --source-only`. Prepare annotated tags
`workflow-kernel-v0.30.2`, `dm-review-v1.89.3` and `pipeline-v1.74.4` at that
verified merge; publish only with separate authorization. Pipeline and dm-review
require Kernel >=0.30.2; Pipeline requires dm-review >=1.89.3.

Follow [the normal installation procedure](../README.md) for Claude and Codex:
refresh the Depot marketplace, update these plugins through each native host,
and restart the host to load new skills. Verify coherent manifests, versions and
installed bytes against the tagged merge, then run the normal release preflight.
Only afterward can the consumer owner use the installed recovery procedure on
the original run and record actual installed-consumer proof. This task performs
none of those merge, tag, publication or installation steps.
