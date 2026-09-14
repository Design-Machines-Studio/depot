# Bounded design consultation

Use role `design-consultant` only for one unresolved UI or design judgment that
the prototype and current rendered evidence do not already settle. Fable is an
eligible native-Claude first candidate for this role; it is never the review
host, implementation worker, or design authority.

The caller supplies exactly one question, the relevant prototype excerpt or
screenshots, the matching implementation evidence, and the constraints needed
to answer it. Do not grant repository exploration or write capabilities. Ask
for one decision, a reason, and at most three implementation implications.
Use the existing one-shot dispatcher and native/OpenRouter timeouts. Output
brevity is advisory because the native Claude CLI exposes no enforceable output
token cap in this transport. Do not repeat the consultation after a completed
answer. The cheaper routed builder implements the resulting settled decision.

If Claude is missing, exhausted, locally disabled, or returns a provider-side
identity outside `servedIdentities`, retain the router receipt and use the one
normal fallback. Never retry an exhausted Claude rail, buy Claude overage
automatically, or claim an unobserved served identity.
