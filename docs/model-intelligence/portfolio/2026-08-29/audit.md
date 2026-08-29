# Depot full-matrix portfolio audit — 2026-08-29

## Outcome

No routing change is justified. DeepSeek V4 Flash 0731 is proven on every
currently applicable builder-fast and review-fast case, but it is already the
incumbent. Native Luna is equally deterministic for review-fast and has zero
subscription marginal cost, yet it lacks attributable production-canary
evidence required to move to role head. Architect has no proven candidate. Six
of nine roles had no sealed standard-runner case.

Audit source: clean detached worktree at Depot `origin/main`, commit
`f0221f6a9e083385ea1114ffd8524b8a0626ad46`. The user's source checkout was not
modified.

## Fresh sealed evidence

| Candidate | Case | Attempts | Scores | Result |
|---|---|---:|---|---|
| DeepSeek V4 Flash | pipeline legacy translation | 3 | 100,100,100 | pass |
| DeepSeek V4 Flash | mechanical owned edit | 3 | 100,100,100 | pass |
| DeepSeek V4 Flash | review zero deferral | 3 | 100,100,100 | pass |
| native Luna | pipeline legacy translation | 1 | 100 | screen only |
| native Luna | mechanical owned edit | 1 | 50 | mandatory failure |
| native Luna | review zero deferral | 3 | 100,100,100 | pass |
| native Sol | Assembly next chunk | 1 | 30 | mandatory failure |
| Fable | Assembly next chunk | 1 | 0 | parse failure |
| Opus request | Assembly next chunk | 1 | 0 | Haiku served |
| Qwen3.8 Max | Assembly next chunk | 1 | 15 | mandatory failure |

DeepSeek was 9/9 perfect with two-second medians. Luna was 3/3 on review-fast
with a six-second median. The architect portfolio was 0/4 perfect.

## Economic views

Fresh receipt-attributable OpenRouter spend was **$0.00538544346**: DeepSeek
`$0.00120944346` and Qwen `$0.004176`. The shared key's daily counter increased
by more than this amount during the window; the excess was concurrent and not
attributed to the audit.

Native calls had **$0 provider-billed marginal subscription spend**. API-
equivalent costs are planning estimates, not spend: Luna review median
`$0.00101460`, Luna pipeline `$0.00101240`, Luna mechanical `$0.00312872`, and
Sol architect `$0.09001900`. Claude API-equivalent evidence was unavailable.

## Portfolio strengths

- Every fresh paid call retained requested/served identity, provider, fallback,
  token, duration, and billed-cost evidence.
- Builder-fast has current role-complete proof for its incumbent.
- Review-fast has two proven families and a real subscription-versus-paid
  tradeoff.
- Same-model provider diversity was observed without model fallback.

## Portfolio weaknesses and gaps

- Architect has no proven candidate and its incumbent failed JSON parsing.
- Six roles had no sealed standard-runner case; 22 of 30 routed cells were
  quality-untested by construction.
- Production attribution covered only Kimi and GLM-5.2, with zero canonical
  finding contributions and 0% median first-pass validation.
- Tool use, multi-turn recovery, browser interaction, actual repository edits,
  validation, and independent-review contribution were not measured.
- OpenRouter Luna and Terra duplicate native subscription rails without a
  demonstrated paid advantage.
- Live Wires, Datastar, Templ, browser, and accessibility implementation has no
  dedicated current role.

## Opportunities

1. Use native Luna as a review-fast subscription-first path when Codex headroom
   is healthy, after attributable production-canary evidence.
2. Keep DeepSeek Flash as builder-fast head and capacity-preserving review head
   while production finding/validation attribution is added.
3. Measure exact `tencent/hy4-preview-20260827` without routing it.
4. Retire GLM-5.2 and challenge redundant matrix entries after consumer checks.
5. Refresh the matrix from the captured live catalog on a clean evidence branch.

## Validation

- `python tests/test_model_intelligence.py -v`: 4/4 passed.
- `tools/test-openrouter-role-benchmark.sh`: 19 assertions passed.
- `tools/validate-provider-neutral-routing.sh`: passed.
- `tools/validate-routing-economics.sh`: passed.
- `tools/validate-composition.sh --all`: passed.

## Next benchmark-suite improvement

Add one role-complete agentic sealed harness to `depot-role-v2`: a
parameterized repository task that supplies each currently unsealed role with
deterministic assertions while recording actual tool use, multi-turn recovery,
repository edits, validation, browser applicability, and reviewer contribution.
