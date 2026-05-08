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

main() {
  local any_failed=0

  printf "\n${BOLD}Dual Compatibility Validation${RESET}\n"
  printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

  printf "${BOLD}Generated Codex manifests:${RESET}\n"
  if ! check_generated_manifests; then
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
