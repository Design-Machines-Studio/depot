# Invocation Protocol

Complete reference for invoking the OpenRouter API from Claude Code via the Bash tool, using `references/openrouter-wrapper.sh`.

## The Wrapper

`openrouter-wrapper.sh` is a single-turn completion runner. Its exit-code semantics match `deepseek-wrapper.sh` (0/28/1/2) so results slot into the same consolidator path, but its arg shape is POSITIONAL (`<model> <prompt|-> [timeout] [fallback]`) whereas `deepseek-wrapper.sh` is flag-based (`-m`/`-s`/`-p`) -- a caller built for deepseek's flags needs an adapter, not just a path swap. It centralizes provider preferences, rate-limit fallback, JSON body construction, and timeout enforcement.

**Argument shape (positional):**

```
openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
```

- `<model-slug>` -- OpenRouter model ID, e.g. `z-ai/glm-5.2` or `deepseek/deepseek-v4-pro`
- `<prompt|->` -- literal prompt string, or `-` to read the prompt from stdin (use for large diffs)
- `[timeout_s]` -- per-attempt timeout in seconds (default `90`)
- `[fallback-slug]` -- a second model to try if the primary returns HTTP 429/503

**Output:** the wrapper prints the model's **text content directly** (it already extracts `.choices[0].message.content`). There is no JSON to parse -- the stdout IS the answer. (This differs from `deepseek-wrapper.sh`, which returns the raw JSON envelope.)

## Resolve the Wrapper Path

Resolve via the plugin cache so this works from any CWD (pipeline runs in worktrees outside the depot where depot-relative paths fail):

```bash
WRAPPER_PATH=""
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER_PATH=$(ls -t "$CACHE_ROOT"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER_PATH" ] && break
done
[ -n "$WRAPPER_PATH" ] && [ -x "$WRAPPER_PATH" ] || { echo "openrouter wrapper not found in plugin cache" >&2; exit 1; }
```

## How to Invoke

```bash
# GLM-5.2, explicit 120s timeout, DeepSeek V4 rate-limit fallback (wrapper default timeout is 90s)
bash "$WRAPPER_PATH" "z-ai/glm-5.2" "your prompt" 120 "deepseek/deepseek-v4-pro"

# Custom system prompt (env), privacy-pinned, prompt via stdin (large content)
echo "large diff content" | OPENROUTER_ZDR=1 \
  OPENROUTER_SYSTEM="You are a senior code reviewer." \
  bash "$WRAPPER_PATH" "z-ai/glm-5.2" - 180 "deepseek/deepseek-v4-pro"
```

## Environment Variables

- `OPENROUTER_API_KEY` (required): your OpenRouter API key. Never commit it.
- `OPENROUTER_SYSTEM` (default: terse coding assistant): system prompt.
- `OPENROUTER_BASE` (default `https://openrouter.ai/api/v1`): API base URL.
- `OPENROUTER_ZDR` (`1` to enable): restrict to providers that do **not** train on / retain data (`data_collection: deny`). Use for any review of private code.
- `OPENROUTER_REQUIRE_PARAMS` (default `1`): skip providers that do not support the requested params (keeps agentic calls from silently degrading).
- `OPENROUTER_PROVIDER_SORT` (`throughput|latency|price`): bias provider selection.

## Security Hardening

- API key is passed via the `Authorization` header, never in URLs or args visible to `ps`.
- The prompt is JSON-encoded via `jq` (`--arg`), preventing injection through shell/JSON metacharacters in user content.
- Provider preferences are sent per-request, not relied upon from dashboard defaults.

## API Endpoint

```
POST https://openrouter.ai/api/v1/chat/completions
```

**Headers:** `Authorization: Bearer ${OPENROUTER_API_KEY}`, `Content-Type: application/json`.

**Request body (built by the wrapper):**

```json
{
  "model": "z-ai/glm-5.2",
  "provider": { "require_parameters": true, "data_collection": "deny" },
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ]
}
```

## Exit Codes & Error Handling

| Exit | Meaning | Action |
|------|---------|--------|
| `0` | Success | stdout is the model's text content. |
| `28` | Timeout | Report timeout, proceed without OpenRouter input. Do not retry. |
| `1` | Exhausted / error | Bad API response or non-recoverable HTTP. The wrapper prints `### RUNNER FAILURE ...` to stderr. Skip gracefully. |
| `2` | Bad args | Missing model or prompt. |

Internally, HTTP 429/503 on the primary triggers the `[fallback-slug]` model if provided; if the fallback also fails, the wrapper returns `1`. All failures are graceful skips -- emit a clean "no findings" report so any consolidator can proceed.
