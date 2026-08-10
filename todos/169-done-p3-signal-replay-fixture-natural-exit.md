---
status: done
priority: p3
issue_id: "169"
---

# Signal replay fixture could pass after natural transport exit

Resolved by requiring the launch-window injection to finish well before the
30-second fake transport can exit naturally and to emit the wrapper's exact
content-free `interrupted` receipt. The ordinary child-start fixture now gives
loaded hosts five bounded seconds to publish before reporting a failure.
