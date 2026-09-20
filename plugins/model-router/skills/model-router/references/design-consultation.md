# Bounded design consultation

Use role `design-consultant` only for one unresolved UI or design judgment that
the prototype and current rendered evidence do not already settle. The default
policy uses native Codex with an eligible OpenRouter fallback. Claude is excluded
from automatic routing. A consultant is never the design authority or builder.

The caller supplies exactly one question, the relevant prototype excerpt or
screenshots, the matching implementation evidence, and the constraints needed
to answer it. Do not grant repository exploration or write capabilities. Ask
for one decision, a reason, and at most three implementation implications.
Use the existing one-shot dispatcher and native/OpenRouter timeouts. Output
brevity is advisory where the selected transport has no enforceable output cap. Do not repeat the consultation after a completed
answer. The cheaper routed builder implements the resulting settled decision.

For separately configured native Claude use only: if Claude is missing, exhausted,
locally disabled, or returns a provider-side
identity outside `servedIdentities`, retain the router receipt and use the one
normal fallback. Never retry an exhausted Claude rail, buy Claude overage
automatically, or claim an unobserved served identity.
