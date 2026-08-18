# Branch A -- OpenRouter lane dispatch

Loaded only when `OPENROUTER_AVAILABLE=true` and at least one selected lane is
routed to OpenRouter. When OpenRouter is unavailable every lane takes Branch B
on Codex and this file is never loaded.

**A. If the agent is routed to OpenRouter** (in the model table and `OPENROUTER_AVAILABLE=true`):

1. **Read the openrouter-agent-runner definition** from `$OPENROUTER_RUNNER_PATH` in the coherent bundle selected above. If the selection receipt was not preserved, rerun the same `resolve-plugin-bundle` request for the complete asset set; never resolve one asset independently.
2. **Build the runner prompt** by combining:
   - The full content of the runner definition file (the runner's instructions)
   - `target_agent_path` -- the simple root variable bound for `TARGET_PLUGIN` (`DM_REVIEW_BUNDLE_ROOT`, `ACCESSIBILITY_BUNDLE_ROOT`, `LIVE_WIRES_BUNDLE_ROOT`, `GHOSTWRITER_BUNDLE_ROOT`, `COUNCIL_BUNDLE_ROOT`, or `OPENROUTER_BUNDLE_ROOT`) plus `TARGET_AGENT_ASSET`; if an optional plugin has no bound root, preserve its Phase 3 skip rather than re-resolving or using a depot-relative path
   - `target_agent_name` -- bare ID (e.g., `pattern-recognition-specialist`)
   - `target_model` / `fallback_model` -- full OpenRouter slugs from policy or the inline table
   - `target_timeout` -- the workload-scaled 1800s, 3600s, or 7200s value
   - `openrouter_bundle_ref` -- ephemeral home-relative selected root used only to bind runner execution to the loaded definition; never publish it
   - `openrouter_bundle_version`, `cache_class`, `resolution_reason` -- durable resolver evidence (never the selected root)
   - The unfiltered list of changed files (the runner filters it before disclosure)
   - The full diff content (the runner invokes `delegation-boundary.sh --mode mechanical-review` and sends only the emitted safe remainder)
   - Project context
3. **Launch without Claude coding execution:** on a Codex host, use a native Codex subagent with the combined runner prompt. On any other host, pipe the prompt to `codex exec -s read-only -c service_tier=fast --skip-git-repo-check -`. The runner performs mechanical orchestration and OpenRouter performs the review judgment; a Claude `Agent` call is not a valid Branch A launcher.
4. `security-auditor-openrouter` targets the installed `security-auditor.md` criteria but keeps its distinct logical lane ID. `security-auditor-codex-signoff` launches independently through Branch D with the full unfiltered diff and is tagged `[family-signoff/security-auditor]`. Neither output substitutes for the other. A full external decline may be completed by Codex under the external lane ID, but it still does not satisfy the independent signoff lane.
