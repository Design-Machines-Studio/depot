# Host-owned deterministic verification evidence

Builds, tests, linters, generators, and repository verification profiles are
host mechanics, not model judgment. When dm-review selects a deterministic
verification lane, run it before any analysis participant.

Use the repository's existing tracked verification profile through Workflow
Kernel when one applies. Otherwise use only the exact repository-owned command
already selected by dm-review's established build/test mapping. Do not invent a
second command ladder, guess a mutating command, or ask a model to discover and
run shell commands.

Capture one bounded evidence envelope per executed command:

```json
{
  "schemaVersion": 1,
  "lane": "tests/build",
  "commandArgv": ["./tools/verify"],
  "exitStatus": 0,
  "result": "passed",
  "stdoutTail": "bounded to 8192 UTF-8 bytes",
  "stderrTail": "bounded to 8192 UTF-8 bytes"
}
```

Keep argv as an array. Record the exact exit status. Retain at most the final
8,192 UTF-8 bytes from each stream, replacing invalid UTF-8 and credential-like
values with the existing safe redaction marker before materializing evidence.
An exit-zero host result settles deterministic execution without a model call.
A nonzero result is authoritative failure evidence; a `review-fast` or
`review-deep` participant may analyze the bounded envelope and relevant
repository evidence with only `read-repository` and `structured-output` (plus
`long-context` only when justified). The participant never receives command
authority and cannot convert a failing command into success.

Reserve routed `tool-use` for a selected task whose participant must actually
invoke tools and for which host-produced evidence is not equivalent. The normal
tests/build lane does not meet that condition.
