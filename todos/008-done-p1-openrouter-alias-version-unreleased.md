---
status: done
priority: p1
issue_id: "008"
tags: [review, openrouter, versioning, plugin-cache]
source_agents: [codex-focused-recheck]
review_date: 2026-08-09
---

# OpenRouter alias contract is unreleased

## Problem

The repair changes OpenRouter's canonical model-matrix contract by adding
`native_api_equivalent_cost`, but leaves the OpenRouter plugin and marketplace
at `1.10.0`. The workflow-kernel consumer also accepts any OpenRouter bundle at
or above `1.8.0`. Installed caches can therefore resolve a valid older bundle
without aliases and silently skip the native imputation the new kernel expects.

## Location

- `plugins/openrouter/.claude-plugin/plugin.json:4` -- remains `1.10.0`
- `.claude-plugin/marketplace.json:344` -- OpenRouter marketplace entry remains `1.10.0`
- `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py:2140` -- minimum remains `1.8.0`
- `plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json:5` -- new cross-plugin contract field

## Evidence

A real, unmocked `_load_cost_imputation_matrix("trusted-openrouter-bundle")`
call succeeded but returned the installed `1.10.0` matrix with
`native_api_equivalent_cost: None`. The tests hide this deployment failure
by mocking the resolver to return a temporary bundle containing the worktree's
modified matrix.

## Fix

1. Bump OpenRouter from its current version in the canonical plugin manifest
   and marketplace, using the repository's version policy for a new reference
   contract field.
2. Regenerate both Codex shim sets.
3. Raise the workflow-kernel resolver minimum to the first OpenRouter version
   that guarantees `native_api_equivalent_cost`.
4. Add a version-contract check binding the consumer minimum to that release.

## Acceptance Criteria

- [x] OpenRouter version is bumped and mirrored in every generated home
- [x] Kernel minimum version guarantees the alias field
- [x] An unmocked resolver selects a bundle containing the aliases
- [x] Release-preflight validation passes; composition is covered by the chunk verification report

## Resolution

OpenRouter 1.11.0 is the first native-cost contract release. Kernel resolution
now requires 1.11.0, and an unmocked temporary-cache fixture proves selection.
