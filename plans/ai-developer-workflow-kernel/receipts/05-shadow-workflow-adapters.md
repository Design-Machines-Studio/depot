# Chunk Receipt: 05-shadow-workflow-adapters

- Title: Shadow Workflow Adapters
- Date: 2026-07-15
- executionMode: codex_native
- implementedBy: codex
- fallback: none
- classification: integration
- chunkBranch: pipeline/ai-developer-workflow-kernel/05-shadow-workflow-adapters
- reviewedHead: 2b4d4bf60c8452fed1334a1ec21cca1f977c2c20
- featureMerge: 92aace7c367fe317e9ccbaa27b4e495f703478db

EVAL_GATE_PASSED: 05-shadow-workflow-adapters | classification: integration | iterations: 8 | findings_remaining: 0 | deferred: 0

## Verification

- Independent Python 3.12 kernel suite: 666/666 passed.
- Independent system-Python kernel suite: 666/666 passed with one expected compatibility skip.
- Merged feature integration suite: 666/666 passed on both supported runtimes, with the same expected system-Python skip.
- Focused repository-scope, prediction-authority, and runtime CLI suite: 34/34 passed.
- Focused scope, prediction, Docker, cleanup, and runtime review suite: 92/92 passed.
- Descriptor-bound repository-scope suite: 8/8 passed, covering scope-name replacement, lease-directory replacement, hardlinks, and worktree `.git` replacement.
- Prediction and direct-comparison authority suite: 4/4 passed; missing, deleted, or reordered lifecycle authority returns a parity gap rather than a match.
- Generated Codex command aliases: 34/34 synchronized with canonical commands.
- Workflow-contract, Codex-native, OpenRouter cascade, routing-economics, description, and dependency validators: passed.
- Exact-head correctness review: clean; descriptor-bound scope I/O, direct comparison authority, and terminal run-state retention were confirmed.
- `git diff --check`: passed.
- Visual verification: contract-level only; this integration chunk changed no product UI route.

## Scope and Boundaries

- Pipeline and dm-review now emit observation-only shadow events without replacing Markdown authority for dispatch, gates, review outcomes, merge decisions, or cleanup.
- Independent prediction evidence is bound durably before `run.started`; observation and comparison both revalidate the same artifact and ordered lifecycle evidence.
- Parity comparison distinguishes matches, explained host differences, missing or unexpected evidence, prediction gaps, and unsafe promotion states while remaining proposal-only.
- Reliability metrics aggregate duration, attempts, routing, verification, findings, cleanup, token, and cost evidence without mutating policy.
- Owned Docker resources now carry a random immutable repository-scope identity in the complete positive label set. Inventory, leases, plans, guarded execution, and receipts all preserve that scope.
- Automatic cleanup is exact-scope and exact-ID only. Cross-repository, legacy, unlabeled, incomplete, or uninspectable resources remain foreign or retained; broad prune remains forbidden.
- The repository-scope document is repository-lifetime durable. Terminal run state remains until a fresh exact-scope inventory proves no matching run objects and no uninspectable matches.
- Browser recovery and required persona coverage are wired into UI/integration and visual-review paths; missing coverage remains blocking evidence.
- Composition remains intentionally incomplete until Chunk 06 generates the workflow-kernel Codex manifest and refreshes the 39/40 search index.
- No findings were deferred.

## Cleanup

- Docker resources created by this chunk: none.
- Workflow-labeled containers, networks, and volumes found at cleanup: none.
- No broad Docker prune, name-based deletion, or unrelated resource removal was performed.
- Generated Python bytecode caches were removed after verification.
- The chunk worktree and branch are removed only after clean-status and merge-ancestry proof.

## Ambiguity Resolution

- ambiguity_resolved: true
- Chose: pre-start lifecycle authority for prediction independence; immutable repository-scoped Docker ownership; fail-closed retention until fresh zero-object proof.
- Rejected: receipt self-comparison, caller-selected lease roots, path-only scope checks, daemon-global cleanup authority, and parity-controlled tombstone deletion.
