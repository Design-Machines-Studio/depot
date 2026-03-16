# Mail Scan -- Email Action Items

Search Mail.app for recent messages that may contain action items, follow-ups, or requests that should become sprint todos.

## When to Run

Phase 6 of the sprint planning workflow. Run after Calendar & Meeting Prep.

## Tools Used

- AppleScript via shell (`osascript`) for Mail.app queries

## Requirements

**Requires shell access.** This phase works in Claude Code only. If running in Claude Desktop (no shell), skip gracefully:

> "Mail scan requires shell access (Mail.app via AppleScript). Skipping this phase. You can run `/sprint-plan` in Claude Code to include mail scanning, or manually flag important emails."

## Procedure

### Step 1: Query Mail.app

Use AppleScript to get recent messages. Focus on unread and flagged messages from the last 14 days:

```applescript
tell application "Mail"
    set cutoffDate to (current date) - 14 * days
    set results to {}

    -- Search across all accounts
    repeat with acct in accounts
        repeat with mbox in mailboxes of acct
            try
                set recentMessages to (messages of mbox whose date received >= cutoffDate and (read status is false or flagged status is true))
                repeat with msg in recentMessages
                    set msgSender to sender of msg
                    set msgSubject to subject of msg
                    set msgDate to date received of msg
                    set msgRead to read status of msg
                    set msgFlagged to flagged status of msg
                    -- Get a preview snippet (first 200 chars of content)
                    set msgContent to ""
                    try
                        set msgContent to (text 1 thru 200 of (content of msg))
                    on error
                        try
                            set msgContent to content of msg
                        end try
                    end try
                    set end of results to msgSubject & " ||| " & msgSender & " ||| " & (msgDate as string) & " ||| " & msgRead & " ||| " & msgFlagged & " ||| " & msgContent
                end repeat
            end try
        end repeat
    end repeat
    return results
end tell
```

**Performance note:** Searching all mailboxes can be slow. If performance is an issue, limit to Inbox only:

```applescript
tell application "Mail"
    set cutoffDate to (current date) - 14 * days
    set results to {}
    repeat with acct in accounts
        try
            set inboxMessages to (messages of inbox of acct whose date received >= cutoffDate and (read status is false or flagged status is true))
            repeat with msg in inboxMessages
                -- ... same extraction as above
            end repeat
        end try
    end repeat
    return results
end tell
```

### Step 2: Filter for Actionable Items

From the raw message list, identify emails that likely need action:

**Include:**
- Unread messages from known contacts (people in ai-memory)
- Flagged messages (Travis manually flagged for follow-up)
- Messages with action keywords in subject: "action needed", "follow up", "please review", "deadline", "by [date]", "reminder", "request", "proposal", "invoice"
- Replies to sent messages that haven't been responded to

**Exclude:**
- Newsletters and marketing emails
- Automated notifications (GitHub, Notion, calendar)
- Spam or promotional content
- Messages already handled (read + not flagged)

### Step 3: Categorize

Group actionable emails into categories:

- **Reply needed** -- someone is waiting for Travis's response
- **Follow-up** -- Travis sent something and needs to check on it
- **Request/task** -- someone is asking Travis to do something
- **Financial** -- invoices, payments, contracts needing action
- **Opportunity** -- potential leads, speaking invitations, collaboration requests

### Step 4: Present Findings

```
### Mail Scan -- Action Items
**Period:** Last 14 days | **Scanned:** X messages | **Actionable:** Y items

**Flagged (Travis-marked):**
1. [Subject] from [Sender] -- [date] -- [brief snippet]
2. ...

**Reply needed:**
1. [Subject] from [Sender] -- [date] -- [context]
2. ...

**Follow-ups:**
1. ...

**Requests/tasks:**
1. ...

**Create todos for any of these? (Y/N per item)**
```

### Step 5: Create Todos

Only after Travis confirms which items need todos.

For each approved item:
- Name: actionable description derived from the email (not just the subject line)
- Status: "Inbox"
- Priority: Medium (High for financial or time-sensitive)
- Do NOT assign to sprint yet -- that happens in Phase 8

## Privacy Notes

- Email content is processed locally via AppleScript -- nothing is sent externally
- Only show subject, sender, date, and brief snippets in the summary
- Do not reproduce full email bodies in Notion todos or ai-memory
- If an email contains sensitive financial or personal information, note its existence but don't quote content

## Edge Cases

- **Mail.app not running:** AppleScript will launch it automatically, but may be slow on first query.
- **Large mailbox:** If the query is too slow, fall back to Inbox-only search.
- **No actionable items:** Report "No actionable emails found in the last 14 days" and move to next phase.
