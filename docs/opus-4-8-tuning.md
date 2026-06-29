# Opus 4.8 Tuning

How depot plugins leverage Opus 4.8 and the effort levers. This is the canonical reference -- pipeline and dm-review point here instead of restating the effort model.

## What Changed in Opus 4.8

Opus 4.8 (released 2026-05-28, model ID `claude-opus-4-8`) is the current Anthropic API flagship. Relevant deltas for depot:

- **Effort levers replace version branches.** The model decides whether and how much to think per step (adaptive reasoning). You steer that with an effort level, not by detecting which model version is running. Hardcoded "if Opus 4.6 / if Sonnet" branches are stale -- tune by effort instead.
- **Adaptive-reasoning only.** Fixed thinking budgets (`MAX_THINKING_TOKENS`, `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`) do not apply to Opus 4.7+. Effort level is the primary control.
- **Aliases auto-upgrade.** `opus`/`sonnet`/`haiku` resolve to the latest release for the provider. On the Anthropic API `opus` is Opus 4.8 and `sonnet` is Sonnet 4.6. Depot agents use aliases, so there are no literal model IDs to bump when a new flagship ships.
- **No breaking changes from 4.7.** Same tools, same API surface. 1M context is the default on Max/Team/Enterprise.

## Effort Matrix (which levels each model supports)

| Model                     | Levels                                  | Default |
| :------------------------ | :-------------------------------------- | :------ |
| Opus 4.8 and Opus 4.7     | `low`, `medium`, `high`, `xhigh`, `max` | `high` (4.8), `xhigh` (4.7) |
| Opus 4.6 and Sonnet 4.6   | `low`, `medium`, `high`, `max`          | `high`  |
| Haiku 4.5                 | not supported (effort is ignored)       | --      |

If you set a level the active model does not support, Claude Code falls back to the highest supported level at or below it (so `xhigh` runs as `high` on Sonnet 4.6, and effort is ignored entirely on Haiku).

Level guidance:

- `low` -- short, scoped, latency-sensitive tasks that are not intelligence-sensitive.
- `medium` -- cost-sensitive work that can trade off some intelligence.
- `high` -- balanced; the default.
- `xhigh` -- deeper reasoning at higher token spend (Opus 4.7+ only).
- `max` -- deepest reasoning, no token constraint, session-only; prone to overthinking, test before adopting.
- `ultracode` -- a Claude Code setting (not a model effort level): sends `xhigh` and additionally has Claude orchestrate [dynamic workflows](https://code.claude.com/docs/en/workflows) for substantive tasks. Session-only.

## Setting Effort

Precedence: `CLAUDE_CODE_EFFORT_LEVEL` env var > skill/subagent frontmatter (while that skill/subagent runs) > session level (`/effort`, `--effort`, `effortLevel` setting) > model default.

- **Session:** `/effort xhigh`, `/effort auto` to reset, or the slider in `/model`. `--effort <level>` at launch. `effortLevel` in settings (`low`/`medium`/`high`/`xhigh` only -- `max` and `ultracode` are session-only).
- **Per agent/skill:** set `effort:` in the markdown frontmatter. Overrides session level while that agent/skill is active. Honored for plugin subagents (not in the plugin-ignored field list).
- **One-off:** include `ultrathink` in a prompt for deeper reasoning on that turn without changing the session level.

## Depot Effort Policy

Right-size effort per agent rather than running everything at the session default. Most depot review/workflow agents are mechanical or delegate to external models, so deep reasoning there only burns tokens. The policy below is mostly tuned *down* (cost-offload) with one strategic *up* where output feeds a hard decision gate.

| Tier | Agents | Effort | Why |
| :--- | :----- | :----- | :-- |
| Decision-gate reasoning | `plan-adversary` (opus) | `xhigh` | Adversarial plan review gates whether expensive execution proceeds. Deepest reasoning pays off; runs once per pipeline, not per chunk. |
| External-LLM wrappers / analysis | `deepseek-bulk-analyst`, `deepseek-code-analyst`, `openrouter-bulk-analyst` (sonnet) | `medium` | The Claude side constructs the prompt, invokes the CLI/API, and maps structured output for the consolidator. The real analysis happens in DeepSeek/OpenRouter -- Claude only needs enough care to not mangle the handoff. |
| Pure command runners | `go-test-runner` (sonnet) | `low` | Run a command and report. Not intelligence-sensitive. |
| Mechanical validators | `nats-reviewer`, `migration-validator` (sonnet) | `medium` | Pattern-and-rule checks with light judgment (PII detection, FK constraints, subject naming). |
| Deep Claude reviewers | `architecture-reviewer`, `security-auditor`, et al. (inherit) | session default | Inherit the session level (`high` on Opus 4.8). Raise the whole session to `xhigh` for high-stakes reviews rather than baking cost into every run. |
| Haiku-tier | `go-build-verifier`, `deepseek-agent-runner` | n/a | Haiku ignores effort; left unset. |

For the pipeline, raise *session* effort (`/effort xhigh` or `ultracode`) for complex or high-stakes features rather than pinning the workhorse `execution-orchestrator` to `xhigh` -- that keeps cost user-controlled per run.

## Dynamic Workflows (opportunity, not yet adopted)

`ultracode` and the `/workflows` system let Claude orchestrate JS-defined multi-step workflows. The pipeline already encodes its phases as a hardened, post-mortem-driven orchestration; do not rewrite it as a dynamic workflow unilaterally. Treat dynamic workflows as a future option for ad-hoc multi-step tasks that lack a dedicated pipeline.

## Maintenance

When a new flagship ships: the aliases auto-upgrade, so check (1) the effort matrix above against the model-config docs, (2) whether any new effort level changes the per-agent policy, and (3) the external-model comparison framing in the `model-selection.md` references under `plugins/deepseek/` and `plugins/openrouter/` (position external models as Sonnet-class cost-offload, never as flagship-replacements).
