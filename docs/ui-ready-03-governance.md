# UI-READY-03: Governance author-loop evidence

Date: 2026-09-09. Depot PR #129. This is candidate-source consumer evidence,
not installed-plugin or published-consumer proof. Governance remains
**REVIEW INCOMPLETE** for the populated and prototype cases below.

## Source and preservation

- Refreshed Depot main: `7ae609fc3e74e6dcfea53c83a732e4e4ceefa1b3`.
- Starting PR head: `07c4d5dd6a3efb0b52dc0c4df4bddd42346143dd`.
- Governance's reported remote head was `5184e5e4f6828cb4ea9eb0d91cc11e657904761e`.
  Its original seven staged repairs were already committed when this execution
  inspected the worktree: clean `294da01d7ff883a7c025ae76d576f02cabeea544`.
- The separately cloned canary captured the subsequent clean consumer snapshot
  `e062db12a37c67a335058bae4c0ced9c101ad6eb`, including its later public-Fixture
  response-table repair. No consumer source was edited or committed here.
- Selected Baseplate: clean alpha19 source
  `77ba34d967967825c1f6f9a5f5f6ba3fdcfe8572`.
- Final repeated build binary SHA-256:
  `a2d246e781c743bf4b097dc6976cd5ff059d738fbc53ade9979af86482258eb7`.
  The rebuilt artifact was identical to the browser-tested artifact.
- Primary Depot work and every existing source worktree were preserved. The
  existing dm027 instance received status/identity reads only. Its reported
  loopback URL was `http://127.0.0.1:8097`; reachability was not used as source proof.

## Reproduction and repair

The exact fixed-project Compose shape from Baseplate's wrapper returned
`managed: false`, `caller_project_name_forbidden`, with zero Docker commands.
The earlier Jig canary did not prove this path.

`plan-compose --repository-project-name` now admits the explicit matching name
only with the run's Kernel registry authority and fresh collision checks.
Unregistered project objects, aliased containers/networks/volumes, external
resources, failed inventory, and conflicting names remain refused. Exact
inspection resolves old short registry IDs without prefix guessing. Owned
network/volume labels stay stable across repeated wrapper calls.

The real wrapper exposed two additional requirements: profiled builders must
be included in configuration inspection, and multiline builder argv must remain
literal. The adapter now handles both. Identifier and cleanup-action validation
remain strict. The existing strict registry validator, exact absence handling,
and stable exact-resource cleanup witness repair from PR #129 are retained.

The host interpreted Governance's AGENTS/README/CONTRIBUTING, Makefile and linked
Baseplate wrapper. A temporary invocation-local Docker command hook used candidate
Kernel APIs for planning, label injection, recording, and guarded cleanup. It
kept `make dev` and the unmodified Baseplate wrapper as lifecycle authority.
No second composer, persistent shim, process supervisor, registry, or service
was added. This source integration harness is not a shipped installed harness.

The hook covered executable lookup, including Governance's `exec docker` seed
path; an exported shell function alone was insufficient. Wrapper cleanup used
terminal reconciliation: safe container steps first, then a fresh network plan.
These are host integration requirements in dm-review's creation/cleanup guidance.

## Real consumer canary

One exact Kernel-owned disposable filesystem root held a separate Governance
clone, state, run files, and private evidence. The repository commands were:

```sh
make dev ACTION=start INSTANCE=ui-ready-03-20260909 STATE_ROOT=<owned>/state RUN_ROOT=<owned>/run BASEPLATE_DIR=<alpha19>
make dev ACTION=status INSTANCE=ui-ready-03-20260909 STATE_ROOT=<owned>/state RUN_ROOT=<owned>/run BASEPLATE_DIR=<alpha19>
make dev ACTION=seed INSTANCE=ui-ready-03-20260909 STATE_ROOT=<owned>/state RUN_ROOT=<owned>/run BASEPLATE_DIR=<alpha19>
make dev ACTION=clean INSTANCE=ui-ready-03-20260909 STATE_ROOT=<owned>/state RUN_ROOT=<owned>/run BASEPLATE_DIR=<alpha19>
```

All addressed `assembly-fdev-ui-ready-03-20260909`. Start and status reported
healthy `http://127.0.0.1:37489`. A repeated final start retained the same network
and built the identical binary. Seed affected only fresh disposable data.

T3 opened the app but its snapshot operation failed. The session's Firefox
Playwright transport completed the interaction. No model routing decision was
used to infer browser availability.

