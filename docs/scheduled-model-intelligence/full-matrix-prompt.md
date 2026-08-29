# Depot full-matrix portfolio audit — T3 prompt

Run this task on the first Sunday of each month at 05:30 Asia/Makassar. It
replaces that week's matrix-maintenance run. Select GPT-5.6 Sol in T3 for the
controller session; do not change the global T3 model configuration.

You are the benchmark controller, not a benchmark candidate or subjective
judge. Run on NED as `ned`. Treat `/home/ned/ai/depot` and the selected
Assembly Baseplate checkout as read-only evidence sources. Never clean, reset,
stash, commit, switch branches, or remove files from either source checkout.

Create a clean isolated Depot worktree from refreshed `origin/main`. If it is
unexpectedly dirty, abandon it and create another one. Store raw evidence only
under `/home/ned/benchmark-results`; never commit provider transcripts,
key-state files, private source excerpts, or credentials.

Use the catalog, versioning, privacy, evidence interpretation, validation, and
no-auto-merge rules in `daily-prompt.md` and `weekly-prompt.md`. The portfolio
contract is
`plugins/openrouter/skills/openrouter-delegate/references/depot-role-portfolio.json`.

## 1. Discover the complete portfolio

Refresh the live OpenRouter catalog, then load:

- `model-matrix.json` for exact OpenRouter catalog identities;
- `role-policy.json` for every role and ordered native/OpenRouter candidate;
- `depot-role-benchmark-suite.json` for runnable closed cases;
- `depot-role-portfolio.json` for prototype cases, gaps, and cadence;
- the latest aggregate model-intelligence and production evidence.

Do not copy a model list into the run. Build it from these live inputs. Record
the exact source commits and catalog observation time.

Construct the complete model-by-role grid. Every cell receives exactly one
classification:

- `ineligible` with a concrete provider, security, family, capability, context,
  or availability reason;
- `catalogued-untested`;
- `stale`;
- `screen-failed`;
- `screened`;
- `benchmarked`;
- `canary`;
- `incumbent`; or
- `promotion-blocked` with the failed gate.

An ineligible cell is evaluated when its exclusion is recorded. Never spend
money on a pairing that policy could not route. Invocation-specific family
independence must remain conditional unless an implementer-family receipt is
present.

## 2. Seal the run before calls

Write `$RUN_ROOT/benchmark-plan.json` with:

- run date, mode, source commits, suite and portfolio IDs;
- catalog receipt and matrix snapshot;
- every role and candidate cell;
- eligibility and exclusion reason;
- chosen case revision and all prompt/evidence/scorer hashes;
- screen order, effort, billing, and estimated calls;
- one-attempt screen and three-attempt advance rules;
- provider guardrail state and paid-stop policy;
- every role lacking a runnable sealed case.

Materialize Baseplate evidence only from an exact clean revision and the
checked-in source selectors. Preserve ordered excerpt boundaries and hashes in
the private run directory. If a prototype's complete prompt/evidence/scorer
contract cannot be reproduced, classify it as unsealed and do not call it.

For current framework or API evidence, use Context7 and official sources. Save
source identity, exact version or revision, retrieval date, and excerpt hash.
Generic current documentation is not proof for another exact version.

The configured OpenRouter key and current provider-side guardrails control
paid availability. Record the returned key state. Track provider-reported
billed cost after every paid call and stop on provider refusal. Do not invent a
local hard cap or treat an account-counter delta as attributable spend.

## 3. Screen broadly, deepen selectively

For every eligible cell with a sealed applicable case, run one attempt using:

- identical sealed prompt and evidence bytes for comparable candidates;
- exact requested identities and admitted native aliases;
- no model fallback;
- same-model provider fallback permitted and receipted;
- unique immutable result directories;
- raw machine-consumed output as the scoring input.

Advance to attempts two and three only when attempt one:

- completed and parsed in the required envelope;
- satisfied every mandatory closed assertion;
- retained the requested/served identity and no model fallback;
- remained plausible on duration and provider-billed cost.

