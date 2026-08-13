---
name: pipeline-failure-modes
description: Use when running, debugging, hardening, or reviewing a pipeline or dm-review run in this repo -- covers the 19 observed production failure modes with their root causes and hardening measures, the post-implementation verification checklist, and the postmortem index. Load before starting a pipeline run, when a run misbehaves, or when writing a postmortem.
---

# Pipeline Failure Modes and Post-Implementation Checklist

## Known Pipeline Failure Modes

These failure patterns have been observed in production pipeline runs. Each has a documented root cause and a corresponding hardening measure in the pipeline plugin.

1. **Pipeline bypass:** Claude skips the pipeline and manually implements features. The pipeline's gates, reviews, and visual checks are all skipped. Hardening: "Do Not Manually Replicate" section in `pipeline.md`.
2. **Silent MCP fallback:** The execution-orchestrator continues without browser verification when Playwright/Chrome DevTools MCP is unavailable. UI chunks ship without visual testing. Hardening: MCP pre-flight check in `execution-orchestrator.md`.
3. **Code-only adversarial review:** The plan-adversary reviews code patterns but not visual/rendered output. UI chunks pass review without visual acceptance criteria. Hardening: Visual Verification Readiness perspective in `plan-adversary.md`.
4. **Evidence-free assertions:** "Requirements covered" claims are assertions without screenshots, computed style comparisons, or other evidence. Hardening: Evidence requirement in `pipeline.md` Phase 7.
5. **Missing visual diff protocol:** When the user says "these should be visually identical," no protocol exists for getComputedStyle comparison. Hardening: Visual Parity Diff step in `execution-orchestrator.md`.
6. **dm-review-loop not invoked:** The caller never runs dm-review-loop on the final result, trusting the orchestrator's self-report. Hardening: Caller Visual Verification section in `pipeline.md` Phase 7.
7. **Prompt quality degradation:** Across large chunk sets, later prompts have less detail, fewer acceptance criteria, and weaker visual specifications. Hardening: Prompt Quality Parity Check in `promptcraft SKILL.md`.
8. **Silent browser-verification-skipped merge claims:** The orchestrator emits "ready to merge" when visual verification was skipped. Browser availability is a verification-evidence status, never an execution mode. Hardening: required browser-evidence status on every UI chunk receipt, browser-recovery escalation ladder (evidence capture -> primary restart -> alternate engine -> human help) in `execution-orchestrator.md`, forbidden-phrases list, and `BLOCKED PENDING CALLER VERIFICATION` merge recommendation; Caller Verification Checklist (screenshot + runtime eval + cardinality) in `pipeline.md` Phase 7.
9. **Multi-chunk rename atomicity:** Identifiers renamed across non-adjacent chunks produce a broken window under orchestrator parallelization. Hardening: Rename Atomicity Check in `plan-adversary.md`.
10. **Append-only revision residue:** Round N amendments coexist with superseded content. Hardening: Append-Only Purge Check + Final Audit + imperative verb discipline (`REPLACE`/`DELETE`/`INSERT`/`RENAME`) in `plan-adversary.md`.
11. **Dev-mode module loader desync:** New JS module ships without updating the dev-mode module map, loads 404 in browser. Hardening: Step 0c Module-Loader Pre-Flight in `execution-orchestrator.md`.
12. **P3 deferral drift:** P3-only returning CLEAN silently compounds tech debt. Hardening: zero-deferral policy as default in `dm-review/skills/review/references/severity-mapping.md` and command files; `--allow-defer-p3` opt-in requires written justification + tracking destination.
13. **Brittle line-number references:** Prompt references to `file:line` become stale as interstitial chunks edit files. Hardening: Phase 3e Stable Anchors Audit in `promptcraft SKILL.md` (prefer function/templ names over line numbers).
14. **Silent mid-execution ambiguity:** A subagent encounters a chunk prompt that admits multiple reasonable interpretations, picks one silently, and ships. The brainstorming skill catches pre-plan ambiguity and plan-adversary catches structural ambiguity, but neither covers implementation-time micro-decisions. Hardening (pipeline v1.10.0): Ambiguity Protocol block in `promptcraft/references/prompt-template.md`; Ambiguity Handling section in `execution-orchestrator.md` (autonomous-mode commit trailers `Chose:` / `Rejected:` + `ambiguity_resolved:` receipt flag); Ambiguity surfacing perspective in `plan-adversary.md` Sprint Contract Negotiation. Three-layer defence with "cheapest catch first" wording aligned across all three locations.
15. **External LLM provider failure without retry:** the OpenRouter runner fails and dm-review immediately classifies the agent as failed without a trusted fallback. Core agent coverage gaps go undetected. Hardening: Phase 4.5 retries coding lanes on Codex before applying failure policies; Claude is reserved for explicitly non-coding lanes.
16. **Orphan worktree and branch residue:** a run that fails, or that exits through a non-terminal gate answer ("Create PR", "Give feedback"), leaves `.worktrees/pipeline/**` paths and `pipeline/**` chunk branches behind. The next run collides on `git worktree add`, and `git branch -d` failures were swallowed by `2>/dev/null` so the receipt claimed refs were cleaned that still existed. Hardening (pipeline v1.26.0, dm-review v1.41.0): `plugins/dm-review/skills/review/references/repo-cleanup-contract.md` defines a ref registry, a safe-to-delete decision table, feature-branch protection (never deleted without `merge-base --is-ancestor` proof into `main`/`origin/main`), blocked-removal reporting, and a mandatory `## Branch & Worktree Inventory` receipt block. Wired into orchestrator Steps 0e/3b/3j/5b, all three pipeline commands, and dm-review Phase 8. Enforced by `tools/validate-workflow-contracts.sh`.
17. **Empty PR review threads read as "no findings":** formal review threads on Baseplate PRs are usually empty; the durable signal lives in checked-in receipts, merge-commit bodies, closed issues, and verification files. A reviewer that checks `gh pr view --comments` and stops concludes the work was unreviewed. Hardening (dm-review v1.41.0): Phase 1b Evidence Source Fallback in `plugins/dm-review/skills/review/SKILL.md` walks four evidence sources in order and reports which one was used; Phase 4.5 generalized from "external LLM failed" to "lane unavailable" (external runner, Codex CLI absent, evidence absent), and a skipped lane must appear in Coverage Gaps.
18. **Hand-rolled JS where Datastar suffices, and inert Pro attributes:** agents reach for `localStorage`, `matchMedia`, `ResizeObserver`, `scrollIntoView()`, `navigator.clipboard`, and `Intl.*` because Depot never documented Datastar Pro (Context7 has no entry; the repo is private). Worse, a Pro attribute whose plugin is missing from the vendored bundle is **inert** -- a silent no-op that reads as correct in review. Hardening (assembly v3.8.0, pipeline v1.26.0, dm-review v1.41.0): `plugins/assembly/skills/development/datastar-pro.md` is the self-contained reference (10 attributes, 3 actions, JS substitution table, bundle-presence rule, transcribed from the plugin sources at v1.0.2); promptcraft Phase 3o Datastar-First Gate; plan-adversary Datastar-first check; `Hand-Rolled JS Where Datastar Suffices` (P2) and `Inert Pro Attribute` (P1) findings in dm-review.
19. **Kind-based browser gates on non-rendered files:** the closed filename heuristic correctly classifies any `.html` chunk as UI and any `main.go` wiring chunk as Integration, but those kinds were also treated as proof that a rendered product surface existed. Unserved planning HTML and non-HTTP CLI entry points then required fabricated routes, personas, visual criteria, and browser evidence. Hardening (pipeline v1.48.0): every new chunk independently declares `renderedSurface: required|not_applicable` plus a concrete rationale; visual/Datastar/persona/browser gates use that field while `kind` retains review/provider meaning; mixed or uncertain scope fails closed to `required`; the plan adversary audits every N/A rationale; legacy manifests default conservatively. See `docs/post-mortems/2026-08-13-pipeline-rendered-surface-applicability.md`.

