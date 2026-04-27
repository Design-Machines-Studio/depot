# Invocation Protocol

Complete reference for invoking DeepSeek V4 API from Claude Code via the Bash tool.

## Fallback Chain

The DeepSeek API does not auto-retry on rate limits. The wrapper script `references/deepseek-wrapper.sh` walks the fallback chain: `v4-pro -> v4-flash -> skip`.

**Why it exists.** Centralizes rate-limit detection, model fallback, JSON escaping, and timeout enforcement. Each caller invokes one function instead of reimplementing curl + error handling.

**How to invoke.**

```bash
# Direct invocation (starts at v4-pro, falls back to v4-flash on 429)
bash plugins/deepseek/skills/deepseek-delegate/references/deepseek-wrapper.sh \
  -p "your prompt"

# Start at a specific model
bash plugins/deepseek/skills/deepseek-delegate/references/deepseek-wrapper.sh \
  -m v4-flash -p "your prompt"

# With system prompt
bash plugins/deepseek/skills/deepseek-delegate/references/deepseek-wrapper.sh \
  -s "You are a code reviewer" -p "Review this diff..."

# Pipe large content via stdin
echo "large prompt content" | bash plugins/deepseek/skills/deepseek-delegate/references/deepseek-wrapper.sh -m v4-pro

# Source it and call the function
source plugins/deepseek/skills/deepseek-delegate/references/deepseek-wrapper.sh
deepseek_with_fallback -p "your prompt"
```

**Environment variables.**

- `DEEPSEEK_API_KEY` (required): your DeepSeek API key
- `DEEPSEEK_TIMEOUT_S` (default `60`): per-attempt timeout in seconds
- `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`): API base URL
- `DEEPSEEK_TEMPERATURE` (default `0`): temperature for deterministic output

**Security hardening.**

- The wrapper resets `PATH` to a fixed value before invoking dependencies.
- API key is passed via Authorization header, never in URLs or command args visible to `ps`.
- Prompts are JSON-escaped via `python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'` to prevent injection via shell metacharacters in user content.
- Temp files are created with 0600 permissions and cleaned up on every return path.

## API Endpoint

```
POST https://api.deepseek.com/v1/chat/completions
```

**Headers:**
```
Content-Type: application/json
Authorization: Bearer ${DEEPSEEK_API_KEY}
```

**Request body:**
```json
{
  "model": "deepseek-v4-pro",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0,
  "stream": false
}
```

## Response Format

### Success Response (HTTP 200)

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "deepseek-v4-pro",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The actual response text"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801
  }
}
```

**Extraction:** Parse `.choices[0].message.content` for the actual content. Use `.usage` for token accounting.

### Error Response

```json
{
  "error": {
    "message": "Rate limit exceeded",
    "type": "rate_limit_error",
    "code": "rate_limit_exceeded"
  }
}
```

## Error Handling Protocol

After every DeepSeek invocation, check these failure modes in order:

### 1. Timeout (curl exit code 28)

**Action:** Report timeout, proceed without DeepSeek input. Do not retry.

### 2. Rate Limit (HTTP 429)

**Action:** Use `deepseek-wrapper.sh` to walk the fallback chain (`v4-pro -> v4-flash`). If both exhausted, report and skip.

### 3. Empty Response

Check if `.choices[0].message.content` is missing or empty.

**Action:** Report "DeepSeek returned empty response." Proceed without input.

### 4. Malformed JSON

If the output isn't parseable as JSON.

**Action:** Report "DeepSeek returned unparseable output." Log the first 200 characters for debugging.

## Parsing Response Content

```bash
RESULT=$(bash deepseek-wrapper.sh -p "prompt")
CONTENT=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])")
```

For token usage:
```bash
TOKENS=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"in={d['usage']['prompt_tokens']} out={d['usage']['completion_tokens']}\")")
```
