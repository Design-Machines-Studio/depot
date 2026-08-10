---
status: done
priority: p2
issue_id: "165"
---

# Required full review passes retained the selective receiver input

Resolved by clearing both `review_lane_allowlist` and `rerun_lanes` before
clean confirmation and final max-iteration verification, then regenerating the
Codex command alias. The contract requires all five fail-open/full-pass reset
sites on canonical and generated surfaces.
