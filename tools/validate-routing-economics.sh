#!/usr/bin/env bash
#
# validate-routing-economics.sh -- Guard second-pass provider routing and
# run-economics contracts for pipeline/dm-review/openrouter.

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

require_absent() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if grep -Fq "$pattern" "$file"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
}

routing="$REPO_ROOT/plugins/pipeline/references/routing-policy.json"
schema="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/manifest-schema.md"
promptcraft="$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
cascade="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
model_cascade="$REPO_ROOT/plugins/pipeline/references/model-cascade.json"
harness="$REPO_ROOT/plugins/pipeline/references/harness-profile.json"
runner="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
dm_review="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
assess="$REPO_ROOT/plugins/pipeline/skills/assess/SKILL.md"
research="$REPO_ROOT/plugins/pipeline/skills/research/SKILL.md"
pipeline_cmd="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
postmortem_schema="$REPO_ROOT/plugins/pipeline/references/run-postmortem-schema.md"
ledger="$REPO_ROOT/docs/pipeline-metrics/ledger.md"

[ -f "$routing" ] || { printf "  FAIL  shared routing-policy.json exists\n"; failures=1; }
if [ -f "$routing" ]; then
  jq -e '.chunkKind.config.provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps config chunks to OpenRouter\n"; failures=1; }
  jq -e '.agentType["doc-sync-reviewer"].provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps doc-sync-reviewer to OpenRouter\n"; failures=1; }
  jq -e '.targets.providerSplit.claude <= 50' "$routing" >/dev/null || { printf "  FAIL  routing policy records Claude share target\n"; failures=1; }
fi

require_text "$schema" '"codex" | "claude" | "openrouter"' "manifest schema includes openrouter executor"
require_text "$promptcraft" "routing-policy.json" "promptcraft reads shared routing policy"
require_text "$orchestrator" "MUST NOT implement it in-process" "orchestrator forbids absorbing non-Claude chunks"
require_text "$orchestrator" "implementedBy:" "orchestrator receipts record implementedBy"
require_text "$orchestrator" "providerSplit:" "orchestrator summary records providerSplit"
require_text "$orchestrator" "final review must run on a different provider" "orchestrator enforces cross-provider final review"
require_text "$orchestrator" "Run Post-Mortem" "orchestrator includes run post-mortem step"
require_text "$orchestrator" "Claude JSONL delta" "postmortem measures Claude JSONL delta"
require_text "$orchestrator" "AWAITING APPROVAL" "postmortem recommendations are proposal-only"
require_text "$model_cascade" '"openrouter"' "model cascade defines OpenRouter class"
require_text "$harness" '"openrouter_exec"' "harness profile exposes openrouter_exec rung"
require_text "$cascade" "dispatch_openrouter_exec" "cascade can dispatch OpenRouter exec runner"
require_text "$runner" "implementedBy: openrouter" "OpenRouter exec runner emits implementedBy receipt"
require_text "$runner" "usage" "OpenRouter exec runner preserves usage information"
require_text "$dm_review" "routing-policy.json" "dm-review reads shared routing policy"
require_absent "$dm_review" "Diff >5000 lines AND openrouter" "dm-review no longer gates OpenRouter on >5000 diff lines"
require_text "$dm_review" "OPENROUTER_API_KEY" "dm-review default-routes external reviewers when keys are set"
require_text "$pipeline_cmd" "Codex + OpenRouter" "Phase 5 defaults to Codex plus OpenRouter lenses"
require_text "$pipeline_cmd" "PIPELINE_CLAUDE_ADVERSARY=1" "Claude adversary is optional third lens"
require_text "$assess" "ASSESS_EXECUTOR" "assess supports non-Claude executor knob"
require_text "$research" "RESEARCH_EXECUTOR" "research supports non-Claude executor knob"
require_text "$postmortem_schema" "providerSplit" "run postmortem schema documents providerSplit"
require_text "$ledger" "providerSplit" "rolling metrics ledger exists"

if [ -x "$runner" ]; then
  if "$runner" --dry-run >/dev/null; then
    printf "  OK    OpenRouter exec runner dry-run works\n"
  else
    printf "  FAIL  OpenRouter exec runner dry-run works\n"
    failures=1
  fi
else
  printf "  FAIL  OpenRouter exec runner is executable\n"
  failures=1
fi

if [ "$failures" -ne 0 ]; then
  printf "FIX  add shared routing policy, OpenRouter exec, and run economics contracts\n"
  exit 1
fi

printf "OK    routing and economics contracts documented\n"
