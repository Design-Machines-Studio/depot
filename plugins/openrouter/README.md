# openrouter

OpenRouter API provider plugin (leaf). Delegates policy-routed review, bulk / large-context diff analysis, second-opinion review, one-shot text generation, and bounded agentic execution to GLM-5.2 (`z-ai/glm-5.2`, 1M context) and DeepSeek V4 over a single OpenAI-compatible endpoint. ZDR opt-in (`OPENROUTER_ZDR`; privacy demoted below quality/price/speed). Powers the pipeline cascade's OpenRouter rail (including the `openrouter-exec` agentic runner) and dm-review's policy-selected external routing.

## What it routes

Routing is governed by the shared `plugins/pipeline/references/routing-policy.json`. When `OPENROUTER_API_KEY` is set, OpenRouter is:

- **Primary** for `doc-sync-reviewer` and `test-coverage-reviewer`, and the bulk analyst for large-context / large-diff first-pass triage.
- **Fallback** for `pattern-recognition-specialist` and `code-simplicity-reviewer` (DeepSeek-primary).
- The cascade rail for `config` / `docs` / `mechanical-logic` chunk execution via `openrouter-exec`.

## Security boundary (non-negotiable)

**Third-party models are bulk pattern reviewers, never security reviewers.**

GLM-5.2 and DeepSeek V4 must NEVER see sensitive material. The routing policy's `security` block is enforced by every delegation path here (`openrouter-bulk-analyst` Security Boundary, `openrouter-delegate` SKILL "Security Boundary" -- covering both the one-shot delegate and the `openrouter-exec` runner):

- **Path exclusions -- route Anthropic-side.** A diff touching any of `internal/auth/**`, `internal/federation/**`, `**/secretbox*`, `**/destructive_confirmation*`, `internal/baseplate/email/settings*`, `deploy/**`, or `*.env*` is declined whole and returned to the Anthropic-native reviewer. A single matching file taints the chunk.
- **Content redaction.** Environment values, API tokens/keys, connection strings/DSNs, production hostnames-with-paths, and credential-bearing migration/seed files are stripped before sending. If they cannot be stripped, the content is returned to Anthropic-side review.
- **Intended lanes.** Style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency. These route off-Anthropic freely when no boundary is tripped.

Security findings and any auth/federation/secrets review are Claude-native and Opus-gated (see the dm-review `security-auditor`). OpenRouter never fills that seat.

## Requirements

- `OPENROUTER_API_KEY` set in the environment. When unset, routing falls back to DeepSeek (if keyed) or Claude, and this plugin is a no-op.
- `OPENROUTER_ZDR=1` opt-in to pin zero-data-retention providers for genuinely sensitive material (privacy demoted by default: Quality > Price > Speed > Provider privacy).
