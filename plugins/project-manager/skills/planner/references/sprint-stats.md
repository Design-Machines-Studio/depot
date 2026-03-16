# Sprint Stats -- Velocity Tracking

Track sprint completion rates to inform capacity planning. Stats are stored in ai-memory and referenced during sprint loading.

## When to Run

Phase 1 (Sprint Review) for data collection. Phase 8 (Sprint Loading) for capacity application.

## ai-memory Entity

**Entity name:** Sprint Stats
**Entity type:** Workflow

Create this entity on first use if it doesn't exist:
```
add_entity("Sprint Stats", "Workflow", ["Tracks sprint completion rates and rolling averages for capacity planning."])
```

## Observation Format

Each completed sprint gets one observation:

```
[Mon YYYY] Sprint N: X/Y completed (Z%), X Travis-assigned done. Rolling avg: A.B tasks/sprint (last 3).
```

Example:
```
[Mar 2026] Sprint 4: 12/15 completed (80%), 12 Travis-assigned done. Rolling avg: 12.0 tasks/sprint (last 1).
```

## Data Collection Procedure

Run this during Phase 1 (Sprint Review) of the sprint planning workflow.

1. **Query the sprint:** Find the outgoing sprint in Sprints DB (Status = "In progress").
2. **Get sprint todos:** Query Todos DB filtered by this sprint's relation.
3. **Filter to Travis:** Only count todos where Person includes Travis.
4. **Count:**
   - Total assigned to Travis
   - Completed (Status = "Done")
   - Rolled over (Status = "In progress" or "Inbox" -- still open)
   - Blocked (Status = "Blocked")
   - New additions mid-sprint (if trackable via created date within sprint period)
5. **Calculate completion rate:** completed / total * 100
6. **Get previous stats:** Use `get_entity("Sprint Stats")` to retrieve past observations.
7. **Calculate rolling average:** Average of completed tasks over the last 3 sprints (or fewer if less data exists).
8. **Store:** Use `add_observation("Sprint Stats", "[observation string]")`.

## Capacity Planning Application

Used during Phase 8 (Sprint Loading):

1. Retrieve the "Sprint Stats" entity from ai-memory.
2. Parse the rolling average from the most recent observation.
3. Factor in known disruptions for the upcoming sprint:
   - Meeting days (from Phase 5 calendar scan)
   - Travel or holidays
   - Known large tasks that will consume disproportionate time
4. Present capacity guidance:

```
### Sprint Velocity
| Sprint | Completed | Total | Rate | Notes |
|--------|-----------|-------|------|-------|
| Sprint 4 | 12 | 15 | 80% | First tracked sprint |
| Sprint 5 | 10 | 14 | 71% | Short week (travel) |
| Sprint 6 | 14 | 16 | 88% | |

**Rolling average (last 3):** 12.0 tasks/sprint
**This sprint factors:** Y meeting days, no travel
**Suggested load:** 12-14 tasks
```

## Starting Point

Begin tracking from **Q1 Sprint 4** onwards. On first run:
1. Query Q1 Sprint 4 from Sprints DB
2. Calculate stats retroactively
3. Store as the first observation
4. Rolling average starts with just this one data point and builds over time

Earlier sprints have no data -- that's fine. The rolling average becomes meaningful after 3 sprints of tracking.

## Edge Cases

- **Sprint not found:** If no sprint has Status = "In progress", ask Travis which sprint to review.
- **No Travis todos:** If a sprint has zero Travis-assigned todos, note it as anomalous and skip stats.
- **Partially tracked data:** The rolling average should only include sprints that have been tracked. Don't estimate missing data.
