---
name: assembly-release
description: Assembly Baseplate release operations for current release state, one-command alpha publication and staging update, failed or stopped release resumption, R2 publication recovery, mechanical staging verification, and beta or stable promotion
argument-hint: "[status|plan|publish|resume|promote] [tag] [channel] [--minimum-version <tag>]"
---

# Assembly Release

Operate the release procedure owned by the current Assembly repository. This is
a small operator command, not a release service or a substitute for the
repository's runbooks and workflows.

## Arguments and safe default

Parse `$ARGUMENTS` as:

```text
[status|plan|publish|resume|promote] [tag] [channel] [--minimum-version <tag>]
```

- No arguments means `status`.
- Accept only `status`, `plan`, `publish`, `resume`, and `promote`.
- Accept only the optional `--minimum-version <canonical tag>` flag. Reject
  unknown flags, extra arguments, and speculative modes.
- `status` and `plan` are read-only. They must not create or move a tag, edit or
  publish a GitHub Release, dispatch a workflow, write a manifest, operate a
  provider, change a deployment, or create a credential.
- `publish`, `resume`, and `promote` require an exact tag and channel in the
  current invocation. The invocation is the operator authorization. Do not ask
  for a second confirmation before mutation. Read-only inspection before
  mutation is allowed and required.
- If a required argument is absent or invalid, return `BLOCKED` with one exact
  corrected invocation. Do not replace missing input with an approval screen.

## Resolve authority first

Before deciding what a release needs:

1. Resolve and report the repository root, remote URL and GitHub repository,
   remote default branch, checked-out branch, exact `HEAD`, upstream state, and
   porcelain worktree status. Fetch remote refs before comparing them. A dirty,
   detached, stale, or unexpected candidate is a candidate-state fact, not
   permission to repair it.
2. Read all root repository instructions that apply, including `AGENTS.md`,
   `CLAUDE.md`, or their repository-specific equivalents.
3. Discover and read the repository-owned release procedure, readiness,
   release-note, staging-acceptance, and recovery runbooks. Follow their links
   when they are required to interpret the current release path.
4. Inspect the actual current workflow definitions and every dispatch or call
   input involved in release creation, artifact publication, orchestration,
   storage locks, and manifest publication. Record the workflow path and blob
   SHA or exact repository head used for the decision.
5. Inspect the executable tag/channel policy when the repository provides one.
   Compare it with the prose journey. Report a disagreement as a blocker; do
   not choose one interpretation silently.
6. Stop with `BLOCKED` when this repository has no current, supported release
   procedure. Do not reconstruct a missing runbook from this command, memory,
   an old receipt, or a previous chat.

Resolve the official staging target from current repository policy before
loading any host-operation skill. Do not infer that staging is a NED target
because NED owns other Assembly operations. At authoring time, Baseplate names
the DigitalOcean-hosted `assembly-staging.service`; invoke `ned:operate-ned`
only if current repository policy explicitly names NED as the target.

Repository code and live state are authority. This command describes the
expected Baseplate concepts and safety boundaries, but it must never replace
current repository policy with embedded procedure.

## Reconstruct live state

Reacquire live facts for every invocation. Use bounded Git and GitHub queries
and public HTTPS reads; do not rely on remembered state.

- Resolve local and remote tags, the tag object when annotated, and its
  dereferenced commit. A pushed tag names one commit permanently.
- Inspect GitHub Releases, including absent/draft/published and
  prerelease/non-prerelease state, the authored body hash, and exact assets with
  names, sizes, and hashes.
- Inspect relevant workflow runs, attempts, exact workflow heads, jobs, and job
  conclusions. A successful job in another lane does not make a failed or
  skipped required lane successful.
- Read every public channel manifest supported by current repository policy.
  Record HTTP state, content hash, selected tag, `minimum_version`, and exact
  artifact identities. Read tag-scoped public files when needed and compare
  their bytes with the trusted GitHub Release assets.
- Look for current staging or beta deployment verification evidence through the
  repository-declared source. A healthy `/healthz` response proves health only;
  it does not prove the running version, migrations, update history, backup
  posture, protected routes, or acceptance.
- Treat old receipts and remembered procedures as historical hints only. Verify
  each claimed fact live before using it as current evidence.

Do not show credential values, raw environments, private endpoints,
secret-bearing URLs, raw provider responses, sensitive receipt bodies, or
unbounded logs. Evidence should be a link, exact SHA, bounded conclusion, or
public content hash.

## Keep the layers separate

Build this table in session. Do not create a release database, durable state
ledger, `.dm/release.json`, repository profile, or Workflow Kernel protocol.

