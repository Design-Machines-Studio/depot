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

## Untrusted Pull Requests

A profile introduced or modified by an untrusted pull request may be schema-
validated and reported for operator review. It cannot produce a valid host
attestation and its Docker/Compose lanes must not execute.

An explicit `--profile` override is trusted only because a local operator chose
it in a trusted checkout and the host recorded that authorization. The string
itself carries no permission.

## Docker and Compose Lanes

Only exact, prevalidated `docker run` or `docker compose` argv arrays may run.
The kernel invokes no shell, accepts no mutable `latest` identity, inherits no
arbitrary environment values, and writes no undeclared evidence or output
path. dm-review records the declared lane, attempted lane, actual tool/image,
and result without rewriting the argv.

Profile, trust, or catalog preflight failure starts zero subprocesses.
