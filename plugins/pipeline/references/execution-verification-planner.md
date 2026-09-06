# Repository verification planner (1d)

Loaded at Step 1d only when the repository declares a workflow-kernel
verification profile (`.dm/verification.json` or an equivalent declaration). A
repository with no profile records that verification planning is not applicable
and never loads this file. A malformed or unsafe declared profile is still a
declared profile: preserve its exact validation evidence and stop with
`human_help_required`; never fall back to repository-native verification.

### 1d: Repository Verification Planner

Use Workflow Kernel `>=0.15.0` as the only executable source of repository test selection. Pin the launcher already resolved for this run. Shadow may degrade to `shadow unavailable`; repository verification on a profile-aware repository fails closed with `human_help_required`.

Validate the declared profile with `plan-verification` before the first builder
dispatch. When valid, the resulting plan remains authoritative for selection,
tiered cadence, and evidence. Profile cadence is unchanged by the separate
no-profile repository-native policy in the orchestrator and Codex adapter.

Before dispatch, run `plan-verification` with the exact base ref, candidate ref, and worktree-inclusion choice. Write a fresh plan under `plans/<feature-slug>/verification-plans/`, then `run-verification`. Required remote lanes remain `remote_pending`; report native CI or review evidence at the exact candidate head rather than importing it into the local result.

The authoritative cadence is:

| Boundary | When | Allowed local depth |
|---|---|---|
| `chunk` | Worker completed one chunk | Doctor, fast, focused |
| `revision_batch` | All fixes from one review pass are applied | Affected doctor, fast, focused |
| `execution_level` | Every chunk in one dependency level is merged | Integrated full non-race once |
| `merge_candidate` | All levels are merged and before final review | Fresh exact-candidate run; remote lanes explicit |
| `post_merge` | Main-branch proof | Repository-declared authoritative lanes |

Expensive required lanes move to their declared merge-candidate/remote boundary.
