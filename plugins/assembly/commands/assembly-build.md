---
name: assembly-build
description: Build and test Assembly through the repository verification planner
argument-hint: "[optional: test, generate, build, focused, race, or full]"
---

# Assembly Build

Plan and execute Assembly verification through Workflow Kernel. The canonical
Baseplate defaults live in
`plugins/assembly/skills/assembly-build/references/assembly-baseplate-verification-profile.json`;
do not reconstruct or guess Go commands from this document.

## Resolution and precedence

1. Resolve the compatible Workflow Kernel runtime using its sanctioned runtime
   resolver. If it cannot be resolved, stop with `unavailable` and explain how
   to install or refresh the Workflow Kernel plugin.
2. Look for an explicit project repository-verification profile. A valid
   project profile outranks the Assembly profile. An incomplete or invalid
   explicit project profile is blocking; do not silently fall back.
3. Use the Assembly Baseplate profile only when the repository has the declared
   Baseplate identity (`go.mod`, `docker-compose.yml`, and `cmd/assembly`). The
   profile outranks heuristics. An unmatched repository is `unavailable`.
4. Validate the selected profile with Workflow Kernel's strict
   repository-verification profile contract, bind the current repository state,
   changed paths/packages, risk inputs, and requested lane IDs, then derive the
   verification plan.
5. Execute only selected, runnable `argv` arrays exactly as returned. Never join
   them into a shell string, interpolate environment values, or substitute a
   generic package path.

## Modes

| Argument | Required planner lane(s) |
|---|---|
| `generate` | `templ-generate` |
| `build` | `build-assembly` |
| `focused` | changed-package or explicitly declared focused lane |
| `test` | `full-test` unless an explicit focused scope was supplied |
| `race` | `race-test` |
| none / `full` | generator, build, and planner-selected focused/full lanes; add higher tiers when risk requires them |

The profile's Go lanes use Docker-only safe argument arrays, `-tags=dev`, and
`-count=1` for fresh focused/full/race evidence. Its application package is
`./cmd/assembly`.

## Compose runtime choice

The plugin profile deliberately uses ephemeral `docker compose run --rm
--no-deps app`. A project profile may declare `docker compose exec app` only
when current runtime evidence proves the intended Compose project, service
`app`, profile digest, and state generation are running and match this plan.
Absent, stopped, stale, or mismatched service evidence cannot authorize
`exec`; use a declared ephemeral lane or return `unavailable`.

## Evidence boundaries

- Focused package selection comes from changed-package selectors or explicit
  project declarations. A Go change does not automatically force local race.
- Full, race, security, container, browser, accessibility, PR, push, schedule,
  merge-group, and post-merge lanes retain separate authority. A passing PR
  lane cannot satisfy Baseplate's non-PR race or container-scan evidence.
- UX task frontmatter under `tests/ux/tasks/` is authoritative for runnable
  status, persona, route, authentication, expected outcome, optional viewport
  and engine, and screenshot points. An absent task directory is `not_declared`;
  malformed present declarations are blocking. `coverage-matrix.md` is not
  declaration authority.
- Browser evidence follows the shared ladder: preserve the failed attempt, quit
  the primary browser, prove a fresh primary session and retry, try a different
  configured engine, then stop with `human_help_required`. Curl is diagnostic
  only and never browser proof.

## Failures

Return the selected lane ID, status, stable reason, exact safe argv (when
runnable), and bounded failure evidence. If Workflow Kernel, the repository
profile, project declarations, prerequisites, or required remote authority are
unavailable, stop with actionable `unavailable` or blocking evidence. Never run
the former hardcoded `exec`, `./cmd/api`, untagged, or cached fallback commands.
