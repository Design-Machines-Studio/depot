---
name: model-router
description: Internal provider-neutral role request and deterministic one-shot dispatch contract for Pipeline, dm-review, and Assembly coordination. Use when a Depot orchestrator must request an architect, critic, builder, reviewer, researcher, or editorial participant without selecting a model, provider, billing rail, or transport.
disable-model-invocation: true
---

# Model Router

This internal skill owns cross-transport role resolution. It is a local policy
bundle and one-shot dispatcher, not a service.

Callers provide only a role, required capabilities, normalized effort, prompt
file, output destination, private receipt destination, an explicit complete
repository-evidence file for prompt-only repository readers, and opaque prior
receipt IDs plus their run-private registry when family independence is
required. Human-authored work uses the explicit `--human-authored` origin flag
instead of fabricating a model-family receipt. Write roles also carry the bound
behavioral contract digest and revision. Callers must not select or receive a
model, provider, family, billing rail, or transport.

Use `${CLAUDE_SKILL_DIR}/references/role-dispatch.sh`. The closed request and
public result shapes are defined by
`${CLAUDE_SKILL_DIR}/references/role-request-schema.json`. Concrete candidates
exist only in `${CLAUDE_SKILL_DIR}/references/role-policy.json`.

The dispatcher:

1. validates the closed request;
2. probes current machine and operator availability;
3. excludes every family named by opaque private receipts;
4. walks the role's deterministic candidate order;
5. invokes one transport at a time with argv arrays;
6. writes model output to the caller-selected output file;
7. emits a role-only public disposition; and
8. writes exact, content-free identity and measurement evidence to the private
   receipt.

For Codex subscription candidates, an optional policy `rateLimitId` is valid
only when an authoritative model-to-allowance mapping exists. The probe parses
response shapes structurally, validates that every 0.147 map key matches its
snapshot `limitId`, and evaluates only the mapped bucket's five-hour and weekly
windows at the existing 8% threshold. It never selects the best bucket. The
legacy 0.146 `rateLimits.primary`/`secondary` snapshot and a single 0.147 bucket
are unambiguous defaults. Multiple 0.147 buckets without an authoritative
candidate mapping close as `rate_limit_mapping_unknown`; the current Codex
app-server schema does not expose that mapping, so the policy does not invent
one for current candidates. Missing, malformed, unsupported, exhausted, or
unmappable evidence fails closed with a content-safe reason; unknown never
means exhausted.

The `browser` request capability means access to the caller's local interactive
browser, not public web search. No current one-shot transport advertises that
capability. dm-review keeps browser interaction host-owned and dispatches only
bounded evidence analysis after its separate readiness gate.

OpenRouter remains the authority for its credentials, provider catalog,
response identity, usage, and cost receipt. The router owns provider-neutral
input eligibility: any prompt and evidence eligible for an available native
Claude or Codex subscription candidate is also eligible for OpenRouter.
External write work uses the bounded patch adapter and its existing owned-path
and diff validation. Workflow Kernel may record attempts but never selects a
role or candidate.

OpenRouter is a first-class automatic rail for every role. Do not require user
approval, impose a provider quota, or decline it because a task discusses
security, authentication, deployment, or a credential-handling path. The
role's deterministic candidate order and capability fit determine when it is
attempted, without a separate native-first rule. Never reject, redact, split,
or hold OpenRouter input because of payload content when a native candidate
would accept the same material. Missing credentials, transport availability,
and malformed request shape may close an attempt; payload subject matter or
secret-bearing repository evidence may not.

Developer-local paid Claude credits default to disabled. The only tracked
preference schema is
`${CLAUDE_SKILL_DIR}/references/operator-profile-schema.json`; an actual
preference belongs in ignored `.dm/model-router.local.json` in the common
checkout and must never contain operator identity.

When a Pipeline, dm-review, or Assembly opinion invocation has reached a closed
terminal state and no later model dispatch is possible, load
`${CLAUDE_SKILL_DIR}/references/terminal-report-contract.md`. Its shared
renderer is the sole operator-facing identity projection. Never load or run it
during routing, implementation, review, repair, synthesis, or merge decisions.
