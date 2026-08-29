# Legacy browser-recovery reconciliation

This is one closed compatibility contract for a retained Pipeline ledger whose
historical `browser_recovery` row was valid when written but predates the
required `recovery_receipts` proof field. It is not a general migration,
invalid-row allowlist, or best-effort observation mode.

Pipeline owns the decision to append the reconciliation. Workflow Kernel owns
only its deterministic derivation, validation, and atomic ledger replacement.
This producer path requires Workflow Kernel `>=0.18.1`; version 0.18.0 cannot
digest the retained schema-owned colon-bearing identifiers.
Invoke it only for an owner-approved known historical row after preserving a
copy of the authoritative ledger:

```sh
"$WORKFLOW_KERNEL" reconcile-legacy-browser \
  --events plans/<feature>/authoritative-receipts.json \
  --target-sequence <exact-zero-based-sequence> \
  --occurred-at <timezone-aware-ISO-8601> \
  --authoritative-receipt plans/<feature>/authoritative-receipts.json
```

The writer derives rather than accepts the run ID, target stage, target digest,
contract digest, reconciliation stage, status, and reason. It appends exactly
one `legacy_browser_reconciliation` row with status `recorded` and fixed reason
`legacy_browser_recovery_missing_canonical_proof`. Its target identity binds the
same run, exact sequence, `browser_recovery` stage, raw receipt digest under the
kernel's canonical document encoding, and current contract digest.

The target must be the exact earlier `blocked` / `human_help_required` shape,
must lack `recovery_receipts`, and must follow the same authoritative contract
binding as the reconciliation. Both timestamps must be timezone-aware ISO-8601,
and the reconciliation timestamp must be strictly later than the target's in the
same contiguous run. An already canonical target is ineligible; no
reconciliation is needed for it.

The original row is never replaced or normalized. It remains a blocked human
intervention in observation and metrics. The reconciliation row has no browser
counts, acceptance status, verification success, or terminal semantics. Only a
genuinely later canonical browser-verification receipt can record later success.

Missing, reordered, duplicate, conflicting, cross-run, cross-contract,
wrong-stage, wrong-reason, digest-mismatched, ambiguous, malformed, oversized,
or tampered claims reject the entire stream. Failure leaves the ledger and all
observation, comparison, metrics, and cost outputs unchanged.
