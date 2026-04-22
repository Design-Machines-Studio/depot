# 009 — P3 — gemini-wrapper.sh additional hardening (security + correctness)

**Status:** pending
**Severity:** P3
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agent:** dm-review:review:security-auditor

## Findings

### P3-S1 — Sourced-vs-direct dual-mode leaves caller-shell state (CWE-664)

When sourced, the script unconditionally `export PATH=...` mutates the caller's environment, and `GEMINI_FALLBACK_CHAIN` + `RATE_LIMIT_PATTERNS` get defined in the caller's namespace. Subsequent operations may collide on those identifiers.

**Fix:** When sourced, only define the function. Move PATH/dependency setup inside the function or guard with `if [ "${BASH_SOURCE[0]}" = "$0" ]; then` block. Use underscore-prefixed names for constants to make namespace pollution explicit.

### P3-S2 — Rate-limit regex too broad (CWE-697)

`exhausted your capacity|quota|rate limit|429|too many requests` (case-insensitive) will match strings that aren't 429s — a normal Gemini reply containing the word "quota" reflected in stderr, prompt-content reflection containing "rate limit," etc. Consequence: silent model downgrade; the workflow runs on flash-lite instead of pro and produces weaker output.

**Fix:** Anchor `429` with word boundaries (`\b429\b`); require surrounding context for "quota"/"rate limit"; combine with exit-code check rather than stderr-only.

### P3-S3 — `--yolo` is forced unconditionally (CWE-250)

The wrapper hardcodes `--yolo` on every invocation. Removes operator's ability to require confirmation for sensitive Gemini features. If `--yolo` semantics expand in future Gemini versions, the wrapper silently grants the broader privileges.

**Fix:** Allow callers to opt out via `GEMINI_YOLO=0` env var, OR remove `--yolo` from the wrapper and let callers pass it explicitly. Document the change in references/invocation-protocol.md.

## Acceptance

- [ ] Sourced mode does not mutate caller PATH; constants use underscore prefix
- [ ] Rate-limit regex anchored with word boundaries; combined with exit-code check
- [ ] `--yolo` is opt-in via `GEMINI_YOLO` env var (default: on for backward compat) OR removed entirely
- [ ] invocation-protocol.md documents the new behavior
