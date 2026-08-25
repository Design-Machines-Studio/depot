# Pipeline Manifest Schema

Promptcraft emits JSON at `prompts/manifest.json`. New manifests request an
execution role; they never select a concrete executor, model, provider,
transport, family, subscription, or billing source.

## Shape

```json
{
  "feature": "member export",
  "workflowClass": "feature",
  "decisionProfile": {"uncertainty": "medium", "consequence": "medium"},
  "renderedSurface": "not-applicable",
  "chunks": [
    {
      "id": "01-export-handler",
      "file": "prompts/01-export-handler.md",
      "dependsOn": [],
      "estimatedComplexity": "medium",
      "risk": "medium",
      "overlapRisk": "low",
      "kind": "logic",
      "renderedSurface": "not-applicable",
      "executorRole": "builder-deep",
      "executorCapabilities": ["read-repository", "write-repository", "tool-use", "long-context", "structured-output"],
      "executorEffort": "high",
      "ownedPaths": ["internal/export/**"],
      "verificationProfile": {
        "cases": [{"id": "export-test", "command": ["go", "test", "./internal/export"]}]
      }
    }
  ]
}
```

The full manifest is a closed operational contract. Preserve the established
feature, workflow class, decision profile, rendered-surface, dependency,
owned-path, verification-profile, risk, overlap, cleanup, and review semantics.
This change replaces routing identity only.

Freeze approved scope: newly discovered desirable work belongs in a follow-up
manifest unless it is required to correct an observable defect in an approved
requirement.

## Branch and final-review controls

| Field | Type | Contract |
|---|---|---|
| `branchMode` | enum | Required `create` or `reuse`; legacy absence defaults to `create` with a receipt. |
| `expectedFeatureHead` | string or null | Required exact remote head for `reuse`; null for `create`. |
| `finalReviewMode` | enum | Required `full` or explicitly approved eligible `quick`. |
| `finalReviewRationale` | string | Required non-empty rationale copied from the approved plan. |

These fields remain unchanged by role resolution.

## Rendered-Surface Applicability

| Field | Type | Contract |
|---|---|---|
| `renderedSurface` | enum | Required on new manifests. Closed values: `"required"` or `"not_applicable"`. Controls visual references, rendered-impression criteria, browser/persona cases, Datastar gates, browser preflight, browser smoke, and final visual verification. It never changes `kind`, role routing, or code-review depth. |
| `renderedSurfaceRationale` | string | Required non-empty evidence for the selected applicability. |

Mixed or uncertain scope must use `required`. Narrow `not_applicable` examples
include a planning/report `.html` artifact that is never mounted by the product
and a non-HTTP CLI `main.go` with no rendered output. Role routing cannot change
this field or weaken its browser/persona evidence.

## Role fields

| Field | Contract |
|---|---|
| `executorRole` | Required: `builder-fast` or `builder-deep`. |
| `executorCapabilities` | Required unique list from `read-repository`, `write-repository`, `tool-use`, `browser`, `long-context`, `structured-output`, `independent-family`. |
| `executorEffort` | Required normalized effort: `low`, `medium`, `high`, or `max`. |
| `routingOverride` | Optional closed object that may change only role, capabilities, effort, and record a reason. |

Derive defaults from `references/routing-policy.json`:

- `docs`, `config`, and bounded `mechanical-logic` use `builder-fast`;
- complex `logic`, `ui`, and `integration` use `builder-deep`;
- add `browser`, `tool-use`, `long-context`, or `structured-output` only when
  the chunk actually requires it.

Risk, consequence, uncertainty, workflow class, sensitive paths, and rendered
surface remain separate workflow inputs. They may strengthen scope,
authorization, or verification but are not encoded into a model or transport.

## Routing overrides

Allowed keys are `executorRole`, `executorCapabilities`, `executorEffort`,
`reasonCode`, and `reason`. An override cannot name or indirectly encode a
provider, model, transport, family, billing source, or subscription. Validate
with `references/validate-role-manifest.sh` before handoff.

## Legacy approved manifests

Do not rewrite historical approved manifests. At consumption time only,
`references/translate-legacy-executor.sh` maps the legacy `executor` field:

- `openrouter` becomes `builder-fast`;
- `codex` or `claude` becomes `builder-deep`.

The in-memory chunk records `legacyExecutorTranslation.occurred=true`, its
source field, and original value. The original file stays byte-identical. After
translation, execution requests the role through model-router and no longer
uses the legacy value for selection.

## Unchanged gates

New role fields never alter project-goal intake, decision-profile semantics,
rendered-surface behavior, dependency ordering, owned-path isolation,
repository verification, proportional review, zero-deferral P1/P2/P3
resolution, cleanup, or credential/authorization/data-loss/release-integrity
boundaries.
