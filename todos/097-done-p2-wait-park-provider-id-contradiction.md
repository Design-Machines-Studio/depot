---
status: done
priority: p2
issue_id: "097"
---

# RC76 wait/park ask still required a provider identifier

Resolved by making live rail status display-only, closing the executable answer
vocabulary to `wait` or `park`, and moving provider selection and override
semantics into the future trusted-authority design. The workflow-contract gate
now rejects the retired provider-identifier instruction.
