# Fresh-session execution prompts

**Run [01 — Depot instruction defaults](01-instructions-01.md) first, using GPT-5.6 Luna High in Codex.** Return its PR and verification result to the planning coordinator before starting a dependent project prompt.

Every linked file contains one complete copy-paste prompt with a model recommendation, exact prepared base, fresh-worktree rules, ownership, scope, acceptance, focused checks, delivery requirements and a proper PR handoff. Nothing requires replacing part of an earlier prompt. The execution text remains provider-neutral; the model recommendation is outside its copy block.

Project prompts inspect repository-owned local skills, agents, hooks and settings as well as AGENTS.md and CLAUDE.md. Shared plugin changes stay in Depot; no prompt edits an installed plugin cache as source.

## Project instruction prompts

| Prompt | Repository | Recommended start | Run condition |
|---|---|---|---|
| [INSTRUCTIONS-01](01-instructions-01.md) | depot | gpt-5.6-luna / high / Codex | Run first |
| [INSTRUCTIONS-02](02-instructions-02.md) | assembly-baseplate | gpt-5.6-luna / high / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-03](03-instructions-03.md) | assembly | gpt-5.6-luna / high / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-04](04-instructions-04.md) | assembly-floor | gpt-5.6-luna / high / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-05A](05-instructions-05a.md) | assembly-fixture-jig | gpt-5.6-luna / low / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-05B](06-instructions-05b.md) | livewires-templ | gpt-5.6-luna / low / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-05C](07-instructions-05c.md) | assembly-governance | gpt-5.6-luna / high / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-06](08-instructions-06.md) | foreman | gpt-5.6-luna / high / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |
| [INSTRUCTIONS-07](09-instructions-07.md) | assembly-demo | gpt-5.6-luna / low / Codex | After INSTRUCTIONS-01 is merged; recheck active ownership |

Baseplate, prototype Assembly, Floor, Jig, livewires-templ and Governance each have their own prompt. Foreman has separate instruction and runtime prompts. Demo is an audit-first prompt: if already aligned, it produces a no-change result rather than an empty PR.

## Shared skills and supporting tasks

| Prompt | Scope | Recommended start | Run condition |
|---|---|---|---|
| [SKILLS-01](10-skills-01.md) | depot | gpt-5.6-luna / high / Codex | After shared defaults and current consumer authority |
| [SKILLS-02](11-skills-02.md) | depot | gpt-5.6-luna / high / Codex | After the preceding skill result is reviewed |
| [SKILLS-03](12-skills-03.md) | depot | gpt-5.6-luna / high / Codex | After #129 finishes its shared review/browser surfaces |
| [SKILLS-04](13-skills-04.md) | depot | gpt-5.6-luna / high / Codex | After shared defaults; one plugin per pass |
| [COST-01](14-cost-01.md) | depot | gpt-6-astra / medium / Codex | Later; does not block instruction repair |
| [HARNESS-01](15-harness-01.md) | foreman | gpt-6-astra / medium / Codex | After Foreman instructions; check current Floor/Foreman owners |
| [CLEANUP-01](16-cleanup-01.md) | depot | gpt-6-astra / low / Codex | Independent read-only inventory; no deletion |
| [CONFIG-01](17-config-01.md) | depot | gpt-6-astra / low / Codex | Optional private setting change only when intended |
| [RELEASE-01](18-release-01.md) | depot | gpt-5.6-luna / high / Codex | If the release comparator defect still reproduces |
| [MODEL-01-RELEASE](19-model-01-release.md) | depot | gpt-6-astra / low / Codex | Optional explicit publication session; resolve real release blockers first |

Only one next implementation chunk is selected: INSTRUCTIONS-01. Workspace inventory can run independently because it writes a new report and performs no cleanup; its owner is workspace maintenance in Depot, with no source-file collision. Consumer prompts share the reviewed generator policy and should not race that prerequisite. Publication is optional and explicitly scoped to the PR #131 versions; run it before those versions are superseded or obtain a newly prepared complete prompt.

## Evidence and recommendation freshness

- Depot main: `386b98e26f493cc220047c981cd5c01b1513b24d` after merged PR #131. Its exact source head was `0c7621749683dfc072ab2051959cb5c7c415190f`; hosted Codesmith was skipped, not a green CI pass.
- The installed Codex router changed during preparation from 0.6.2 to 0.7.0. The final recommendations use a coherent installed 0.7.0 bundle and installed OpenRouter 1.20.3 matrix, resolved through Workflow Kernel. This session did not change caches.
- Native recommendations are attemptable from current subscription evidence. Each prompt names exactly one fallback; the executor refreshes availability before routed work. Identical role/capability/effort requests reuse the same read-only recommendation result instead of probing nineteen times.
- Matrix evidence is 2026-08-27. Native API-equivalent price evidence is older and absent for the primary driver; it is never labeled as subscription billing. The operator target remains at most $50/month; each execution prompt caps optional paid model calls at $0.25 total, subject to known remaining budget.
- Small instruction changes use Luna Low; bounded edits use Luna High. Cost integration and Pi runtime work use Astra Medium. Host-only inventory/configuration/release operations use Astra Low because their required tool capabilities must be real. Worker selection remains separate from the human planning driver.
- At the last tag check, the three PR #131 target tags were absent. Codex versions 0.7.0 / 1.67.0 / 1.14.0 were observed; Claude still had the older router/Pipeline/coordinator. These are observations, not byte-equality or full publication proof. The release prompt reacquires all state.
- No model participant was dispatched and no paid model call was made to prepare this pack. Recommendations and fixtures are not consumer-performance measurements.

Current consumer main snapshots are recorded in [prompt-index.json](prompt-index.json). Active work at preparation: prototype #118, Floor #6, Governance #42 and Depot #129; Baseplate had only dependency PRs #826–#828. Every prompt refreshes its own head/ownership and can use a newer compatible main without manual placeholder replacement.

The [complete rollout plan](../../astra-routing-and-system-rollout.md) remains the program context. The [recommendation evidence](recommendation-evidence.json) stores the five reusable request profiles. Return execution results for inspection at their exact head before advancing dependent work.

## Validation

Full `validate-composition.sh --all` passed on the unchanged merged runtime at
`386b98e26f493cc220047c981cd5c01b1513b24d`; log:
`/tmp/assembly-prompts-composition.log`. The planning diff changes no plugin,
tool, test, manifest or installed-cache source. All 19 prompts passed complete-field,
exact-base, single-fallback, role/effort recommendation, provider-neutral packet,
budget, proper-PR and local-link checks. No implementation prompt was executed.