| Layer | Allowed state |
|---|---|
| Candidate | exact commit, dirty, stale, or unverified |
| Tag | absent, local-only, pushed, or mismatched |
| GitHub Release | absent, draft, published prerelease, or published stable |
| Assets | absent, partial, exact, or conflicting |
| Storage locks | not applicable, planned, applied, verified, or failed |
| Staging manifest | previous, candidate, or conflicting |
| Staging deployment | unverified, mechanically verified, or failed |
| Beta manifest | previous, candidate, or conflicting |
| Stable manifest | absent, previous, candidate, or conflicting |
| Final evidence | complete or named gaps |

These facts are not interchangeable:

- A pushed tag names a commit.
- The tag-triggered release workflow builds assets and opens a draft GitHub
  Release.
- Publishing the GitHub Release exposes the authored release and assets.
- Artifact publication rehearses or publishes immutable tag-scoped files.
- The real orchestrated publication performs first publication to `staging`.
- R2 lock planning, application, and verification protect exact published
  files.
- A staging, beta, or stable manifest is a mutable pointer to existing files.
- The actual staging service is separate from the `staging` manifest.
- Manifest promotion reuses artifacts; it does not rebuild them.
- Publishing `stable.json` does not change Assembly's product-wide beta
  default.
- Repointing a manifest affects future updates and does not downgrade an
  installation that already updated.

## Validate release class and journey

Derive tag class, allowed channels, GitHub prerelease posture, and progression
from the current executable policy and runbooks. The expected current journeys
are:

| Class | Journey |
|---|---|
| Alpha | staging only |
| Beta | staging, then beta |
| RC | staging, then beta |
| Stable | staging, beta acceptance, explicit `promote <tag> stable` invocation, stable |

Reject a tag/channel combination that current policy does not allow. If this
table and the current repository disagree, stop and report the disagreement.

For alpha first publication to staging, current Baseplate policy may mark the
direct `Publish Release Artifacts` dry run optional. When it does, continue
directly through the real orchestrated publication; keep the dry run available
for explicit diagnosis, credential testing, or policy-classified higher risk.
Do not recommend an orchestrated dry run for first publication because its
manifest leg correctly requires tag-scoped objects that do not exist yet.

Beta, RC, and stable retain the repository-defined artifact rehearsal and
promotion evidence. Before any execution, re-derive the exact workflow names,
inputs, and class-specific rehearsal requirement from current code.

### Alpha staging fast path

For an exact `publish <alpha-tag> staging --minimum-version <floor>` or matching
`resume` invocation, treat that invocation as authorization for every valid
transition in one unattended journey:

1. mechanically validate the exact `main` candidate, annotated tag, alpha
   class, staging channel, support floor, authored notes, and current workflow
   head;
2. push the exact annotated tag and wait for the tag-triggered release build;
3. validate the complete asset inventory and publish the authored GitHub
   prerelease;
4. dispatch the real `Publish Release` orchestrator directly when the current
   alpha policy makes the direct artifact rehearsal optional;
5. verify GitHub and public R2 byte identity, the bound lock plan and applied
   lock configuration, exact `staging.json` tag and floor, and unchanged beta
   and stable manifests;
6. run the repository-supported privileged backup and required off-host copy
   for the official staging service;
7. apply the candidate through the repository-supported CLI update path; and
8. mechanically verify staging and return one final report.

Continue through every valid alpha transition without asking whether to push
the bound tag, publish the validated prerelease, dispatch the real workflow,
apply the exact candidate, or accept a mechanically proven result. Stop only
for an actual failure, conflicting live state, missing product decision,
missing authority, unsupported bridge, required external wait, or another
non-automatable repository gate.

## Mode behavior

### `status`

Reconstruct every live layer without mutation. If the tag is omitted, identify
the relevant current release from live tags, releases, manifests, and runs;
state the selection rule. Report one smallest valid next action, even when it is
only to obtain missing acceptance evidence.

### `plan`

Produce one exact read-only plan for the selected candidate, tag, class,
channel, storage target, deliberate `minimum_version`, and current workflow
head. Name each transition and its evidence prerequisite, but keep the normal
response compact. Do not dispatch a dry run: a workflow dispatch is not a
read-only plan. Prefer mechanically derived facts over a checklist for the
operator to re-verify.

### `publish`

Use only for a new release plan. Reconstruct state and reject candidate drift,
tag collision, unsupported class/channel posture, missing authored notes, or
an incomplete exact plan. Mechanically bind and validate the invocation as
described below, then execute the repository-defined valid transitions toward
the requested channel without another confirmation. Verify every transition
before continuing and respect any live repository-defined GitHub environment
gate. Never move, delete, or recreate a pushed tag.

