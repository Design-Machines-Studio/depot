# Campaign State Schema

The campaign state file (`.campaign/state.json`) enables cross-session state persistence between the prototype repo (assembly) and the production repo (assembly-baseplate). It records the outcome of each pipeline run so the next planning session can pick up where the last one left off.

## Schema

```json
{
  "campaignSlug": "governance-v1",
  "lastFeatureSlug": "proposal-voting",
  "branch": "feature/proposal-voting",
  "commit": "abc123def456789",
  "completedAt": "2026-05-11T14:30:00Z",
  "requirementsCovered": [
    "Add vote handler and routes",
    "Display vote counts on proposal page",
    "Wire voting into proposal detail with Datastar"
  ],
  "requirementsDeferred": [
    "Quorum threshold visualization"
  ],
  "dmReviewFindingsSummary": {
    "p1": 0,
    "p2": 1,
    "p3": 3,
    "mergeRecommendation": "APPROVE WITH FIXES"
  },
  "nextSuggestedFeature": "member-equity-tracking"
}
```

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `campaignSlug` | string | Campaign identifier matching the manifest's `campaignSlug` field |
| `lastFeatureSlug` | string | Feature slug of the most recent pipeline run |
| `branch` | string | Feature branch name from the completed run |
| `commit` | string | HEAD SHA of the feature branch at completion |
| `completedAt` | string | ISO 8601 datetime of pipeline completion |
| `requirementsCovered` | string[] | List of requirements addressed in this run (from final-requirements-crosscheck.md) |
| `requirementsDeferred` | string[] | List of requirements not addressed, with reasons (from final-requirements-crosscheck.md) |
| `dmReviewFindingsSummary` | object | Summary of final dm-review findings: `{ p1: number, p2: number, p3: number, mergeRecommendation: string }` |
| `nextSuggestedFeature` | string or null | Suggested next feature from the campaign plan. Null if no campaign plan exists or no next feature is obvious. |

## Read/Write Conventions

- **Orchestrator writes** after a successful pipeline run (Step 5c in execution-orchestrator.md)
- **Planning session reads** before writing the next master prompt -- uses `requirementsCovered`, `requirementsDeferred`, and `nextSuggestedFeature` to scope the next feature
- **File location:** `.campaign/state.json` in the production repo root
- **Create** the `.campaign/` directory if absent
- **Overwrite** (not append) -- the latest run is the current state. Previous state is available via git history.
- The file is committed to the production repo so both sides (prototype and production) can read it
