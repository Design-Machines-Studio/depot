---
status: done
priority: p2
issue_id: "031"
tags: [review, release-preflight, read-only]
source_agents: [architecture-reviewer]
review_date: 2026-08-09
---

# Remote preflight probes write fetched objects into the repository

## Acceptance Criteria

- [x] Remote objects are fetched into a temporary quarantined object database.
- [x] Repository refs, FETCH_HEAD, and object store remain byte-identical.
- [x] Remote evidence remains evaluable and failure cleanup is proven.
- [x] `--no-net` usage names both skipped network probes.

## Resolution

The equal-bump gate now fetches and reads remote-only objects through a
temporary `GIT_OBJECT_DIRECTORY`, with the repository object store available
read-only through `GIT_ALTERNATE_OBJECT_DIRECTORIES`. Normal, fetch-failure,
signal, and process-exit paths clean the validated `/tmp` quarantine. A real
remote-only divergence still produces the expected equal-bump failure while
refs, `FETCH_HEAD`, and every repository object byte remain unchanged; the
failure regression proves the quarantine is removed. The usage line now states
that `--no-net` skips both remote branch and authentication probes. Focused
tests, Bash syntax, ShellCheck, dependency validation, canonical sync,
workflow-contract validation, and diff check passed.
