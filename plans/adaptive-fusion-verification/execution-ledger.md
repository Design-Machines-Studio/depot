# Execution Ledger: adaptive-fusion-verification

- Run ID: `adaptive-fusion-verification`
- Started: 2026-07-22T02:53:35Z
- Feature branch: `codex/adaptive-fusion-verification`
- Base: `origin/main@21f3d9b495068acecd2a7a755f3a2c3062e52114`
- Workflow class: `feature`
- Execution mode: `codex_native`
- Isolation strategy: `per-chunk-worktree`
- MCP pre-flight: not required (0 UI/Integration chunks)
- Module-loader pre-flight: not applicable
- Gitignore enforcement: added `.workflow-kernel/`
- Receipt tracking: `plans/` is ignored; final durable artifacts will be force-added to the feature branch
- OpenRouter availability: unavailable (`tenant-policy-denied`); requested OpenRouter lanes retain provenance and use explicit Codex fallback

## Level 0

- `01-behavioral-contract-core`: merged; 37 focused tests passed; evaluation clean after 2 iterations; Docker ownership empty and reconciled.
- `04-review-synthesis-provenance`: merged; focused validator and shellcheck passed; evaluation clean after 3 iterations; OpenRouter declined by tenant policy and Codex fallback recorded; Docker ownership empty and reconciled.
- Combined level gate: focused suites passed. The release validator currently expects seven schema documents and therefore rejects the newly added eighth schema; chunk 06 owns that validator inventory. The refreshed `origin/main` baseline independently fails later in its unittest stage with a redacted `value-sha256` receipt.

## Level 1

- `02-contract-policy-integration`: merged; 137 focused tests passed; evaluation clean after 2 iterations; pre-bind dispatch and hostile dual-key equality bypasses fixed; Docker ownership empty and reconciled.

## Level 2

- `03-authoritative-pipeline-feedback`: merged; routing/workflow validators passed; evaluation clean after 2 iterations; requested OpenRouter declined by tenant policy and Codex fallback recorded; Docker ownership empty and reconciled.
- Shadow observation after chunk 02 became unavailable with `unsafe_payload` because this run hot-upgraded its own translator to require a bound verification contract that the pre-feature run did not possess. Canonical Markdown receipts remain authoritative.

## Level 3

- `05-attempt-economics-and-contribution`: merged; 109 focused tests passed; evaluation clean after 3 iterations; cross-event identity, per-artifact finding IDs, intervention shapes, bounds, parity, and ambiguous coverage fixed; Docker ownership empty and reconciled.

## Level 4

- `06-cross-plugin-release-integration`: merged; released workflow-kernel 0.3.0, Pipeline 1.32.0, and dm-review 1.45.0 with synchronized generated adapters and exact 8-schema/21-command release inventories.
- Focused release, compatibility, parity, routing, dm-review, workflow-contract, dependency, dual-compatibility, generated-file, and composition-reference gates passed; evaluation was clean after 1 review iteration.
- The complete kernel/composition gate remains non-green only at the explicitly permitted live sibling `assembly-baseplate` declaration check (`invalid_verification_declaration`). No Assembly files were changed. The same boundary predates this branch.
- The prompt's bare `python3.12 -m unittest tests.test_release_validator` omits the repository-required kernel import path; the equivalent `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references` invocation passes 9/9.
- OpenRouter was requested but declined by tenant policy; Codex fallback provenance is retained. Docker ownership was empty and reconciled.

## Final Review and Closeout

- Three Codex review lenses converged to CLEAN after repairing all newly found P1/P2 issues; zero findings were deferred.
- Final focused verification: 123 tests passed; routing, workflow-contract, dm-review, dependency, dual-compatibility, generated manifest/alias, and diff checks passed.
- Final full discovery: 786 tests, 1 skipped, exactly 1 external live `assembly-baseplate` declaration error; no Depot-owned failure.
- Terminal Docker reconciliation inspected the exact managed repository scope outside the sandbox: current-run and stale-sweep inventories were empty, with zero blocked resources.
- Successful artifact cleanup removed all six generated chunk prompts. Terminal shadow inputs remain because the self-hosting adapter upgrade makes comparison unavailable rather than a semantic match.
- Post-terminal `observe-pipeline`, `compare`, and `metrics` were attempted in the required order and each returned the same safe `unsafe_payload` boundary from the self-hosting contract upgrade. No shadow artifact or metric was treated as authoritative, and no terminal input was deleted.
