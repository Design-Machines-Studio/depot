# Required UI-lane readiness

This contract is consumed only by dm-review's required rendered UI lanes. It
prevents participant dispatch when no rendered application or real local
interactive browser exists. It replaces reviewer-owned localhost scanning,
generic `tool-use` guesses, and OpenRouter web-search substitution. It is not a
browser broker, capability negotiation framework, or workflow engine.

## Repository declaration

Discover only `<repository>/.dm/ui-review.json`; never scan generic localhost
ports or infer a start command from incidental files. The closed version 1
shape is:

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

1. Check declared application readiness independently with
   `ui-review-readiness.sh prepare`.
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
5. Materialize a private bounded browser evidence file only after successful
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
7. Keep browser interaction host-owned. Give each UI analysis role the bounded
   screenshots, accessibility snapshots, console summary, route/viewport IDs,
   interaction observations, and computed-style results it needs. Request
   `review-deep` with `read-repository`, `long-context`, and
   `structured-output`; do not request `browser` or generic `tool-use`.
8. Settle the public participant result through `ui-review-readiness.sh
   settle`, then clean every exact registered process or Compose resource.
   Install the same cleanup call on interruption and failure paths.

The private state has a closed `app_ready` -> `ready` -> `settled` lifecycle.
It snapshots the exact readiness and cleanup argv/timeouts when the process is
registered; cleanup never reloads a mutable declaration. A failed confirmation
closes the state after exact cleanup. A settled state cannot be reused for a
second participant, and repeated cleanup reports zero resources removed.

OpenRouter web search is remote public-web retrieval. It never satisfies this
local browser contract. No model-router candidate currently advertises local
`browser`; a future candidate may do so only after its transport has a runtime
probe that proves local navigation.

## Closed outcomes

| Reason | Review state | One next action |
|---|---|---|
| `dev_server_unavailable` | `REVIEW INCOMPLETE` | Declare or recover the exact repository-owned consumer and rerun. |
| `browser_transport_unavailable` | `REVIEW INCOMPLETE` | Attach a local interactive browser, navigate the target, and rerun. |
| `model_participant_unavailable` | `REVIEW INCOMPLETE` | Restore an eligible provider-neutral analysis participant and rerun the lane. |
| `resource_cleanup_failed` | `REVIEW INCOMPLETE` | Run only the recorded repository-owned cleanup and inspect that resource. |

These are prerequisite/coverage outcomes, never code-quality findings. Emit
one exact cause and one next action. Do not dispatch a doomed participant,
silently omit a required lane, or convert missing evidence into approval.
