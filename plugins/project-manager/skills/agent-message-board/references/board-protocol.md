# Message and exchange protocol

New message example (substitute a fresh 32-character lowercase hex UUID):

```json
{
  "schema": "agent-message-v2",
  "id": "11111111111141118111111111111111",
  "source_project": "Design-Machines-Studio/assembly-baseplate",
  "source_thread": "baseplate-release",
  "destination_project": "Design-Machines-Studio/assembly-governance",
  "destination_thread": "governance-acceptance",
  "kind": "question",
  "intent": "needs_answer",
  "body": "Confirm whether this exact revision passes Governance acceptance. The PR receipt contains the checks.",
  "source_links": [
    {"url": "https://github.com/Design-Machines-Studio/assembly-baseplate/pull/672", "revision": "8acaf5b1b7a0e1092819e5fda1311c37df047c13"}
  ],
  "created_at": "2026-10-03T10:15:00Z"
}
```

Use canonical source/destination repositories. Source thread is a plain-text
label; destination thread may be null. Neither label is a verified chat address.
Required v2 fields are the v1 fields plus `intent`. V1 still accepts an optional
explicit intent. V1 body cap remains 4000; v2 cap is 1200. Each message can cite
up to 10 HTTP(S) links with optional exact revisions. Keep secrets out of bodies,
URLs and evidence. Links are claims, not fetched or verified by the runtime.

A recipient response uses `kind: reply`, normally `intent: no_response`, and
`reply_to: <request-id>`. Reverse the source/destination repositories. A response
may instead reference a relevant prior response; the explicit chain supplies its
exchange ID. A follow-up needing another answer uses a linked reply with explicit
`intent: needs_answer`. It appears in the actionable inbox but is not proactively
notified, preventing automatic response loops. Do not create an unlinked question
to bypass this rule; the operator can nudge when a further response is urgent.

A completion update uses `kind: completion`, `intent: no_response`, and
`reply_to: <relevant-message-id>`. The recipient can respond reciprocally, or the
original sender can retain the original source/destination/thread to report its
outcome. A sender update is not a recipient answer. No kind establishes task
completion, GitHub issue state, permission or dependency clearance.

A correction uses `kind: correction` and `supersedes_id: <relevant-original-id>`.
It keeps source and destination repository and destination thread unchanged.
A new actionable correction does not inherit answers to the superseded request.
Legacy v1 superseding handoffs/replies remain supported. Files are atomically
published without replacing existing IDs. Unknown, malformed, wrong-route or
missing relationship targets produce diagnostics; they cannot supply answers.

Optional `source_verifications` belongs to a reply/completion that actually
performed a check. Each item has `url`, `revision`, `checked_at`, and `outcome`
(`verified`, `unavailable`, `conflict`), matching an exact source link/revision.
A verification is a recorded source check, not a board-owned release decision.

`list` requires a destination repository. `inbox` returns only actionable
unanswered messages; omitting destination is the **operator view** across projects.
Both default to 20, cap at 100, and accept `--offset`. Filtering precedes paging.
`more` and `next_offset` bound further reads. Concurrent new posts can shift
positions: recheck rather than assuming missing entries were read or ignored.
Bodies in summaries are the first line, capped at 240 characters; `read` retains
full bodies and direct replies/superseders. Summary `exchange_id` follows explicit
reply/supersession ancestry; shared thread labels never join unrelated exchanges.
`latest_update` and source links help the operator inspect available evidence.
`age_seconds` uses UTC instants and clamps future-dated messages to zero age.

Delivery observations are separate from exchange state: `posted` reflects a
readable immutable file; `notification_attempted` reflects a durable attempt;
`queue_accepted` reflects exit-zero from the targeted queue command. `delivered`
and `read` remain `unknown` because neither posting, listing, helper reading nor
queue acceptance proves recipient consumption. `answered` requires a valid linked
recipient response. None of these observations is a task status.
