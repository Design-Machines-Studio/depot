# deepseek

DeepSeek V4 delegation for Design Machines review workflows. Offloads mechanical, high-volume review lanes from the Anthropic Max quota to the DeepSeek V4 API (1M-token context) at Sonnet-class quality and lower cost, while keeping high-judgment work on Claude.

## What it routes

Routing is governed by the shared `plugins/pipeline/references/routing-policy.json`. DeepSeek is:

- **Primary** for `pattern-recognition-specialist` and `code-simplicity-reviewer`.
- **Fallback** for `doc-sync-reviewer` and `test-coverage-reviewer` (OpenRouter-primary).
- The **bulk analyst** for large-context / large-diff first-pass triage.

## Security boundary (non-negotiable)

**Third-party models are bulk pattern reviewers, never security reviewers.**

DeepSeek (like any off-Anthropic provider) must NEVER see sensitive material. The routing policy's `security` block is enforced as a hard boundary by every delegation path in this plugin (`deepseek-agent-runner` Step 1.4, `deepseek-bulk-analyst` Security Boundary, `deepseek-code-analyst` Step 0):

- **Path exclusions -- route Anthropic-side.** If a diff touches any of `internal/auth/**`, `internal/federation/**`, `**/secretbox*`, `**/destructive_confirmation*`, `internal/baseplate/email/settings*`, `deploy/**`, or `*.env*`, the whole chunk is declined and returned to the Anthropic-native reviewer. A single matching file taints the chunk.
- **Content redaction.** Environment values, API tokens/keys, connection strings/DSNs, production hostnames-with-paths, and credential-bearing migration/seed files are stripped before sending. If they cannot be stripped, the diff is returned to Anthropic-side review rather than sent.
- **Intended lanes.** Style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency. These route off-Anthropic freely when no boundary is tripped.

Security findings and any auth/federation/secrets review are Claude-native and Opus-gated (see the dm-review `security-auditor`). DeepSeek never fills that seat.

## Requirements

- `DEEPSEEK_API_KEY` set in the environment. When unset, routing falls back to OpenRouter (if keyed) or Claude, and this plugin is a no-op.
