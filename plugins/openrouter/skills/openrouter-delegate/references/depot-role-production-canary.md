# Depot role production canary

`depot-role-production-canary-v1` measures one exact policy-admitted candidate
in one disposable Depot worktree. It supplements `depot-role-v2`; it never
relabels a sealed attempt, ordinary Pipeline/dm-review observation, or provider
economics as canary evidence.

The current consumer is the model-intelligence operator deciding whether a
challenger has enough attributable production evidence to justify a later
routing proposal. The boundary prevents repository, evaluator, identity,
transport, and harness failures from becoming model conclusions. It replaces
the ad hoc production experiments preserved in PR #106, not the v2 runner or
Workflow Kernel.

## Run one attempt

Use a clean isolated Depot checkout whose `HEAD` is the immutable base. The
runner rejects dirty source checkouts and never changes the invoking checkout.
Run only one lane at a time:

```sh
CANARY=./plugins/openrouter/skills/openrouter-delegate/references/depot-role-production-canary.sh
BASE="$(git rev-parse HEAD)"

"$CANARY" --list
"$CANARY" --run \
  --work-unit canary-research-claim-map \
  --transport codex-cli \
  --model gpt-5.6-luna \
  --effort medium \
  --base-revision "$BASE" \
  --result-dir /home/ned/benchmark-results/depot-role-production-canary/native/research-fast/run-1
```

The runner creates one temporary detached worktree, binds the repository,
work unit, fixture, v2 case/scorer, role policy, harness, and plugin versions,
then removes the worktree on success, failure, interruption, or benchmark
fault. It retains only the bounded result directory. The result directory must
be new or empty, real, and outside the operator checkout.

OpenRouter uses the same work-unit prompt, context extracts, v2 scorer, and
attempt schema:

```sh
"$CANARY" --run \
  --work-unit canary-research-claim-map \
  --transport openrouter \
  --model google/gemini-3.7-flash \
  --effort medium \
  --base-revision "$BASE" \
  --max-corrections 0 \
  --result-dir /home/ned/benchmark-results/depot-role-production-canary/openrouter/research-fast/run-1
```

A configured OpenRouter key authorizes this one bounded attempt. The runner
computes a conservative maximum from bounded input bytes, checked-in prices,
and the model's maximum output tokens. It stops before contact unless that
maximum is at most USD $1.00. It passes no model fallback, disables provider
fallback, permits no paid retry, and requires a numeric nonnegative provider
cost at or below both the preflight bound and USD $1.00.

## Stop conditions

Stop the lane and make no model conclusion on a broken fixture, evaluator or
scorer substitution, validator defect, dirty base or repository setup failure,
missing required instrumentation or tool, unsafe artifact, or harness failure.
These are `benchmarkFault:true`. Preserve bounded diagnostics, repair the
boundary, and pass offline fixtures before another call.

Transport failure, provider refusal, model fallback, missing or unknown served
identity, unmapped native alias, and cross-model response are non-comparable.
A missing paid-cost receipt also stops all further paid attempts. Only a result
with intact repository, fixture, evaluator, validator, instrumentation, tool,
harness, and identity boundaries may produce a model conclusion.

## Measurements and coverage

The attempt records first-pass and final validity, every mandatory assertion,
useful findings, false positives, correction count, validation attempts,
changed-file count, tool calls by useful class, time to first useful result,
time to valid, total duration, tokens when supplied, and context/tool coverage.
Unavailable optional measurements remain `null`. Reporter coverage is
`recorded / comparable attempts`; null never becomes zero.

The runner permits at most two native correction cycles and no paid correction
cycle. A correction is one additional candidate invocation after bounded
failed-assertion feedback. Independent reruns are separate attempts.

## Retention, cleanup, and privacy

- Keep raw attempts outside Git below a private, mode-0700 result root.
- Retain only the bounded artifacts named by the attempt; do not retain
  unrestricted transcripts.
- Candidate identity stays out of participant prompts and in the private
  attempt and final operator report.
- Never send credentials, environment files, client repositories, private
  endpoints, raw private receipts, unrelated content, or paths outside the
  checked-in selectors.
- The runner owns and removes its temporary worktree on every exit. Do not run
  repository-wide worktree pruning as cleanup.

## Reporting and routing boundary

```sh
./tools/model-intelligence.py report \
  --canary-root /home/ned/benchmark-results/depot-role-production-canary \
  --benchmark-root /home/ned/benchmark-results/depot-role-v2 \
  --json-output /tmp/model-intelligence.json \
  --markdown-output /tmp/model-intelligence.md
```

The routing ledger uses only `absent`, `incompatible`, `benchmark-faulted`,
`comparable-but-insufficient`, and `gate-clearing`. Five comparable valid
attempts clear this canary evidence threshold for one exact candidate, role,
transport, and compatible cohort. The field is evidence state only and never
changes candidate ordering.

Even `gate-clearing` canary evidence is insufficient by itself. A routing
proposal still needs the current sealed cohort, exact availability and
identity, capability and family gates, policy review, subscription preference,
compatible evaluator bindings, fault analysis, and attributable production
outcomes. The two implementation smoke attempts demonstrate contract
operability only: **no routing change justified**.
