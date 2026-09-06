# Final-review browser evidence handoff

Load this reference before Pipeline's final dm-review when at least one executed
chunk has `renderedSurface: required`. It reuses host-owned capture; it does not
add a browser broker, evidence service, or Workflow Kernel capability.

## Capture once at the integrated head

After the integrated feature branch and selected browser cases are final,
capture those cases once with the existing host-owned browser protocol. Do not
reuse a chunk packet from an earlier commit. Store bounded artifacts under the
current ignored owned run location:

```text
plans/<feature-slug>/evidence/browser/final-review/
```

Write the explicit selected case IDs to `selected-cases.json` and the bounded
host capture projection to `capture.json`. The capture projection contains only
artifact references, compact DOM/class/copy/action observations, compact
layout/computed-style observations, console/accessibility summary, successful
completion, and the local-navigation confirmation. It contains no credentials,
private endpoints, browser storage, complete HTML, or unbounded logs.

Resolve `browser-evidence-packet.sh` from the same coherent dm-review bundle
that the final review will use. Invoke `create` with the exact repository root,
explicit `capture.json`, explicit output
`browser-evidence-v1.json`, and exact prototype root when applicable. Creation
is permitted only after successful host capture. The helper records repository
identity, exact commit, clean/dirty state, prototype identity/commit, selected
case IDs, artifact references/hashes, compact observations, and completion.

## Explicit handoff

Pass these exact paths in the enclosing final dm-review invocation:

```text
uiBrowserEvidencePacket: plans/<feature-slug>/evidence/browser/final-review/browser-evidence-v1.json
uiBrowserSelectedCases: plans/<feature-slug>/evidence/browser/final-review/selected-cases.json
```

Never search plans, run roots, screenshots, or timestamps for a packet. Never
choose a `latest` file. Nested dm-review validates the explicitly passed packet
against its current selected cases before application readiness.

An exact match replaces a second capture and feeds the same packet to
visual-browser, UX-quality, and UI-standards analysis. Repository identity or
commit, clean/dirty state, prototype identity or commit, selected case set,
completion, missing artifact, or hash mismatch rejects reuse. On rejection,
dm-review attempts normal current target readiness. If current capture cannot
run and rendered evidence is required, one browser gap remains; no lane may
claim rendered success from the rejected packet.

The packet records dirty state, but Pipeline hands off only a clean integrated
candidate. Dirty packets are diagnostic and are not reusable because this
bounded contract deliberately carries no uncommitted-diff ledger.

Pipeline owns this ignored run evidence and its normal exact-run cleanup. Do
not publish it, copy it into a durable database, sign it, or leave a global
pointer to it.
