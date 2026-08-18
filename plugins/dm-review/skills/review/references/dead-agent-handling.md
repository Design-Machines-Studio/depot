# Dead or missing agent handling

Loaded by `review-consolidator` only when a dispatched lane died, returned
empty or truncated output, or never reported. A run in which every dispatched
lane returned usable output never loads this file.

## Dead / Missing Agent Handling

An agent can die mid-flight -- monthly spend limit, context overflow, or crash -- and return nothing or a truncated report. When that happens:

- **Do NOT relaunch it.** A relaunch doubles spend against the same failure mode and can stall the whole run. (The external-LLM Phase 4.5 fallback in the dm-review skill is the one sanctioned retry; it has already run before you see the output.)
- **Write its lane from whatever returned.** Salvage any complete ledger blocks; a partial finding set still has value.
- **Record the gap.** Add a Coverage Gaps entry naming the dead/absent agent and what it was responsible for (e.g. `security-auditor -- DIED at cap, auth-path review incomplete`). A silently missing lane is the failure that costs the most: it reads as "clean" when it was never checked.
- **Continue.** Consolidate the surviving lanes and ship the report with the gap flagged, rather than blocking on the dead one.
