---
status: done
priority: p2
issue_id: "005"
tags: [review, workflow-kernel, trust-boundary]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# Matrix trust is not enforced

## Problem

The CLI accepts any caller-provided JSON path as pricing authority and loads it
directly. It does not use the repository/cache trust resolution used for plugin
assets, verify that the file belongs to the resolved OpenRouter bundle, or
validate the matrix's schema and shared snapshot before its prices and
provenance are emitted. The generated prose also names a depot-relative path,
which is absent when these plugins run from their installed caches in another
repository.

## Location

- `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py:2115` -- direct arbitrary-path JSON load
- `plugins/workflow-kernel/skills/workflow-kernel/references/run-cost-summary-contract.md:19` -- hard-coded depot-relative matrix path

## Evidence

The only handling around `args.matrix` is `_load_json(matrix_path)` plus a broad
exception catch. No `resolve-plugin-bundle`, cache-class check, symlink/scope
check, or matrix contract validation occurs before the object reaches cost
calculation.

## Fix

1. Resolve the coherent OpenRouter bundle through the kernel's trusted bundle
   resolver and derive the matrix path from that selected root.
2. Validate the matrix schema, unique model slugs, finite non-negative prices,
   and snapshot-date consistency before using it.
3. Preserve observation-only behavior: an unavailable or invalid trusted
   matrix emits one skip-imputation diagnostic and does not fail the summary.

## Acceptance Criteria

- [x] Installed-cache consumers resolve the matrix without assuming depot cwd
- [x] Arbitrary or untrusted matrix paths are not accepted as pricing authority
- [x] Invalid matrix content skips imputation with one diagnostic
- [x] A valid trusted matrix remains deterministic

## Resolution

The CLI accepts only the trusted selector, resolves one coherent OpenRouter
bundle, validates matrix shape and snapshot consistency, and skips safely.
