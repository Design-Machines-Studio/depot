# Browser MCP pre-flight (rendered-surface runs)

Loaded at Step 0b only when the manifest has at least one chunk with validated
`renderedSurface: required`. A run with no rendered-surface chunk never loads it.

### 2. Check host browser availability

Use dm-review's formal Playwright transport contract in
`repository-browser-target-discovery.md`. Discover the host's Playwright MCP
variants or the established repository-owned Playwright harness. T3 is for
operator handoff and verified target context; its status/open failures never
gate automated checks. A missing routed participant does not imply missing
host browser tools.

### 3. Decision gate

Rendered-surface chunks > 0 AND no supported Playwright transport found: treat as the first failed required-browser attempt. Quit primary, retry fresh primary, then a different configured engine. If exhausted, BLOCKED and record `human_help_required`. Do not offer curl or a skip. Merge recommendation remains `BLOCKED PENDING CALLER VERIFICATION`. If tools are available, log availability and proceed.

### 4. Exact target check

With browser tools and rendered-surface chunks, load dm-review's
`repository-browser-target-discovery.md` and follow its target precedence.
An explicit invocation override comes first; otherwise use the established
project domain and designated serving checkout, with documented rebuild and
actual served-source verification. Bind the originating maintained folder/domain
pair explicitly when the repository has multiple instances; do not pick another
instance merely because it shares the same remote. Carry this pair into the final
repair and operator handoff, and leave the reviewed feature head serving there. `manifest.devServerURL` is target context,
not proof of source identity. An unrelated attached tab never overrides the
project declaration. Keep maintained instances available after review. Never infer a port from
Compose mappings, scan localhost, guess a project domain, or invent a start
command. Navigate the one selected target. If it does not respond, feed the
selected cases into the Step 3h recovery ladder. Curl may diagnose but cannot
satisfy the case. Merge recommendation remains `BLOCKED PENDING CALLER
VERIFICATION`.
