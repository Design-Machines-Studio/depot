# Depot Role Benchmark

This is a small project-specific complement to public coding-agent benchmarks,
not a replacement for them. It measures four contracts Depot actually depends
on: Pipeline manifest translation, review severity with zero deferral, bounded
Assembly chunk selection, and an exact owned mechanical edit.

The suite is manual and one-candidate-at-a-time. It never schedules a sweep,
chooses a model for an orchestrator, or uses another model as a judge. Each
answer is scored locally with closed assertions. Run at least three successful
attempts per applicable case before using the evidence to promote a candidate;
retain every result, including failures, to avoid selection bias.

```shell
./depot-role-benchmark.sh --list
./depot-role-benchmark.sh --run \
  --case pipeline-legacy-translation \
  --model deepseek/deepseek-v4-flash-0731 \
  --role-policy ../../../../model-router/skills/model-router/references/role-policy.json \
  --result-dir /private/operator-owned/result-directory
```

`--run` requires the explicit checked-in role policy, rejects substituted live
suite/matrix/wrapper assets, and validates the exact slug against both the role
policy and checked-in OpenRouter matrix,
uses the same input eligibility as a native Claude/Codex candidate, disables
model fallback, invokes the existing wrapper, and produces a private
provider receipt plus a compact scored result. The explicit model is permitted
here because this is an operator measurement command, not orchestration.

Offline fixture scoring uses `--prepare` and `--score`; it makes no provider
call. Compare candidates using median quality, median duration, success rate,
and measured token/cost receipt fields. Do not collapse those axes into one
opaque leaderboard number. A role-policy change still requires review.

## Optima mapping

Artificial Analysis Optima can be an optional hosted measurement surface. The
suite records a suggested Optima task type and objective-rubric grader for each
case. Copy or trace a case manually, keep its prompt and deterministic expected
result unchanged, and record the Optima benchmark version beside Depot's local
result. Pairwise judging may be useful for genuinely subjective editorial work,
but it must not replace the closed scorers in this suite.

Depot does not depend on Optima and does not automate hosted spend. No public
Optima import/API contract was available during this refresh, so this slice
does not invent one. If a stable import format becomes available, add an export
adapter—not a scheduler, service, database, or generic benchmark framework.
