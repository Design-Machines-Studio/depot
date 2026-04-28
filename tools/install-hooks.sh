#!/usr/bin/env bash
#
# install-hooks.sh: One-shot installer for the depot's git hooks.
#
# WHY THIS EXISTS:
#   Git stores hooks under .git/hooks by default, which lives outside the
#   tracked tree. We track our hooks under .githooks/ so they ship with the
#   repo. This installer points git at that directory by setting
#   `core.hooksPath` for the local clone.
#
# WHAT THIS DOES:
#   git config core.hooksPath .githooks
#
# USAGE:
#   bash tools/install-hooks.sh
#   (run once after cloning the depot; hooks then run automatically)
#
# BYPASS:
#   git commit --no-verify
#   (only when you're CERTAIN the change is intentional, e.g. an
#    expected SKILL.md restructure)
#
# DEPENDENCIES:
#   git (any version with core.hooksPath support, i.e. >= 2.9)

set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  printf "ERROR: not inside a git repository\n" >&2
  exit 1
}

HOOKS_DIR="$REPO_ROOT/.githooks"

if [ ! -d "$HOOKS_DIR" ]; then
  printf "ERROR: %s does not exist\n" "$HOOKS_DIR" >&2
  exit 1
fi

# Ensure all hook scripts in .githooks are executable. This is idempotent and
# protects against the executable bit getting dropped during patch transfers.
find "$HOOKS_DIR" -type f -not -name "*.md" -not -name "README*" -exec chmod +x {} +

# Point git at the tracked hooks directory for this clone.
git -C "$REPO_ROOT" config --local core.hooksPath .githooks

current_hooks_path=$(git -C "$REPO_ROOT" config --local core.hooksPath)

printf "Installed: core.hooksPath = %s\n" "$current_hooks_path"
printf "\n"
printf "Hooks active for this clone:\n"
for h in "$HOOKS_DIR"/*; do
  [ -f "$h" ] || continue
  case "$(basename "$h")" in
    *.md|README*) continue ;;
  esac
  printf "  - %s\n" "$(basename "$h")"
done
printf "\n"
printf "Bypass any hook with: git commit --no-verify\n"
