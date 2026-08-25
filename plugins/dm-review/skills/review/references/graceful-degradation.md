# Graceful degradation

A selected lane is never silently dropped. Keep its criteria and request the
mapped role through model-router.

| Failure | Action | Reported state |
|---|---|---|
| Role fallback succeeds | Keep output and role-level fallback reason | Completed (fallback) |
| Partial disclosure coverage | Keep completed sections; dispatch held sections only | Completed (partial coverage) |
| Independent-family role exhausted | Do not use an implementing family | REVIEW INCOMPLETE |
| Required build/browser lane unavailable | Preserve exact failed requirement | REVIEW INCOMPLETE or blocked |
| Optional enrichment unavailable | Omit silently unless attempted and failed | Core review unaffected |

Public reports use stable lane/role names and anonymous participants. Exact
participant identity remains only in private router receipts. Pipeline's final
full review cannot use gap-and-continue. Every retained P1/P2/P3 still requires
repair and affected-lane recheck.
