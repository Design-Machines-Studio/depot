# Live observation v1

`live-observation-v1` records bounded callback metadata. It is separate from
`observation-index-v1`, WorkflowEvent/RunState, workflow receipts, Foreman
indexes, routing, and costs. None of those contracts change.

## Identity and publication

The operator assigns `workspace` and `producer` namespaces once. They are
opaque identifiers, not directory-derived project names. Each native session
has a stable SHA-256 directory key over the canonical JSON array
`[workspace, producer, native_session_id]`. A child gets its own session record
with an explicit parent relationship. A consumer attaches that record to its
parent; arrival before the parent must not hide either record. No parent record
is fabricated. Multiple nesting levels use the same explicit relationships.
An explicit work binding may associate sessions with workflow work; its absence
must not suppress a session. There is no implicit Pipeline, review or Foreman
binding. A fork is distinct; link it only with an explicit source relationship.

`facts` use `{value, reason, provenance}`. Unavailable facts have a null value
and provenance, with a closed reason. Available facts identify `native_callback`
or `explicit_binding` provenance. Model facts mean harness-reported slugs,
not independently verified served identities. Provider, cost, token use,
progress, project, lane and workflow stage are absent from this contract.

A callback projection has an observer-generated `publication_id`; this is not
a native event ID or a deduplication claim. Multiple callback deliveries without
native event IDs remain multiple observations, even if their payloads match.
Turn, tool-call, attempt, agent and session IDs remain separate facts. Repeated
turns and resumes are not collapsed by time, model, objective or directory.

A **publication** is a validated snapshot, identified by namespace, session key,
revision and digest. `publish_live_observation(parent, identity, publication)`
replays an existing publication without rewriting files, advancing revision or
refreshing contact, including after its activity entries leave recent history.
A conflicting current revision fails. Future or absent publications cannot be
replayed. Older revisions are acknowledged without claiming their historical
contents were reverified against a retained ledger. There is no unbounded ledger.

The same function accepts pre-publication callback projections. Retrying the
same observer ID is idempotent while retained in recent history; conflicting
content fails. To retry later, retain the returned publication, not raw callback
input. Native duplicate delivery cannot be identified authoritatively when the
harness supplies no event ID. Do not derive one from a payload hash.

## Meaning and time

`recent_activity` is publication order. `observed_at` records callback receipt
at the adapter; `published_at` records preparation of the committed snapshot.
`source_timestamp` remains unavailable when absent from the native contract.
The timestamps do not establish native causal order. Out-of-order callbacks
remain in history. State fields carry their observation timestamps; an older
observation cannot overwrite a newer known state field. Unknown fields do not
erase known waiting or terminal facts. State and stable relationships survive
activity truncation. An observation is not a claim that every intervening event
was observed.

Keep these meanings separate:

- Last observed activity: a bounded code, never a prompt or tool name.
- Execution, response and session state: independent recorded facts.
- Attention: approval required, none reported, or unknown.
- Contact: confirmed only for 30 seconds after fresh observed metadata.
- Producer/read health: diagnostics and read failures, independent of work.
- Outcome: unknown unless an explicit outcome fact is supplied.

A response closing does not establish objective success. Session closure does
not establish verification. Tool output is discarded, so it cannot become a
whole-run failure. A tool return does not reopen a response or resolve an
unrelated approval; delayed returns after interruption preserve its boundary. Silence, observer failure and a failed read cannot produce a
terminal outcome. `observation_view` keeps recorded state while contact becomes
unconfirmed, including after a failed read. Fresh valid callbacks restore
contact. Reading a file or finding a process never creates a heartbeat.

## Bounds, privacy and filesystem boundary

Each configured parent contains at most 200 session directories, one persistent
writer lock and one bounded diagnostic. Each session exposes only
`snapshot.json`, at most 64 KiB, with at most 200 recent activities. The byte
limit often retains fewer than 200 entries. `dropped_activity` and
`activity_truncated` disclose this. Overflow refuses new sessions and exposes
`session_limit`; it never removes active sessions or deletes user evidence.
Readers discover direct children and need no transcript or source paths.

Identifiers are at most 128 ASCII characters; enums are closed. The callback
input limit is 256 KiB, checked before parsing. Depth is limited to 12, duplicate
keys and non-finite numbers are rejected. Only documented metadata enters the
adapter projection. Prompts, assistant messages, tool arguments/results,
transcript paths, cwd, environment, credentials, raw payloads and unrecognized
extensions are discarded before persistence. Referenced files are never opened.
Errors contain only closed codes. Hook stdout is exactly `{}` and stderr is
empty; observer errors never return decisions or model context.

This implementation supports POSIX local filesystems. Provision a current-user
owned mode-0700 parent, then pin its device/inode in configuration. Every path
component is opened with no-follow directory descriptors. Descendant reads
reject symlinks, hard links, FIFOs, devices, public permissions, changing files
and replacement parents. Writers serialize on the parent lock for at most
450 ms. Temporary mode-0600 files are flushed before an atomic rename, which is
the commit point. Failures before that point preserve the prior snapshot.
There is no promise of power-loss durability after directory rename.

The private parent must remain controlled by the configured OS account. A
malicious process with that same authority can edit metadata or move the entire
directory after a successful identity check; no filesystem API can revoke that
account's authority. Pinned descriptors prevent following a replacement into
an attacker-selected destination. Root replacement between invocations fails.
Do not share parents across producer/workspace configurations or use network
filesystems. Stale temporary files from process termination are preserved and
cause a visible failure; only an operator may remove confirmed owned residue.

The callback handler budgets 250 ms for input and 850 ms for work; native hook
configuration also sets a one-second timeout. One second from supported callback
receipt to publication is the target, not an all-launch-path guarantee. Runtime
startup, native queueing and OS scheduling need measured acceptance evidence.
