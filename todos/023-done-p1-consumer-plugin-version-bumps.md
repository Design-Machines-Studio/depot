---
status: done
priority: p1
issue_id: "023"
tags: [review, versioning, release]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Changed dm-review and pipeline plugins are unreleased

## Problem

Installed dm-review and pipeline command/skill behavior changed without a
plugin version bump, so cache update detection cannot publish the changes.

## Fix

Read the current versions, apply one PATCH bump to each canonical manifest and
marketplace entry, and regenerate both Codex surfaces.

## Acceptance Criteria

- [x] dm-review is PATCH-bumped from its current canonical version
- [x] pipeline is PATCH-bumped from its current canonical version
- [x] marketplace entries match canonical plugin versions
- [x] generated manifests and command-skill aliases are current

## Resolution

Read the canonical versions, then PATCH-bumped dm-review `1.58.0` to `1.58.1`
and pipeline `1.44.0` to `1.44.1` in their plugin manifests and the marketplace.
Regenerated Codex shims; manifest and command-skill `--check` modes passed for
19 manifests and 34 aliases.
