---
name: airlift-in
description: Resume work from an existing .airlift handoff bundle.
argument-hint: "[path]"
allowed-tools: Bash, Read, Edit
---

Resume work from an existing airlift bundle in the current repository.

## Locate and read the bundle

Use the path argument from `$ARGUMENTS` when present. Otherwise default to `.airlift/`.

Read:

- `HANDOFF.md`
- `state.json`
- `RESUME_PROMPT.md` when present

If the supplied path is a directory, read files inside it. If the supplied path is a `HANDOFF.md` file, use its parent directory as the bundle.

## Patch handling

Inspect `uncommitted.patch`. If it is non-empty and `git status --porcelain` is empty, offer to apply it with:

```bash
git apply .airlift/uncommitted.patch
```

Never apply the patch silently. If the working tree is dirty, skip patch application with a note that the current tree is not clean.

## Local conventions and harness

Read local `CLAUDE.md` and `AGENTS.md` conventions when those files exist. Detect the current harness via the airlift harness registry at `references/harness-profiles.json` from the installed airlift skill cache when available.

The registry is helpful but not required. This command works from the markdown alone: `HANDOFF.md` plus `RESUME_PROMPT.md` are sufficient even if the current harness is not in the registry. In that case, use the paste-prompt fallback by pasting `RESUME_PROMPT.md` into the new session and attaching or pasting `HANDOFF.md`.

## Resume plan

Summarize the resume plan back to the user before changing files:

- Objective from `HANDOFF.md`
- Current status and git baseline from `state.json`
- Patch application decision
- Applicable local conventions
- Next steps to continue

Then continue from the `Next steps` section in `HANDOFF.md`.

## Delegate resume paths

For `resume-via-deepseek`, require env `DEEPSEEK_API_KEY`. Resolve the wrapper and invoke it with the resume prompt as system context and the handoff as prompt:

```bash
WRAPPER=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER=$(ls -t "$CACHE"/deepseek/*/skills/deepseek-delegate/references/deepseek-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER" ] && break
done
bash "$WRAPPER" -m v4-pro -s "$(cat .airlift/RESUME_PROMPT.md)" -p "$(cat .airlift/HANDOFF.md)"
```

One-line form:

```bash
WRAPPER=""; for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do WRAPPER=$(ls -t "$CACHE"/deepseek/*/skills/deepseek-delegate/references/deepseek-wrapper.sh 2>/dev/null | head -1); [ -n "$WRAPPER" ] && break; done; bash "$WRAPPER" -m v4-pro -s "$(cat .airlift/RESUME_PROMPT.md)" -p "$(cat .airlift/HANDOFF.md)"
```

For `resume-via-gemini`, require gemini CLI auth. Resolve the wrapper and invoke it with the combined resume prompt and handoff:

```bash
WRAPPER=""
for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER=$(ls -t "$CACHE"/gemini/*/skills/gemini-delegate/references/gemini-wrapper.sh 2>/dev/null | head -1)
  [ -n "$WRAPPER" ] && break
done
bash "$WRAPPER" -m flash -p "$(cat .airlift/RESUME_PROMPT.md; printf '\n\n'; cat .airlift/HANDOFF.md)"
```

One-line form:

```bash
WRAPPER=""; for CACHE in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do WRAPPER=$(ls -t "$CACHE"/gemini/*/skills/gemini-delegate/references/gemini-wrapper.sh 2>/dev/null | head -1); [ -n "$WRAPPER" ] && break; done; bash "$WRAPPER" -m flash -p "$(cat .airlift/RESUME_PROMPT.md; printf '\n\n'; cat .airlift/HANDOFF.md)"
```
