---
status: done
priority: p1
issue_id: "022"
tags: [review, dependencies, workflow-kernel]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Workflow Kernel dependency floors predate the matrix asset contract

## Problem

dm-review and pipeline now pass the Workflow Kernel 0.13.0-only `--matrix`
flag, but their plugin dependencies and the runtime-resolution reference still
permit older kernels that reject the invocation.

## Fix

Raise both canonical plugin dependency floors and the run-cost-summary runtime
floor to `>=0.13.0`, then regenerate Codex manifests.

## Acceptance Criteria

- [x] dm-review requires Workflow Kernel `>=0.13.0`
- [x] pipeline requires Workflow Kernel `>=0.13.0`
- [x] runtime-resolution documents `>=0.13.0` for matrix-backed summaries
- [x] generated Codex manifests match canonical sources

## Resolution

Raised both canonical dependency floors, the dependency validator's exact-floor
contract, and the matrix-backed runtime-resolution floor to `>=0.13.0`.
Regenerated Codex manifests. `check-dependencies.sh` passed the dependency graph
and Workflow Kernel leaf contract; `generate-codex-manifests.py --check`
reported all 19 manifests current.
