---
status: done
priority: p2
issue_id: "110"
---

# Hostile-override canary was closed before measurement

Resolved by keeping the probe daemon and its canary alive across the hostile
client run and asserting the probe daemon's own hit counter.
