---
name: assembly-build
description: Build and test Assembly, with opt-in tiered repository verification
argument-hint: "[generate, build, test, full, focused, level, candidate, or post-merge]"
---

# Assembly Build

Legacy build modes remain backward compatible. The new pipeline-oriented modes
plan repository-declared verification through Workflow Kernel.

## Modes

| Argument | Behavior |
|---|---|
| _(none)_ / `full` | Legacy: generate, build, then run the full Go suite |
| `generate` | Legacy: generate Templ output only |
| `build` | Legacy: build `./cmd/api` only |
| `test` | Legacy: run the full Go suite only |
| `focused` | Planner `chunk` boundary |
| `level` | Planner `execution_level` boundary |
| `candidate` | Planner `merge_candidate` boundary |
| `post-merge` | Planner `post_merge` boundary |

Legacy modes continue to use the established Docker commands:

```sh
docker compose exec app templ generate
docker compose exec app go build -o bin/app ./cmd/api
docker compose exec app go test ./...
```

Run only the command appropriate to `generate`, `build`, or `test`; run all
three in order for the default or `full` mode.

## Required project profile

The target repository owns `.dm/verification.json`. It is a closed command-array
profile conforming to Workflow Kernel's
`repository-verification-profile-schema.json`.

If the profile is absent, stop with:

```text
BLOCKED: .dm/verification.json is not configured.
Copy the Assembly example profile into the project, then adjust its Docker
service, build tags, declared dependents, and remote lane owners.
```

The example is shipped at
`${CLAUDE_PLUGIN_ROOT}/references/repository-verification-profile.example.json`.
Planner modes never fall back to the legacy `./cmd/api`, running-container, or
full-suite commands; those remain available only through the explicit
backward-compatible modes above.

`ASSEMBLY_VERIFICATION_RISK` may be `low`, `medium`, or `high`; default
`medium`. `ASSEMBLY_VERIFICATION_BASE_REF` defaults to `HEAD` only for
`focused`, with uncommitted and staged changes included. `level`, `candidate`,
and `post-merge` require an explicit authoritative base ref; stop rather than
planning `HEAD...HEAD`.

Planner execution also requires:

- `DM_VERIFICATION_SUBSTRATE`: the resolved Docker image digest plus Go/Templ
  toolchain identity used by the lane.

The planner hashes the repository-owned profile, command inputs, declared
execution paths/environment, base commit, candidate commit, and worktree mode.

## Execution

Resolve one compatible Workflow Kernel launcher using its
`references/runtime-resolution.md` contract. Require Workflow Kernel `>=0.17.0`
and pin that launcher for the command.

Resolve and read its `exact-owned-cleanup.md`, create one disposable root with
`owned-run-start --workflow assembly-build --run-id <unique-run-id>`, and
create a `raw-output` child named `verification`. Export the exact root as
`DEPOT_EXACT_RUN_ROOT` so Workflow Kernel records its temporary execution home.
Install the same terminal reconciliation for `EXIT`, `SIGINT`, and `SIGTERM`.
Legacy modes use the repository's already-running Compose service and create no
run-owned Docker object, so they do not adopt or clean that service.

Use this run-owned disposable artifact:

```text
<exact-run-root>/verification/plan.json
```

Invoke `plan-verification` with:

- repository root: the exact current repository;
- profile: `.dm/verification.json`;
- the selected boundary and risk;
- `--base-ref "$ASSEMBLY_VERIFICATION_BASE_REF"`;
- `--candidate-ref HEAD`;
- `--include-worktree` for `focused` only; and
- the plan output path above.

Then invoke `run-verification` with the same repository and profile, the fresh
plan. It prints the bounded result for that invocation.

On success, call `owned-run-finish --outcome succeeded`; no verification home,
plan, temporary repository, or cache remains. On failure/interruption, remove
the root unless one compact diagnostic is genuinely useful. A retained root is
the only diagnostic root and the terminal report states its exact path, reason,
contents, and exact cleanup command. A retry reuses only the exact recorded root
with `--resume-root`; it never searches by prefix or age.

The runner revalidates the exact Git range, execution closure, changed inputs,
argv, and execution substrate
before executing anything. It uses an empty temporary home, fixed executable
path, incrementally bounded output/time, and a minimal environment without an
implicit shell. It terminates descendant process groups and refuses a complete
result when undeclared mutation changes the final input identity.

## Cadence contract

- Chunk and revision boundaries run doctor, fast, and focused lanes only.
- Collect all findings from one review pass, apply them as one revision batch,
  then run the `revision_batch` boundary once.
- Run full non-race lanes once after a complete execution level has been
  integrated.
- Merge-candidate and post-merge boundaries keep race, security, browser, and
  other remote lanes explicit. They are moved, never omitted.
- Remote lanes remain explicit `remote_pending` entries. Their native CI or
  review evidence is reported independently at the exact candidate head; it is
  not imported into the local result.
- Documentation and unrelated metadata edits do not select a
  code lane unless the repository profile explicitly includes them.

## Result

Report every lane as `passed`, `failed`, `remote_pending`, `blocked`,
or `unavailable`. Use `LOCAL PASS — REMOTE PENDING` when local evidence is
complete but required provider evidence is outstanding. Reserve unqualified
`PASS` for complete local and independently reported remote evidence at the
same exact head.