See `docs/post-mortems/` for detailed root cause analysis.

## Post-Implementation Checklist

After any pipeline run or manual feature implementation, verify:

- [ ] All affected pages render without console errors
- [ ] Screenshots taken at desktop (1440px) and mobile (375px) for every UI change
- [ ] Visual output compared to design spec or brainstorm mockup (if one exists)
- [ ] dm-review-loop run on the final branch (not just per-chunk quick reviews)
- [ ] Zero pending P3 findings OR explicit `--allow-defer-p3` with justification + tracking ID for each (zero-deferral default)
- [ ] Requirements cross-check with EVIDENCE type for each requirement (screenshot, build pass, computed style)
- [ ] No "visually identical" requirements left unverified (visual diff protocol applied)
- [ ] If any UI chunk receipt carries a browser-evidence status other than verified (browser unavailable, alternate engine, or human-help escalation), the 3-item Caller Verification Checklist is complete with attached evidence
- [ ] Repository cleanup phase ran; receipt carries a `## Branch & Worktree Inventory` with every created ref dispositioned, every kept/blocked ref carrying a follow-up command, and a clean `git status --porcelain`
- [ ] Run receipt carries either the `run-cost-summary.json` artifact path or a literal `run-cost-summary: skipped (<reason>)` line; silence fails the checklist
- [ ] Cost summary has at least one populated `lanes[]` row, or the receipt states why every lane is `unavailable` -- a structurally valid artifact with zero measured lanes is not evidence of measurement
- [ ] Feature branch preserved unless `git merge-base --is-ancestor <branch> origin/main` proves it landed
- [ ] UI work uses Datastar/Datastar Pro attributes rather than hand-rolled JS; every Pro attribute has a recorded bundle-presence check
- [ ] Session recorded to ai-memory
- [ ] Postmortem written if any failure patterns were observed

## Postmortems

Pipeline failure analysis documents live in `docs/post-mortems/`:

- `2026-04-07-pipeline-ui-refinement-postmortem.md` -- 6 failure modes from Assembly UI refinement run
- `2026-04-10-pipeline-visual-testing-postmortem.md` -- 7 failure modes from Assembly pipeline bypass and visual testing gaps
- `2026-08-13-pipeline-rendered-surface-applicability.md` -- kind/applicability conflation made non-rendered HTML and CLI chunks impossible to approve

These postmortems inform the Known Pipeline Failure Modes section above and the hardening measures in the pipeline plugin.
