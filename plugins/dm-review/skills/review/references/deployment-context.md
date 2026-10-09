# Deployment Context (Design Machines)

Canonical statement of the Design Machines deployment and trust model. This is
the single owner; other surfaces point here or inline this block. Host-assembled
external reviewer prompts MUST inline this text (external models have no
filesystem).

Design Machines is a small designer-led team using agents to implement and vet
code. The owner approves plans and execution prompts, accepts UI behavior in
the browser and decides when to merge. Agents own backend correctness and the
applicable architecture, simplicity, security, testing and Fixture/distribution
checks; they never ask the designer to inspect backend code. Baseplate and its
Fixtures are first-party private development with trusted authors. Third-party
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

P3 is a retained concrete minor defect to repair and recheck. Speculative
preferences, optional abstractions and future scale are discarded during
consolidation rather than retained as deferred work.
