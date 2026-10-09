# Issue 178 candidate evidence

The repair gives validated required review evidence 32 MiB / 1,024 files while
keeping disposable diagnostics at 9 MiB / 416 files. The same complete-package
partition governs projection, copying, retained validation and terminal cleanup.
Only unchanged coverage, source, scope, digest, provenance, ownership and safe
path checks establish required membership. All local report links are copied.

The final isolated replay reproduced installed Kernel 0.27.0's
`preservation_input / retention_limit` failure. Candidate 0.28.0 preserved
**221 files / 9,639,003 bytes**, including final report links, then passed repeated
preservation, retained validation and repeated terminal cleanup. Read the
[machine proof](review-retention-178-proof.json). All 16 selected lane records and
five browser cases, including stored native 200% zoom proof, were validated;
none was redispatched or rerun. The original two consumer roots match their
initial whole-root SHA256 inventories. The supplied `preservation-result.json`
is empty; it remains unchanged. The new isolated baseline captured the actual
structured rejection separately.

Workflow Kernel 0.28.0 and dm-review 1.88.1 are source candidates. Their canonical
manifests, generated Codex manifests and affected dependency contracts agree.
Only dm-review requires the new Kernel floor. The generated search index was
refreshed and had no content change. Origin/main still matched the prepared
`f471605e6507aa4d634907bae918f080c46056c8` at delivery inspection.

## SIMPLICITY-CHECK

Use existing exact-owned diagnostic storage, source seals, closure selection,
copy verification and terminal ownership. No service, database, compression,
automatic pruning or migration was added. Two finite categories replace the
shared allowance. Recent complete packages measured 5.9 MB, 8.1 MB, 8.6 MB and
9.5 MB; 32 MiB gives about three times the observed byte use and 1,024 files more
than twice the largest observed count. Assembly and copying use finite workspace
ceilings; those ceilings never establish retained eligibility.

Two independent judgment lanes inspected the candidate, followed by one affected
recheck. Every retained finding was repaired:

| Finding | Repair and proof |
| --- | --- |
| P2: synthetic `outside/` keys could hide diagnostic bytes | Measure real diagnostic-relative paths; collision regression rejects oversized additions before cleanup |
| P3: router copy imposed a combined 32 MiB cap | Permit the finite combined workspace; complete-package partition accepts indexed 26 MiB plus diagnostic 8 MiB |
| P3: projection skipped unrelated `review/` entries | Count unrelated entries and preserve them under diagnostic bounds |
| P3: missing/empty report readiness was hidden | Projection names failures; invalid reports receive no required membership |
| P2: report-linked router files could fail a local count check | Remove local membership inference; 417 linked router files preserve, and unlinking restores diagnostic rejection |
| P3 in affected recheck: unrelated directories looked like scopes | Filter actual helper scope names; nested diagnostics survive preservation and repeated finish, and oversized ones fail |

The host also fixed canonical router placement on retained-source retries and
strengthened the existing retry test to check the whole retained tree stays
byte-identical without nested duplicate copies. Inventory stops before allocating
a 1,441st entry. A safety-stop measurement marks `measurement_complete: false`;
its counts describe the observed lower bound rather than a complete projection.
Supported packages receive complete exact measurements.

No retained P1/P2/P3 finding remains open. Reviewers used read-only source/probe
inspection; the host supplied real filesystem, cleanup and replay verification.

## COMMANDS-RUN

- `git fetch origin main`, source/ownership/Issue refresh, bounded board reads,
  read-only Project 1 lookup and final remote ownership check.
- Pipeline 1.74.0 `select-workflow.sh` selected lean; short plan and original
  request retained in `plans/review-retention-178/`.
- Focused retention, closeout, owned-run, historical compatibility and CLI suite:
  **139 tests passed**. An affected producer/version/validator batch also passed
  **208 tests** before the final narrow repairs.
- `tools/validate-workflow-kernel.py`: all **13 sections passed** on final source.
- `tools/validate-composition.sh --all`: **all validators passed**; full output is archived before commit. Optional Superpowers absence and Bash 3.2 absence
  remain explicit coverage gaps below.
- Both Codex generators ran and their `--check` modes passed. Dependency graph
  and search index regenerated. Affected dependency, perspective and workflow
  contract checks passed. `git diff --check` passed.
- `tests/replay_issue178.py` ran against fresh exact-owned copies with the actual
  consumer's clean producer source. Installed baseline fails; candidate succeeds;
  projection writes nothing; retained copy digests match source bytes; repeated
  preservation and finish are idempotent; original roots stay byte-identical.
- Installed model-router 0.13.0 dispatched two review-deep lanes and one bounded
  affected recheck. Private original receipts, prompts and outputs are retained
  with the command evidence. No consumer models were dispatched.
- Local Claude/Codex CLI help checked the future synchronization commands. No
  marketplace update, plugin install, release preflight, tag or publication ran.

Failed development attempts were diagnosed rather than reported as passes. The
full suite caught incomplete-copy report-error precedence, the runtime version
constant and the new CLI command inventory; these were repaired. Composition
caught exact dependency/version assertions; affected contracts were refreshed.

## NOT-COVERED

This proves candidate source behavior. It does not prove publication, cache
synchronization or installed consumer closeout. Both live consumer roots and the
dirty primary Depot checkout remain intact. Only disposable isolated replay roots
were finished. The current Baseplate PR remains draft at the recorded head;
separate CI issue #1166 still prevents overall readiness.

Independent reviewer sandboxes lacked writable temporary directories, so they
could not execute filesystem tests. Host tests and the actual isolated replay
cover those operations. No rendered UI exists in this repair; there was no
browser campaign. The composition suite reports Bash 3.2 runtime unavailable
and optional Superpowers uninstalled. Source fixture hook tests do not prove
native hook delivery or a live-domain deployment.

Project 1: **None**; no existing relevant item found or changed. Issue #178 stays
open. [Release, dual-harness synchronization and terminal-only retry](review-retention-178-delivery.md)
are documented operator steps after approval.

## Model and cost details

The [terminal model/cost report](review-retention-178-model-cost.md) is rendered
once from the three actual private router receipts after model work closes.
The parent builder ran through T3 Codex as GPT-6.1-Sol with high effort; its
per-task tokens and charge were not supplied and are not estimated. The report
accounts for routed reviews only. Missing paid-cost evidence stays unavailable.

Durable private evidence: `/home/ned/.local/state/design-machines/depot/runs/depot-repair-review-retention-178-kkn_fpn4/diagnostic`.
The final candidate package remains at the exact task-owned replay root named in the machine proof.