### `resume`

This is the preferred mode for a partial release. Rebuild live state, then
identify and execute every currently valid incomplete transition toward the
exact requested channel. Reuse the exact pushed tag and byte-identical existing
artifacts. Verify each completed transition before starting the next. Stop at
the first failed, conflicting, approval-waiting, or genuinely non-automatable
gate. Do not artificially limit a resume invocation to one transition. Retry a
failed gate without rebuilding or republishing completed irreversible work
merely to make a cleaner receipt.

Required distinctions include:

1. If the tag, published GitHub Release, and exact tag-scoped artifacts exist,
   lock work failed, and the channel remains previous, retry or recover only the
   lock gate allowed by current policy.
2. If exact locks are verified but the ordinary orchestrated manifest step
   failed, bounded direct manifest recovery may be the smallest transition only
   when current repository policy permits it. Record separately that direct
   recovery does not prove the ordinary orchestrator works.
3. If `staging` points to an alpha candidate but the actual deployment lacks
   mechanical verification, continue through supported backup, CLI update, and
   verification in this invocation; do not request named acceptance and do not
   promote alpha.
4. If a beta dry run succeeded but live `beta` remains previous, do not call it
   promoted; the next transition is the authorized real manifest move after
   prerequisites remain valid.
5. If one workflow lane succeeded while a required release lane failed or was
   skipped, report the required lane's actual state and do not collapse the run
   to "released."

Stop on tag mismatch, candidate drift, different artifact bytes, unexpected
manifest movement, backward progression, or conflicting release state. Never
use an old receipt as current proof.

### `promote`

Move only an existing exact artifact set to a permitted later channel. Verify
the source manifest, immutable public bytes, current destination manifest,
release posture, deliberate support floor, and required staging/beta acceptance
evidence. Use the current manifest workflow; do not invoke artifact builds or
publication. Alpha cannot promote, beta/RC cannot promote to stable, and stable
requires both staging and distinct beta acceptance. The explicit
`promote <tag> stable` invocation is the stable-promotion approval; do not ask
for a second confirmation.

## Credential and configuration semantics

Inspect credential names and current workflow references only. Never read or
print values. Distinguish persistent repository/environment setup from
per-release inputs.

At authoring time, the expected Baseplate shape is repository-level
`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_R2_CONFIG_TOKEN`, and one `R2` writer
bundle, plus persistent `CLOUDFLARE_R2_LOCK_TOKEN` in the protected
`r2-release-locks` environment. Current workflow definitions and live name-only
configuration must confirm or supersede this expectation.

Never recommend a fresh credential per release unless current repository policy
explicitly declares it ephemeral. Never resurrect removed Object Read
credential pairs from memory or old receipts. For a missing credential, say:

- what capability it enables;
- which current workflow reference requires it;
- whether it is persistent or per-release;
- who owns the configuration; and
- the one action required.

Classify a missing configured name as configuration, not a workflow defect. If
code repair is actually required, stop and report that as a separate next
action; invocation authority never includes patching Baseplate.

## Invocation authority and deterministic checks

`publish`, `resume`, and `promote` mutate only when the current invocation
contains an exact tag and channel. That invocation is the operator
authorization. Do not ask "are you sure?", present an authorization envelope,
or emit a paused-for-approval state.

Before the first mutation, mechanically bind and validate:

```text
candidate commit: <40-character SHA>
tag: <exact tag>
release class: <alpha|beta|rc|stable>
channel: <exact channel>
storage target: <exact current target>
minimum_version: <exact floor>
transition: <exact workflow dispatch or state change, including dry_run posture>
workflow head: <40-character SHA>
```

Resolve `minimum_version` in this order:

1. an explicit `--minimum-version` value in the current invocation;
2. for `resume`, the verified input of the release attempt being resumed;
3. for `promote`, the verified source manifest floor; or
4. one unambiguous value required by current executable repository policy.

Reject conflicting sources. Validate the selected floor against current tag
policy, channel rules, manifest-forward-movement rules, and supported-upgrade
evidence. An explicit flag supplies a product choice; it never overrides those
checks. If the floor or another bound value cannot be determined mechanically,
return `BLOCKED` with the exact missing decision and one corrected invocation.
Do not turn machine-checkable facts into a human review checklist.

