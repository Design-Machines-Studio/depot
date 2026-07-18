# Claude Non-Coding Tuning

How depot plugins leverage Opus 4.8 and the effort levers. This is the canonical reference -- pipeline and dm-review point here instead of restating the effort model.

## What Changed in Opus 4.8

Claude remains supported for non-coding work and Claude Code compatibility, but it is outside Depot's executable coding graph. Implementation, code review, security, and architecture use Codex or OpenRouter. The model notes below apply only to strategy, writing/voice, research synthesis, planning, and compatibility metadata.

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

Claude effort applies only to explicitly non-coding lanes. Coding-agent `model:` and `effort:` frontmatter remains parseable for Claude Code compatibility, but dm-review and pipeline provider routing override it with Codex/OpenRouter execution.

| Tier | Agents | Effort | Why |
| :--- | :----- | :----- | :-- |
| Non-coding decision-gate reasoning | optional `plan-adversary` (opus compatibility alias) | `xhigh` | Deep plan critique may use Claude when explicitly selected; it never implements or reviews code. |
| Non-coding editorial/synthesis | `voice-editor`, strategy, research synthesis | session-controlled | Raise effort only when the writing or synthesis warrants it. |
| Coding and review agents | `execution-orchestrator`, `architecture-reviewer`, `security-auditor`, OpenRouter runners, validators | n/a | Codex/OpenRouter routing is authoritative. Claude model/effort frontmatter is inert compatibility metadata for these lanes. |

For non-coding planning and strategy, raise *session* effort (`/effort xhigh` or `ultracode`) when deeper synthesis is useful. Coding execution remains on Codex/OpenRouter regardless of the Claude session effort.

## Fable (Mythos-Class) Escalation -- plan-conditional

Claude Fable 5 (`claude-fable-5`, alias `fable`) sits ABOVE Opus in a Mythos-class tier. Availability is **plan-conditional**: it comes and goes with the user's subscription window, so it is an escalation option, never a baseline dependency. Rules:

- **Never pin `model: fable` in agent frontmatter.** Pins must always resolve; a lapsed plan would break dispatch. Defaults stay `opus`.
- **Use it via inheritance for non-coding agents:** strategy, voice/editorial, research-synthesis, and planning agents may inherit Fable from the session. Coding reviewers do not.
- **Use it via dispatch-time override for non-coding decision gates:** the Agent tool's `model` parameter takes precedence over frontmatter. When the session runs Fable (or the user opts in), an explicitly non-coding `plan-adversary` may use `model: fable`. If unavailable, re-dispatch with its frontmatter default.
- **Coding cascade:** `model-cascade.json` retains Fable's quality rank for research comparison only. `harness-profile.json` exposes Claude aliases solely for explicit non-coding compatibility; no coding cascade references that role.
- **Fable vs GPT-5.6 Sol:** the quality scores remain useful research context, but they do not imply a shared executable ladder. Sol leads Codex coding; Fable is non-coding-only.
- Effort levels on Fable: assume the full range (it is above Opus); confirm against the model-config docs when a new tier ships.

## Dynamic Workflows (opportunity, not yet adopted)

`ultracode` and the `/workflows` system let Claude orchestrate JS-defined multi-step workflows. The pipeline already encodes its phases as a hardened, post-mortem-driven orchestration; do not rewrite it as a dynamic workflow unilaterally. Treat dynamic workflows as a future option for ad-hoc multi-step tasks that lack a dedicated pipeline.

## Maintenance

When a new flagship ships: the aliases auto-upgrade, so check (1) the effort matrix above against the model-config docs, (2) whether any new effort level changes the per-agent policy, and (3) the quality-first model ordering in `plugins/openrouter/skills/openrouter-delegate/references/model-selection.md`.
