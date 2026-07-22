# Codify Report: depot-mechanical-workflow-hardening

## Friction

- Final review showed that caller-authored repository evidence was still treated as execution authority.
- The original read-only boundary could exclude a caller-selected repository subtree and had no stable capture/compare launcher surface.
- A live sibling declaration failure obscured otherwise clean Depot-owned release results for the second consecutive Pipeline run.
- Shadow observation could consume receipts but could not prove the sealed prediction binding.

## Lessons -> Encodings

| # | Lesson | Durable target | Status | Recurrence |
|---|---|---|---|---|
| 1 | Capture repository truth from the pinned checkout immediately before execution; caller JSON is expected evidence only. | Workflow Kernel runtime + regression tests | encoded in this branch | first seen |
| 2 | Read-only evidence may exclude only the EventStore-owned run root and must pin physical identity through stable launcher commands. | Workflow Kernel runtime, dm-review contract, CLI/release tests | encoded in this branch | first seen |
| 3 | Report live sibling compatibility independently from Depot-owned release health without weakening either. | `tools/validate-workflow-kernel.py` and composition reporting | PROPOSED; AWAITING APPROVAL | seen in 2 runs |
| 4 | Verify a prediction binding immediately after sealing, before any authoritative action. | Pipeline shadow initialization | PROPOSED; AWAITING APPROVAL | first seen |

## Automated checks added now

- Stale plan state and a different physical checkout block before command execution.
- A mutation inside the former caller-excluded subtree is detected.
- EventStore evidence-root displacement fails closed.
- `review-boundary-capture` and `review-boundary-compare` are exercised through the real launcher with stable exit contracts and release inventory coverage.

## Proposed encodings (await approval)

### Separate sibling compatibility reporting

Keep strict live sibling checks, but emit two explicit results: Depot-owned release validation and live sibling integration compatibility. A sibling declaration error remains failing evidence, but no longer collapses the owned result into an opaque suite hash.

### Shadow binding startup receipt

After `bind-prediction`, run a read-only binding verification and persist the state-directory identity, source digest, event digest, and failure category before `run.started`. Do not repair or rebind after authoritative actions.

## Memory disposition

No ai-memory connector was callable in this Codex runtime, and the user did not explicitly request a global Codex memory write. No memory was changed. The durable repo-backed encodings and proposal artifacts above remain the authority for this run.
