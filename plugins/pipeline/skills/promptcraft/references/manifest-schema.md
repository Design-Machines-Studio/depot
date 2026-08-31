# Pipeline Manifest Schema

Promptcraft emits JSON at `prompts/manifest.json`. New manifests request an
execution role; they never select a concrete executor, model, provider,
transport, family, subscription, or billing source.

## Shape

```json
{
  "feature": "member export",
  "workflowClass": "feature",
  "decisionProfile": {"uncertainty": "medium", "consequence": "medium", "rationale": "Bounded member export."},
  "renderedSurface": "not_applicable",
  "baseBranch": "main",
  "featureBranch": "feat/member-export",
  "branchMode": "create",
  "expectedFeatureHead": null,
  "finalReviewMode": "full",
  "finalReviewRationale": "The export changes data handling.",
  "chunks": [
    {
      "id": "01-export-handler",
      "level": 0,
      "title": "Implement the export handler",
      "prompt": "prompts/01-export-handler.md",
      "dependsOn": [],
      "estimatedComplexity": "medium",
      "risk": "medium",
      "overlapRisk": "low",
      "kind": "logic",
      "renderedSurface": "not_applicable",
      "renderedSurfaceRationale": "The export is a non-HTTP command.",
      "executorRole": "builder-deep",
      "executorCapabilities": ["read-repository", "write-repository", "tool-use", "long-context", "structured-output"],
      "executorEffort": "high",
      "filesToModify": ["internal/export/**"],
      "companionSkills": [],
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

## Optional Declared Prototype Context

When a prototype is declared, the manifest carries exactly one top-level
`prototypeReference`. A counterpart-covered rendered chunk carries its own
non-empty `prototypeParity` array; `prototypeReference` is forbidden inside a
chunk and `prototypeParity` is forbidden at the top level. Both objects are
closed shapes validated by `validate-role-manifest.sh`.

```json
{
  "prototypeReference": {
    "status": "counterpart",
    "canonicalRepository": "Design-Machines-Studio/assembly",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "authoritySource": "current PR",
    "prototypeSourceFiles": ["prototype/templates/positions.html"],
    "targetSourceFiles": ["internal/positions/index.templ"],
    "matchedCases": [
      {
        "prototypeRoute": "/prototype/positions",
        "targetRoute": "/positions",
        "state": "default",
        "viewports": [375, 1440]
      }
    ],
    "intentionalDifferences": ["Production keeps its authenticated shell."]
  },
  "chunks": [
    {
      "id": "01-positions-ui",
      "renderedSurface": "required",
      "prototypeParity": [
        {
          "surface": "positions index",
          "prototypeSourcePaths": ["prototype/templates/positions.html"],
          "targetSourcePaths": ["internal/positions/index.templ"],
          "prototypeRoute": "/prototype/positions",
          "targetRoute": "/positions",
          "state": "default",
          "viewports": [375, 1440],
          "sourceDecisions": {
            "structure": ["Heading precedes the position list."],
            "classes": ["cluster cluster--spread"],
            "copy": ["Positions"],
            "actions": ["Create position is the first action."]
          },
          "sourceEvidenceStatus": "complete",
          "renderedEvidenceStatus": "pending",
          "intentionalDifferences": ["Production keeps its authenticated shell."]
        }
      ]
    }
  ]
}
```

| Field | Contract |
|---|---|
| `prototypeReference.status` | Required enum: `counterpart` or `no_counterpart`. |
| `canonicalRepository` | Required non-empty canonical remote identity, never a workstation path. |
| `commit` | Required exact 40-character lowercase Git commit. |
| `authoritySource` | Required non-empty source of the declaration. |
| `prototypeSourceFiles` | Required non-empty unique list of inspected prototype paths. |
| `targetSourceFiles` | Unique target paths; non-empty for `counterpart`. |
| `matchedCases` | Closed route/state/viewport objects; non-empty for `counterpart` and empty for `no_counterpart`. |
| `intentionalDifferences` | Unique concise approved differences; may be empty. |
| `chunks[].prototypeParity` | Closed affected-surface items. Allowed only on `renderedSurface: required` chunks when status is `counterpart`; every route/state/viewport tuple and source path must agree with the top-level reference. |

Each parity item requires non-empty prototype and target source paths, matched
routes/state/viewports, closed `sourceDecisions` arrays for `structure`,
`classes`, `copy`, and `actions`, `sourceEvidenceStatus` and
`renderedEvidenceStatus` from `pending|complete|unavailable`, plus a unique
intentional-differences list. A `counterpart` reference requires at least one
chunk parity item. A source-proven `no_counterpart` reference requires empty
target files and matched cases and forbids chunk parity. When no prototype was
declared, omit both fields. These compact objects never embed complete
templates or create a durable registry.

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
