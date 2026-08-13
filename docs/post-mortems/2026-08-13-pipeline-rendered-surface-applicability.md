# Post-Mortem: Kind-Based Browser Gates Blocked Non-Rendered Work

**Date:** 2026-08-13
**Project:** Assembly Baseplate FIX-01 prompt generation
**Pipeline version:** 1.47.1
**Outcome:** Phase 5 correctly blocked execution, but only after two prompt-pack revisions exposed a contradiction in Pipeline's manifest contract.

## What Happened

Promptcraft used a closed filename heuristic to classify any `.html` change as
`kind: ui` and any `main.go` change as `kind: integration`. Downstream gates
then treated both kinds as proof that a rendered product surface existed and
required visual criteria, persona/browser cases, Datastar checks, a dev server,
and Playwright evidence.

FIX-01 contained two truthful counterexamples:

- a planning `work-paths.html` artifact restored byte-for-byte from `main`; it
  is not served by Assembly; and
- `cmd/sdk-verifier/main.go`, a non-HTTP CLI entry point with no route or page.

Changing either `kind` would have violated the installed classification rule.
Keeping the correct kinds made the prompt pack impossible to approve because
no authoritative route, persona, or browser case existed. Inventing them would
have produced false evidence.

## Root Cause

One field carried two independent meanings:

1. code/review classification and provider routing; and
2. rendered-output/browser-evidence applicability.

Filename and wiring heuristics are conservative and useful for the first
meaning, but cannot determine the second. The downstream rules silently
assumed `ui|integration => rendered product surface`, so a syntactic trigger
became an impossible runtime obligation.

## Repair

Pipeline now keeps `kind` unchanged and adds an independent closed per-chunk
classification:

- `renderedSurface: required|not_applicable`
- `renderedSurfaceRationale: <non-empty specific explanation>`

New manifests require both fields. `required` applies to served routes,
rendered output, browser interactions, and visual/browser acceptance criteria.
`not_applicable` is accepted only when every UI/integration syntactic trigger
is demonstrably unserved or non-rendering. Mixed or uncertain scope fails
closed to `required`.

Promptcraft, the plan adversary, execution orchestrator, `/pipeline`,
`/pipeline-prompts`, and `/pipeline-run` now use this field for visual,
Datastar, persona, browser, dev-server, and caller-verification obligations.
Workflow Kernel 0.15.0 accepts the same independent applicability at its
persona gate; a zero-required-surface run binds a null profile pair and empty
case arrays instead of manufacturing a profile. `kind` continues to control
review depth and provider routing.

Legacy manifests remain conservative: missing fields default UI/Integration to
`required` and Logic/Trivial to `not_applicable`, with
`rendered_surface_defaulted=true` in receipts. Supplying only one field is
invalid.

## Prevention

- Treat applicability and implementation classification as separate axes.
- Require explicit, adversarially checked rationale for every not-applicable
  evidence gate.
- Never manufacture routes, personas, browser cases, or visual criteria to
  satisfy a filename heuristic.
- Keep contract anchors in `tools/validate-workflow-contracts.sh`, including
  negative checks that the retired kind-only browser triggers do not return.

## Validation

The workflow-contract validator checks the closed fields, fail-closed mixed
scope rule, unserved HTML and non-HTTP CLI examples, adversarial rationale
audit, rendered-surface browser preflight, empty N/A case handling, and absence
of the retired kind-only browser triggers. Full Depot composition validation is
required before release.
