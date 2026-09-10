# Prototype fidelity and existing development-site reviews

Coordination snapshot: 2026-09-10. User requirements are authoritative; this
document records their implementation ownership and proof boundaries.
Parent program: [Assembly development improvements](astra-routing-and-system-rollout.md).

## Decision

Finish the existing `fix/prototype-review-defaults` work as **UI-DEFAULTS-01**.
It already spans the two reported problems; do not launch competing browser
or prototype rewrites. The [complete continuation prompt](prompts/ui-defaults-01.md)
is for its current owner or a fresh session after handoff.

At inspection, the branch was based on
`7e5475195ecab8c626b03ee79185d3b863852c82` with uncommitted changes in 18 files.
The implementation worktree is
`/home/ned/ai/depot-worktrees/prototype-review-defaults`.
This is ownership evidence, not verified completion. No implementation PR was
open at the initial authenticated check. Refresh these facts before continuing.

## What belongs where

| Owner | Responsibility |
|---|---|
| Assembly development | Make the prototype definitive for production Fixture/Baseplate UI; distinguish prototype-only implementation examples early |
| Pipeline | Carry exact source, structure/classes/components, Datastar interaction and persistence expectations into bounded execution prompts |
| dm-review | Select the established project site, follow its existing author loop, and compare source plus actual browser interactions |
| Assembly Coordinator | Include the exact prototype and development-site authorities when preparing an affected task |
| Project Scaffolder | Put a short development-site and prototype declaration into existing generated instruction entrypoints |
| Consumer repository | Own its actual URL, served checkout, build/status/restart procedure, authentication/setup references and current prototype mapping |
| Workflow Kernel | Retain existing evidence/resource mechanics; no new environment manager or domain catalog |

Design Machines strategy supplies the small-team/product constraint. Live Wires
and livewires-templ own reusable components, not the review site's lifecycle.
Keep the existing reference structure and concise owner-specific instructions;
do not create dependency cycles to centralize a paragraph.

## Definitive prototype contract

For a counterpart, reproduce the affected HTML hierarchy, wrappers, Live Wires
class strings, shared livewires-templ composition, literal copy and control
placement. Reuse source/components; do not reinterpret a screenshot or substitute
custom CSS. Implementation reuse is allowed even though prompt packets should
not duplicate whole templates.

Read Datastar attributes/signals and relevant handlers. Trace event, timing,
payload, response, feedback and saved state. Try each affected interaction in
both prototype and application at matching desktop/mobile states. Test
save/autosave, reload/revisit, keyboard/focus, cancel and validation when affected.
Label prototype stubs separately from real persistence.

Theme values and small pixel differences are acceptable. They do not waive
structure/classes/spacing or interaction comparison. Production authentication,
authorization, CSRF, storage and SDK wiring must remain correct; use only the
minimal necessary adaptation, with evidence. Other design changes require
explicit approved scope and start from the prototype. No counterpart requires
an inspected-source explanation rather than an invented redesign.

## Existing development-site contract

The normal review path is the established `[project-code].asmbly.app` site
serving the selected feature source from its designated checkout. Root
instructions or a directly linked runbook must identify the actual binding and
existing status/build/restart command. The private Project Codes catalog can
help find a code, but is never a shared workflow dependency. Its supplied link
was inaccessible to the public browser tool during this pass; no complete
catalog mapping was verified.

Local evidence names `dm006.asmbly.app` for the prototype and
`dm027.asmbly.app` for Governance. These are declared URLs, not current runtime
source proof. A Fixture's running Baseplate consumer may use a recorded source
checkout; inspect that binding before assuming the primary folder is served.

Switch the clean, available serving checkout with ordinary Git and rebuild
through its existing command. That maintenance is authorized by the requested
development/review task. Preserve unrelated changes and another session's work.
When the branch is already checked out elsewhere, a normal detached checkout of
the exact committed feature head is sufficient for a free serving checkout;
do not force duplicate branch checkout. Bind owned dirty-source reviews to the
actual fingerprint. A missing/stale binary is not repaired merely by changing HEAD.

Keep the same domain, service, data, configuration and topology. Do not change
DNS, Caddy, tunnels, ports or environment files. Do not reset shared data or
silently run incompatible migrations. A maintained service is not adopted into
review cleanup just because it was rebuilt. Leave the reviewed state available;
restore/rebuild only according to an agreed handoff.

Separate browser transport from target selection. Prefer T3, recover through
actual available host browser tools, and never use an unrelated attached tab as
project authority. New environments need a concrete test requirement, such as
simultaneous federation peers; development worktrees and unit-test containers
do not themselves require new browser instances.

## Evidence and remaining proof

- Authenticated main: `7e5475195ecab8c626b03ee79185d3b863852c82`.
- [PR #129](https://github.com/Design-Machines-Studio/depot/pull/129) merged exact
  head `52f4e2717dc1529c7bbd9cc39c3c06f79cc36da8`; main matches that feature tree.
  It added fixed-project author-loop support, not the new maintained-site default.
  Its [Governance canary](../docs/ui-ready-03-governance.md) used a disposable
  instance and did not complete all populated/prototype comparisons.
- Current source versions: dm-review 1.80.2, Kernel 0.22.0, Pipeline 1.67.0,
  Assembly 3.16.0, project-manager 1.14.0, project-scaffolder 1.9.4.
- The existing [prototype authority](../plugins/pipeline/references/prototype-authority.md)
  already requires source/rendered comparison, but lacks explicit save-event
  and persistence traces. Assembly's production rule is deep in its entrypoint.
- The merged [target discovery](../plugins/dm-review/skills/review/references/repository-browser-target-discovery.md)
  forbids rebuilding pre-existing targets. The prototype repository explicitly
  assigns browser review to its main checkout and existing container.
- User reports establish repeated drift. This pass did not reproduce or assign
  new product findings against a particular Fixture diff.

Acceptance for UI-DEFAULTS-01: no contradictory entrypoints; focused behavioral
contracts for maintained-site identity/retention and prototype interaction
parity; full composition on the implementation; one real comparison using
existing sites and designated demo data. Retain every P1/P2/P3 finding and honest
coverage gaps. Existing evidence is reused only when still exact.

## Sequence and completion

One active implementation owner; no parallel writer on these plugin surfaces.
The general SKILLS-01/02/03 reduction passes must account for this file ownership.
The merged generator and #129 are no longer prerequisites awaiting completion.

After exact implementation review: proper PR, then separately authorized merge,
tags, Claude/Codex cache synchronization and installed-consumer proof. Consumer
instruction corrections, if needed, get repository-owned PRs after inspecting
actual declarations; no blanket generator-merge gate.

This coordination PR changes plans/prompts only. It does not change plugin
behavior, consumer checkouts, running services or installed caches.
