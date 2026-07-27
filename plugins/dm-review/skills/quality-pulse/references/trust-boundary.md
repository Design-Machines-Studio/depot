# Quality-Pulse Trust Boundary

Pulse profiles are repository-controlled data. They describe policy and
commands but never grant permission to execute them.

## Host-Derived Authority

Before lane admission, dm-review must:

1. inspect the canonical checkout and profile source;
2. verify the Git source/ref, commit, and dirty state;
3. obtain a host-derived local operator authorization event;
4. validate the complete profile and compute its canonical digest;
5. construct a separate kernel trust attestation outside the canonical
   repository root.

The attestation binds:

- canonical repository root;
- normalized profile path;
- canonical validated profile digest;
- verified source and ref;
- verified commit;
- dirty state;
- operator authorization event ID;
- execution purpose `quality-pulse`.

No profile field, repository file, pull-request text, command argument, or lane
output can supply or self-assert this authority. The profile is never allowed
to nominate the attestation path.

`inspection-run` freezes the validated profile snapshot, matches every
attestation binding—including the caller's host-observed operator
authorization event ID—revalidates the profile source identity, and executes
only the frozen snapshot. A missing, repository-held, self-asserted, stale, or
mismatched attestation fails before subprocess invocation.

Publication transitions use a second host-derived authority: an HMAC key
loaded only from the fixed OS-account path
`~/.config/design-machines/quality-pulse/publication-authority.key`. The
account home comes from the OS account database, not `$HOME`; there is no
profile, environment, or CLI key-path override. The key file must be a
single-link regular file owned by the current user with no group/world
permissions. Each embedded receipt binds the pulse and content digest, prior
and target publication states and state digests, completed host action,
original operator authorization event, and authority-key ID.
Authoritative-result validation requires that host-selected key and verifies
the MAC with constant-time comparison. A repository caller cannot authorize a
transition or rollback by choosing an attacker key, editing JSON, moving a file
to `/tmp`, or recomputing public hashes.

The key is not a generic signing oracle. `inspection-finalize` may only rebind
the ready state while computing a trend. `inspection-publish` is the sole
process-boundary path for `markdown_rendered` and `published`: the kernel
derives the output paths from the validated profile, durably writes and
byte-verifies the exact Markdown before the rendered transition, then durably
writes and byte-verifies the exact rendered authoritative JSON before the
published transition. Identical, symlink-aliased, hard-linked, or
identity-changing profile destinations fail closed. The published authority is
not either mutable profile pathname: the kernel creates the exact signed JSON
and Markdown read-only from birth inside an unguessable staging directory and
atomically promotes that directory to a content-addressed path under
`.quality-pulse-publications/`. Validation derives that path from the pulse ID
and signed publication-state digest. The profile JSON and Markdown are
replaceable views, so a descriptor opened against an older view cannot mutate
the sealed publication bundle or change what `published` means.

## Untrusted Pull Requests

A profile introduced or modified by an untrusted pull request may be schema-
validated and reported for operator review. It cannot produce a valid host
attestation and its Docker lanes must not execute.

An explicit `--profile` override is trusted only because a local operator chose
it in a trusted checkout and the host recorded that authorization. The string
itself carries no permission.

## Docker and Compose Lanes

Only exact, prevalidated pinned `docker run` argv arrays may run in profile
schema v1. Compose is rejected because its external service configuration is
not bound by the profile attestation. Profiles cannot supply mounts. The
kernel synthesizes a fixed read-only mount
of the attested checkout at `/workspace` and a fresh empty read-write evidence
mount at `/quality-pulse-evidence`; direct Docker lanes also run with networking
disabled and a read-only container filesystem, and all lanes run as the host
operator's numeric user/group identity. The lane must write one
schema-1 envelope containing its exact lane ID and observations to
`/quality-pulse-evidence/observations.json`.

The kernel invokes no shell, accepts no mutable `latest` identity, inherits no
arbitrary environment values, and opens the fresh envelope with `O_NOFOLLOW`.
It snapshots the canonical bytes and binds their digest, lane ID, observation
IDs, classified-observation projection digest, declared argv identity,
synthesized execution-policy digest, and declared evidence reference into the
receipt. Exit zero with missing, linked, malformed, stale, lane-mismatched, or
post-classification-substituted evidence is `failed`, never `available`.
`inspection-run` accepts no separate caller observations file.

Profile, trust, or catalog preflight failure starts zero subprocesses.
