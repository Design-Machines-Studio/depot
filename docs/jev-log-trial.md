# Jev log-selection experiment

This manual experiment asks whether Jev can reduce the verification-log context
read by a coding agent after ordinary deterministic filtering. It has no hook,
service, production routing effect, review authority, or plugin dependency floor.
It reuses the existing OpenRouter Decisions adapter rather than adding transport
or credential code. Do not treat it as a replacement for tests or review lanes.

## Run

Prepare both evidence packets without network access:

```sh
python3 tools/jev-log-trial.py \
  --corpus tests/fixtures/jev-log-corpus.json --out /tmp/jev-log-prepared
python3 tests/test_jev_log_trial.py -v
```

The output directory must not already exist. Each case retains the original
log, its SHA-256, repository/revision/artifact reference, exact original line
numbers, observed exit code (or null), and baseline/selected JSON packets.
Labels stay outside provider input. Labels are evaluation references, not facts
established by the model. The checked-in 30 scenarios are synthetic test data;
their successful fixture execution is not measured Jev accuracy.

For a paid trial, resolve one coherent installed OpenRouter bundle with the
Workflow Kernel `resolve-plugin-bundle` command, minimum version 1.21.1, requiring
`skills/openrouter-delegate/references/openrouter-decisions.sh` and its
`openrouter-credential.sh`. Follow the installed Jev adapter reference and pass
its inspected executable path:

```sh
python3 tools/jev-log-trial.py --corpus /path/to/historical-corpus.json \
  --out /path/to/new-private-results \
  --live-adapter /resolved/openrouter/skills/openrouter-delegate/references/openrouter-decisions.sh
```

This explicitly enables paid calls. The existing adapter loads credentials;
the experiment does not inspect keys. A run accepts at most 30 cases and sends
at most one 32,000-byte request per eligible case, with a 20-second adapter
timeout. An input exceeding the adapter's byte/question limits bypasses Jev
without truncation. The first transport/credential/provider failure stops further
calls in that run. Remaining cases keep the baseline; there are no retries.
An optional `--fixture-responses FILE` supplies offline response fixtures and is
mutually exclusive with live mode. Its results are marked synthetic transport.

## What is compared

Both arms first keep the first/last four lines and two lines around each
error/failure/panic/warning/availability marker. Contiguous selections are split
into sections of at most twelve lines. This is a fixed, deliberately simple
baseline, not a general log parser. The reference essential-line list exposes
evidence missed by this baseline separately from anything missed by Jev.

Jev classifies the failure and each section. Only an explicit `drop` with both
probability and confidence at least 0.95 removes a section. Uncertain or malformed
answers keep the baseline; an empty selection also keeps it. This threshold is
an experimental policy, not a claim of calibrated 95% accuracy on Depot logs.
All original evidence remains available for follow-up inspection.

Results distinguish log bytes from complete packet bytes. They record provider
token usage and a price-derived estimate at $0.042/M input tokens (2026-09-30),
not a measured charge or subscription saving. Missing measurements stay null.
The model/provider identity and timing in the adapter receipt are authoritative
for the call; a requested model name alone is not served-identity proof.

If selection shows promise, use the two packets in fresh, matched Codex sessions
with the same model, effort, tools and exact repository head. Alternate which
arm runs first. Ask for the same diagnosis and allow original-log/code reads.
Record authoritative input/cached/output tokens, all follow-up reads and calls,
elapsed time, subscription calls, paid charges when available, and independently
checked diagnosis correctness. Include Jev's overhead in the assisted arm.
Do not infer total completion cost from packet length, API-equivalent pricing,
or confidence. The runner deliberately leaves downstream metrics null until
that paired evidence exists; it does not launch a second model harness.

Before adoption, expand to approximately 30 representative historical failures,
including ambiguous and multi-cause cases, with independently checked labels.
Fix the question/threshold before the held-out comparison. Require lower total
completion cost without losing essential evidence or worsening diagnosis.
Stop early if the classifier adds work without reducing the packet. Deployment
into Pipeline, dm-review, or Foreman is separate work requiring this evidence.

## Initial live result — 2026-09-30

Two historical Baseplate PR #1066 artifacts were tested through installed
OpenRouter 1.22.0. Both bind to head
`2137de06c6d4c4f8c78e3528ca552c4177c9138d`. Reference labels were assigned by the
implementing agent, not an independent human evaluator.

| Artifact | Baseline log bytes | Jev-selected bytes | Reference / response | Essential lines lost |
|---|---:|---:|---|---:|
| [Docker startup CI failure](https://github.com/Design-Machines-Studio/assembly-baseplate/actions/runs/36667152709/job/109734148312) | 11,972 | 11,972 | dependency / unknown | 0 |
| Retained failed reviewer-dispatch receipt | 1,199 | 1,199 | routing / routing | 0 |

The original Docker log was 392,344 bytes: deterministic filtering already did
most of the reduction. Jev made no further reduction on either case. Both live
responses passed adapter validation, totaling 8,197 reported input and 626 output
tokens. The price-derived estimate is $0.000344274; measured paid charges and
downstream Codex usage are unavailable. Raw logs and private receipts remain
outside Git at `/home/ned/benchmark-results/jev-log-trial-20260930/`.

**Decision: do not adopt.** The initial selection trial added two calls without
reducing either packet, so no paired Codex runs were spent on identical packets.
This small result does not establish that Jev is ineffective in other settings.
It establishes no token, latency, accuracy, or subscription saving for this one.
The reusable experiment and synthetic failure tests remain available for a
future, evidenced workload with more difficult relevance selection.
