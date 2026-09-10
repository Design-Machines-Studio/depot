# Browser MCP pre-flight (rendered-surface runs)

Loaded at Step 0b only when the manifest has at least one chunk with validated
`renderedSurface: required`. A run with no rendered-surface chunk never loads it.

### 2. Check host browser availability

Try actual T3 preview status/open first. If it cannot perform the selected
case, try an available suitable host browser fallback. A missing routed browser
participant does not imply host browser tools are unavailable.

Check Playwright MCP availability when T3 cannot complete the case.

ToolSearch for both naming variants and Chrome DevTools MCP:

- `mcp__plugin_compound-engineering_pw__browser_take_screenshot`
- `mcp__plugin_playwright_playwright__browser_take_screenshot`
- `mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_screenshot`

### 3. Decision gate

Rendered-surface chunks > 0 AND no browser MCP tools found: treat as the first failed required-browser attempt. Quit primary, retry fresh primary, then a different configured engine. If exhausted, BLOCKED and record `human_help_required`. Do not offer curl or a skip. Merge recommendation remains `BLOCKED PENDING CALLER VERIFICATION`. If tools are available, log availability and proceed.

### 4. Exact target check

With browser tools and rendered-surface chunks, load dm-review's
`repository-browser-target-discovery.md` and follow its target precedence.
An explicit invocation override comes first; otherwise use the established
project domain and designated serving checkout, with documented rebuild and
actual served-source verification. `manifest.devServerURL` is target context,
not proof of source identity. An unrelated attached tab never overrides the
project declaration. Keep maintained instances available after review. Never infer a port from
Compose mappings, scan localhost, guess a project domain, or invent a start
command. Navigate the one selected target. If it does not respond, feed the
selected cases into the Step 3h recovery ladder. Curl may diagnose but cannot
satisfy the case. Merge recommendation remains `BLOCKED PENDING CALLER
VERIFICATION`.
