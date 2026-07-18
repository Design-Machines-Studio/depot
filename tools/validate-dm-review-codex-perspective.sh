#!/usr/bin/env bash
#
# validate-dm-review-codex-perspective.sh -- Ensure dm-review keeps the
# Codex second-opinion reviewer and verify-before-close gates documented.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

failures=0

require_text() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if grep -Fq "$pattern" "$file"; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

review_skill="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
consolidator="$REPO_ROOT/plugins/dm-review/agents/workflow/review-consolidator.md"
registry="$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md"
codex_agent="$REPO_ROOT/plugins/dm-review/agents/review/codex-perspective.md"

require_text "$review_skill" "codex-perspective" "review skill selects codex-perspective reviewer"
require_text "$review_skill" "codex exec -s read-only -c service_tier=fast --skip-git-repo-check" "review skill documents known-good Codex invocation"
require_text "$review_skill" "service_tier=fast" "review skill forces fast tier override"
require_text "$review_skill" "Verify-before-close" "review skill gates stale/already-fixed dispositions"
require_text "$review_skill" "code-evidence re-verification at HEAD" "review skill requires HEAD evidence before stale closeout"
require_text "$consolidator" "merge findings from both" "consolidator merges dual-perspective findings"
require_text "$consolidator" "a finding from either coding provider is in-scope" "consolidator treats either coding provider as actionable"
require_text "$registry" "codex-perspective" "agent registry includes codex-perspective"
require_text "$codex_agent" "Normalize output to P1/P2/P3" "codex-perspective agent normalizes output"

if [ "$failures" -ne 0 ]; then
  printf "FIX  add codex-perspective review routing and verify-before-close gates\n"
  exit 1
fi

printf "OK    dm-review codex-perspective reviewer documented\n"
