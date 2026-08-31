# Required UI-lane readiness

This contract is consumed once when any of dm-review's three logical UI lanes
is selected. It separates source-capable analysis from rendered proof, prevents
the visual-browser lane from dispatching without a rendered application or
accepted exact-head evidence, and replaces reviewer-owned localhost scanning,
generic `tool-use` guesses, and OpenRouter web-search substitution. It is not a
browser broker, capability negotiation framework, or workflow engine.

## Lane evidence classes

- `ui-standards-reviewer` always runs when triggered. From changed target
  source, exact prototype source, the bounded parity packet, local design
  specifications, components, and Live Wires patterns it may assess hierarchy,
  wrappers, reuse, exact class strings, literal copy/metadata, action order,
  and named intentional differences. Without browser evidence it is
  `source-only` and cannot pass spacing, computed style, interaction,
  responsive behavior, or rendered parity.
- `ux-quality-reviewer` always runs when triggered. Its labelled `source-only`
  pass may assess represented task flow, routes/templates, control placement,
  action order, copy/metadata, source-visible information hierarchy, and
  prototype/source divergence. It cannot pass rendered usability, focus,
  computed styles, responsiveness, or visual parity.
- `visual-browser-tester` requires a live target or an accepted exact-head
  packet for the selected cases. It is `NOT RUN` when that rendered proof is
  absent.

Load `ui-case-selection.md` first and materialize one selected case set. Run
`ui-review-contract.sh plan` after the one readiness/packet decision to project
the source/rendered disposition without duplicating the gap per lane.

## Target selection

Select exactly one target in this order:

1. an explicit URL supplied by the current invocation;
2. an already attached, automation-capable T3 preview and its current URL;
3. the optional tracked `<repository>/.dm/ui-review.json` declaration;
4. otherwise no rendered target is available.

Pass invocation and T3 targets to `prepare` with `--target-url` and
`--target-source explicit|t3-preview`. Do not scan localhost ports, infer a URL
from file extensions, or guess a start command. The helper validates the URL;
successful host navigation remains the readiness proof.

"One target" applies per readiness state. When a host-resolved prototype
parity packet supplies both an exact prototype URL and target URL, run this
same gate for each in sequence and collect one bounded matched evidence packet;
do not invent a broker or new transport. The prototype and target cases must
use the same meaningful states and viewports. Required prototype evidence
cannot be replaced by target-only navigation.

## Optional repository declaration

When present, discover only `<repository>/.dm/ui-review.json`. Its closed
version 1 shape is:

```json
{
  "schemaVersion": 1,
  "targetUrl": "http://localhost:8080",
  "readiness": {
    "argv": ["./tools/ui-review-ready"],
    "attempts": 10,
    "timeoutSeconds": 5
  },
  "start": {
    "resourceKind": "process",
    "argv": ["./tools/ui-review-start"],
    "cleanupArgv": ["./tools/ui-review-stop"],
    "timeoutSeconds": 30
  }
}
```

`start` may be `null` for a consumer that must already be running. Every argv
is an array, never a shell string. Its executable must be a tracked,
non-symlinked repository-owned `./` path. The target must be an explicit local
HTTP(S) URL. Unknown fields or unsupported values fail closed.

`resourceKind: process` is prepared and settled by
`ui-review-readiness.sh`. `resourceKind: compose` is executed only through
`review-docker-create.md`, using the exact declaration argv and exact composed
consumer. Run the helper again after Compose readiness; cleanup remains owned
by `review-docker-cleanup.md`. Never start the whole stack when one declared
consumer is sufficient.

## Ordered gate

1. Select the target using the order above. For an explicit URL or attached T3
   preview, run `ui-review-readiness.sh prepare` with that exact target. For a
   declaration, check its application readiness independently with `prepare`.
2. If a stopped `process` consumer has an exact start procedure, start it and
   register only that created resource. `prepare` returns `app_ready` with
   `dispatchAllowed: false` and leaves that registered process available for
   host browser navigation. A pre-existing ready consumer is never registered
   or stopped.
3. For declared Compose, follow the existing Docker creation contract, then
   rerun the independent readiness check.
4. On the host, inspect actual callable browser tools. In T3 Code, call
   `preview_status`; if no automation-capable preview is attached, call
   `preview_open`, then navigate the exact declared target. A tool name or
   generic `tool-use` is not readiness evidence.