Retain failures, refusals, timeouts, malformed output, identity mismatches, and
incomplete directories. Never rerun into the same directory or repair output
after the fact. Diagnostic retries use a new directory and do not become
promotion evidence.

## 4. Score and report per axis

Closed correctness is deterministic. A candidate never scores itself, and
another model does not replace a closed scorer. Subjective axes may be retained
separately, but never collapsed with closed quality into one opaque leaderboard.

A scorer correction is permitted only when the scorer contradicts the written
sealed task. Preserve its original bytes and scores, hash the corrected scorer,
rescore unchanged raw outputs, and mark the old scores non-comparable. Never
change the task or make another paid call to rescue a score.

Report separately:

- success rate and all failures;
- deterministic quality per case;
- median duration;
- prompt, completion, reasoning, and cache tokens when reported;
- deterministic input bytes as a separate native measurement unit;
- provider-billed OpenRouter cost;
- native subscription marginal cost;
- native API-equivalent cost, explicitly labeled as an estimate;
- context and capability coverage;
- family diversity;
- production completion, fallback, retry, first-pass validation, rework, and
  finding contribution;
- missing evidence that prevents a comparison.

Quality per token or dollar is valid only when both numerator and denominator
have complete compatible coverage.

## 5. Produce portfolio findings

For every role, report:

- incumbent and complete ordered ladder;
- best deterministic quality and reliability;
- subscription-first and paid alternatives;
- best eligible different-family reviewer;
- latency, token, cost, context, and capability tradeoffs;
- evidence freshness and confidence;
- missing cases or instrumentation;
- exact retain/change rationale.

For every model, report:

- strongest, competitive, failed, prohibited, and untested roles;
- unique capabilities and redundant coverage;
- cost, latency, context, and reliability profile;
- whether continued matrix inclusion is justified.

For the portfolio, report:

- roles with no proven candidate or only one viable family;
- incumbents lacking three-attempt applicable-case evidence;
- production-canary gaps;
- stale, untested, redundant, obsolete, or unavailable entries;
- missing tool-use, multi-turn, repository-edit, validation, browser,
  accessibility, and finding-contribution coverage;
- subscription-capacity preservation opportunities;
- places where a paid model proves a material advantage;
- role gaps, including whether frontend work still lacks an explicit role.

## 6. Guard routing decisions

Screening is nomination evidence only. A controlled promotion requires three
retained successful attempts on every applicable closed case, no model
fallback, no case median below 90, compatible claimed-axis coverage, and every
family/capability invariant.

Prefer an included-subscription native incumbent within the quality and
reliability floor unless a paid challenger proves a material latency, context,
capability, or capacity-preservation advantage. A new paid model enters only as
a later canary rung. Moving to role head additionally requires at least five
attributable production attempts with acceptable completion, fallback, retry,
and first-pass validation evidence.

Security models remain confined to security work. `anthropic/*` remains
forbidden on OpenRouter. Missing evidence is never scored as zero or converted
into a promotion. When any gate fails, preserve the evidence and name the gate.

## 7. Commit only durable evidence

Commit:

- changed benchmark contracts, source selectors, deterministic scorers, and
  tests;
- complete eligibility, case-coverage, and evidence-freshness grids;
- content-free aggregate reports and routing-decision ledger;
- prompt/evidence/scorer hashes and source revisions;
- matrix or policy changes only when every gate passes.

Do not commit raw prompts containing private excerpts, raw candidate outputs,
provider receipts, key-state files, stderr, credentials, or large token traces.

Run the daily and weekly validations plus:

```sh
./tools/test-openrouter-role-benchmark.sh
./tools/test-model-router.sh
./tools/validate-workflow-contracts.sh
./tools/validate-composition.sh --all
git diff --check
git status --short
```

If validation fails, do not commit. Stage only intentional files; never use
`git add -A`. Never merge automatically.

Always return the full grids, per-role and per-model findings, measured spend,
subscription and API-equivalent views, every failed gate, validation, branch,
commit, and exactly one next benchmark/instrumentation improvement. End with
`no routing change justified` whenever no candidate clears every gate.