For alpha, prove the real update from the version currently running on official
staging to the candidate and validate the selected floor. Do not require a new
disposable oldest-supported, below-floor, bridge, rollback, or restore
rehearsal unless current policy says the selected floor creates a new
compatibility boundary. An actual unsupported bridge still blocks. Retain the
broader repository-defined support-range evidence for beta and stable
promotion, reusing valid exact evidence where policy permits.

A vague `continue` without an exact tag and channel cannot mutate. An exact
invocation does not need a second approval. Continue to respect an actual live
GitHub environment wait or other repository-owned approval that the workflow
itself enforces, and report that external wait plainly instead of adding a
Depot-owned gate.

Invocation authority never expands to repairing code/workflows, moving tags,
changing the support floor beyond an explicit validated `--minimum-version`,
creating credentials, changing the default update channel, altering DNS,
firewall, backups, staging topology, Cloudflare configuration, unrelated GitHub
Projects, or other releases.

## Staging execution and mechanical result

Use only the current repository-supported backup unit or command and CLI update
path. Do not invent an ad-hoc privileged maintenance command. This automation
does not weaken the ordinary self-hosted web UI: CSRF, authorization, HMAC
confirmation tokens, separate Download and Install actions, checksum and
signature checks, candidate preflight, migration snapshots, and rollback
evidence remain intact.

An alpha staging result is mechanically verified only when current evidence
proves the exact tag and exact-head CI; published prerelease posture and
validated notes; byte-exact GitHub and public R2 assets; verified lock plan and
applied configuration; exact staging tag/floor with beta and stable unchanged;
fresh backup and off-host copy; supported CLI update; exact running version;
strict preflight; current migrations; active named systemd service without an
unexpected restart loop; loopback and public health; correct HTTPS login-route
response; and expected hashes for release-relevant static assets.

Compute HTTP hashes from raw response bytes only. Never hash RTK's compact
human-formatted curl output; use RTK's raw proxy path with an output file when
exact bytes are required.

For ordinary alpha staging, missing authenticated-browser capture and a missing
restore rehearsal are named non-blocking coverage gaps after the mechanical
core passes. Require focused repository-defined proof when the candidate
changes authentication, update integrity, backups, restore, or another
high-consequence behavior. Staging enables subsequent human product testing;
it does not require a separate owner to accept a mechanically verified alpha.

## Receipts

Use a repository receipt location only when current repository instructions
explicitly declare it and Git confirms it is ignored. Otherwise resolve
Workflow Kernel `>=0.17.0`, read `exact-owned-cleanup.md`, and create one
disposable root with `owned-run-start --workflow assembly-release --run-id
<unique-run-id>`. Create temporary repositories, caches, raw provider output,
and transient receipts only through `owned-run-create` beneath that root.
Install terminal reconciliation for `EXIT`, `SIGINT`, and `SIGTERM`.

Keep the receipt compact:

- repository and exact SHA;
- tag, channel, storage target, and floor;
- state before and after;
- workflow URLs and conclusions;
- public artifact and manifest hashes;
- exact invocation mode, tag, channel, and resolved floor;
- remaining gaps; and
- commands actually run.

Never retain credential values, private endpoints, raw environments, provider
bodies, sensitive workflow artifacts, or unbounded logs.

Successful `status`, `plan`, `publish`, `resume`, and `promote` invocations
remove the disposable root after the compact receipt is projected to its
declared durable destination. Failure/interruption also removes it unless one
bounded diagnostic root is genuinely useful. When retained, terminal output
states the exact path, why it was retained, what compact evidence it contains,
and the exact safe cleanup command. Resume/retry uses that exact recorded root;
it never adopts an older prefix- or age-matched directory.

## Output contract

Every response begins with exactly one of:

```text
READY
IN PROGRESS
BLOCKED
FAILED
COMPLETE
```

Then provide, in order:

1. `Next action:` followed by exactly one sentence.
2. The compact ten-layer current-state table with evidence links or hashes.
3. Only actual blockers, using this shape when blockers exist:

   | Source | Plain-English meaning | Owner | User action required? |
   |---|---|---|---|

   Allowed sources are `repository policy`, `GitHub workflow`, `GitHub
   configuration`, `provider configuration`, `live deployment`, and
   `plugin/tool limitation`.
4. A short `Invocation changed:` statement.

"Nothing changed" means only that this invocation made no additional changes.
It must be followed by the overall live release state, including tags,
artifacts, locks, or manifests completed by earlier attempts.

Keep ordinary output preferably below 700 words. Do not dump raw logs or the
entire roadmap, and avoid invented release-management jargon. Offer deeper
bounded evidence only when it helps the operator decide the one next action.
