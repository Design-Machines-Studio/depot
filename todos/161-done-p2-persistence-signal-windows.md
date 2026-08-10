---
status: done
priority: p2
issue_id: "161"
---

# Persistence signals could strand temporary or final batches

Resolved by lifecycle-owning the temporary handle/path, blocking handled
signals across temp registration and replace/rollback-ownership publication,
and injecting pending signals inside both ownership-publication windows. No
temp, batch, or private envelope survives either fixture; deleting either
signal mask makes the corresponding fixture fail.
