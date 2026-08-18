# Deployment Context (Design Machines)

Canonical statement of the Design Machines deployment and trust model. This is
the single owner; other surfaces point here or inline this block. Host-assembled
external reviewer prompts MUST inline this text (external models have no
filesystem).

Design Machines is a two-person development team and the only developers of
Baseplate and its Fixtures -- there are no external contributors. Third-party
API stability, deprecation cycles, and backward-compatibility shims are
therefore out of scope by default. Each install serves roughly 4--50 users.
Installs are largely hidden from the open web and are not search-indexed: the
threat model is small authenticated groups, not internet-scale exposure, and
security and hardening must stay proportional to that. Real boundaries remain
hard regardless of scale -- credentials, authentication and authorization, data
loss, destructive or external mutations, release/update integrity, and honest
verification. Overall Design Machines goals apply: small self-hosted products,
YAGNI, developer ergonomics, speed, and token economy constrain every
abstraction. No enterprise architecture, generic OWASP possibility, future
marketplace, or defence-in-depth preference is a finding without a demonstrated
current consumer or a reachable current defect.
