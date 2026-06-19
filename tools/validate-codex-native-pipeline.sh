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

require_text "$orchestrator" "codex_native" "orchestrator accepts codex_native execution mode"
require_text "$orchestrator" "Codex Native Adapter Parity" "orchestrator documents parity rules for Codex"

require_text "$generated_alias" "## Codex Native Execution Adapter" "generated pipeline-run skill contains adapter section"

if [ "$failures" -ne 0 ]; then
  printf "FIX  add the Codex-native pipeline execution adapter and regenerate command skill aliases\n"
  exit 1
fi

printf "OK    Codex-native pipeline execution adapter documented and generated\n"
