# Plan and receipt template

Keep plans and receipts under `/home/ned/.local/state/design-machines/publish-preview/`. They are
operator-local, non-secret, and never committed to Depot.

## Reviewed plan

Record:

- operation, project ID, hostname, inventory fingerprint, and discovery timestamp;
- account preflight facts without environment or credential values;
- runtime facts: checkout, project/service, health, persistence, restart policy, loopback backend;
- current and proposed Caddy fragment plus full-config fingerprint;
- current and proposed exact Tunnel hostname and DNS record IDs/fingerprints;
- current and proposed Access application/policy IDs, ownership markers, and identity-file digest/count;
- current and proposed Kuma monitor ID, signal, and notification-provider identity;
- exact `ned` steps and exact bounded `trav` steps;
- verification commands/evidence, rollback order, conflicts, and manual gaps.

Compute a plan ID from the canonical non-secret plan bytes. Show the complete plan and ask the user to
approve that ID. Approval expires when relevant inventory or live-state fingerprints change. Never describe
a dry run as published.

## Ownership identities

Use the inventory marker as a prefix, then a resource suffix. Every automatic update or removal requires
provider/resource ID, exact marker, expected hostname/scope, and the receipt's before/after fingerprint:

| Resource | Identity stored remotely or locally |
|---|---|
| Caddy fragment | owned filename header + marker + exact hostname/backend |
| Tunnel ingress | marker in the local receipt plus tunnel ID, exact hostname/service, ordered position, and before/current whole-config fingerprints; removal requires every field to match fresh rediscovery, otherwise stop as `ambiguous` and use a manual step |
| DNS record | provider ID + exact ownership comment/tag + exact hostname/CNAME |
| Access application | application ID + workflow tag/name marker + exact domain |
| Access policy | app-scoped policy ID + workflow marker + approved identity-file digest/count |
| Kuma monitor | monitor ID + deterministic owned name + exact monitored signal |

Missing, duplicate, or mismatched ownership evidence is a conflict. Never infer ownership from hostname,
display name, or backend alone.

## Receipt

Create the receipt atomically in `planned` state before the first mutation. After every attempted or
completed step, atomically replace it with the new step outcome and any non-secret resource ID before
advancing. This small per-step ledger is the interruption/retry record; a final summary written only after
publication is not sufficient.

Record one entry per attempted step:

```json
{
  "version": 1,
  "operation": "publish",
  "planId": "sha256-of-reviewed-plan",
  "projectId": "fictional-assembly-preview",
  "hostname": "dm999.asmbly.app",
  "outcome": "partial",
  "steps": [
    {
      "layer": "caddy",
      "outcome": "verified",
      "ownership": "created-by-run",
      "resourceId": "generated-fragment:dm999.asmbly.app",
      "beforeFingerprint": "sha256-or-null",
      "afterFingerprint": "sha256"
    },
    {
      "layer": "kuma",
      "outcome": "manual-required",
      "ownership": "not-created",
      "resourceId": null,
      "nextAction": "Complete the bounded Kuma UI enrollment, then rerun verify."
    }
  ],
  "unresolved": ["Kuma enrollment and authenticated browser verification remain unperformed."]
}
```

Allowed outcomes are `planned`, `verified`, `failed`, `ambiguous`, `manual-required`, `rolled-back`, and
`partial`. Record resource IDs and fingerprints, never credentials, identity values, provider response
bodies, headers, cookies, or notification configuration.

On retry, rediscover live state first. Delete only a resource whose ID and ownership marker match the
receipt. If a provider timeout leaves the result ambiguous, do not retry or compensate until rediscovery
proves what happened.
