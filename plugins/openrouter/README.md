# openrouter

OpenRouter API provider plugin (leaf). Delegates policy-routed review, bulk / large-context diff analysis, second-opinion review, one-shot text generation, and bounded agentic execution to quality- and cost-ranked third-party OpenRouter model slugs over one endpoint. The matrix includes GLM-5.2 (`z-ai/glm-5.2`), DeepSeek V4, and Kimi K3. OpenAI and Anthropic are native-only: they run through Codex and Claude CLIs respectively, never through OpenRouter.

## What it routes

Task-to-model routing is governed by `plugins/pipeline/references/routing-policy.json`; the installed OpenRouter delegation policy owns the security boundary. When `OPENROUTER_API_KEY` is set, OpenRouter is:

- **Primary external provider** for `pattern-recognition-specialist`, `code-simplicity-reviewer`, `doc-sync-reviewer`, and `test-coverage-reviewer`; each lane uses the model and fallback model selected by policy.
- **Primary external bulk lane** for large-context / large-diff first-pass triage.
- The cascade rail for `config` / `docs` / `mechanical-logic` chunk execution via `openrouter-exec`.

## Security boundary (non-negotiable)

**Provider selection and disclosure classification are separate controls.**

The canonical policy is `skills/openrouter-delegate/references/delegation-security-policy.json`; Pipeline carries a validated mirror for planning. Every delegation path enforces it before invoking the wrapper:

- **Threat/content classification.** High-confidence credentials, private keys, authenticated DSNs, access/session tokens, and explicitly classified private values decline disclosure. Security-looking paths, vendors, nationalities, jurisdictions, and placeholder names do not.
- **Bounded execution.** Model output is accepted only as a validated unified diff restricted to the caller's exact owned-path allowlist. The runner performs fixed structural Git validation and allowlist-only staging; executable project verification is deferred to native Codex review.
- **Intended lanes.** Style, duplication, pattern-recognition, large-diff first-pass triage, and doc consistency.

High-consequence security completion still requires independent Codex review. GLM, DeepSeek, Kimi, and other third-party models are not banned by nationality.

Every live caller selects one coherent installed plugin root with workflow-kernel `resolve-plugin-bundle`, then derives its wrapper, policy, boundary, protocols, and templates from that root. Semantic version wins over mtime; the active host breaks only equal-version ties. Durable receipts keep the version, cache class, and reason, never the absolute home path.

## Requirements

- `OPENROUTER_API_KEY` set in the environment. When unset, external coding-review lanes fall back to Codex.
- `OPENROUTER_ZDR=1` opt-in to pin zero-data-retention providers for genuinely sensitive material (privacy demoted by default: Quality > Price > Speed > Provider privacy).
