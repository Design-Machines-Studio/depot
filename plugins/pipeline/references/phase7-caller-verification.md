# Phase 7 caller verification (rendered surfaces)

Loaded by `/pipeline` Phase 7 only when a `renderedSurface: required` chunk ran.

## Caller Verification Checklist

Complete ALL THREE checks; record evidence in the delivery report.

- [ ] **(1) Screenshot the selected viewports.** Cover each selected affected
  case at its declared viewport. Add at most one justified baseline viewport
  when it can detect a realistic adjacent regression. Save to
  `plans/<feature-slug>/screenshots/phase7-*.png`.
- [ ] **(2) One runtime state eval per new JS module.** For each chunk that added a JS module, run `browser_evaluate` with a snippet like `typeof window.<globalName>` or `typeof document.querySelector('<selector>').dataset.<attr>` to confirm the module attached at runtime (curl confirms the file responds; `browser_evaluate` confirms it ran). Record the snippet and result.
- [ ] **(3) Cardinality check per AC containing quantity language.** For every acceptance criterion containing "exactly N", "no duplicate", "only one", "should replace", or "instead of", run a counting `browser_evaluate` (e.g. `document.querySelectorAll('button[type=submit]').length`): "Post comment should REPLACE the old button" passes only when count is 1, not 2.

Use the complete verification profile selected from project configuration and `tests/ux/` declarations: persona, scenario, concrete route, browser engine, viewport, authentication state, and expected evaluation. `not_declared` is valid only when declarations are absent; a present but incomplete declaration is blocking. Any required check that cannot initially run because the browser, dev server, authentication fixture, route binding, or verification profile is unavailable MUST preserve the failed attempt and follow the evidence-preserving ladder: quit the browser process/session, launch a demonstrably fresh primary session and retry, try a genuinely different configured browser/engine, then stop with blocked `human_help_required`, the exact missing case IDs, and a request that the user restore the missing prerequisite. Do NOT deliver as "ready" or convert the case to skipped, deferred, degraded, or proceed-without-browser. Curl is diagnostic only and never produces `BROWSER_VERIFIED`.

If `final-review-browser-evidence.md` already produced an accepted packet for
this exact candidate and selected case set, use its bounded screenshots,
runtime observations, and cardinality observations here instead of recapturing
them. Any caller check absent from that packet still runs once. Never select a
packet by timestamp or `latest` lookup.

### Orchestrator Blind Spots (read before starting Phase 7)

The execution-orchestrator verifies per-chunk, but `curl` + `grep` + HTML regex CANNOT observe:

- **JS runtime state** -- whether `window.assemblyPopup` actually attached, whether an event listener bound, whether a module imported.
- **Visual cardinality** -- whether a button appears "exactly once" vs duplicated via a second code path that independently satisfies the same DOM assertion.
- **Layout regressions** -- whether a neighboring card got pushed off-screen by your margin change.
- **Duplicate elements** -- an AC saying "Post comment button is present" passes when there are two Post comment buttons as long as at least one is there.

Any `renderedSurface: required` receipt without complete browser evidence is blocked, regardless of host execution mode. Required browser cases run the recovery ladder below and cannot be delivered until complete or `human_help_required` is resolved. A validated `not_applicable` receipt carries its rationale and requires no fabricated browser evidence.

### Ambiguity Protocol Check (pipeline v1.10.0+)

The three-layer ambiguity defence added in v1.10.0 leaves an audit trail. Inspect each chunk's commit and receipt:

- **Commit trailers** -- each chunk commit may contain two trailers: `Chose: <interpretation>` and `Rejected: <alt-1>; <alt-2>`. Extract with `git log <featureBranch> --format=%B | git interpret-trailers --parse --only-trailers` or grep. Trailers are emitted only when a subagent had to pick between defensible interpretations in autonomous mode.
- **Receipt flag** -- chunk receipts may include `ambiguity_resolved: true` with a one-line summary. Cross-check against the commit trailers.
- **If trailers or the flag are present,** review the chosen path. If the chosen interpretation conflicts with what the user actually wanted, this is a Phase 7 gap -- fix inline on the feature branch, then re-run `/dm-review-quick` on the affected chunk.
- **If neither signal is present,** either the chunks were unambiguous OR the subagents silently picked. The plan-adversary's scope review should have caught the latter at Phase 5; if you suspect it didn't, sample one or two chunks' rendered output against the approved Key Requirements before approving merge.
