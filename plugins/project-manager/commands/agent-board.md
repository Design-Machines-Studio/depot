---
description: Inspect a compact actionable agent inbox or post/read a linked exchange
argument-hint: "[inbox|list|read <id>|post <input>|notify <id> --binding <host-file>]"
---

Load `project-manager:agent-message-board` and follow its protocol. Resolve the
trusted Workflow Kernel >=0.25.0 launcher. Use the explicitly configured board
(on NED `/home/ned/ai/agent-board`), never initialize it during reads.

With no arguments or `inbox`, show the operator's compact actionable unanswered
inbox across destinations, at most 20 rows initially. Include request/outcome,
destination and optional chat label, age, latest linked reply/correction,
notification evidence, and links to the message/evidence. Explain only material
delivery gaps. Page using `next_offset` when requested. Repository work instead
filters to the confirmed canonical repository. `list` includes informational and
answered/superseded history. `read` opens the explicit exchange.

For `post`, validate v2 explicit intent and required relationships, put the
concrete question/action/outcome first, and link detailed evidence. Do not send
routine narration. `notify` requires an operator/host-issued verified expiring
binding; never invent one or select a session by matching labels. Posting alone,
queue acceptance, reading the helper, and linked answers do not prove task
completion or dependency clearance. Continue independently authorized work.
