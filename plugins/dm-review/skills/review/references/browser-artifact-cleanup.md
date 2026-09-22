# Browser artifact cleanup

Before browser capture, the host selects one absolute evidence directory in the
repository's documented ignored artifact area (verify with `git check-ignore`)
or its existing external run-artifact location. Never use the repository root
or a bare screenshot filename. Pass this destination to every browser tool and
worker; record exact returned paths for screenshots, snapshots, traces, videos,
and console dumps in the existing run ownership records. Include captures made
in the maintained serving checkout, not only the implementation worktree.

If a tool ignores the destination and writes into a source checkout, reconcile
its exact returned file immediately. Preserve required evidence in the selected
retained location, verify the copied bytes, update report/packet references and
hashes as needed, then remove only the verified run-owned source copy. Do not
move or delete a pre-existing file merely because its name looks like a review
artifact. Keep ownership and entry-baseline evidence; unknown files are foreign.

Before removing a worktree or disposable root, preserve screenshots referenced
by the final report, exact-head packets, unresolved findings, or human review in
that retained evidence location. Preserve one bounded set proving the final
selected cases; delete redundant run-owned intermediate captures after consumers
finish. Never leave dangling evidence links, commit incidental screenshots into
product history, or add broad ignore rules to hide residue. Intentional product
image assets remain ordinary source changes. No new artifact service is needed.

After final reports and receipts are written, repeat status checks in every
checkout this run used, including the maintained serving folder. Reconcile new
run-owned screenshots, reports, todos, lessons and planning files: commit/push
intentional source changes; preserve required evidence outside tracked source;
remove disposable material. Then verify the PR head, retained evidence links,
and status again. Do not stop at a pre-report status check or call cleanup
complete merely because the code review is clean.

Report `Next chunk: ready` only when all run-owned changes are delivered and no
run-owned dirty residue remains. Otherwise report `Next chunk: blocked -- <exact
paths and reason>`, preserving the separate code/coverage verdict. List foreign
baseline or concurrent changes separately; they are not permission to delete
another owner's work. Keep the reviewed preview running on its feature head;
readiness never means restoring main, stopping the maintained app, or deleting
its source checkout. Cleanup also runs after standalone visual review and aborts.

