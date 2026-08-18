# Browser MCP pre-flight (rendered-surface runs)

Loaded at Step 0b only when the manifest has at least one chunk with validated
`renderedSurface: required`. A run with no rendered-surface chunk never loads it.

### 2. Check Playwright MCP availability

ToolSearch for both naming variants and Chrome DevTools MCP:

- `mcp__plugin_compound-engineering_pw__browser_take_screenshot`
- `mcp__plugin_playwright_playwright__browser_take_screenshot`
- `mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_screenshot`

### 3. Decision gate

Rendered-surface chunks > 0 AND no browser MCP tools found: treat as the first failed required-browser attempt. Quit primary, retry fresh primary, then a different configured engine. If exhausted, BLOCKED and record `human_help_required`. Do not offer curl or a skip. Merge recommendation remains `BLOCKED PENDING CALLER VERIFICATION`. If tools are available, log availability and proceed.

### 4. Dev server check

With browser tools and rendered-surface chunks, try in order: `manifest.devServerURL`; host URLs from `docker compose ps` port mappings; `http://localhost:8080`; `http://localhost:3000`; project-specific local domains. Use `browser_navigate`. If none respond, feed cases into the Step 3h recovery ladder. Curl may diagnose but cannot satisfy the case. Merge recommendation remains `BLOCKED PENDING CALLER VERIFICATION`.
