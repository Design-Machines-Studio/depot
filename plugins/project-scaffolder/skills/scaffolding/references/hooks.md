# Hook Templates

All hook scripts for Claude Code project scaffolding. Each template uses `{{PROJECT_PREFIX}}` as a placeholder -- replace with the lowercase project directory name before writing.

## Contents

- [General Notes](#general-notes) (line 15) -- Exit codes, stdin format, permissions
- [1. block-bare-go.sh](#1-block-bare-gosh) (line 26) -- Prevents Go commands outside Docker
- [2. block-bare-craft.sh](#2-block-bare-craftsh) -- Prevents Craft and Composer commands outside DDEV
- [3. commit-push-reminder.sh](#3-commit-push-remindersh) -- Once-per-session commit and push reminder
- [4. post-edit-context.sh](#4-post-edit-contextsh) -- Optional context reminders after edits
- [5. pre-stop-check.sh](#5-pre-stop-checksh) -- Once-per-session uncommitted-work reminder
- [6. a11y-check.sh](#6-a11y-checksh) -- Once-per-session accessibility reminder for frontend files
- [7. nats-safety.sh](#7-nats-safetysh) -- Once-per-session NATS safety reminder

## General Notes

- **Exit codes**: `0` = allow the tool call, `2` = block it
- **PreToolUse hooks** receive tool input as JSON on stdin
- **PostToolUse hooks** receive tool input as JSON on stdin; return JSON with `systemMessage` to inject context
- **Stop hooks** receive conversation context on stdin
- All hooks must be executable: `chmod +x .claude/hooks/*.sh`
- All paths use `$CLAUDE_PROJECT_DIR` (set automatically by Claude Code)

---

## 1. block-bare-go.sh

**Event:** PreToolUse | **Matcher:** Bash | **Applies to:** Go projects (go-templ-datastar, go-library with Docker)

Prevents Go and Templ commands from running outside Docker. Forces `docker compose exec app` pattern.

```bash
#!/bin/bash
# block-bare-go.sh -- Prevent Go/Templ commands from running outside Docker
#
# Exit code 2 = block the command and feed error to Claude

COMMAND=$(jq -r '.tool_input.command')

# Match bare go/templ commands not wrapped in docker compose
# Allows: docker compose exec app go build, echo "go build" (quoted), comments
if printf '%s\n' "$COMMAND" | grep -qE '(^|\&\&|\|\||;)\s*(go |templ )' && \
   ! printf '%s\n' "$COMMAND" | grep -q 'docker compose'; then
  printf '%s\n' "BLOCKED: Go/Templ commands must run inside Docker." >&2
  printf '%s\n' "" >&2
  printf '%s\n' "Use: docker compose exec app <command>" >&2
  printf '%s\n' "Example: docker compose exec app go build -o bin/app ./cmd/api" >&2
  printf '%s\n' "Example: docker compose exec app templ generate" >&2
  exit 2
fi

exit 0
```

### Customization
- No placeholders needed -- this hook is universal for Docker-based Go projects
- For projects using a different Docker service name, change `docker compose` to the appropriate command
- For `go-library` projects without Docker, skip this hook entirely

---

## 2. block-bare-craft.sh

**Event:** PreToolUse | **Matcher:** Bash | **Applies to:** `craft-cms`

Prevents Craft and Composer commands from running outside DDEV. Create this file for Craft projects and register it in `settings.json`.

```bash
#!/bin/bash
# block-bare-craft.sh -- Prevent Craft/Composer commands from running outside DDEV

COMMAND=$(jq -r '.tool_input.command // empty' 2>/dev/null)

# Match bare php craft or composer commands. Commands already using ddev are allowed.
if printf '%s\n' "$COMMAND" | grep -qE '(^|&&|\|\||;)\s*(php[[:space:]]+craft|composer([[:space:]]|$))' && \
   ! printf '%s\n' "$COMMAND" | grep -q 'ddev'; then
  printf '%s\n' "BLOCKED: Craft and Composer commands must run inside DDEV." >&2
  printf '%s\n' "Use: ddev craft <command> or ddev composer <command>" >&2
  exit 2
fi

exit 0
```

### Customization
- For projects with a different DDEV command policy, keep the real repository-owned restriction and adjust only the command pattern.

---

## 3. commit-push-reminder.sh

**Event:** PostToolUse | **Matcher:** Edit|Write | **Applies to:** ALL projects

Provides one quiet reminder per session when the working tree has changes. It does not count files or commits, and it is silent when there is nothing to act on.

```bash
#!/bin/bash
# commit-push-reminder.sh -- Once-per-session reminder for verified changes
#
# Emits no output for a clean tree. The session marker prevents repeated nudges.

INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
  exit 0
fi

if ! git -C "$PROJECT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  exit 0
fi

CHANGES=$(git -C "$PROJECT_DIR" status --short 2>/dev/null)
if [ -z "$CHANGES" ]; then
  exit 0
fi

SESSION_ID=$(printf '%s\n' "$INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null || printf '%s\n' 'nosession')
SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -c '[:alnum:]_.-' '_')
STATE_DIR="${TMPDIR:-/tmp}/claude-hook-state"
MARKER="$STATE_DIR/{{PROJECT_PREFIX}}-${SESSION_ID}-commit-push"
mkdir -p "$STATE_DIR" 2>/dev/null
if [ -f "$MARKER" ]; then
  exit 0
fi
touch "$MARKER" 2>/dev/null

MSG="Changes are present. When this coherent change is verified, commit it; push when the branch is ready or sharing and recovery benefit from it."
MSG_JSON=$(printf '%s\n' "$MSG" | jq -Rs '.')
printf '{"systemMessage": %s}\n' "$MSG_JSON"
exit 0
```

### Customization
- Replace `{{PROJECT_PREFIX}}` with the project's lowercase directory name.
- Keep the reminder conditional and once per session. Do not add file-count or commit-count thresholds.

---

## 4. post-edit-context.sh

**Event:** PostToolUse | **Matcher:** Edit|Write | **Applies to:** ALL projects (content varies by type)

Provides optional context after file edits. The template includes all possible blocks -- remove the ones that don't apply to your project type.

**Silence discipline (required).** This hook fires on a broad matcher (every Edit|Write), so each reminder category fires **once per session** via a marker file under `$TMPDIR/claude-hook-state` keyed on `session_id`, then stays silent. Emitting the same static reminder on every edit only burns context tokens -- the assembly-baseplate project hit exactly this and fixed it the same way (2026-07-04). A hook that reminds on a broad matcher must be silent on the second and later occurrences; output only on first occurrence (or on a genuine violation).

```bash
#!/bin/bash
# post-edit-context.sh -- After file edits, inject agent reminders.
#
# Returns systemMessage JSON that reminds Claude to use the right agents.
# Each reminder category fires ONCE per session (marker files under
# $TMPDIR/claude-hook-state keyed on session_id): repeating the same static
# reminder on every edit only burns context tokens. Silent on every repeat.

INPUT=$(cat)
FILE_PATH=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Classify the edited file into a single reminder CATEGORY + MESSAGE. Delete the
# blocks that do not apply to your project type (see Customization below).
CATEGORY=""
MESSAGE=""

# --- GO PROJECTS: keep for go-templ-datastar, go-library ---
if printf '%s\n' "$FILE_PATH" | grep -qE '1_tokens/'; then
  CATEGORY="tokens"
  MESSAGE="Design tokens changed: if this changes styling behavior, consult Live Wires theming guidance and use css-reviewer as needed."
elif printf '%s\n' "$FILE_PATH" | grep -qE 'src/css/|\.css$'; then
  CATEGORY="css"
  MESSAGE="CSS changed: use css-reviewer when the change needs a Live Wires review (cascade layers, naming, or tokens)."
elif printf '%s\n' "$FILE_PATH" | grep -qE '\.templ$'; then
  CATEGORY="templ"
  MESSAGE="Templ changed: use go-builder for generation/build verification when relevant; update docs if behavior or operating instructions changed."
elif printf '%s\n' "$FILE_PATH" | grep -qE '\.go$'; then
  CATEGORY="go"
  MESSAGE="Go source changed: use go-builder for Docker-wrapped build or test verification when relevant."
# --- END GO PROJECTS ---
# --- CRAFT CMS PROJECTS: keep for craft-cms ---
elif printf '%s\n' "$FILE_PATH" | grep -qE '\.twig$|\.html\.twig$'; then
  CATEGORY="twig"
  MESSAGE="Twig template changed: update docs if behavior or operating instructions changed; use doc-sync when impact is unclear."
elif printf '%s\n' "$FILE_PATH" | grep -qE '\.php$'; then
  CATEGORY="php"
  MESSAGE="PHP changed: preserve auth and data boundaries; use security-auditor for auth, authorization, credential, input, or data-handling changes."
# --- END CRAFT CMS PROJECTS ---
# --- UNIVERSAL: keep for all project types ---
elif printf '%s\n' "$FILE_PATH" | grep -qE '\.sql$|migrations/'; then
  CATEGORY="sql"
  MESSAGE="Migration/SQL changed: check authorization and data behavior; use security-auditor when the change affects those boundaries and update docs when behavior changes."
elif printf '%s\n' "$FILE_PATH" | grep -qE '\.(yaml|yml|json|toml)$'; then
  CATEGORY="config"
  MESSAGE="Config changed: update CLAUDE.md or other operating documentation when behavior or setup changes; use doc-sync if impact is unclear."
fi
# --- END UNIVERSAL ---

if [ -z "$CATEGORY" ]; then
  exit 0
fi

# Fire each category at most once per session -- silent on every repeat.
SESSION_ID=$(printf '%s\n' "$INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null || printf '%s\n' 'nosession')
SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -c '[:alnum:]_.-' '_')
STATE_DIR="${TMPDIR:-/tmp}/claude-hook-state"
mkdir -p "$STATE_DIR" 2>/dev/null
MARKER="$STATE_DIR/{{PROJECT_PREFIX}}-${SESSION_ID}-postedit-${CATEGORY}"

if [ -f "$MARKER" ]; then
  exit 0
fi
touch "$MARKER" 2>/dev/null

MSG_JSON=$(printf '%s\n' "$MESSAGE" | jq -Rs '.')
printf '{"systemMessage": %s}\n' "$MSG_JSON"
exit 0
```

### Customization by Project Type

**go-templ-datastar**: Keep Go, CSS/tokens, Templ, SQL, config, and universal blocks. Remove Craft and CSS-framework blocks.

**go-library**: Keep Go, SQL, config, and universal blocks. Remove CSS/tokens, Templ, Craft, and CSS-framework blocks.

**css-framework**: Keep the CSS-framework block (uncommented), config, and universal blocks. Remove Go, Templ, and Craft blocks.

**craft-cms**: Keep Craft, CSS/tokens, SQL, config, and universal blocks. Remove Go and Templ blocks.

Add project-specific blocks as needed (e.g., governance code detection for Assembly).

---

## 5. pre-stop-check.sh

**Event:** Stop | **Matcher:** -- (fires on all stops) | **Applies to:** ALL projects

Checks for uncommitted work before stopping. It is silent when the tree is clean and reminds at most once per session.

```bash
#!/bin/bash
# pre-stop-check.sh -- Before stopping, remind about uncommitted work

INPUT=$(cat)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
  exit 0
fi

if ! git -C "$PROJECT_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  exit 0
fi

CHANGES=$(git -C "$PROJECT_DIR" status --short 2>/dev/null)
if [ -z "$CHANGES" ]; then
  exit 0
fi

SESSION_ID=$(printf '%s\n' "$INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null || printf '%s\n' 'nosession')
SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -c '[:alnum:]_.-' '_')
STATE_DIR="${TMPDIR:-/tmp}/claude-hook-state"
MARKER="$STATE_DIR/{{PROJECT_PREFIX}}-${SESSION_ID}-prestop-uncommitted"
mkdir -p "$STATE_DIR" 2>/dev/null
if [ -f "$MARKER" ]; then
  exit 0
fi
touch "$MARKER" 2>/dev/null

MSG="Uncommitted changes remain. Before stopping, verify the work is complete and commit it when ready."
MSG_JSON=$(printf '%s\n' "$MSG" | jq -Rs '.')
printf '{"systemMessage": %s}\n' "$MSG_JSON"

exit 0
```

### Customization

Replace `{{PROJECT_PREFIX}}` with the project's lowercase directory name. No per-project agent-compliance list is needed. Keep this hook focused on the real uncommitted-work boundary; choose implementation, documentation, security, and accessibility agents from the task and risk.

---

## 6. a11y-check.sh

**Event:** PostToolUse | **Matcher:** Edit|Write | **Applies to:** Frontend projects (go-templ-datastar, css-framework, craft-cms)

Provides an accessibility review reminder after relevant template, CSS, or JavaScript changes. Each category fires once per session and the hook is silent for unrelated files.

```bash
#!/bin/bash
# a11y-check.sh -- Once-per-session accessibility reminder after frontend changes
#
# Returns systemMessage JSON only when an applicable review may help.

INPUT=$(cat)
FILE_PATH=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

SESSION_ID=$(printf '%s\n' "$INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null || printf '%s\n' 'nosession')
SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -c '[:alnum:]_.-' '_')
STATE_DIR="${TMPDIR:-/tmp}/claude-hook-state"
mkdir -p "$STATE_DIR" 2>/dev/null

remind_once() {
  CATEGORY="$1"
  MESSAGE="$2"
MARKER="$STATE_DIR/{{PROJECT_PREFIX}}-${SESSION_ID}-a11y-${CATEGORY}"
  if [ -f "$MARKER" ]; then
    return 0
  fi
  touch "$MARKER" 2>/dev/null
  MSG_JSON=$(printf '%s\n' "$MESSAGE" | jq -Rs '.')
  printf '{"systemMessage": %s}\n' "$MSG_JSON"
}

if printf '%s\n' "$FILE_PATH" | grep -qE '\.(templ|twig|html)$'; then
  remind_once "html" "Template changed: use a11y-html-reviewer when the change affects semantics, forms, landmarks, ARIA, or alt text."
  exit 0
fi

if printf '%s\n' "$FILE_PATH" | grep -qE '\.css$'; then
  remind_once "css" "CSS changed: use a11y-css-reviewer when the change affects contrast, focus visibility, motion safety, touch targets, or reflow."
  exit 0
fi

if printf '%s\n' "$FILE_PATH" | grep -qE '\.(js|ts)$'; then
  remind_once "dynamic" "JavaScript or Datastar changed: use a11y-dynamic-content-reviewer when the change affects live regions, focus management, or keyboard operability."
  exit 0
fi

exit 0
```

### Customization

- No placeholders needed -- this hook is universal for frontend projects
- For go-library projects (no frontend): skip this hook entirely
- For projects using Datastar heavily, the JS check will fire on Datastar signal files too
- **Note:** This hook may fire alongside `post-edit-context.sh` on `.css` and template files. Both reminders are once per session and optional; use the accessibility reviewer when the change actually affects an accessibility boundary.

---

## 7. nats-safety.sh

**Event:** PostToolUse
**Matcher:** Edit|Write
**Project types:** `go-templ-datastar`

Fires when NATS-related Go files are edited. Reminds about DontListen enforcement, event-after-commit ordering, and ScopedEventBus usage.

```bash
#!/usr/bin/env bash
# PostToolUse hook: NATS safety reminder
# Fires once per session after editing Go files related to NATS/events

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.command // empty' 2>/dev/null || printf '%s\n' '')

# Only check Go files related to NATS
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *.go ]]; then
  exit 0
fi

# Check if the file is NATS-related
if ! grep -qE '(nats\.|embeddednats|jetstream|ScopedEventBus|EventBus|KVStore|kv\.Watch|kv\.Put|kv\.Get)' "$FILE_PATH" 2>/dev/null; then
  exit 0
fi

SESSION_ID=$(printf '%s\n' "$INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null || printf '%s\n' 'nosession')
SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -c '[:alnum:]_.-' '_')
STATE_DIR="${TMPDIR:-/tmp}/claude-hook-state"
MARKER="$STATE_DIR/{{PROJECT_PREFIX}}-${SESSION_ID}-nats"
mkdir -p "$STATE_DIR" 2>/dev/null
if [ -f "$MARKER" ]; then
  exit 0
fi
touch "$MARKER" 2>/dev/null

MESSAGE="NATS-related Go file changed: preserve DontListen=true, publish events after db.WithTx() commit, use ScopedEventBus in fixtures, and keep assembly.{scope}.{entity}.{event} subjects. Use nats-reviewer when this change needs a focused check."
MSG_JSON=$(printf '%s\n' "$MESSAGE" | jq -Rs '.')
printf '{"systemMessage": %s}\n' "$MSG_JSON"

exit 0
```

**Customization notes:**
- The grep pattern can be extended for project-specific NATS types
- Consider adding a marker file to prevent repeated reminders within the same edit session
