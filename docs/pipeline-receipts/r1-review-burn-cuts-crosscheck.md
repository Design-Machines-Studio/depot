# Final Requirements Cross-Check

Feature: r1-review-burn-cuts
Date: 2026-08-08
Branch: bionic/r1-review-burn-cuts
executionMode: full_cli
isolationStrategy: per-chunk-worktree
Contract: sha256:5e696da32a9a6dd8d18a2a3a353deb942467bb949a5a72689bb8c88f8a7dc7ca revision 1

| # | Requirement | Addressed In | Evidence |
|---|-------------|--------------|----------|
| REQ-01 | Selective lane re-run on iteration 2+, security signoff never narrowed, CLEAN only from full fan-out, kill switch fails open, receipts list re-run vs skipped, R0 baseline committed | 7e3d8d1 | grep:`grep -c "A CLEAN verdict may only ever be issued by a full fan-out" SKILL.md commands/dm-review-loop.md` -> 2 and 2. grep:`grep -c DM_REVIEW_LOOP_FULL_FANOUT` -> 3 and 3. grep:`grep -n "in EVERY narrowed lane set unconditionally"` -> present. build:passed `./tools/validate-composition.sh --all` exit 0. Baseline: `docs/cost-baselines/2026-08-07-r0-measurement-backbone.json`, schema-validated 10/10 required keys, 5 lanes, cost_usd 2.996011 |
| REQ-02 | review_tier required receipt field with 3 values plus why-line, suite dispatch named a violation, PIPELINE_FULL_TIER_REVIEW fail-open, validator anchor pinned | 4af8633 | test:negative-test-anchor -- mutating the pinned sentence drove `bash tools/validate-workflow-contracts.sh` to exit 1 with `FAIL execution orchestrator requires the review_tier chunk-receipt field`; restored -> exit 0, tree clean. Independently reproduced by the orchestrator, not just claimed |
| REQ-03 | Extension-triggered lanes sliced, closed full-diff list never scoped, diff_scope required, DM_REVIEW_FULL_DIFF and slice failure fail open, migration-validator in full mode with registry row | de70eea | grep:`grep -c "Recording each lane (mandatory, one call per attempt)"` -> 1, and the block is byte-identical to base (51 lines, `diff` clean). grep:`grep -n "migration-validator" agent-registry.md` -> rows 54 and 76. Stale "(security-auditor covers SQL)" note: 0 matches. build:passed composition exit 0 |
| REQ-04 | Browser trio compressed with parity table, zero dropped checks, recovery ladder and lens separation intact, frontmatter unchanged | a87467c | Two independent parity audits both returned `PARITY: INTACT` with 0 P1 (GPT-5.6 Terra via OpenRouter, and Fable). Frontmatter byte-identical in all three files. Heading sets diff-identical to base. Sizes 67,928 -> 55,089 B. Full evidence: `plans/r1-review-burn-cuts/receipts/04-parity-table.md`. Target 40,000 B NOT met -- the prompt's sanctioned stop-report path, blocking checks named |
| REQ-05 | model-matrix.json as machine-readable source of truth, model-selection.md declares authority plus refresh protocol, three drift checks, matrixReceipt policy | 2058e78 | test:negative-tests -- all three independently reproduced by the orchestrator: quality_rank drift -> exit 1; routing-policy slug absent from matrix -> exit 1; snapshot-date divergence -> exit 1; each restored to exit 0. Plus a fourth added at review: matrix Terra rank 94 -> 99 -> exit 1 `DRIFT openai/gpt-5.6-terra ... native twin`. grep:`11 models, snapshot 2026-08-03, 0 anthropic slugs` |
| REQ-06 | subscriptionFirst with both windows and unknown-as-at-threshold, probe parsers pinned with pluggable rails, operator profile schema plus example gitignored, family-independent second opinion and sign-off, two validator anchors | 0e94574 + b5327a0 + 5c4ce43 + 41c7b82 + 96dbf5c | Implementation anchors and live probe fixtures passed, but run-level sign-off is **NOT SATISFIED**: Claude implemented 01-05 and Codex/OpenAI implemented 06; the full-diff Codex and Terra reviewers were OpenAI-family for chunk 06, while Kimi did not run full-diff. See the durable coverage-gap section in `r1-review-burn-cuts.md`. |

## Regressions (REG-*)

| ID | Statement | Evidence |
|----|-----------|----------|
| REG-COVERAGE | Final verification pass never narrowed | grep-verified sentence present in both loop files; CLEAN-promotion pass added so a narrowed zero-finding iteration must re-run full before reporting clean |
| REG-KILLSWITCH | Every coverage-reducing mechanic fails OPEN and records why | 4 switches audited at the final gate; tier selection had no fail-open rule and one was added (historical run-local todo 145, uncommitted); scoping default was inverted from fail-closed to fail-open (historical run-local todo 146, uncommitted) |
| REG-SECURITY | Security lanes never scoped; sign-off stays full-diff and required | Contract invariant remains present, but this historical run did not satisfy the independent-family full-diff sign-off and is recorded `REVIEW INCOMPLETE`; no same-family result is promoted to completion |
| REG-ZERODEFER | Every finding disposition is explicit | 53 findings raised across all gates; 50 fixed, 2 deferred with specific technical justifications, and 1 rejected with justification, matching the durable per-chunk table in `r1-review-burn-cuts.md` |
| REG-VERSIONSYNC | Every changed plugin bumped in plugin.json and marketplace.json | dm-review 1.52.0->1.56.0, pipeline 1.40.0->1.42.0, openrouter 1.8.0->1.9.0, each verified across `.claude-plugin`, `.codex-plugin`, and `marketplace.json` |
| REG-ASCII | Added lines ASCII only | `git diff main..HEAD | grep '^+' | LC_ALL=C grep -c '[^ -~\t]'` -> 0 |
| REG-EMISSION | Generated emission paragraphs and Recording blocks survive | `bash tools/sync-run-cost-summary-contract.sh --check` -> `ok 11 consumers match`; Recording block byte-identical (51 lines) |
