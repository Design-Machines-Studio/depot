# Assembly Baseplate scoped-DB implementation spike

Run date: 2026-08-28 (Asia/Makassar)

Baseplate evidence revision: `f527fdf4b69725d73ed4ba01a3b4903a6b694211`

Candidates: `deepseek/deepseek-v4-pro-0813` and `x-ai/grok-4.6` through
OpenRouter.

The candidate packet contained the first 150 lines of Baseplate `AGENTS.md`,
`internal/module/scoped_db.go`, and the visible `scoped_db_test.go`. Each
candidate produced a patch and provider receipt.

This was a useful harness spike, but the result directory did not retain one
exact sealed task, fixture revision manifest, deterministic scorer, hidden-test
contract, or validation receipt. The two patches are retained privately under
`/home/ned/benchmark-results/assembly-baseplate-role-spike-2026-08-28` and are
not committed because they contain repository-derived output.

The case is now represented in `depot-role-portfolio.json` as
`prototype-unsealed`. It must be rebuilt in a disposable exact-revision
Baseplate worktree with patch-apply, owned-path, Docker Go, existing-test,
hidden-scope, compatibility, and no-unrelated-change gates before it can
support a `builder-deep` comparison.

**No routing change justified.**
