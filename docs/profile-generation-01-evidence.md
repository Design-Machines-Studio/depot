# PROFILE-GENERATION-01 evidence

Draft PR #175 provides `generate-verification-profile` in Kernel 0.27.0 and Pipeline 1.73.1 integration with Kernel >=0.27.0. Generation prepares and reloads an authoritative plan; it proves no browser execution. Baseplate remains paused. Kernel 0.27.0 now supplies a closed native host-event provenance variant so original committed-source outputs can be recovered through the supported assembler.

## SIMPLICITY-CHECK

One CLI handler delegates discovery to ProjectPersonaAdapter. Explicit task selection runs before expansion; exact case selection retains declared primitives and required flags. Existing parsers, identities, origin digests, serialization, safe publication, reload and immutable binding are reused. There is no second discovery implementation, new profile schema, browser service, runbook parser or application sweep. Pipeline now compares all required acceptance dimensions, including mobile, before dispatch.

Native recovery adds one bounded host-event validator to the existing assembler. Routed receipts, source snapshots, inspection, history, contribution accounting and retention keep their existing owners and rules.

## Integration and versions

Recorded order remains **#172 → #174 → #173 → #175**. Refreshed reviewed heads:

| PR | Exact source | Preserved behavior |
| --- | --- | --- |
| [172](https://github.com/Design-Machines-Studio/depot/pull/172) | ff171bae66a51ad20acbaa40d89d0183cf4d05fb | Pinned historical retained-review compatibility; new reviews remain strict |
| [174](https://github.com/Design-Machines-Studio/depot/pull/174) | 6c87b5eaf010e9d3b52c409dd68c627eb36aa8a9 | Final whole-package 9 MiB / 416-file bounds; source references reused without seal rewriting |
| [173](https://github.com/Design-Machines-Studio/depot/pull/173) | 2f27d0fa143453952da623e774daa3e2b1ea16a1 | Final readiness/publication and maintained-checkout repairs; exact reviewed dependency ancestors |

Those PRs merged in order on 2026-10-09. Main is 424f42ff30614ac98a2ec765bc4a06e40918d936. A normal merge into #175 preserves their commits, late historical-digest race protection and readiness repairs. Kernel 0.26.2/Pipeline 1.73.0 are already released; this branch's generation command still requires its later unpublished versions. #175 retains later Kernel 0.27.0/Pipeline 1.73.1; Pipeline also preserves dm-review>=1.87.0. dm-review's Kernel>=0.26.2 floor and all other owner versions remain intact. Generated manifests/aliases and dependency graph are regenerated from canonical sources. No owner branch, primary checkout or consumer work was rewritten.

## Exact preservation diagnosis

The failed attempt supplied the entire working `router/` directory. All 18 actual indexed receipt JSON files are valid, but `_copy_router_tree` accepts only JSON files. Actual traversal first rejects **router/plan-prompt.md** with `private router receipt directory has an unexpected file`; the wrapper reports `preservation_input/invalid_evidence`. The other rejected files are plan-evidence.txt, plan-output.md, builder-prompt.md, builder-completion-prompt.md, builder-completion-evidence.txt and builder-final-prompt.md. Originals are preserved. An exact receipt-only copy containing 18 receipts and the original index passes the directory requirement.

The supported helper now preserves the complete initial review at its actual source, 676b40b5: 83 files and 1,764,469 bytes. An identical retry leaves every retained hash unchanged. Literal native outputs and actual host traces are byte-verified as separate supplemental diagnostics. This successful interim retention does not approve the newer source.

That correction alone cannot establish final coverage. The last committed request and aggregate bind **676b40b5**, while the accepted documentation recheck and six settled native collaboration outputs inspected **53298592**. The final integrated commit needs a new source-bound aggregate and validated transitions. An edited request or old seal cannot approve it.

All six native literal outputs and their hashes remain unchanged. Actual private Codex host JSONL traces were recovered for the three agents, recording parent/agent thread identities, actual model/effort, timestamps, task assignments, tool executions and returned results. Their derived index is explicitly host-trace evidence; it is not a router receipt. Each agent covered two affected lanes with shared context. Native usage/cost is not inferred from routing metadata.

**Native provenance repair:** the former production contract required an actual router dispatch plus companion. Kernel 0.27.0 supplies the closed `literal={output_ref,native_trace_ref,native_index_ref}` variant in the same assembler. It validates structural T3 subagent session/parent/turn identity, assignment header, unambiguous committed Git HEAD and clean-status observations, exact successful AddFile/FileChange bytes, nonempty paired call IDs, final answer and task completion. The required bound index checks excerpt digest, thread and original ordinal/line mapping. The host separately byte-verifies and privately preserves the complete actual trace: Kernel does not authenticate T3 origin or its declared full-trace digest. Encrypted assignments remain opaque; commands and patches are never executed. Unknown identity/cost stays unavailable. Existing router validation, source/inspection/history rules, contribution accounting and retention remain strict. No new command, review framework or schema redesign was added.

Exact selected original JSONL lines form bounded inert excerpts; their line numbers and complete original trace digests are retained. Full private traces and literal outputs stay unchanged. The first prototype admitted six native rechecks at **53298592** and preserved 126 files / 2,219,185 bytes with an immutable retry. Independent review then found P2 gaps in command matching, clean-status evidence, call IDs and index binding. That prototype result is superseded candidate evidence, not final proof. Five original outputs have recoverable clean-source witnesses; the voice follow-up lacks a same-turn clean-status observation and stays diagnostic. The required affected current-source voice inspection resolves its initial finding history without relabeling the old output. Recovery invokes no model and does not validate earlier consumer dispatch.

The historical integration inspections recorded staged trees 62615245/c8f85fe1, not later commit f4dc2f36. They remain supplemental evidence and are never relabeled. New intake/merged-source changes receive only the required affected reviews at a clean committed boundary before final source-bound assembly, strict preservation and its immutable repeat. Final current-head receipts are linked from the PR; candidate proof remains separate from installed proof.

The first new pattern report at d6bbbde6 used a computed, relative AddFile patch.
Its literal output and actual host trace are retained, but this narrower native
contract cannot decode that call as the required exact exec patch witness. It
stays supplemental; the already required affected recheck uses a literal absolute
patch and verifies its reported repairs. No host event or receipt is synthesized.

## Complete Baseplate declaration-tree diagnosis

Consumer exact source: [f508cd6c890473246c43c3d9b6d7f59c1c62903b](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/1152). Full-tree supported generation exits 2 and writes no profile. The exact blocker is [tests/ux/tasks/baseplate/fixtures/bp-fix-002-autosave.md:26](https://github.com/Design-Machines-Studio/assembly-baseplate/blob/f508cd6c890473246c43c3d9b6d7f59c1c62903b/tests/ux/tasks/baseplate/fixtures/bp-fix-002-autosave.md#L26):

```yaml
tags: [fixtures, autosave, keyboard, accessibility, csrf, no-js, responsive]
heuristics: [N1, N4, N5, G1]
```

Lines 26–27 use inline arrays for ordinary task list fields. The existing limited declaration contract requires indented lists; `_validate_frontmatter_lines` rejects nonempty inline values for these keys. Tags is the first rejection; changing only one field in a disposable copy exposes the other. Discovery validates all authoritative tasks before focused selection, so this unrelated task blocks the seven-task union. This declaration syntax defect belongs to Baseplate; Depot must not weaken parsing to accept it. File SHA256: 9297154e2a92682a6fcaaea494a86e9cd55abf7054c1b76a96277add29bc405a.

Supported CLI isolation found this one failure among 149 additional frontmatter tasks. A disposable complete-tree counterfactual that changes both fields to the supported list form yields 30 candidate cases. It is diagnostic evidence, not a consumer implementation or normal exact-source passing canary.

## Acceptance coverage and corrected canary claim

The earlier reduced-copy canary generated 30 candidates and selected eight Firefox desktop cases. It proved supported generation/reload/binding mechanics on a bounded fixture only. Its driver ignored the source planning artifact's **1440x900 and 375x812** selection. It omitted all eight approved mobile cases and three approved desktop cases, while adding three persona-default desktop cases. The prior description of that matrix as invented was incorrect: the artifact and retained contract specify wide/narrow obligations. That eight-case output is **not normal consumer proof and does not satisfy approved acceptance**.

Required focused coverage remains:

| Task | Persona | Route | Required Firefox viewports |
| --- | --- | --- | --- |
| bp-dev-001 | power-secretary | /dev/markdown-editor | 1440x900; 375x812 |
| bp-dev-001 | casual-member | /dev/markdown-editor | 1440x900; 375x812 |
| bp-memb-004 | engaged-chair | /admin/members/new | 1440x900; 375x812 |
| bp-adm-004 | engaged-chair | /admin/members | 1440x900; 375x812 |
| bp-adm-007 | super-admin | /super/fixtures | 1440x900; 375x812 |
| bp-acct-002 | casual-member | /account/edit | 1440x900; 375x812 |
| bp-adm-001 | engaged-chair | /admin/settings | 1440x900; 375x812 |
| bp-adm-018 | super-admin | /super/design | 1440x900; 375x812 |

Firefox is the approved primary engine; Chromium remains alternate recovery. Editor 200% zoom, narrow keyboard interaction and design-token 375px assertions remain behavioral obligations. Viewport generation proves none of these passed.

Current `tests/ux/verification.json` declares route bindings but no viewport override. Persona desktop defaults win under existing precedence; screenshot instructions and Markdown browser matrices are not parsed as declarations. Baseplate's owner must reconcile the approved viewport set through the existing configuration mechanism. It was handed off through exchange b29cc4ad4dbb4fa39921c883b9a9242d; no consumer file was changed.

A second disposable counterfactual applies only the two list fixes and explicit existing `verification.json.viewports=[1440x900,375x812]`. Full discovery yields 60 candidates; the approved eight pairs × Firefox × two viewports yields 16 cases with the **same sixteen case IDs** as the diagnostic plan. The generated profile nevertheless differs in viewport provenance and coverage-matrix diagnostics, so profile ID and full-document digest differ. Counterfactual profile ID: profile-sha256:bea7f595e1689a1450504ff4623c1deaf998a2c7a39bdebae1136240ced96454; full digest: sha256:7d35b9de9454a2aaed299b285a5e0a2031b41fdbe654af308f363ef1f3a72289. This is hypothetical fixture proof, never normal consumer proof. No binding or browser tests were attempted for it.

## Supported invocation and binding recovery

After publication/install and valid consumer declarations, generate the complete task union through the supported launcher:

```sh
"$WORKFLOW_KERNEL" generate-verification-profile \
  --project-root . --output plans/<new-plan>/verification-profile-candidate.json \
  --target-origin "$VERIFIED_TARGET_ORIGIN" \
  --task-id bp-dev-001 --task-id bp-memb-004 \
  --task-id bp-adm-004 --task-id bp-adm-007 \
  --task-id bp-acct-002 --task-id bp-adm-001 --task-id bp-adm-018
```

Reload the output and compare declared task/persona/engine/viewport cases with every approved acceptance obligation. Missing mobile/browser coverage blocks dispatch. For the approved focused set, pass all sixteen exact candidate IDs through repeated `--case-id` in a second invocation with a fresh output path. Never select eight desktop cases as a substitute.

Preserve the diagnostic run/profile/immutable binding. Only an identical complete binding permits supported idempotent retry. Changed profile provenance or full digest requires a newly planned run, even when all sixteen case IDs match. Initialize that run, generate/reload its approved profile, build the contract with exact profile identity/digest and required case arrays, then bind with `--verification-profile`. Never rewrite an old binding or retroactively validate earlier dispatch.

## NOT-COVERED

- Historical staged-tree native inspections remain supplemental. Original committed-source recovery cannot approve the new intake implementation; affected current-source reviews and complete strict preservation are separately required.
- No normal exact-source full-tree passing consumer canary, consumer declaration repair, new consumer binding, browser execution, application repair, review restart, serving-checkout change or shared-data change occurred.
- Native macOS, publication/tags, Claude/Codex synchronization and installed-consumer proof remain separate. Original evidence and consumer Issue/PR state are unchanged. Project 1 update: None.

## COMMANDS-RUN

- Refreshed origin/main and exact 172/174/173 PR files/heads; verified ancestor order; normal Git integration and canonical/generated version/dependency reconciliation.
- Focused CLI/discovery/binding and retention/historical tests; `tools/validate-workflow-kernel.py`; full `tools/validate-composition.sh --all`; generated manifest/alias/index/dependency and `git diff --check` validation.
- Read-only exact 532 validator reproduction; all 18 actual receipt validation, seven rejected extra files, byte-identical 19-file receipt-only copy; initial/final request-scope failures; six unchanged literal-output hashes; actual native host-trace preservation.
- Supported generation on disposable exact-source declarations; isolated inline-list failures; explicitly patched hypothetical full-tree probes; complete approved 16-case/identity/provenance comparison. Every diagnostic scratch scope was removed after preserving results. No private installed-module workaround.

## Remaining delivery and consumer steps

1. Judge source readiness only from complete current-head review, supported assembly/preservation and immutable-repeat receipts linked from #175. Older recovery proof grants no current-head approval. Preserve original evidence and settled lanes; resolve affected findings before marking this draft ready.
2. The owner merges #175 after the already merged #172 → #174 → #173 dependencies. Run release preflight on combined main; publish required workflow-kernel-v0.27.0 and pipeline-v1.73.1 tags under the repository release procedure. These versions are reserved source, not published releases.
3. Refresh Claude marketplace and update workflow-kernel@depot/pipeline@depot. Refresh/restart independent Desktop Cowork caches where used. Use supported Codex marketplace upgrade and plugin-add paths; confirm coherent required versions in each harness. Never edit installed caches.
4. Baseplate owner fixes the two declared list fields and reconciles viewport authority with approved 16-case acceptance. After required plugins are published and installed, run the normal installed full-tree generation/reload path, prepare a new plan/run, and bind its complete approved contract. Only then may its owner resume authorized consumer work. Baseplate remains paused until all these conditions hold.
