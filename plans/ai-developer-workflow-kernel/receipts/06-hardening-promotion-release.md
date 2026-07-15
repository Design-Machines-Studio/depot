# Chunk Receipt: 06-hardening-promotion-release

- Title: Hardening, Promotion, and Release
- Date: 2026-07-15
- executionMode: codex_native
- implementedBy: codex
- fallback: none
- classification: integration
- chunkBranch: pipeline/ai-developer-workflow-kernel/06-hardening-promotion-release
- reviewedHead: a954aea99c7efa3a33f8637572e225314679f5b1
- featureMerge: c47bb3abdf433b2e9dc2ad7ccf6c5d6f1ad843bf

EVAL_GATE_PASSED: 06-hardening-promotion-release | classification: integration | iterations: 6 | findings_remaining: 0 | deferred: 0

## Verification

- Python 3.12 kernel suite: 688/688 passed with one expected opt-in live-Docker skip.
- System-Python kernel suite: 688/688 passed with two expected compatibility/opt-in skips.
- Offline behavioral validator: all 13 named sections passed.
- Failure injection: all 43 strict ID-bound scenarios passed, including real stale-materialization replay, fallback-review failure, terminal reconciliation failure, browser recovery, persona completeness, provider failures, and resource cleanup faults.
- Runtime CLI: all 18 commands exercised with valid-success fixtures plus invalid, blocked, unavailable, conflict, unsafe-plan, and parity-gap exits.
- Docker safety: structural broad-cleanup detection passed; exact-ID operations remain allowed. The opt-in live-Docker smoke was not run and is excluded from the offline release gate.
- Promotion evidence: deterministic fixture-only receipt written with `real_run_evidence: false`; native default remains blocked behind separate human approval.
- Description evaluation: workflow-kernel 17/17; all 40 skills met the repository threshold.
- Generated Codex manifests: 20/20 synchronized. Generated command aliases: 34/34 synchronized.
- Dependency graph, dual compatibility, workflow contracts, Codex-native pipeline, OpenRouter cascade, routing economics, search index, and full composition validation: passed.
- Exact-head review: clean after six fix/review iterations; zero P1-P3 findings remain and none were deferred.
- `git diff --check`: passed.
- Visual verification: contract-level only; this integration chunk changed no product UI route.

## Scope and Boundaries

- The workflow kernel remains shadow-first. Canonical Markdown workflows retain authority until measured promotion criteria and separate human approval permit later modes.
- Scenario replay is fault-identity strict: each ID is bound to an exact category, driver, evidence shape, and public runtime path. ID, route, or evidence swaps fail closed.
- Successful resumed builder sessions require evidence; empty or malformed agent output cannot be promoted into a successful resume.
- Browser verification preserves the required primary quit/relaunch/retry, alternate-engine, then human-help ladder. Curl-only proof cannot satisfy a required browser case.
- Assembly and assembly-baseplate persona declaration layouts are discovered and required persona coverage remains blocking for UI/integration completion.
- Docker ownership and cleanup remain exact-scope, exact-label, and exact-ID only. Broad prune, negative-label authority, foreign-resource removal, and cleanup after inspect uncertainty remain forbidden.
- The default release evidence is deterministic and explicitly fixture-only. It cannot masquerade as real shadow-run evidence.
- No findings were deferred.

## Cleanup

- Docker resources created by this chunk: none; the live-Docker smoke remained opt-in and skipped.
- Exact workflow-labeled containers, networks, and volumes found at chunk cleanup: none.
- No broad Docker prune, name-based deletion, or unrelated resource removal was performed.
- Generated Python bytecode caches were removed after verification.
- The chunk worktree and branch are removed only after clean-status and merge-ancestry proof.

## Ambiguity Resolution

- ambiguity_resolved: true
- Chose: deterministic default fixture-only evidence; strict fault adapters; successful CLI fixtures with injected offline Docker behavior; exact canonical-versus-generated inventory definitions.
- Rejected: self-confirming scenario fixtures, help-only CLI validation, safe-failure-only handler coverage, raw validator error output, Docker as an offline gate prerequisite, and real-run promotion claims from fixtures.
