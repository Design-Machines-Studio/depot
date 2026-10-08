# PROFILE-GENERATION-01 evidence

Pipeline Step 0f now has a supported launcher path for authoritative browser-plan discovery, focused selection, materialization and reload. Kernel 0.27.0 supplies `generate-verification-profile`; Pipeline 1.73.1 requires Kernel >=0.27.0 and resolves the Kernel contract from its coherent bundle. Generation and binding prepare a test plan. They do not prove browser execution.

## SIMPLICITY-CHECK

One CLI handler delegates discovery to `ProjectPersonaAdapter`; task selection runs before expansion and an optional exact case-ID filter retains declared primitives and required flags. It reuses the existing profile parser, identity, origin digest, durable writer, loader and behavioral binding. No alternate discovery implementation, profile schema, browser service, sweep framework or private-module workaround was added. No changes to application UI or Baseplate repairs were made. Generated aliases/manifests come from canonical sources.

## Candidate canary

Baseplate source: `f508cd6c890473246c43c3d9b6d7f59c1c62903b`, branch `fix/owner-ui-feedback-20261008`, PR [#1152](https://github.com/Design-Machines-Studio/assembly-baseplate/pull/1152). Every copied declaration retained exact source bytes. The bounded declaration copy contains the seven affected task files, four additional task declarations named by the unchanged route-binding configuration, the complete persona index/files, configuration and generated coverage matrix. Full original checkout, serving state, shared data, original run evidence and native PR/Issues were untouched.

The launcher generated/reloaded 30 candidate cases for the seven-task union. Exact candidate case IDs selected the eight Firefox task/persona pairs named by the source planning artifact. This preserves declared viewports and provenance; it does not reproduce the diagnostic profile's invented desktop/mobile matrix.

| Task | Persona | Route | Browser | Declared viewport |
| --- | --- | --- | --- | --- |
| bp-acct-002 | casual-member | /account/edit | firefox | 1280x800 |
| bp-dev-001 | casual-member | /dev/markdown-editor | firefox | 1280x800 |
| bp-adm-001 | engaged-chair | /admin/settings | firefox | 1440x900 |
| bp-adm-018 | super-admin | /super/design | firefox | 1440x900 |
| bp-adm-004 | engaged-chair | /admin/members | firefox | 1440x900 |
| bp-dev-001 | power-secretary | /dev/markdown-editor | firefox | 1680x1050 |
| bp-adm-007 | super-admin | /super/fixtures | firefox | 1440x900 |
| bp-memb-004 | engaged-chair | /admin/members/new | firefox | 1440x900 |

Both generated-profile binding and its exact idempotent retry succeeded in a fresh disposable Git scope. The original diagnostic profile/contract also bound and retried in a separate disposable run. Attempting to bind the changed generated profile/contract to that run was rejected. No immutable binding was rewritten and no earlier dispatch was retroactively validated.

Supported bounded-copy invocation (substitute the exact source copy and verified origin):

```sh
"$WORKFLOW_KERNEL" generate-verification-profile \
  --project-root "$AFFECTED_DECLARATION_COPY" --declaration-root . \
  --output plans/profile-generation-candidate.json \
  --target-origin "$VERIFIED_TARGET_ORIGIN" \
  --task-id bp-dev-001 --task-id bp-memb-004 \
  --task-id bp-adm-004 --task-id bp-adm-007 \
  --task-id bp-acct-002 --task-id bp-adm-001 --task-id bp-adm-018
```

Ordinary repository discovery uses `--project-root .` and omits `--declaration-root`. For an explicitly approved narrower combination set, reload the candidate JSON and pass its exact approved `--case-id` values in a second invocation with a fresh output path. Every task in the explicit union must retain at least one case. Generation receipts expose profile ID, full digest, exact selected/required IDs, discovery/selection status and `reload_verified=true`.

## Binding recovery

The diagnostic profile has 16 Firefox cases at `1440x900` and `375x812`. Authoritative focused discovery has eight cases at the declarations' applicable viewports. Both profile ID and full-document digest differ. Preserve the original run/profile/binding. Prepare and review a new consumer plan, initialize its fresh run, generate/reload the approved profile, create the contract with the exact profile ID/full digest and required case arrays, then call `bind-verification-contract` with `--verification-profile`. Only an identical existing binding permits idempotent reuse.

## NOT-COVERED

- No browser tests, application repairs, review restarts, serving-checkout changes, shared data changes, release publication, tags or harness synchronization occurred.
- The complete exact-source declaration-tree copy was rejected by existing declaration validation and wrote no profile. The bounded affected-source canary passed; it does not claim production whole-tree discovery passed. Unrelated declaration repair remains outside this Depot scope.
- Candidate source proof is separate from installed-consumer proof. Baseplate remains blocked until compatible releases are published/installed, declaration authority is valid, and its changed profile is bound in a newly planned run.
- Existing sandbox socket failures and `/tmp/.git` interference are retained in failed attempts. Host verification uses one task-owned temporary directory outside Git checkouts; the foreign `/tmp/.git` is preserved.
- Project 1 update: None. No native consumer Issue/PR state was changed.

## COMMANDS-RUN

- Focused CLI/discovery/release-validator tests; runtime CLI and behavioral binding checks.
- `tools/validate-workflow-kernel.py` and `tools/validate-composition.sh --all`, using a registered non-Git temporary directory for host fixture sockets/bindings.
- Canonical manifest/alias generation, generated index/dependency graph refresh and corresponding current-surface checks.
- Candidate launcher generation/reload, disposable `init`/`append`, `bind-verification-contract`, exact binding retries and changed-binding rejection.
- `git diff --check`; source ownership, remote main and PR #172/#173 inspection. Exact results and private routed receipts remain in the retained task evidence.

## Required delivery after this unmerged source PR

1. Review and merge the authorized source changes. Coordinate/reconcile #172's retained-review Kernel changes and #173's readiness/cleanup changes before release, preserving their versions/dependency updates. This PR reserves Kernel 0.27.0 and Pipeline 1.73.1; it does not absorb those repairs.
2. Run the repository release preflight against the final combined main. Publish `workflow-kernel-v0.27.0` and `pipeline-v1.73.1` under the repository release procedure; confirm canonical/generated manifests and dependency floors on that exact release. No tag is created here.
3. Refresh the Claude marketplace clone and run `claude plugin update workflow-kernel@depot` and `claude plugin update pipeline@depot`. Desktop Cowork has an independent cache and must be refreshed/restarted separately where used.
4. Use `codex plugin marketplace list` to identify the managed snapshot; refresh it with the supported marketplace upgrade path, then run `codex plugin add workflow-kernel@depot` and `codex plugin add pipeline@depot`. Do not edit cache files manually. Confirm each host resolves coherent assets at the required versions, without an older cross-host fallback.
5. After publication/install, run the installed launcher generation/reload/binding canary on the approved consumer declarations. Resolve the full-tree declaration failure or explicitly approve a valid bounded fixture authority. Create a newly planned consumer run for changed profile coverage; preserve the diagnostic run. Only then may the consumer resume its own authorized work.
