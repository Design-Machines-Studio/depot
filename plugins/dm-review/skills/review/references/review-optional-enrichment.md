# Optional memory enrichment (Phase 7)

Loaded at Phase 7 only in full mode and only when the ai-memory tools are
callable in this session. When they are absent, omit Phase 7 and 7b silently and
never load this file.

Official and third-party Claude Code plugins that complement this skill:

| Plugin | Tool | When to Use |
|--------|------|-------------|
| **compound-engineering** | `/lint` | Supplement code-simplicity-reviewer findings |
| **pr-review-toolkit** | `/review-pr` | PR-specific deep analysis (comments, error handling, types) |
| **superpowers** | `/verify` | After applying review fixes, verify nothing broke |
| **code-review** | `/code-review` | Alternative single-pass confidence-scored review |
| **rag** (optional global MCP) | `mcp__rag__rag_search` | When callable, search the personal knowledge library for design, typography, layout, accessibility, UX, and editorial design references. Its absence is silent during incidental review enrichment. |

---

### Phase 7: Optional Memory Enrichment (Full mode only)

**Skip this phase in Quick mode.**

After issue tracking (or if skipped), inspect the callable-tool inventory or
tool-search result for the required ai-memory tools. Do not invoke a memory tool
merely to probe availability. If they are absent, omit Phase 7 and Phase 7b
silently with no lane, coverage, receipt, summary, or completion entry.

When the tools are callable, record the review in ai-memory:

1. Read the memory recorder from the same dm-review root bound before dispatch:
   ```bash
   RECORDER_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-memory-recorder.md"
   [ -f "$RECORDER_PATH" ] || { echo "ERROR: bound dm-review memory recorder missing" >&2; exit 1; }
   ```
   Read from `$RECORDER_PATH`.
2. Use the ai-memory MCP tools to:
   - Search for the project entity
   - Add a review summary observation (under 300 characters)
   - Add P1 architectural observations if any
3. Call `save` to persist

#### Phase 7b: Depot Agent Metrics

After the project-level memory capture, record depot-level metrics. This tracks which agents fire across reviews, feeding back into marketplace analytics.

1. Search for `DepotMetrics` entity -- create if missing (type: System)
2. Add ONE batched observation summarizing the agent dispatch:
   `[YYYY-MM-DD] Review session: X/Y agents completed, Z skipped (<agent>: <reason>, ...)`
   - Example: `[2026-03-25] Review session: 9/11 agents completed, 1 unavailable (craft-reviewer: no .twig files), browser: human_help_required (dev server unavailable after recovery)`
3. Search for `DepotPlugin:dm-review` entity -- create if missing (type: PluginMetrics)
4. Add the review skill invocation: `[YYYY-MM-DD] Invocation: review -- correct`
5. Call `save` to persist

See `docs/plugin-memory-schema.md` for entity conventions and rollup policy.

---

