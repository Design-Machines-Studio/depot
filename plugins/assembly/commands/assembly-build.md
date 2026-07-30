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

- `ASSEMBLY_VERIFICATION_APPROVAL`: the immutable host-authenticated approval
  artifact issued before builder dispatch and bound to repository scope,
  profile path/digest, execution closure, trusted base commit, run ID,
  authorization event, and approval time;
- `ASSEMBLY_VERIFICATION_KEY_BROKER`: a host-owned broker outside the
  repository and worker identity that writes the stable authority key to the
  kernel's standard input. Never name a key file in process arguments; and
- `DM_VERIFICATION_SUBSTRATE`: the resolved Docker image digest plus Go/Templ
  toolchain identity used by the lane.

A profile, authority-path, or authority-environment change requires explicit
host approval and a newly sealed approval artifact.

## Execution

Resolve one compatible Workflow Kernel launcher using its
`references/runtime-resolution.md` contract. Require Workflow Kernel `>=0.6.0`
and pin that launcher for the command.

Use these run-owned artifacts:

```text
.workflow-kernel/verification/plan.json
.workflow-kernel/verification/receipts.json
```

Before the first builder dispatch, the host invokes
`approve-verification-profile` with the trusted base commit, exact candidate
commit, worktree-inclusion choice, run ID, authorization event ID, and
timezone-aware approval time. The broker supplies
the authority key through `--receipt-key-stdin`; write the immutable result to
`$ASSEMBLY_VERIFICATION_APPROVAL`.

Invoke `plan-verification` with:

- repository root: the exact current repository;
- profile: `.dm/verification.json`;
- the selected boundary and risk;
- `--approval "$ASSEMBLY_VERIFICATION_APPROVAL"`;
- the existing receipt ledger when present; and
- broker-supplied authority on standard input via `--receipt-key-stdin`; and
- the plan output path above.

Then invoke `run-verification` with the same repository and profile, the fresh
plan, the existing receipt ledger when present, and the receipts output path.
Also pass the approval and broker-supplied key:

```text
--approval "$ASSEMBLY_VERIFICATION_APPROVAL"
--receipt-key-stdin
```

The runner revalidates the authenticated approval, approved execution closure,
changed inputs, exact argv, cache key, execution substrate, and receipt history
before executing anything. It uses an empty temporary home, fixed executable
path, incrementally bounded output/time, and a minimal environment without an
implicit shell. It terminates descendant process groups and refuses to sign a
complete result when undeclared mutation changes the final input identity.

## Cadence contract

- Chunk and revision boundaries run doctor, fast, and focused lanes only.
- Collect all findings from one review pass, apply them as one revision batch,
  then run the `revision_batch` boundary once.
- Run full non-race lanes once after a complete execution level has been
  integrated.
- Merge-candidate and post-merge boundaries keep race, security, browser, and
  other remote lanes explicit. They are moved, never omitted.
- A host integration clears a remote lane only with
  `record-verification-result` and a broker-sealed provider attestation
  matching its provider, provider run ID, exact candidate commit, evidence
  digest, observed time, outcome, profile, command, input, cache, and substrate
  identities.
- A passing receipt is reusable only when the profile, exact argv, relevant
  source inputs, and declared environment fingerprint are identical.
- Documentation, receipt, and unrelated metadata edits do not invalidate a
  code lane unless the repository profile explicitly includes them.

## Result

Report every lane as `passed`, `failed`, `reused`, `remote_pending`, `blocked`,
or `unavailable`. Use `LOCAL PASS — REMOTE PENDING` when local evidence is
complete but a required provider receipt is outstanding. Reserve unqualified
`PASS` for complete authenticated evidence from every required lane.
