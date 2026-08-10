---
status: done
priority: p3
issue_id: "118"
---

# Codex duration classification lacked a behavioral fixture

Resolved by running the production usage probe with a test-only app-server
response seam and asserting that 300 and 10080 minutes map to the required
windows while an unrecognized 1440-minute duration leaves weekly headroom
conservatively unknown.
