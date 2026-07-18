Note: `~/.codex/prompts/` is deprecated by OpenAI in favor of skills, but it is still functional.

Resume work from an existing airlift bundle in the current repository.

Use the path argument when present. Otherwise default to `.airlift/`.

Read:

- `HANDOFF.md`
- `state.json`
- `RESUME_PROMPT.md` when present

If the supplied path is a directory, read files inside it. If the supplied path is a `HANDOFF.md` file, use its parent directory as the bundle.

Inspect `uncommitted.patch`. If it is non-empty and `git status --porcelain` is empty, offer to apply it with:

```bash
git apply .airlift/uncommitted.patch
```

Never apply the patch silently. If the working tree is dirty, skip patch application with a note that the current tree is not clean.

Read local `CLAUDE.md` and `AGENTS.md` conventions when those files exist. Detect the current harness via the airlift harness registry at `references/harness-profiles.json` from the installed airlift skill cache when available.

The registry is helpful but not required. This prompt works from the markdown alone: `HANDOFF.md` plus `RESUME_PROMPT.md` are sufficient even if the current harness is not in the registry. In that case, use the paste-prompt fallback by pasting `RESUME_PROMPT.md` into the new session and attaching or pasting `HANDOFF.md`.

Summarize the resume plan back to the user before changing files:

- Objective from `HANDOFF.md`
- Current status and git baseline from `state.json`
- Patch application decision
- Applicable local conventions
- Next steps to continue

Then continue from the `Next steps` section in `HANDOFF.md`.

For `resume-via-deepseek`, require env `OPENROUTER_API_KEY`. The target name remains stable for compatibility, but transport is through OpenRouter using `deepseek/deepseek-v4-pro`. Resolve the OpenRouter wrapper, pass the resume prompt as system context, and pipe the handoff as the user prompt:

```bash
WRAPPER=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER=$(ls -t "$CACHE"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER" ] && break
done
if [ -z "$WRAPPER" ] || [ ! -x "$WRAPPER" ]; then
  echo "openrouter wrapper not found in plugin cache" >&2
  exit 1
fi
OPENROUTER_SYSTEM="$(cat .airlift/RESUME_PROMPT.md)" \
  bash "$WRAPPER" "deepseek/deepseek-v4-pro" - 180 < .airlift/HANDOFF.md
```
