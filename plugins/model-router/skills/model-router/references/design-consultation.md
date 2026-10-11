# Bounded design participation

## Required design skill

For every design-related task, load the available `claude-design` skill before
design judgment or execution and apply its relevant instructions. This includes
research, planning, implementation and review of interface, interaction, visual,
layout, typography and design-system choices. Use the native skill loader for a
built-in skill; read `SKILL.md` when file-backed. Resolve the actual skill through
the host's catalog rather than guessing a cache path or substituting a similarly
named skill. A host without direct access obtains the actual instructions from
an available native Claude session for its participant packet. If the skill
cannot be loaded, report that coverage gap and request its
source; never claim it was used.

The lead loads it once and supplies the relevant instructions and source to
each bounded design participant. Prompt-only participants receive those excerpts
in their packet; do not grant extra tools merely to load a skill. Include the
approved requirements, prototype and actual browser evidence needed for the
question. Skill use assists judgment and execution without changing model-router
selection, account settings, tool permissions or publication authority. Explicit
user decisions, approved prototypes and required accessibility, functional and
browser checks remain authoritative. Reuse still-valid design evidence.

Anthropic documents `/design` as the native Claude Code entry point in its
[Claude Design guide](https://support.claude.com/en/articles/14604416-get-started-with-claude-design).
That command's existence does not prove the skill was loaded in a worker or that
its current transport can execute design tools. Record actual use separately.

Prefer Opus 5.5 for applicable UI/UX judgment and front-facing design repair
drafting. `design-consultant` routes to `claude-opus-5-5` over native Claude,
then `gpt-6.1-sol` over Codex when Opus is unavailable. Validate the identity of
the selected candidate; never accept a provider silently substituting a model.
The design review remains required, and either eligible candidate can supply it.
Fable leads architecture/deep review with Astra as its immediate fallback;
Opus/Sol implements substantive changes.

## Current identity/catalog evidence

Verified 2026-10-05 against Anthropic's [model overview](https://platform.claude.com/docs/en/models/opus-5-5/overview)
and [Claude Code model configuration](https://support.claude.com/en/articles/11940350-claude-code-model-configuration):
`claude-opus-5-5` is the documented identifier and Claude Code supports native
selection. This is catalog/transport evidence, not proof of this account's
model access or remaining subscription allowance. Dispatch checks current auth,
subscription/credit eligibility and allowance evidence and validates the served
identity. Unknown allowance stays unknown; one bounded eligible attempt may
establish actual availability. Paid credits remain disabled unless the existing
local operator preference explicitly enables them. No automatic overage.

## Bounded packet and authority

Use this role for selected UX-quality, UI-standards and visual design judgment,
and for affected front-facing design repair decisions/patch drafts. Accessibility,
security and functional lanes retain their ordinary roles and mandatory gates.
Pass the affected surfaces and required interaction/persona cases, approved
requirements, exact prototype source, HTML hierarchy, Live Wires class strings,
Datastar events, save semantics and matched screenshots/DOM/interaction evidence.
One completed decision per affected repair batch is enough; do not commission
an unrelated design sweep or repeat settled judgments.

The participant has final design judgment among agents, subject to the
operator's explicit decisions and approved prototype. It cannot redesign a
settled prototype choice or waive accessibility, security or functionality.
Ask for the smallest adequate patch/decision, rationale and verification cases.
The Claude design participant is prompt-only (`--tools ""`); the Codex fallback
can inspect source with its read-only sandbox. The host supplies browser evidence,
applies accepted patches, commits/pushes and verifies them. Do not request
write/tool/browser capabilities for `design-consultant`.
The separate `builder-deep` role supports native Claude implementation tools;
its permissions do not expand this consultation role. Model identity and browser availability
are separate: use dm-review's existing browser evidence handoff when direct
browser tools are absent.

Unavailable, disabled, exhausted, missing identity or provider substitution
advances to the configured fallback. If both candidates fail, return the existing
role-level `model_participant_unavailable` result with its exact private reason
and report required design coverage as incomplete. Concrete identity is operator-visible
through the existing recommendation/terminal report, outside ordinary participant
packets. No new account budget service or organization ceiling is claimed.
