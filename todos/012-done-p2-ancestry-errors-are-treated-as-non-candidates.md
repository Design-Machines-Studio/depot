---
status: done
priority: p2
issue_id: "012"
tags: [review, release-preflight, equal-bump, fail-closed]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# Ancestry errors are silently treated as ordinary non-candidates

## Problem

The last-tag ancestry test uses `if ! git merge-base --is-ancestor ...` and
continues for every non-zero status. Git uses status 1 for a valid
"not-an-ancestor" result, but operational and object errors return values above
1. Those errors are therefore silently classified as an ineligible branch and
the receipt can remain green without inspecting it.

## Location

- `tools/check-release-preflight.sh:320` -- conflates the expected status 1 with fatal statuses such as 128

## Root Cause

The boolean negation discards Git's three-way exit contract. A safe local
reproduction with an invalid object returns 128, which follows the same
`continue` path as a legitimate non-ancestor.

## Suggested Fix

Run the ancestry command, capture its status, continue only for status 1, and
record a blocking FAIL for any status greater than 1. Apply the same explicit
status discipline to other new Git predicates where an operational error can
otherwise be interpreted as ordinary comparison output.

## Acceptance Criteria

- [ ] An ordinary non-ancestor remains an ignored out-of-scope branch
- [ ] Missing/corrupt-object and other ancestry errors produce FAIL and a non-zero preflight
- [ ] The receipt names the plugin and remote branch that could not be classified
