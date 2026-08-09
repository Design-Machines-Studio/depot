# 017 P3: sync contract lacks repeatable mutation and failure tests

- [x] Consumer drift is detected, repaired, and idempotent in an isolated fixture.
- [x] Invalid canonical markers fail without changing consumers.
- [x] Tests execute the real script.

## Evidence

`tests.test_sync_run_cost_summary_contract` copies the real synchronizer into
an isolated eleven-consumer fixture. It proves paragraph/resolver drift repair,
second-run byte stability, green `--check`, and fail-closed malformed markers
without consumer mutation.
