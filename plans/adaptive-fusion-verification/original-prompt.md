# Original Prompt

## User Input

Let's implement.

## Approved Context

Implement the adapted improvements recommended immediately before this request, without blindly copying the creator's custom harness or command surface:

1. Add a versioned pre-build verification contract that binds required behavior, deterministic checks, browser/persona cases, evidence, and explicit failure conditions without freezing test implementation.
2. Wire workflow-kernel validation feedback and browser recovery into the authoritative pipeline with bounded retries, repeated-failure detection, and `human_help_required` escalation.
3. Make dm-review convergence disagreement-aware, preserving consensus, unique findings, conflicts, retained/discarded recommendations, rationale, and source provenance.
4. Extend routing decisions with uncertainty and consequence so multi-model synthesis is selective rather than mandatory.
5. Extend telemetry to measure per-attempt/per-model tokens, duration, cost, fallback, unique contribution, retained findings, retries, and human intervention.
6. Preserve the existing architecture: pipeline coordinates, workflow-kernel owns deterministic state and evidence, dm-review supplies independent criticism, and deterministic tools prove completion.

## Date

2026-07-22

## Key Requirements Extracted

1. Implement a versioned verification contract that is bound before builder dispatch and can be explicitly revised without silently changing behavioral requirements.
2. Make structured validation failure feedback and browser recovery authoritative in pipeline execution, with bounded retries and fail-closed human escalation.
3. Preserve reviewer disagreement and provenance through dm-review convergence instead of flattening results to deduplicated findings.
4. Select additional model perspectives using uncertainty and consequence, keeping simple work fast and sensitive work on trusted routes.
5. Record per-attempt and per-model economics and contribution metrics sufficient to evaluate whether additional compute improves outcomes.
6. Retain all existing workflow-kernel safety, cleanup, persona, browser, provider-routing, and zero-deferral guarantees.
