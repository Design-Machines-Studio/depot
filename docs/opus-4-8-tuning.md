# Claude Non-Coding Tuning

How depot plugins leverage Opus 4.8 and the effort levers. This is the canonical reference -- pipeline and dm-review point here instead of restating the effort model.

## What Changed in Opus 4.8

Claude Code effort behavior remains relevant to the host session and direct
operator work. Routed implementation, review, security, architecture,
planning, and editorial work instead uses model-router's provider-neutral role
and normalized effort contract. The model notes below document host
compatibility, not orchestration selection.

- **Effort levers replace version branches.** The model decides whether and how much to think per step (adaptive reasoning). You steer that with an effort level, not by detecting which model version is running. Hardcoded "if Opus 4.6 / if Sonnet" branches are stale -- tune by effort instead.
- **Adaptive-reasoning only.** Fixed thinking budgets (`MAX_THINKING_TOKENS`, `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`) do not apply to Opus 4.7+. Effort level is the primary control.
- **Aliases auto-upgrade.** `opus`/`sonnet`/`haiku` resolve to the latest release for the provider. On the Anthropic API `opus` is Opus 4.8 and `sonnet` is Sonnet 5. Depot agents use aliases, so there are no literal model IDs to bump when a new flagship ships.
- **No breaking changes from 4.7.** Same tools, same API surface. 1M context is the default on Max/Team/Enterprise.

## Effort Matrix (which levels each model supports)

| Model                     | Levels                                  | Default |
| :------------------------ | :-------------------------------------- | :------ |
| Opus 4.8 and Opus 4.7     | `low`, `medium`, `high`, `xhigh`, `max` | `high` (4.8), `xhigh` (4.7) |
| Sonnet 5                  | `low`, `medium`, `high`, `xhigh`, `max` | `high`  |
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

Operational routed cards use `model: inherit` and contain no concrete effort
branch. Pipeline, dm-review, and the Assembly coordinator pass normalized role
effort; model-router maps it to the selected transport's supported setting and
records any normalization privately.

| Tier | Agents | Effort | Why |
| :--- | :----- | :----- | :-- |
| Planning decision-gate reasoning | `architect` or independent `plan-critic` role | `high` or `max` | model-router resolves the participant; callers never pin an alias. |
| Editorial/synthesis | `editorial` role | workload-controlled | Raise effort only when the writing or synthesis warrants it. |
| Coding and review agents | `builder-fast`, `builder-deep`, `review-fast`, `review-deep`, or `security-review` role | `low` through `max` | Agent cards inherit; model-router normalizes effort for the resolved transport. |

Orchestrators use only the normalized role effort vocabulary
`low|medium|high|max`. A host session's own effort setting is separate and does
not choose a routed participant.

## Fable availability

Fable is a normal router-owned `architect` and `editorial` candidate. Never pin
it in agent frontmatter or orchestration prompts. Each dispatch checks current
Claude CLI authentication, positively reported subscription type, observable
interactive or Agent SDK headroom, bounded invocation results, and the ignored
developer-local paid-credit preference. Missing initial rate-limit telemetry
permits one bounded attempt only when subscription authentication and an
included entitlement are positively established. An exhaustion response falls
through without retrying the exhausted candidate.

Tracked policy never stores operator identity, plan, quota, allocation, or paid
credit choice. Paid credits default off. API-key authentication cannot
masquerade as subscription use, and Fable unavailability never blocks a caller
whose role has another eligible candidate.

## Dynamic Workflows (opportunity, not yet adopted)

`ultracode` and the `/workflows` system let Claude orchestrate JS-defined multi-step workflows. The pipeline already encodes its phases as a hardened, post-mortem-driven orchestration; do not rewrite it as a dynamic workflow unilaterally. Treat dynamic workflows as a future option for ad-hoc multi-step tasks that lack a dedicated pipeline.

## Maintenance

When a new flagship ships, refresh provider evidence, then change only
model-router's private candidate policy and adapters. Recheck effort mapping and
availability fixtures without changing Pipeline, dm-review, or coordinator
contracts.
