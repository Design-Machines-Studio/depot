# Measurement CLI commands

`run-cost-summary` aggregates `attempt_usage` events that are already in a
run's receipt stream. It invents nothing. A run that appends no usage events
gets an artifact whose every row reads `unavailable` -- structurally valid,
informationally empty, and indistinguishable from a run that was never
measured at all.

Two commands produce those events. Each reads one input and emits one
attempt-scoped payload. With `--append-to` the same invocation also wraps that
payload as an `attempt_usage` receipt and appends it to the run's ledger, so
wiring a lane is one command rather than a prose recipe. See
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

Without `--output` or `--append-to` the payload goes to stdout as canonical
JSON (sorted keys, no spaces, trailing newline), so two runs over the same
receipt produce byte-identical bytes.

**Receipt requirements.** `schemaVersion` must be the integer `2` and
`outcome` must be a non-empty string. A counter that is negative, boolean,
float, or string-typed is rejected outright rather than propagated.

`outcome` is required rather than defaulted because the two available defaults
are both wrong. Treating a missing outcome as success would mask real
failures; treating it as failure would reclassify a legacy success and invent
failures that never happened. A schemaVersion-2 receipt that cannot state its
outcome is malformed, and the command says so and exits non-zero. (The library
function is more conservative than the CLI: called directly with a receipt
lacking `outcome`, it returns a failure row, because a library that cannot
reject must not assume success.)

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

## `emit-cost-summary`

One command, one transaction: it owns the artifact path, clears any stale file
left there by an earlier run, builds and writes the summary, and appends
exactly one inventory line to the run receipt.

```sh
"$WORKFLOW_KERNEL" emit-cost-summary \
  --events <run-dir>/authoritative-receipts.json \
  --output <run-dir>/run-cost-summary.json \
  --receipt <run-dir>/run-receipt.md \
  [--repository-commit <sha>] [--dirty-state]
```

**It always exits 0.** The artifact is observation-only, so a measurement
failure must never become a workflow failure. Signalling by exit code would
also leave the caller nothing useful to do, because the command has already
recorded what happened. The one case a caller still handles is the launcher
itself failing to run, which no process inside it can report:

```sh
"$WORKFLOW_KERNEL" emit-cost-summary ... \
  || printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> <receipt>
```

**Exactly one line, always.** Either `run-cost-summary: <artifact path>` or
`run-cost-summary: skipped (<reason>)`. Reasons are `unsafe-path` (a symlinked
artifact or receipt component inside the workspace),
`stale-artifact-not-removable`, and `summary-failed`.

**Why this is one command and not a shell block.** It used to be six lines
duplicated into eleven consumer files: remove the stale artifact, run the
summary, then branch on the exit code to append either the artifact path or a
skip line. Six independent review lanes found defects in that block -- an
unchecked `rm -f` that let a stale artifact be recorded as the current run's, a
`test -L` preflight that a later `>>` raced, an `&& ... || ...` chain that
could append a skip line after already appending the artifact line, and a
validator that could only check the prose beside it. None of those were shell
bugs to patch. They were what happens when a transaction is written as a
sequence of independent commands.

**Symlink handling, honestly.** The command refuses a symlinked component of
the artifact or receipt path inside the workspace, and opens the receipt with
`O_NOFOLLOW`. Components *above* the workspace are not judged: the operating
system legitimately symlinks them (macOS resolves `/var` to `/private/var`).
This closes accidental and leftover symlinks. It does not defeat an attacker
who can swap a directory between the check and the open -- but that attacker
can already edit the scripts being run, so the check is stated for what it is.

A symlinked *receipt* is the one refusal the command cannot record, because
there is nowhere safe to record it. That goes to stderr and the receipt is left
untouched; it is an operator misconfiguration, not a measurement gap.

## The emission boundary

The translators are reachable only if something calls them. An orchestrator
that runs lanes and never invokes them produces a structurally correct,
permanently empty cost summary -- the exact failure this measurement backbone
exists to end.

After each lane attempt completes, before the run's terminal receipt, run the
matching translator with `--append-to`. Pick it by rail: a lane that went
through `openrouter-wrapper.sh` has a receipt, so use `openrouter-usage`; a
Codex or Claude lane has none, so use `lane-input-bytes` with the exact files
that lane was fed.

```sh
"$WORKFLOW_KERNEL" openrouter-usage \
  --receipt <wrapper-receipt.json> \
  --lane <lane> --chunk-id <chunk> --node-id <node> \
  --attempt <n> --host <host> --duration-seconds <seconds> \
  --append-to <run-dir>/authoritative-receipts.json \
  --run-id <run-id> \
  --occurred-at <timezone-aware-ISO-8601> \
  --authoritative-receipt <path-to-that-lane-s-receipt>
```

`--append-to` is the whole boundary in one command. It wraps the payload as an
`attempt_usage` receipt, derives `sequence` from the existing array so a caller
cannot collide two receipts or leave a gap, re-translates the entire stream to
prove it still parses, and only then replaces the file atomically. A crash
mid-append leaves the prior stream intact.

`--run-id`, `--occurred-at`, and `--authoritative-receipt` are required with
`--append-to` and rejected-by-omission rather than defaulted: a receipt with a
guessed timestamp or a missing provenance pointer is not evidence.

The append holds an exclusive `flock` on `<receipts>.lock` across load,
validate, and replace. Lane attempts finish concurrently by design, and atomic
replacement alone would not save them: two appenders could both read length
`n`, both claim sequence `n`, and the later write would silently discard the
earlier attempt -- a measurement backbone losing exactly what it exists to
keep.

`--append-to` and `--output` are mutually exclusive. Appending mutates a
durable ledger; writing `--output` does not. Allowing both would mean an
`--output` failure could report the command as failed over an attempt already
recorded, and a retry would append it twice.

Emit a row for **every** attempt, including failed ones. An attempt that
vanishes from the receipt stream is indistinguishable from an attempt that
never ran, and its spend disappears with it.

What this boundary does not do: nothing forces an orchestrator to call it. The
command exists so that wiring a lane is one invocation rather than a prose
recipe, but a runner that never invokes it still produces an empty summary.
That is what the verification below is for -- check the artifact, not the
intention.

Verify the wiring by reading the artifact, not the code path:

```sh
jq '{lanes: (.lanes | length), coverage: .measurement_coverage.usage}' run-cost-summary.json
```

`lanes: 0` after a run that executed lanes means the boundary is not wired.
A structurally valid artifact with zero measured lanes is not evidence of
measurement.
