# Deterministic validation feedback

Load on an eligible deterministic check failure in Step 3e.

Persist a closed feedback receipt with exactly these fields (nullable fields stay present):

```json
{
  "stage": "deterministic_validation",
  "contract_digest": "sha256:<current>",
  "contract_revision": 1,
  "failing_check_ids": ["CHK-..."],
  "evidence_refs": ["receipts/<safe-ref>"],
  "failure_signature": "sha256:<stable-safe-digest>",
  "reproduction_instruction": "<trusted profile-derived bounded instruction>",
  "retry_reason": "deterministic_validation_failure",
  "attempt": 1,
  "remaining_retry_budget": 1,
  "builder_session_continuity": "unavailable",
  "action": "replace",
  "human_intervention_id": null,
  "human_intervention_reason": null,
  "requestedProvider": "openrouter",
  "attemptedProvider": "codex",
  "implementedBy": "codex",
  "fallback": true,
  "fallbackReason": "provider-unavailable",
  "prior_attempt_ref": "receipts/<safe-prior-attempt-ref>",
  "resume_unavailable_reason": "session-continuity-unavailable",
  "receipt_ref": "receipts/<safe-ref>",
  "repo_scope_ref": ".workflow-kernel/repository-scope.json"
}
```

`failing_check_ids` is sorted by the behavioral contract's check order. Closed enums: `builder_session_continuity: proven|unavailable|invalid`, `action: resume|replace|human_help_required`, `implementedBy: codex|openrouter|null`. `fallback` is strictly boolean. Provider transition is only `requestedProvider` / `attemptedProvider` / `implementedBy`. Durable refs are `evidence_refs`, `prior_attempt_ref`, `receipt_ref`, and `repo_scope_ref`.

Derive `reproduction_instruction` from the trusted repository verification profile. Never include raw output, prompts, tokens, credentials, environment, URLs, arbitrary host paths, or unbounded output.

Derive `failure_signature` from contract digest/revision, `failing_check_ids` in contract order, and safe evidence digests. `attempt` and `remaining_retry_budget` are kernel projections.

```text
$WORKFLOW_KERNEL decide-validation-retry --state-dir .workflow-kernel/runs/<run-id> --reason deterministic_validation_failure --signature <stable-signature>
```

Reject non-zero output or a document whose keys are not exactly `allowed`, `reason_code`, `budget`, `attempt_count`, and `prior_signature`. Consume all five. Append prior failure count and signature to `AttemptLedger` before the next decision.

Project into `ValidationFeedback`:

```text
node_id: <chunk-id>
reason_code: deterministic_validation_failure
evidence: [<safe feedback receipt ref>, <safe deterministic evidence refs>]
```

Resolver stays inside repository scope and extracts only failing check IDs, safe evidence refs/digests, and bounded `reproduction_instruction`. Invalid receipts stop repair before any model call.

Resume only when durable evidence proves dispatch identity, protected session token/handle, same host, same repository scope, same chunk/node, same rail context, and exact current contract digest/revision (`builder_session_continuity: proven`). Missing proof is `unavailable`; conflicting proof is `invalid`. Use `resume_or_replace` with the three-field `ValidationFeedback`.

When continuity is unavailable/invalid but retry is allowed, dispatch a replacement and record requested/attempted/implementedBy, boolean fallback and reason, prior attempt reference, and why resume was unavailable. If replacement cannot be dispatched, use `human_help_required` with `human_intervention_reason`: `replacement_adapter_dispatch_failed`, `replacement_invalid_session_handle`, or `replacement_session_handle_unavailable`.

When the kernel returns `identical_failure_convergence`, `retry_budget_exhausted`, or a replacement-dispatch failure, write the closed receipt with `action: human_help_required`, a deterministic `human_intervention_id`, and the exact terminal reason. Mark the chunk failed and every transitive dependency blocked.
