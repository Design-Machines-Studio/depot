---
name: depot-metrics
description: Track and report plugin usage metrics via ai-memory
argument-hint: "[record <skill> <outcome> | report | sync]"
allowed-tools:
  - mcp__ai-memory__search_entities
  - mcp__ai-memory__get_entity
  - mcp__ai-memory__add_entity
  - mcp__ai-memory__add_observation
  - mcp__ai-memory__delete_observation
  - mcp__ai-memory__save
---

# Depot Metrics

Track skill invocations and outcomes across the depot marketplace. Records to ai-memory so the depot learns which descriptions work and which need improvement.

See `docs/plugin-memory-schema.md` for entity types and observation formats.

## Modes

Parse the first argument to determine mode. If no arguments, show usage help.

---

### Record Mode

**Trigger:** `/depot-metrics record <plugin/skill> <outcome>`

Outcome must be one of: `correct`, `false-positive`, `false-negative`.

#### Process

##### 1. Parse Arguments

Extract plugin name, skill name, and outcome from arguments.

Examples:
- `/depot-metrics record ghostwriter/voice correct`
- `/depot-metrics record live-wires/livewires false-positive`

If arguments are incomplete, ask for them.

##### 2. Find or Create Plugin Entity

```
search_entities(query: "DepotPlugin:<plugin>")
```

If not found, create it:

```
add_entity(name: "DepotPlugin:<plugin>", entityType: "Tool", observations: ["[YYYY-MM-DD] Created for metrics tracking"])
```

##### 3. Add Invocation Observation

```
add_observation(entityName: "DepotPlugin:<plugin>", contents: ["[YYYY-MM-DD] Invocation: <skill> — <outcome>"])
```

##### 4. Record Corrections to DepotMetrics

If outcome is `false-positive` or `false-negative`, also record to the global entity:

```
search_entities(query: "DepotMetrics")
```

Create if missing:

```
add_entity(name: "DepotMetrics", entityType: "System", observations: ["[YYYY-MM-DD] Created for depot marketplace metrics"])
```

Add the observation:

```
add_observation(entityName: "DepotMetrics", contents: ["[YYYY-MM-DD] Skill invocation: <plugin>/<skill> — <outcome>"])
```

##### 5. Confirm

```
Recorded to DepotPlugin:<plugin>: "<skill> — <outcome>"
```

---

### Report Mode

**Trigger:** `/depot-metrics report`

#### Process

##### 1. Search for All Plugin Entities

```
search_entities(query: "DepotPlugin:")
```

Also fetch `DepotMetrics` for global observations.

##### 2. Count Observations by Outcome

For each `DepotPlugin:<name>` entity, use `get_entity` and count observations matching:
- `Invocation:.*correct` -> correct count
- `Invocation:.*false-positive` -> FP count
- `Invocation:.*false-negative` -> FN count
- `User correction:` -> correction count

##### 3. Calculate Accuracy

For each skill with invocations: `accuracy = correct / (correct + FP + FN) * 100`

##### 4. Flag Problem Skills

Any skill with >10% false positive rate gets flagged for description review.

##### 5. Output Report

```markdown
## Depot Metrics Report

| Plugin/Skill | Invocations | Correct | FP | FN | Accuracy |
|---|---|---|---|---|---|
| ghostwriter/voice | 12 | 10 | 2 | 0 | 83% |
| dm-review/review | 8 | 8 | 0 | 0 | 100% |

### Flagged for Description Review
- ghostwriter/voice — 17% false positive rate (2/12)

### DepotMetrics Status
- X total observations (rollup recommended if >50)
```

---

### Sync Mode

**Trigger:** `/depot-metrics sync`

Compares eval predictions with real-world usage. Stays within the MCP tool boundary -- reads eval files directly instead of running external scripts.

#### Process

##### 1. Read Eval Files

Read each JSON file in `description-evals/` using the Read tool. For each file:
- Count `should_trigger: true` cases (expected positive triggers)
- Count `should_trigger: false` cases (expected negatives)
- Note the plugin/skill name from the filename

##### 2. Get Real-World Data

Search ai-memory for `DepotPlugin:*` entities. For each, extract invocation observation counts by outcome.

##### 3. Compare

For each skill that has both eval data and real-world data:
- **High eval positives + low real-world correct** = description contains the right words but doesn't trigger in practice (distribution mismatch)
- **Low eval negatives + high real-world false-positives** = eval false cases are too easy, not catching real confusion patterns
- **No real-world data** = skill never invoked (either unused or perfectly routed elsewhere)

##### 4. Output Divergence Report

```markdown
## Eval vs Real-World Divergence

| Skill | Eval Accuracy | Real Accuracy | Divergence | Action |
|---|---|---|---|---|
| ghostwriter/voice | 70% | 83% | +13% | Real-world outperforms eval — add harder eval cases |
| council/governance | 95% | 60% | -35% | Description needs work — failing on real queries |
```

Skills with no real-world data are listed separately as "No usage data yet."

---

### Rollup Mode

**Trigger:** `/depot-metrics rollup`

Compacts old observations on `DepotMetrics` into monthly summaries.

#### Process

##### 1. Get DepotMetrics Entity

```
get_entity(name: "DepotMetrics")
```

##### 2. Group Observations by Month

Parse `[YYYY-MM-DD]` prefixes and group by `YYYY-MM`.

##### 3. Create Monthly Summaries

For each month older than the current month, count:
- Review sessions
- Skill invocations by outcome
- Top 3 most-invoked skills

Add summary observation:

```
add_observation(entityName: "DepotMetrics", contents: ["[YYYY-MM] Monthly rollup: X review sessions, Y invocations, Z false positives. Top: a, b, c."])
```

##### 4. Delete Individual Observations

For each rolled-up daily observation, delete it:

```
delete_observation(entityName: "DepotMetrics", content: "<original observation text>")
```

##### 5. Confirm

```
Rolled up N observations into M monthly summaries on DepotMetrics.
```
