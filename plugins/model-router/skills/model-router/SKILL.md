---
name: model-router
description: Internal provider-neutral role request and deterministic one-shot dispatch contract for Pipeline, dm-review, and Assembly coordination. Use when a Depot orchestrator must request an architect, critic, builder, reviewer, researcher, or editorial participant without selecting a model, provider, billing rail, or transport.
disable-model-invocation: true
---

# Model Router

This internal skill owns cross-transport role resolution. It is a local policy
bundle and one-shot dispatcher, not a service.

Callers provide only a role, required capabilities, normalized effort, prompt
file, output destination, private receipt destination, and opaque prior receipt
IDs when family independence is required. They must not select or receive a
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

OpenRouter remains the authority for its credentials, payload screening,
provider catalog, response identity, usage, and cost receipt. External write
work uses the bounded patch adapter and its existing owned-path and diff
validation. Workflow Kernel may record attempts but never selects a role or
candidate.

OpenRouter is a first-class automatic rail for every role. Do not require user
approval, impose a provider quota, or decline it because a task discusses
security, authentication, deployment, or a credential-handling path. The
role's deterministic candidate order and capability fit determine when it is
attempted, without a separate native-first rule. Exact outbound bytes still
pass the provider-owned scan; only actual secret material or explicitly
classified data closes that attempt.

Developer-local paid Claude credits default to disabled. The only tracked
preference schema is
`${CLAUDE_SKILL_DIR}/references/operator-profile-schema.json`; an actual
preference belongs in ignored `.dm/model-router.local.json` in the common
checkout and must never contain operator identity.
