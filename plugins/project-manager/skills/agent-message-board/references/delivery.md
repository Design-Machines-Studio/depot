# Targeted delivery contract

Inspected locally on 2026-10-03: Claude Code 2.1.287 (`claude --help`,
`claude agents --help`) and Codex CLI 0.160.0 (`codex --help`,
`codex agents --help`, `codex queue --help`). The current T3 MCP tool inventory
exposes preview/PR/device tools, not cross-chat delivery. Parent/child collaboration
messaging does not address independent Assembly chats. No remote API or transcript
scraping is needed for this feature.

Codex exposes `queue --thread <session UUID or name> --message <text>`. This
adapter deliberately permits **only a verified exact UUID**, never a name.
Codex's agent browser is interactive; it does not offer a documented JSON
repository-to-live-session binding in the inspected CLI. Claude can list sessions
as JSON but exposes no equivalent queue command. Resume/background/stream-input
features can start or copy sessions and do not prove delivery to the intended
existing chat. Consequently there is no automatic session discovery or Claude
notification adapter. Native queue support does not prove that the T3-managed
session is on the same local app-server daemon.

## Operator/host binding

Only an operator or trusted host may provision a binding after verifying the
exact UUID, intended repository/thread and queue-capable host instance from
trusted session metadata/UI. Message text, a Git remote, a matching cwd alone,
thread labels, or an agent's self-assertion are insufficient. Do not mint a binding
as an agent. If verification is unavailable, use the inbox fallback.

The operator creates a single-link, current-user-owned mode-0600 JSON file
outside **all Git checkouts and the board**. It is explicitly passed to `notify`
or `post --binding`; the board does not search for it. For example:

```json
{
  "schema": "agent-session-binding-v1",
  "issuer": "operator_verified",
  "host": "codex",
  "session_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
  "destination_project": "Design-Machines-Studio/assembly-governance",
  "destination_thread": "governance-acceptance",
  "verified_at": "2026-10-03T10:00:00Z",
  "expires_at": "2026-10-03T11:00:00Z",
  "evidence": "Operator checked exact UUID and repository in the local session UI",
  "executable": "/home/ned/.local/bin/codex"
}
```

These are placeholders, not a live binding. The file itself is host/operator
routing authority in this trusted single-account system; its `issuer` field is
not cryptographic attestation. Same-account hostile writers are out of scope.
The runtime validates file ownership/mode, UUID, exact destination/thread, and
an interval of at most eight hours, rejecting future verification or expired
bindings. Revoke by removing the file; reverify when a session/host changes.
The CLI path must be absolute and resolve to a regular executable outside Git
checkouts, owned by this user or root and not writable by others. The operator
must verify the executable is the intended Codex CLI. No executable or argv
comes from messages. No shell, session startup/resume, CLI flags that bypass
permissions, automatic retries, or broadcast is used.

```sh
"$WORKFLOW_KERNEL" agent-board --directory /home/ned/ai/agent-board notify \
  <message-id> --binding /operator-owned/path/session-binding.json
```

`post --binding` publishes first, then attempts notification; an unavailable or
invalid binding is reported separately without losing the posted message.
A later `notify` can try an eligible posted request with a valid binding.
Only unanswered `needs_answer` questions, handoffs and corrections are eligible.
Replies and completion updates never notify, even if actionable. A linked reply
with explicit `needs_answer` requests a further answer through the inbox fallback;
do not create an unlinked question or new ID solely to bypass deduplication.

`.delivery/<message-id>/` holds separate attempt/outcome evidence, leaving every
message immutable. Atomic directory claiming deduplicates across processes,
bindings and repeated invocations. A claim precedes invocation; an interruption
before/after queuing remains ambiguous and will not retry. Failed attempts also
remain deduplicated. Do not delete receipts to force a retry; nudge manually.
Pre-invocation missing/expired bindings, unsupported Claude host or missing CLI
create no attempt claim, so an operator can repair the binding and explicitly
try once. The command times out after 30 seconds and discards CLI output.
Exit-zero means queue accepted; nonzero means failed; timeout/OS error means
unavailable. None proves delivered, read or answered. Evidence fields retain
`unknown` for delivery/reading until a future host supplies real acknowledgments.

## When the operator still needs to nudge

Nudge the identified recipient chat when a response is needed before its next
start/resume/dependency checkpoint and no verified queue-capable binding exists,
Claude is the recipient, the daemon cannot address a T3 session, queue failed,
the attempt was interrupted/ambiguous, or the accepted queue has no response.
Successful queue acceptance may leave an idle chat idle. The compact operator
`inbox --limit 20` shows destination/thread labels, age, latest linked update,
message path and source evidence. Labels help a person locate a chat; they never
route automatically. Follow pagination when required. This is an exchange inbox,
not a task tracker and not a duplicate of GitHub issue state.
