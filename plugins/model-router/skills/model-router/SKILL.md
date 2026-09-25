---
name: model-router
description: Internal provider-neutral role request and deterministic one-shot dispatch contract for Pipeline, dm-review, and Assembly coordination. Use when a Depot orchestrator must request an architect, critic, builder, reviewer, researcher, or editorial participant without selecting a model, provider, billing rail, or transport.
disable-model-invocation: true
---

# Model Router

This internal skill owns cross-transport role resolution. It is a local policy
bundle and one-shot dispatcher, not a service.

For human-facing session setup and calibration, read
`references/driver-worker-guidance.md`. It separates the operator's main driver
from routed workers. Never copy its concrete identities into participant
packets; explicit role effort and transport normalization remain separate.

Callers provide only a role, required capabilities, normalized effort, the
exact validated Workflow Kernel launcher for that invocation, prompt file,
output destination, private receipt destination, an explicit complete
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

For Codex subscription candidates, authentication and allowance observation
remain separate. The probe validates that every 0.147 map key matches its
snapshot `limitId`, parses the 0.146 `rateLimits.primary`/`secondary` and 0.147
`rateLimitsByLimitId` forms, and evaluates every observed supported window at
the existing 8% threshold. An absent optional window is not fabricated and
does not invalidate another observed window. An empty or incomplete snapshot
stays unknown with its content-safe diagnostic. With confirmed ChatGPT
subscription authentication, unknown or unavailable allowance telemetry
permits one bounded native attempt and is labelled `attemptable`, never
verified healthy. An observed applicable exhausted bucket, API-key-only or
unknown authentication, or missing authentication still closes the native
candidate. Multiple 0.147 buckets without an authoritative candidate mapping
remain unattributed; the router does not choose a best bucket. If all
unattributed buckets are exhausted, Codex is skipped as
`rate_limit_exhausted`.

An OpenRouter `insufficient_credits` failure is actionable only from its
validated provider receipt with its HTTP status. It closes the OpenRouter
credential rail for the current dispatch, while preserving the receipt
evidence and allowing later eligible candidates on other rails. A 429
`rate_limited` response remains a distinct model attempt failure. No
account-wide balance cache or budget service is implied.

Before availability probing, the dispatcher uses the supplied launcher to
resolve one coherent OpenRouter bundle. That exact binding supplies credential
loading, availability, the disclosure boundary, and wrapper invocation; it is
never re-resolved during an attempt. Closed public diagnostics distinguish the
Kernel launcher, provider bundle, credential, availability, boundary,
transport, and model-unavailable causes without exposing stderr or private
paths.

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
checkout and must never contain operator identity. `disabledCandidates` is the
small local preference for retiring a candidate such as `opus`; it filters both
dispatch and human recommendation without changing shared policy or retrying an
exhausted Claude rail.

For one narrow unresolved UI/design question, load
`${CLAUDE_SKILL_DIR}/references/design-consultation.md` and request
`design-consultant`. The default candidate is native Codex. Claude candidates are excluded from
automatic routing; an explicitly configured Fable consultation still requires
that bounded native-Claude contract. It is not a repository-wide reviewer or builder.

For a coordinator preparing a human copy-paste execution prompt, use
`${CLAUDE_SKILL_DIR}/references/operator-recommendation.sh`. This read-only
projection filters the current role policy by requested capabilities and
availability, reads prices only from the caller-bound model matrix, and returns
one concrete primary plus one fallback. It never invokes a model. Its identity
and cost projection is human-only and must not enter any participant prompt,
planning-opinion packet, reviewer prompt, participant output, or synthesis
input.

When a Pipeline, dm-review, or Assembly opinion invocation has reached a closed
terminal state and no later model dispatch is possible, load
`${CLAUDE_SKILL_DIR}/references/terminal-report-contract.md`. Its shared
renderer is the sole operator-facing identity projection. Never load or run it
during routing, implementation, review, repair, synthesis, or merge decisions.
