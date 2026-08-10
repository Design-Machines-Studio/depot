---
status: done
priority: p2
issue_id: "153"
---

# A malformed existing lane retained its private companion

Resolved by deriving and registering the manifest-owned companion path
immediately after parsing the manifest, before schema or nested-field checks
can fail, without trusting a path supplied by malformed manifest content.