Candidate `ui-review-readiness.sh` accepted the real source/registry evidence,
returned `app_ready`, then `ready` after host browser confirmation, retaining
`registry_cleanup_required`. Browser readiness did not imply complete coverage.

Through supported UI, the seeded super-admin signed in, enabled Governance,
created a Standard Decision proposal, and opened it for input. Desktop
1440×1000 showed the open proposal and empty Member positions panel with no
horizontal overflow. At 390×844, the Return to drafting dialog opened and
cancelled; focus returned to its trigger, with no horizontal overflow. The final
rebuild was reloaded and the mobile interaction repeated successfully.

Screenshots: [desktop open proposal](evidence/ui-ready-03/desktop-open.png) and
[mobile confirmation](evidence/ui-ready-03/mobile-dialog.png).

The wrapper's clean command requested Kernel teardown. Exact registered
containers were removed or proven absent, then the network was removed after
fresh inspection. The final registry reconciliation inventory was empty. The
wrapper removed its positively created exact image and run directory. Its
preserved disposable state was removed by the owned-root terminal cleanup.
A labelled rootless `--rm --network none` container restored ownership on only
that disposable state directory after mapped container UIDs prevented host
removal. The terminal helper then retained one 150-KiB diagnostic root containing
bounded receipts/screenshots and no database, build cache, or runtime resource.
No dm027 reset, seed, rebuild, stop, cleanup, or database write was performed.
The untouched consumer worktree and remote PR later advanced independently to
`264d62eb191db53aafdcd5e21eeabdbf61afc818`; this report does not claim browser
proof for that later source.

## NOT-COVERED

- Mixed-response and abstention-only open/resolved proposal cases. This snapshot
  has no supported position-taking UI; its documented seed supplies Baseplate
  Northstar data only. Governance assigns position-taking to GOV-POS-01 and
  story data to GOV-DEV-04. Direct database injection or product implementation
  was outside this execution. The populated cases remain required.
- Matched rendered prototype at `6268ea42ff34f13652f0f06967f6a175dd6756b2`.
  The supplied review identified this exact source but no matching live rendered
  target. No comparison against a different prototype is claimed.
- Installed Claude/Codex consumer proof, publication, tags, merge, and cache
  synchronization. These require the separately authorized release step.
- External independent review. The bounded integration/cleanup review was local;
  no optional routed participant or paid call was used.

## SIMPLICITY-CHECK

The repair extends existing Compose planning and command-value validation, and
clarifies host-owned integration. The repository wrapper still composes, builds,
starts, seeds, reports status, and requests cleanup. Kernel owns only its existing
exact resource mechanics. Existing targets remain unadopted. No product features
or story-data system were added.

## Verification and delivery boundary

Versions: dm-review `1.80.1`; Workflow Kernel `0.22.0`. The dm-review dependency
floor moves to `>=0.22.0` for the explicit repository-project integration. Other
plugins retain refreshed main's versions and functionality.

Final validation passed: the full 13-section Kernel release gate,
`validate-composition.sh --all`, 230 UI readiness assertions, 48 repository
browser-discovery assertions, 30 UI contract assertions, 12 Pipeline browser
handoff assertions, affected Docker/registry/CLI tests, generated manifests and
command aliases, dependency/dual-compatibility checks, and whitespace checks.

Release preflight verified source/version/tag-collision and origin-authentication
checks. Installed caches remain dm-review 1.80.0 and Kernel 0.21.0, so release
preflight is blocked on those cache gates. No publication or synchronization is
claimed. The authorized PR source push is separate from release authorization.
The PR
remains draft because the required populated/prototype consumer coverage is
incomplete. A skipped hosted check is not clean CI.

## COMMANDS-RUN

- Authenticated `gh api` PR/review/check reads and Project 1 field/item reads;
  `git fetch origin main fix/ui-ready-03-compose-proof`; normal main merge.
- Zero-resource fixed-name reproduction; candidate Kernel-owned disposable root
  creation; the real Governance author-loop commands above; host browser tools;
  candidate readiness prepare/confirm/cleanup; guarded exact cleanup.
- Focused Docker, resource registry and runtime CLI unittests; repository
  discovery and UI readiness shell suites; full Kernel release gate.
- Canonical manifest/alias/index/dependency regeneration; full composition,
  generated-file/dependency/whitespace checks; release preflight.

No routed calls: paid cost $0; subscription participant calls 0. No provider
receipt, participant token count, or participant duration exists for this run.
