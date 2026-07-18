# openrouter

OpenRouter API provider plugin (leaf). Delegates policy-routed review, bulk / large-context diff analysis, second-opinion review, one-shot text generation, and bounded agentic execution to quality- and cost-ranked OpenRouter model slugs over a single OpenAI-compatible endpoint. The matrix includes GLM-5.2 (`z-ai/glm-5.2`), DeepSeek V4 model slugs, Kimi K3, and paid frontier fallbacks. ZDR is opt-in (`OPENROUTER_ZDR`; privacy demoted below quality/price/speed). Powers the pipeline cascade's OpenRouter rail, dm-review's generic `openrouter-agent-runner`, the bulk analyst, and the `openrouter-exec` agentic runner.

## What it routes

Task-to-model routing is governed by `plugins/pipeline/references/routing-policy.json`; the installed OpenRouter delegation policy owns the security boundary. When `OPENROUTER_API_KEY` is set, OpenRouter is:

- **Primary external provider** for `pattern-recognition-specialist`, `code-simplicity-reviewer`, `doc-sync-reviewer`, and `test-coverage-reviewer`; each lane uses the model and fallback model selected by policy.
- **Primary external bulk lane** for large-context / large-diff first-pass triage.
- The cascade rail for `config` / `docs` / `mechanical-logic` chunk execution via `openrouter-exec`.

## Security boundary (non-negotiable)

**Third-party models are bulk pattern reviewers, never security reviewers.**

Third-party models selected through OpenRouter must NEVER see sensitive material. The canonical policy is `skills/openrouter-delegate/references/delegation-security-policy.json`; Pipeline carries a validated mirror for planning. Every delegation path must enforce it before invoking the wrapper:

- **Path exclusions -- route Codex-side.** A diff touching auth, federation, secret, deploy, or env paths is declined whole and returned to Codex-native review.
- **Content redaction.** High-confidence credential material declines the whole chunk. An empty or still-sensitive result returns to Codex-native review.
- **Intended lanes.** Style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency.

Security findings and auth/federation/secrets review are Codex-native. OpenRouter never fills that seat; Claude is non-coding-only.

## Requirements

- `OPENROUTER_API_KEY` set in the environment. When unset, external coding-review lanes fall back to Codex.
- `OPENROUTER_ZDR=1` opt-in to pin zero-data-retention providers for genuinely sensitive material (privacy demoted by default: Quality > Price > Speed > Provider privacy).
