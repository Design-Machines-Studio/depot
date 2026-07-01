#!/usr/bin/env bash
#
# validate-codex-native-pipeline.sh -- Ensure /pipeline-run has a real Codex
# execution adapter instead of relying on Claude-only Agent/Skill tools.

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

pipeline_run="$REPO_ROOT/plugins/pipeline/commands/pipeline-run.md"
pipeline_command="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
generated_alias="$REPO_ROOT/plugins/pipeline/skills/pipeline-run/SKILL.md"

require_text "$pipeline_run" "## Codex Native Execution Adapter" "pipeline-run documents Codex-native execution"
require_text "$pipeline_run" "multi_agent_v1.spawn_agent" "pipeline-run maps implementation dispatch to Codex subagents"
require_text "$pipeline_run" "dm-review inline protocol" "pipeline-run replaces nested Skill calls with inline review protocol"
require_text "$pipeline_run" "executionMode: codex_native" "pipeline-run records codex_native receipts"

require_text "$pipeline_command" "Codex Native Execution Adapter" "full pipeline Phase 6 links to Codex-native adapter"
require_text "$pipeline_command" "Codex + OpenRouter" "full pipeline defaults adversarial review to non-Claude dual lenses"

require_text "$orchestrator" "codex_native" "orchestrator accepts codex_native execution mode"
require_text "$orchestrator" "Codex Native Adapter Parity" "orchestrator documents parity rules for Codex"
require_text "$orchestrator" 'BASE_BRANCH="${manifest.baseBranch:-main}"' "orchestrator branches from manifest.baseBranch with main fallback"
require_text "$orchestrator" "pipeline-owned artifacts" "orchestrator distinguishes pipeline artifacts from user changes"
require_text "$orchestrator" "sequential-on-branch" "orchestrator documents container-mounted sequential execution mode"
require_text "$orchestrator" "docker compose ps" "orchestrator probes Docker Compose port mappings for dev server"
require_text "$orchestrator" "manifest.devServerURL" "orchestrator accepts manifest.devServerURL for browser proof"
require_text "$orchestrator" "git add -A --" "orchestrator stages pathspecs without aborting on missing renamed files"
require_text "$orchestrator" "git commit -F" "orchestrator writes commit messages from files"
require_text "$orchestrator" "git check-ignore -q plans/" "orchestrator detects ignored plans receipts"

require_text "$generated_alias" "## Codex Native Execution Adapter" "generated pipeline-run skill contains adapter section"
require_text "$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md" "Small UI" "promptcraft scales quality floors by estimatedComplexity"
require_text "$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md" "module build/tests pass in Docker" "promptcraft avoids bare Go command phrases in commit text"

if [ "$failures" -ne 0 ]; then
  printf "FIX  add the Codex-native pipeline execution adapter and regenerate command skill aliases\n"
  exit 1
fi

printf "OK    Codex-native pipeline execution adapter documented and generated\n"
