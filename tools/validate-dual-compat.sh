#!/usr/bin/env bash
#
# validate-dual-compat.sh -- Validate Claude + Codex marketplace surfaces
#
# Claude manifests are canonical. Codex manifests are generated shims and must
# stay byte-for-byte aligned with tools/generate-codex-manifests.py output.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -t 1 ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[0;33m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN='' RED='' YELLOW='' BOLD='' RESET=''
fi

check_generated_manifests() {
  "$SCRIPT_DIR/generate-codex-manifests.py" --check
}

check_generated_command_skills() {
  "$SCRIPT_DIR/generate-codex-command-skills.py" --check
}

check_codex_component_paths() {
  local result
  result=$(REPO_ROOT="$REPO_ROOT" python3 << 'PYEOF'
from pathlib import Path
import json
import os

repo = Path(os.environ["REPO_ROOT"])
issues = []

component_paths = {
    "skills": Path("skills"),
    "commands": Path("commands"),
    "agents": Path("agents"),
}

for plugin_dir in sorted((repo / "plugins").iterdir()):
    if not plugin_dir.is_dir():
        continue

    manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        issues.append(f"{plugin_dir.name}: missing .codex-plugin/plugin.json")
        continue

    manifest = json.loads(manifest_path.read_text())

    for key, rel_dir in component_paths.items():
        expected = f"./{key}/"
        has_component_dir = (plugin_dir / rel_dir).is_dir()
        actual = manifest.get(key)

        if has_component_dir and actual != expected:
            issues.append(f"{plugin_dir.name}: expected {key}={expected!r}, found {actual!r}")
        if not has_component_dir and key in manifest:
            issues.append(f"{plugin_dir.name}: manifest declares {key} but {rel_dir}/ is missing")

for issue in issues:
    print(issue)
PYEOF
)

  if [ -n "$result" ]; then
    while IFS= read -r issue; do
      [ -z "$issue" ] && continue
      printf "  ${RED}FAIL${RESET}  %s\n" "$issue"
    done <<< "$result"
    printf "  ${YELLOW}FIX${RESET}   Run ./tools/generate-codex-manifests.py after editing Claude manifests or component directories\n"
    return 1
  fi

  printf "  ${GREEN}OK${RESET}    Codex manifests expose skills, commands, and agents component paths\n"
}

check_claude_cache_fallbacks() {
  local result
  result=$(REPO_ROOT="$REPO_ROOT" python3 << 'PYEOF'
from pathlib import Path
import os

repo = Path(os.environ["REPO_ROOT"])
issues = []

for path in sorted((repo / "plugins").rglob("*")):
    if path.suffix not in {".md", ".sh"}:
        continue
    text = path.read_text(errors="ignore")
    has_claude_cache = (
        "~/.claude/plugins/cache/depot" in text
        or "$HOME/.claude/plugins/cache/depot" in text
    )
    has_codex_cache = (
        "~/.codex/plugins/cache/depot" in text
        or "$HOME/.codex/plugins/cache/depot" in text
    )
    if not has_claude_cache:
        continue
    if has_codex_cache:
        continue
    issues.append(str(path.relative_to(repo)))

for issue in issues:
    print(issue)
PYEOF
)

  if [ -n "$result" ]; then
    while IFS= read -r rel; do
      [ -z "$rel" ] && continue
      printf "  ${RED}FAIL${RESET}  %s has Claude cache lookup without Codex fallback\n" "$rel"
    done <<< "$result"
    printf "  ${YELLOW}FIX${RESET}   Add a fallback that checks ~/.codex/plugins/cache/depot after ~/.claude/plugins/cache/depot\n"
    return 1
  fi

  printf "  ${GREEN}OK${RESET}    Claude cache lookups include Codex fallbacks\n"
}

check_plugin_hooks() {
  local result
  result=$(REPO_ROOT="$REPO_ROOT" python3 << 'PYEOF'
from pathlib import Path
import json
import os
import re

repo = Path(os.environ["REPO_ROOT"])
# Lifecycle events both Claude Code and Codex deliver to plugin hooks.
shared_events = {
    "PreToolUse", "PostToolUse", "PermissionRequest", "PreCompact", "PostCompact",
    "SessionStart", "SessionEnd", "UserPromptSubmit", "SubagentStart", "SubagentStop", "Stop",
}
# Both harnesses set CLAUDE_PLUGIN_ROOT for plugin hook commands.
command_pattern = re.compile(r'^"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)"( [a-z-]+)?$')
issues = []

for hooks_path in sorted((repo / "plugins").glob("*/hooks/hooks.json")):
    plugin_dir = hooks_path.parent.parent
    rel = hooks_path.relative_to(repo)
    try:
        config = json.loads(hooks_path.read_text())
    except json.JSONDecodeError as error:
        issues.append(f"{rel}: invalid JSON ({error})")
        continue
    events = config.get("hooks") if isinstance(config, dict) else None
    if not isinstance(events, dict) or not events:
        issues.append(f"{rel}: expected a non-empty hooks object")
        continue
    for event, groups in events.items():
        if event not in shared_events:
            issues.append(f"{rel}: {event} is not delivered by both Claude and Codex")
        for group in groups if isinstance(groups, list) else [None]:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list) or not handlers:
                issues.append(f"{rel}: {event} group has no hooks list")
                continue
            for handler in handlers:
                if not isinstance(handler, dict) or handler.get("type") != "command":
                    issues.append(f"{rel}: {event} handler must be a command")
                    continue
                match = command_pattern.match(str(handler.get("command", "")))
                if not match:
                    issues.append(f"{rel}: {event} command must run a quoted ${{CLAUDE_PLUGIN_ROOT}} script")
                    continue
                script = plugin_dir / match.group(1)
                if ".." in Path(match.group(1)).parts or not script.is_file() or not os.access(script, os.X_OK):
                    issues.append(f"{rel}: {event} script {match.group(1)} is missing or not executable")

for issue in issues:
    print(issue)
PYEOF
)

  if [ -n "$result" ]; then
    while IFS= read -r issue; do
      [ -z "$issue" ] && continue
      printf "  ${RED}FAIL${RESET}  %s\n" "$issue"
    done <<< "$result"
    printf "  ${YELLOW}FIX${RESET}   Keep plugin hooks on shared events and point them at executable bundle scripts\n"
    return 1
  fi

  printf "  ${GREEN}OK${RESET}    Plugin hooks use shared events and executable bundle scripts\n"
}

main() {
  local any_failed=0

  printf "\n${BOLD}Dual Compatibility Validation${RESET}\n"
  printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

  printf "${BOLD}Generated Codex manifests:${RESET}\n"
  if ! check_generated_manifests; then
    any_failed=1
  fi

  printf "\n${BOLD}Generated command skill aliases:${RESET}\n"
  if ! check_generated_command_skills; then
    any_failed=1
  fi

  printf "\n${BOLD}Codex component paths:${RESET}\n"
  if ! check_codex_component_paths; then
    any_failed=1
  fi

  printf "\n${BOLD}Plugin hooks:${RESET}\n"
  if ! check_plugin_hooks; then
    any_failed=1
  fi

  printf "\n${BOLD}Runtime cache-path fallbacks:${RESET}\n"
  if ! check_claude_cache_fallbacks; then
    any_failed=1
  fi

  printf "\n"
  if [ "$any_failed" -eq 1 ]; then
    printf "${RED}FAIL: Dual compatibility checks reported issues${RESET}\n\n"
    exit 1
  fi

  printf "${GREEN}PASS: Claude and Codex compatibility surfaces are in sync${RESET}\n\n"
}

main "$@"
