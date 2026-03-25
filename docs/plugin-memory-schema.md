# Plugin Memory Schema

Defines how depot plugin metrics are stored in ai-memory. These entities track skill invocations, user corrections, and review session data to improve plugin descriptions.

## Entity Types

### `DepotMetrics` (type: System)

Single entity tracking marketplace-wide events. One entity for the entire depot.

Only receives non-correct invocations and review session summaries. Correct invocations are tracked per-plugin only.

**Observation formats:**

```
[YYYY-MM-DD] Skill invocation: <plugin>/<skill> — <outcome>
[YYYY-MM-DD] Review session: X/Y agents completed, Z skipped (<reasons>)
[YYYY-MM-DD] Accuracy alert: <plugin>/<skill> false-positive rate >10%
```

Outcomes recorded here: `false-positive`, `false-negative` (not `correct` — those go to `DepotPlugin:<name>` only).

**Example observations:**

```
[2026-03-25] Skill invocation: ghostwriter/voice — false-positive
[2026-03-25] Review session: 9/11 agents completed, 2 skipped (visual-browser-tester: no dev server, craft-reviewer: no .twig files)
[2026-03-25] Accuracy alert: ghostwriter/voice false-positive rate 15%
```

### `DepotPlugin:<name>` (type: Tool)

Per-plugin entities. One entity per plugin that has been invoked (e.g. `DepotPlugin:ghostwriter`, `DepotPlugin:dm-review`).

**Observation formats:**

```
[YYYY-MM-DD] Version: X.Y.Z
[YYYY-MM-DD] Invocation: <skill> — <outcome>
[YYYY-MM-DD] User correction: <skill> — false-positive, query was about <domain-label>
```

`<domain-label>` must be a generic category (e.g. "social media scheduling"), not a paraphrase or excerpt of the user's actual query. Avoid capturing client names, project details, or sensitive context.

**Example observations:**

```
[2026-03-25] Version: 3.8.0
[2026-03-25] Invocation: voice — correct
[2026-03-25] User correction: voice — false-positive, query was about social media scheduling
[2026-03-25] Invocation: review — correct
```

## Conventions

Observations follow these conventions:

- **Search before create** -- check if entity exists before calling `add_entity`
- **Date-prefix** all observations with `[YYYY-MM-DD]`
- **<300 characters** per observation (hard limit 500)
- **No duplicates** -- check for existing same-day observations before adding
- **Batch review dispatches** -- one observation per review session, not one per agent
- **Use exact entity names** -- `DepotMetrics` and `DepotPlugin:<name>` with exact capitalization

## Rollup Policy

Individual daily observations on `DepotMetrics` accumulate fast. Roll up monthly to keep the entity compact.

### Monthly rollup process

1. Get the `DepotMetrics` entity
2. Count observations for the month being rolled up
3. Add a summary observation:
   ```
   [YYYY-MM] Monthly rollup: X review sessions, Y skill invocations, Z false positives. Top skills: a, b, c.
   ```
4. Delete the individual daily observations for that month using `delete_observation`
5. Save

Run via `/depot-metrics rollup` or manually during session capture.

### When to roll up

- When `DepotMetrics` has more than 50 individual observations
- At the start of each month for the previous month
- The report mode flags when rollup is needed

## MCP Tools Used

All operations use the ai-memory MCP server:

| Tool | Purpose |
|------|---------|
| `search_entities` | Find DepotMetrics and DepotPlugin:* entities |
| `get_entity` | Read existing observations, check for duplicates |
| `add_entity` | Create DepotMetrics or DepotPlugin:<name> if missing |
| `add_observation` | Record invocations, corrections, alerts |
| `delete_observation` | Remove individual observations during rollup |
| `save` | Persist after batch operations |

## Relationship to Description Evals

The `description-evals/` JSON files test vocabulary overlap between SKILL.md descriptions and user queries. Plugin memory tracks real-world outcomes. The `/depot-metrics sync` command compares these two data sources to find skills where eval predictions diverge from actual usage -- skills that pass evals but fail in practice need description rewrites.
