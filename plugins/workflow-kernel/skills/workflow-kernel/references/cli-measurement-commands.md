# Measurement CLI commands

`run-cost-summary` aggregates `attempt_usage` events that are already in a
run's receipt stream. It invents nothing. A run that appends no usage events
gets an artifact whose every row reads `unavailable` -- structurally valid,
informationally empty, and indistinguishable from a run that was never
measured at all.

Two commands produce those events. Both are pure translators: they read one
input, emit one attempt-scoped payload, and write nothing to the run's ledger.
Appending the payload is the orchestrator's job, described under
**The emission boundary** below.

Both are observation-only. Nothing here gates, waives, selects, or alters any
lane, phase, or review outcome.

## `openrouter-usage`

Translates one schemaVersion-2 receipt written by `openrouter-wrapper.sh` into
an attempt-scoped usage payload carrying provider-reported token counts and
cost.

```sh
"$WORKFLOW_KERNEL" openrouter-usage \
  --receipt <wrapper-receipt.json> \
  --lane <logical-lane-id> \
  --chunk-id <chunk-id> \
  --node-id <node-id> \
  --attempt <n> \
  --host <claude|codex|...> \
  --duration-seconds <seconds> \
  [--output <payload.json>]
```

Without `--output` the payload goes to stdout as canonical JSON (sorted keys,
no spaces, trailing newline), so two runs over the same receipt produce
byte-identical bytes.

**Receipt requirements.** `schemaVersion` must be the integer `2`. A counter
that is negative, boolean, float, or string-typed is rejected outright rather
than propagated.

**Omitted, never null.** A counter absent from the receipt is absent from the
payload. `metrics._number` raises on a present-null numeric and `cost_summary`
gates on key presence, so absence is the only honest spelling of "not
reported". Never fill a gap with `0`.

**Three provenance outcomes.** The `measurement_source` string is the single
field that tells a reader what happened:

| `measurement_source` | Meaning |
|---|---|
| `openrouter_api_receipt` | The attempt succeeded and the provider reported usage. |
| `openrouter_receipt_no_usage` | The attempt succeeded and the provider reported no usage. |
| `openrouter_receipt_failed` | The attempt failed. `failure_kind` names the wrapper's reason. |

The last two both carry no counters, and `_translation` allows exactly those
two strings to hold a measurement-less scoped row. They are separate strings
because they are separate facts: **OpenRouter can bill a generation that
returns HTTP 200 with `usage: null`**, so a failed attempt collapsed into
"reported nothing" hides real spend. Any `outcome` other than the literal
`"success"` -- including a missing one -- is treated as a failure, because a
receipt that cannot state it succeeded has not demonstrated that it did. A
failed receipt that does carry counters keeps them: a partial generation that
billed tokens must show those tokens.

**Identity trust.** `provider` and `model` are the only payload fields sourced
from the receipt, and `identity_provenance` records that they were. Everything
else -- lane, chunk, node, attempt, host -- comes from the caller's flags, so
editing a receipt cannot reattribute usage to another lane. `generationId`,
`authorization`, and `routing` are deliberately not propagated; the receipt
file stays the durable provenance store.

## `lane-input-bytes`

Claude Code subagent and Codex CLI lanes expose no usage receipt surface at
all. Their measurement currency is deterministic input bytes: the agent
definition, the diff slice, and the boilerplate a lane is fed are computable
even when what the provider meters is not.

```sh
"$WORKFLOW_KERNEL" lane-input-bytes \
  --agent-definition <path> \
  --diff <path> \
  [--boilerplate <path> ...] \
  --lane <logical-lane-id> \
  --chunk-id <chunk-id> \
  --node-id <node-id> \
  --attempt <n> \
  --host <claude|codex|...> \
  --duration-seconds <seconds> \
  --requested-provider <id> --attempted-provider <id> --implemented-by <id> \
  --provider <id> --model <id> \
  [--output <payload.json>]
```

**Bytes are bytes.** The measurement lands in `input_bytes`, never in
`input_usage_count`. Those fields carry different units, the aggregator totals
them separately, and nothing anywhere converts between them. A byte count is
roughly four times the token count it corresponds to, so a reader who received
bytes under a token-named key would silently overstate usage -- which is the
entire reason the two fields are distinct.

`input_bytes` is always a present integer. A zero-length input contributes
`0`, which is a real measurement, not an omission. Every token counter and
`cost_usd` are absent.

**Fails closed and names the path.** Sizes come from `os.stat().st_size` only;
no file content enters the process. A missing path, a directory where a file
was expected, a dangling symlink, or a permission-denied file each raise with
the path in the message. There is never a silent `0` and never a zero-filled
row. Live symlinks are followed, matching `os.stat` semantics. Repeated
`--boilerplate` paths count once per occurrence; the list is deliberately not
deduplicated.

## Reading the two units together

A cost summary can contain rows in both units. Consumers must read `lanes[]`
per row and respect `measurement_source`:

```sh
jq -r '.lanes[] | [.lane, .measurement_source, .input_usage_count, .input_bytes] | @tsv' \
  run-cost-summary.json
```

`totals` sums a field only when every expected attempt contributed it *and*
all contributing rows agree on `measurement_source`. Partial coverage or
disagreeing provenance yields `null` for that field with `null` provenance --
never a partial sum presented as a whole. Per-lane rows stay fully populated
regardless.

## The emission boundary

The translators are reachable only if something calls them. An orchestrator
that runs lanes and never invokes them produces a structurally correct,
permanently empty cost summary -- the exact failure this measurement backbone
exists to end.

After each lane attempt completes, before the run's terminal receipt:

1. Pick the translator by rail. A lane that went through
   `openrouter-wrapper.sh` has a receipt: use `openrouter-usage`. A Codex or
   Claude lane has none: use `lane-input-bytes` with the exact files that lane
   was fed.
2. Wrap the returned payload in the run's `attempt_usage` event envelope.
3. Append it to that run's `authoritative-receipts.json` before
   `run-cost-summary` reads it.

Emit a row for **every** attempt, including failed ones. An attempt that
vanishes from the receipt stream is indistinguishable from an attempt that
never ran, and its spend disappears with it.

Verify the wiring by reading the artifact, not the code path:

```sh
jq '{lanes: (.lanes | length), coverage: .measurement_coverage.usage}' run-cost-summary.json
```

`lanes: 0` after a run that executed lanes means the boundary is not wired.
A structurally valid artifact with zero measured lanes is not evidence of
measurement.
