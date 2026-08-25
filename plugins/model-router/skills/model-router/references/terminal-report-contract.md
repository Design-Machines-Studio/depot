# Terminal operator model and cost report

This contract is the only point where concrete router identity may leave a
private receipt. It runs for the human operator only, after the invocation has
a closed terminal status and every model-dependent decision has settled.

## Terminal ownership

Exactly one workflow owns reporting for an invocation:

| Invocation | Terminal report owner | Nested behavior |
|---|---|---|
| `/pipeline` | the Pipeline caller after its final disposition gate | execution-orchestrator and nested dm-review suppress reporting |
| `/pipeline-run` | execution-orchestrator | nested dm-review suppresses reporting |
| `/dm-review` or `/dm-review-quick` | the standalone review invocation | no nested owner |
| `/dm-review-loop` | the loop after its last verification pass | every internal dm-review pass suppresses reporting |
| Assembly opinion comparison | the coordinator after synthesis | no report when no routed opinion ran |

Suppression means identity remains private and the exact receipt directory and
index remain available to the terminal owner. It never means delete the
receipts before the owner has rendered or closed reporting as unavailable.

## Ordered private index

Every terminal owner uses one mode-`0700` run-private router directory. The
file `terminal-receipt-index.json` in that directory has exactly:

```json
{
  "schemaVersion": 1,
  "receiptFiles": ["dispatch-a.json", "dispatch-b.json"]
}
```

Entries are safe basenames for files in that same directory. Record them in
dispatch-start order. For a parallel fan-out, precompute the deterministic
selected-lane order and write the settled receipt basenames in that order after
the fan-out joins; completion order never reorders the index. Nested workflows
receive the owner's directory and extend this same index instead of creating a
second report scope. Duplicate references are permitted; the renderer keeps
the first valid object for each receipt ID.

The index is a bounded input list, not a public receipt or event stream. Never
copy its contents or any private receipt into a prompt, planning artifact,
review output, synthesis input, merge decision, public disposition, or
run-cost summary.

## Closed generation boundary

Resolve one coherent model-router bundle at minimum version `0.2.0` and require
`skills/model-router/references/render-terminal-report.sh`. Generate only when:

1. implementation, reviews, repairs, synthesis, requirements checks, and merge
   or recommendation decisions are final;
2. no later model dispatch can occur in this invocation; and
3. terminal status is one of `complete`, `failed`, `blocked`, or `stopped`.

Invoke exactly once:

```bash
"$MODEL_ROUTER_ROOT/skills/model-router/references/render-terminal-report.sh" \
  --receipt-index <exact-private-router-dir>/terminal-receipt-index.json \
  --status <complete|failed|blocked|stopped> \
  --json-output <durable-run-dir>/model-cost-report.json \
  --markdown-output <durable-run-dir>/model-cost-report.md
```

The JSON and Markdown paths sit beside the workflow's existing run-cost
artifacts. Generate them before private receipts or their exact-owned directory
are cleaned. Then complete cleanup and terminal receipts, and append the
already-generated Markdown to the human handoff. The report is never read by a
model and no dispatch, review, repair, synthesis, routing, or merge decision may
follow generation or display.

Failed and blocked invocations still render incurred attempts once dispatch has
stopped. An Assembly coordinator invocation that made no routed opinion call
does not create an empty index or report.

## Failure closure

Reporting is observation-only. Do not retry it. If the renderer fails, accept
only its closed stderr shape `terminal-model-report: <lowercase-hyphen-reason>`;
otherwise use `renderer-failed`. Preserve the workflow result, continue exact
cleanup, and append exactly one line to the terminal handoff:

```text
Model & Cost Report unavailable: <closed reason>
```

Failure never reopens review, triggers another model, blocks cleanup, requests
approval, changes the workflow result, or retries provider work.