5. Materialize one private bounded browser evidence file only after successful
   local navigation:

   ```json
   {
     "schemaVersion": 1,
     "status": "ready",
     "transportClass": "local-interactive",
     "localNavigation": "confirmed",
     "targetUrl": "http://localhost:8080",
     "evidenceRef": "review/browser/navigation.json"
   }
   ```

6. Run `ui-review-readiness.sh confirm-browser` with that evidence and the
   exact state file created by `prepare`. It rechecks the registered target and
   consumes the browser proof. Only `dispatchAllowed: true` permits a
   participant call.
7. Keep browser interaction host-owned. Collect screenshots, accessibility
   snapshots, console summary, route/viewport IDs, interaction observations,
   and computed-style results once. Give the same bounded evidence packet to
   each applicable UI analysis role. Request
   `review-deep` with `read-repository`, `long-context`, and
   `structured-output`; do not request `browser` or generic `tool-use`.
   For a declared counterpart, include matched prototype/target route, state,
   viewport, targeted hierarchy, actual classes, visible copy/action order, and
   explanatory layout/spacing values. Exact theme colors are not a parity gate.
8. Dispatch each applicable analysis lane once with the same packet reference.
   Settle the aggregate analysis result once through `ui-review-readiness.sh
   settle`, then clean every exact registered process or Compose resource.
   Install the same cleanup call on interruption and failure paths.

The private state has a closed `app_ready` -> `ready` -> `settled` lifecycle.
It snapshots the exact readiness and cleanup argv/timeouts when the process is
registered; cleanup never reloads a mutable declaration. A failed confirmation
closes the state after exact cleanup. The ready state belongs to the
review-level packet, not one participant; settle consumes it only after the
applicable UI analyses join. Repeated cleanup reports zero resources removed.

## Explicit Pipeline evidence reuse

An enclosing Pipeline may pass one exact packet path from its owned ignored
run/evidence directory. Never glob for it, choose a latest file, or infer it
from timestamps. Validate it with `browser-evidence-packet.sh validate` against
the current repository identity, exact commit, clean/dirty state, selected
case-set equality, prototype identity/commit when applicable, successful
completion, and every artifact hash. The packet schema is closed and bounded;
it excludes credentials, private endpoints, raw browser storage, complete HTML,
and unbounded logs.

The packet records dirty state for truthful diagnostics, but reusable evidence
requires a clean exact head because the bounded packet intentionally carries no
uncommitted-diff database or second content ledger.

An accepted packet replaces a second host capture for exactly its selected
cases and feeds the same three applicable UI analyses. A rejection is explicit
and never grants rendered success: attempt ordinary current target readiness;
if that also fails, retain the single rendered gap when evidence is required.

OpenRouter web search is remote public-web retrieval. It never satisfies this
local browser contract. No model-router candidate currently advertises local
`browser`; a future candidate may do so only after its transport has a runtime
probe that proves local navigation.

## Closed outcomes

| Reason | Review state | One next action |
|---|---|---|
| `visual_target_unavailable` | `NOT RUN` ordinarily; `REVIEW INCOMPLETE` when required | Supply an explicit URL, attach T3 preview, or add the optional declaration when coverage is required. |
| `dev_server_unavailable` | `NOT RUN` ordinarily; `REVIEW INCOMPLETE` when required | Declare or recover the exact repository-owned consumer when rendered coverage is required. |
| `browser_transport_unavailable` | `NOT RUN` ordinarily; `REVIEW INCOMPLETE` when required | Attach a local interactive browser or pass exact matching evidence when rendered coverage is required. |
| `model_participant_unavailable` | `REVIEW INCOMPLETE` | Restore an eligible provider-neutral analysis participant and rerun the lane. |
| `resource_cleanup_failed` | `REVIEW INCOMPLETE` | Run only the recorded repository-owned cleanup and inspect that resource. |

These are prerequisite/coverage outcomes, never code-quality findings. When no
target exists during an ordinary quick or full review, run the source-capable
UI lanes, leave visual-browser `NOT RUN`, and emit one aggregated
`visual_target_unavailable` coverage note with `NOT RUN`; the review remains
otherwise complete. Do not repeat that note for the three UI lanes.

Rendered evidence is required only for `/dm-review-visual`, explicit user or
acceptance-criteria requirements, or a repository verification profile. Call
`prepare --visual-required true` for those cases. If no target exists, emit one
honest `REVIEW INCOMPLETE` coverage result and one next action. File extensions
and template changes alone do not make visual infrastructure mandatory.
