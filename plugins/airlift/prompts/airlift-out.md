Note: `~/.codex/prompts/` is deprecated by OpenAI in favor of skills, but it is still functional.

Create or refresh a `.airlift/` handoff bundle for the current repository.

Parse arguments as:

- `--no-commit`: default behavior. Capture current uncommitted work as `.airlift/uncommitted.patch`; do not force a commit.
- `--commit`: create a single clearly-labeled checkpoint commit first, then write the bundle.
- Remaining text: the handoff note. Pass it to the engine as `--note "<note>"` when non-empty.

If neither `--commit` nor `--no-commit` is present, use `--no-commit`.

Resolve `airlift-engine.sh` with this dual-cache pattern exactly:

```bash
ENGINE=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  ENGINE=$(ls -t "$CACHE"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)
  [ -n "$ENGINE" ] && break
done
```

If `ENGINE` is still empty, stop and report that the airlift engine was not found in either plugin cache.

The default is `--no-commit`. In this mode, do not make any commit and do not ask the user to make one. Run the deterministic engine against the current tree so the bundle captures all uncommitted work in `.airlift/uncommitted.patch`.

For `--commit`, make the checkpoint commit FIRST, then write the bundle. This ordering is required: a committed run's patch should be clean, not a patch of already-committed work. Use one commit with this exact subject:

```bash
git add -A
git commit -m "wip: airlift checkpoint"
```

If there is nothing to commit on the `--commit` path, note that no checkpoint commit was created and continue to write the bundle.

Run the engine with the parsed note:

```bash
if [ -n "$NOTE" ]; then
  bash "$ENGINE" write --note "$NOTE"
else
  bash "$ENGINE" write
fi
```

After the command succeeds, read `.airlift/HANDOFF.md` and `.airlift/state.json`.

Use Edit to layer narrative onto the existing tier-2 enrichment markers in `.airlift/HANDOFF.md`. Keep the deterministic facts from the skeleton intact. Enrich these sections:

- `Objective`: state the concrete user goal and the repository boundary.
- `Status`: describe what was captured, whether the patch is expected to be empty or non-empty, and any checkpoint commit created on the `--commit` path.
- `Next steps`: list the next concrete actions in order.
- `Gotchas / traps`: record fragile assumptions, sandbox limits, generated-file rules, or risks that the next model must not miss.

Do not remove the tier-2 marker comments unless replacing them with the enriched text in their own sections.

Print the bundle path and checkpoint sequence at the end. The bundle path is `.airlift/`. Read the checkpoint sequence from `.airlift/state.json` field `seq`.
