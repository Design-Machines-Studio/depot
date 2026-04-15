# Hook Templates

All hook scripts for Claude Code project scaffolding. Each template uses `{{PROJECT_PREFIX}}` as a placeholder — replace with the lowercase project directory name before writing.

## Contents

- [General Notes](#general-notes) (line 15) -- Exit codes, stdin format, permissions
- [1. block-bare-go.sh](#1-block-bare-gosh) (line 26) -- Prevents Go commands outside Docker
- [2. session-start-gate.sh](#2-session-start-gatesh) (line 62) -- Blocks edits until planner workflow runs
- [3. commit-push-reminder.sh](#3-commit-push-remindersh) (line 106) -- Nudges frequent commits and pushes
- [4. post-edit-context.sh](#4-post-edit-contextsh) (line 182) -- Context-aware agent reminders after edits
- [5. pre-stop-check.sh](#5-pre-stop-checksh) (line 290) -- Verifies commits and agents before stopping
- [6. a11y-check.sh](#6-a11y-checksh) (line 396) -- Accessibility agent reminders for frontend files

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
# block-bare-go.sh — Prevent Go/Templ commands from running outside Docker
#
# Exit code 2 = block the command and feed error to Claude

COMMAND=$(jq -r '.tool_input.command')

# Match bare go/templ commands not wrapped in docker compose
# Allows: docker compose exec app go build, echo "go build" (quoted), comments
if printf '%s\n' "$COMMAND" | grep -qE '(^|\&\&|\|\||;)\s*(go |templ )' && \
   ! printf '%s\n' "$COMMAND" | grep -q 'docker compose'; then
  echo "BLOCKED: Go/Templ commands must run inside Docker." >&2
  echo "" >&2
  echo "Use: docker compose exec app <command>" >&2
  echo "Example: docker compose exec app go build -o bin/app ./cmd/api" >&2
  echo "Example: docker compose exec app templ generate" >&2
  exit 2
fi

exit 0
```

### Customization
- No placeholders needed — this hook is universal for Docker-based Go projects
- For projects using a different Docker service name, change `docker compose` to the appropriate command
- For `go-library` projects without Docker, skip this hook entirely

---

## 2. session-start-gate.sh

**Event:** PreToolUse | **Matcher:** Edit|Write | **Applies to:** Projects using the planner workflow (opt-in)

Blocks file modifications until the planner session start workflow completes (sprint check, todos).

```bash
#!/bin/bash
# session-start-gate.sh — Block file changes until session workflow runs
#
# Marker: /tmp/{{PROJECT_PREFIX}}-session-YYYY-MM-DD
# To manually clear: rm /tmp/{{PROJECT_PREFIX}}-session-$(date +%Y-%m-%d)
#
# Exit code 2 = block the tool call

TODAY=$(date +%Y-%m-%d)
MARKER="/tmp/{{PROJECT_PREFIX}}-session-${TODAY}"

if [ -f "$MARKER" ]; then
  exit 0
fi

echo "BLOCKED: Session workflow not completed." >&2
echo "" >&2
echo "Before making changes, complete the planner session start:" >&2
echo "  1. Invoke the planner skill:" >&2
echo "     /planner (or read the project-manager planner skill from depot)" >&2
echo "  2. Check memory/sessions.md for last session context" >&2
echo "  3. Query Sprints DB for active sprint (Status = In progress)" >&2
echo "  4. Query Todos DB for this project's open sprint todos" >&2
echo "  5. Brief the user on sprint status" >&2
echo "" >&2
echo "Then mark session started: touch ${MARKER}" >&2
exit 2
```

### Customization
- Replace `{{PROJECT_PREFIX}}` with the project's lowercase directory name
- The planner skill is invoked via `/planner` (installed from the depot's project-manager plugin)
- For projects without Notion/planner integration, skip this hook

---

## 3. commit-push-reminder.sh

**Event:** PostToolUse | **Matcher:** Edit|Write | **Applies to:** ALL projects

Nudges toward frequent commits and pushes. Fires after every file edit.

```bash
#!/bin/bash
# commit-push-reminder.sh — Nudge toward frequent commits and pushes
#
# Checks:
# 1. Uncommitted file count → suggest commit at 2+ files, insist at 3+
# 2. Unpushed commit count → suggest push at 2+ commits
#
# Uses HEAD-keyed markers so nudges reset after each commit.

INPUT=$(cat)

HEAD=$(git -C "${CLAUDE_PROJECT_DIR}" rev-parse --short HEAD 2>/dev/null)
if [ -z "$HEAD" ]; then
  exit 0
fi

# Count uncommitted changes (unstaged + staged, deduplicated)
CHANGED=$(git -C "${CLAUDE_PROJECT_DIR}" diff --name-only 2>/dev/null)
STAGED=$(git -C "${CLAUDE_PROJECT_DIR}" diff --cached --name-only 2>/dev/null)
TOTAL=$(printf "%s\n%s" "$CHANGED" "$STAGED" | sort -u | grep -c -v '^$')

# Count unpushed commits (0 if no upstream tracking)
UNPUSHED=$(git -C "${CLAUDE_PROJECT_DIR}" log @{u}..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')
[ -z "$UNPUSHED" ] && UNPUSHED=0

MSG=""

# Strong nudge at 3+ files — fires every time
if [ "$TOTAL" -ge 3 ]; then
  MSG="You have $TOTAL uncommitted file changes. Run /simplify on the changed files, then stop and commit with a focused message. Keep commits to 1-4 files."

# Gentle nudge at 2+ files — fires once per HEAD (resets after each commit)
elif [ "$TOTAL" -ge 2 ]; then
  MARKER="/tmp/{{PROJECT_PREFIX}}-commit-nudge-${HEAD}"
  if [ ! -f "$MARKER" ]; then
    touch "$MARKER"
    MSG="$TOTAL files changed since last commit. Consider running /simplify, then commit before making more changes."
  fi
fi

# Push nudge at 2+ unpushed commits — fires once per count
if [ "$UNPUSHED" -ge 2 ]; then
  PUSH_MARKER="/tmp/{{PROJECT_PREFIX}}-push-nudge-${UNPUSHED}"
  if [ ! -f "$PUSH_MARKER" ]; then
    touch "$PUSH_MARKER"
    PUSH_MSG="You have $UNPUSHED unpushed commits — push to remote."
    if [ -n "$MSG" ]; then
      MSG="$MSG $PUSH_MSG"
    else
      MSG="$PUSH_MSG"
    fi
  fi
fi

if [ -n "$MSG" ]; then
  MSG_JSON=$(echo "$MSG" | jq -Rs '.')
  echo "{\"systemMessage\": $MSG_JSON}"
fi

exit 0
```

### Customization
- Replace `{{PROJECT_PREFIX}}` with the project's lowercase directory name
- Adjust thresholds (2/3) if needed — these match the Assembly defaults
- The gentle nudge fires once per HEAD (resets after each commit); the strong nudge fires every time

---

## 4. post-edit-context.sh

**Event:** PostToolUse | **Matcher:** Edit|Write | **Applies to:** ALL projects (content varies by type)

Provides context-aware agent reminders after file edits. The template includes all possible blocks — remove the ones that don't apply to your project type.

```bash
#!/bin/bash
# post-edit-context.sh — After file edits, inject agent reminders
#
# Returns systemMessage JSON that reminds Claude to use the right agents.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# --- GO PROJECTS: Keep for go-templ-datastar, go-library ---

# Token file changes → theming skill reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '1_tokens/'; then
  echo "{\"systemMessage\": \"Design tokens modified: Reference livewires theming.md for token guidelines. Run css-reviewer to verify compliance.\"}"
  exit 0
fi

# CSS file changes → css-reviewer reminder
if printf '%s\n' "$FILE_PATH" | grep -qE 'src/css/|\.css$'; then
  echo "{\"systemMessage\": \"CSS modified: Consider running the css-reviewer agent to verify Live Wires compliance (cascade layers, naming, tokens).\"}"
  exit 0
fi

# Templ template changes → go-builder + doc-sync reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '\.templ$'; then
  echo "{\"systemMessage\": \"Templ template modified: Run templ generate + go build via the go-builder agent. Check documentation via doc-sync.\"}"
  exit 0
fi

# Go source changes → go-builder reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '\.go$'; then
  echo "{\"systemMessage\": \"Go source modified: Rebuild via the go-builder agent (docker compose exec app go build).\"}"
  exit 0
fi

# --- END GO PROJECTS ---

# --- CRAFT CMS PROJECTS: Keep for craft-cms ---

# Twig template changes → doc-sync reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '\.twig$|\.html\.twig$'; then
  echo "{\"systemMessage\": \"Twig template modified: Check if documentation needs updating via doc-sync.\"}"
  exit 0
fi

# PHP changes → rebuild reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '\.php$'; then
  echo "{\"systemMessage\": \"PHP modified: Clear caches if needed (ddev craft clear-caches/all). Run security-auditor for handler/controller changes.\"}"
  exit 0
fi

# --- END CRAFT CMS PROJECTS ---

# --- CSS FRAMEWORK PROJECTS: Keep for css-framework ---

# CSS file changes (standalone framework) → css-reviewer + build reminder
# Note: The CSS block above (under GO PROJECTS) covers css-framework too.
# Only keep this block if you DON'T have the Go CSS block above.
# if printf '%s\n' "$FILE_PATH" | grep -qE '\.css$'; then
#   echo "{\"systemMessage\": \"CSS modified: Run css-reviewer to verify naming conventions, cascade layers, and token usage. Rebuild with npm run build.\"}"
#   exit 0
# fi

# --- END CSS FRAMEWORK PROJECTS ---

# --- UNIVERSAL: Keep for all project types ---

# SQL migration changes → doc-sync + security reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '\.sql$|migrations/'; then
  echo "{\"systemMessage\": \"Migration/SQL modified: Run security-auditor to check for injection risks. Update documentation via doc-sync.\"}"
  exit 0
fi

# Config file changes → doc-sync reminder
if printf '%s\n' "$FILE_PATH" | grep -qE '\.(yaml|yml|json|toml)$'; then
  echo "{\"systemMessage\": \"Config file modified: Check if CLAUDE.md or other documentation needs updating via doc-sync.\"}"
  exit 0
fi

# --- END UNIVERSAL ---

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

**Event:** Stop | **Matcher:** — (fires on all stops) | **Applies to:** ALL projects

Checks for uncommitted work before stopping. Reminds about agent compliance and session end workflow.

```bash
#!/bin/bash
# pre-stop-check.sh — Before stopping, verify work is committed and agents ran
#
# Uses a diff-hash marker to prevent infinite loops.

INPUT=$(cat)

# --- CONFIGURE THESE PER PROJECT ---
# List agents that should be checked based on file types changed
# Format: "file_pattern:agent_name:description"
AGENT_CHECKS=(
  '\.css$:css-reviewer:CSS files changed'
  '\.(go|templ)$:go-builder:Go/Templ files changed — verify build succeeded'
  '(handlers/|middleware/|auth|migrations/):security-auditor:Handler/auth/data code changed'
  '\.(go|templ|css|js|sql|yaml|yml|html|twig|php)$:doc-sync:Code changed — verify documentation is fresh'
)
# --- END CONFIGURATION ---

# Check for uncommitted changes
UNSTAGED=$(git -C "${CLAUDE_PROJECT_DIR}" diff --name-only 2>/dev/null)
STAGED=$(git -C "${CLAUDE_PROJECT_DIR}" diff --cached --name-only 2>/dev/null)
CHANGES=$(printf "%s\n%s" "$UNSTAGED" "$STAGED" | sort -u | grep -v '^$')

# Check recent commits (changes already committed this session)
TODAY=$(date +%Y-%m-%d)
COMMITTED_TODAY=$(git -C "${CLAUDE_PROJECT_DIR}" log --since="$TODAY" --name-only --pretty=format: 2>/dev/null | sort -u | grep -v '^$')
ALL_CHANGES=$(printf "%s\n%s" "$CHANGES" "$COMMITTED_TODAY" | sort -u | grep -v '^$')

if [ -z "$ALL_CHANGES" ]; then
  # No changes at all — just remind about session end
  TODAY_MARKER="/tmp/{{PROJECT_PREFIX}}-session-${TODAY}"
  if [ -f "$TODAY_MARKER" ]; then
    echo "{\"systemMessage\": \"Session end: Append session summary to memory/sessions.md.\"}"
  fi
  exit 0
fi

# Prevent infinite loops — hash the changes and check if we already reminded
find /tmp -name "{{PROJECT_PREFIX}}-stop-review-*" -type f -mmin +60 -delete 2>/dev/null
DIFF_HASH=$(echo "$ALL_CHANGES" | md5 -q 2>/dev/null || echo "$ALL_CHANGES" | md5sum | cut -d' ' -f1)
REVIEW_MARKER="/tmp/{{PROJECT_PREFIX}}-stop-review-${DIFF_HASH}"

if [ -f "$REVIEW_MARKER" ]; then
  exit 0
fi
touch "$REVIEW_MARKER"

# Build agent reminders from AGENT_CHECKS
AGENT_REMINDERS=""
for check in "${AGENT_CHECKS[@]}"; do
  IFS=':' read -r pattern agent desc <<< "$check"
  if printf '%s\n' "$ALL_CHANGES" | grep -qE "$pattern"; then
    AGENT_REMINDERS="${AGENT_REMINDERS}\n- ${agent}: ${desc}"
  fi
done

FILE_COUNT=$(echo "$ALL_CHANGES" | wc -l | tr -d ' ')
MSG="STOP — ${FILE_COUNT} files changed this session. Before finishing:"

if [ -n "$AGENT_REMINDERS" ]; then
  MSG="${MSG}\n\nAgents to run (if not already done):${AGENT_REMINDERS}"
fi

# Simplification reminder
MSG="${MSG}\n\nRun /simplify on changed files before finishing to catch complexity creep."

# Uncommitted changes warning
if [ -n "$CHANGES" ]; then
  UNCOMMITTED_COUNT=$(echo "$CHANGES" | wc -l | tr -d ' ')
  MSG="${MSG}\n\nWARNING: ${UNCOMMITTED_COUNT} uncommitted files. Commit before stopping."
fi

# Session end workflow (only if session was started)
TODAY_MARKER="/tmp/{{PROJECT_PREFIX}}-session-${TODAY}"
if [ -f "$TODAY_MARKER" ]; then
  MSG="${MSG}\n\nSession end workflow:"
  MSG="${MSG}\n- Append session summary to memory/sessions.md"
fi

MSG_JSON=$(printf "%b" "$MSG" | jq -Rs '.')
echo "{\"systemMessage\": $MSG_JSON}"

exit 0
```

### Customization

**AGENT_CHECKS array**: Edit this to match the project's agents. Each entry is `pattern:agent_name:description`.

**By project type:**

- **go-templ-datastar**: All 4 default checks + a11y agents. Add governance/domain-specific checks as needed.
- **go-library**: Keep go-builder and doc-sync. Remove css-reviewer and a11y agents.
- **css-framework**: Keep css-reviewer, doc-sync, and a11y-css-reviewer. Remove go-builder and security-auditor.
- **craft-cms**: Replace go-builder with a craft-builder check (`\.php$:craft-builder:PHP changed`). Keep doc-sync, security-auditor, and a11y agents.

---

## 6. a11y-check.sh

**Event:** PostToolUse | **Matcher:** Edit|Write | **Applies to:** Frontend projects (go-templ-datastar, css-framework, craft-cms)

Triggers accessibility agent reminders after template, CSS, or JavaScript file modifications.

```bash
#!/bin/bash
# a11y-check.sh — Remind about accessibility after frontend file changes
#
# Returns systemMessage JSON that reminds Claude to run a11y review agents.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Template files → HTML accessibility review
if printf '%s\n' "$FILE_PATH" | grep -qE '\.(templ|twig|html)$'; then
  echo "{\"systemMessage\": \"Template modified: Run the a11y-html-reviewer agent to check WCAG 2.2 compliance (landmarks, headings, forms, ARIA, alt text).\"}"
  exit 0
fi

# CSS files → Visual accessibility review
if printf '%s\n' "$FILE_PATH" | grep -qE '\.css$'; then
  echo "{\"systemMessage\": \"CSS modified: Run the a11y-css-reviewer agent to verify contrast, focus visibility, motion safety, and touch targets.\"}"
  exit 0
fi

# JavaScript/Datastar files → Dynamic content review
if printf '%s\n' "$FILE_PATH" | grep -qE '\.(js|ts)$'; then
  echo "{\"systemMessage\": \"JavaScript modified: Run the a11y-dynamic-content-reviewer agent to check live regions, focus management, and keyboard operability.\"}"
  exit 0
fi

exit 0
```

### Customization

- No placeholders needed — this hook is universal for frontend projects
- For go-library projects (no frontend): skip this hook entirely
- For projects using Datastar heavily, the JS check will fire on Datastar signal files too
- **Note:** This hook fires alongside `post-edit-context.sh` on `.css` and template files. That's intentional — post-edit-context reminds about build/CSS agents while this hook reminds about accessibility agents. Both systemMessages are useful.

---

## 7. nats-safety.sh

**Event:** PostToolUse
**Matcher:** Edit|Write
**Project types:** `go-templ-datastar`

Fires when NATS-related Go files are edited. Reminds about DontListen enforcement, event-after-commit ordering, and ScopedEventBus usage.

```bash
#!/usr/bin/env bash
# PostToolUse hook: NATS safety reminders
# Fires after editing Go files related to NATS/events

set -euo pipefail

# Read the tool result from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.command // empty' 2>/dev/null || echo "")

# Only check Go files related to NATS
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *.go ]]; then
  exit 0
fi

# Check if the file is NATS-related
if ! grep -qE '(nats\.|embeddednats|jetstream|ScopedEventBus|EventBus|KVStore|kv\.Watch|kv\.Put|kv\.Get)' "$FILE_PATH" 2>/dev/null; then
  exit 0
fi

# Provide context-aware reminder
cat <<'REMINDER'

🔒 NATS file changed. Remember:
- DontListen: true must be set on embedded NATS server (P1 if missing)
- Events publish AFTER db.WithTx() commit, never inside the transaction
- Fixtures use ScopedEventBus, not raw nats.Conn
- Subject pattern: assembly.{scope}.{entity}.{event}
- Run nats-reviewer agent to validate patterns

REMINDER

exit 0
```

**Customization notes:**
- The grep pattern can be extended for project-specific NATS types
- Consider adding a marker file to prevent repeated reminders within the same edit session
