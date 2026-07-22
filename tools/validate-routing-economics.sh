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

  if grep -Fq -- "$pattern" "$file"; then
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

  if grep -Fq -- "$pattern" "$file"; then
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
agent_runner="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
delegation_policy="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
dm_review="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
assess="$REPO_ROOT/plugins/pipeline/skills/assess/SKILL.md"
research="$REPO_ROOT/plugins/pipeline/skills/research/SKILL.md"
pipeline_cmd="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
postmortem_schema="$REPO_ROOT/plugins/pipeline/references/run-postmortem-schema.md"
ledger="$REPO_ROOT/docs/pipeline-metrics/ledger.md"

[ -f "$routing" ] || { printf "  FAIL  shared routing-policy.json exists\n"; failures=1; }
if [ -f "$routing" ]; then
  jq -e '.chunkKind.config.provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps config chunks to OpenRouter\n"; failures=1; }
  jq -e '.chunkKind.ui.provider == "codex" and .chunkKind.integration.provider == "codex"' "$routing" >/dev/null || { printf "  FAIL  UI and integration coding route to Codex\n"; failures=1; }
  jq -e '.agentType["security-auditor"].provider == "codex" and .agentType["architecture-reviewer"].provider == "codex"' "$routing" >/dev/null || { printf "  FAIL  security and architecture code review route to Codex\n"; failures=1; }
  jq -e '.agentType["doc-sync-reviewer"].provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps doc-sync-reviewer to OpenRouter\n"; failures=1; }
  jq -e '[.agentType["pattern-recognition-specialist"], .agentType["code-simplicity-reviewer"], .agentType["doc-sync-reviewer"], .agentType["test-coverage-reviewer"]] | all(.provider == "openrouter")' "$routing" >/dev/null || { printf "  FAIL  all mechanical reviewers route through OpenRouter\n"; failures=1; }
  jq -e '
    .targets as $targets
    | ($targets.subscriptionProfiles[$targets.activeSubscriptionProfile]) as $active
    | ($active | type) == "object"
      and ($active | keys | sort) == ["claude", "codex", "openrouter"]
      and (($active.claude + $active.codex + $active.openrouter) == 100)
      and ([ $targets.subscriptionProfiles[] | (.claude + .codex + .openrouter) == 100 ] | all)
      and ($targets.activeSubscriptionProfile == "codex-20x")
      and ($targets.subscriptionProfiles["codex-20x"] == {"codex":65,"claude":0,"openrouter":35})
      and ($targets.subscriptionProfiles["codex-5x"] == {"codex":40,"claude":0,"openrouter":60})
      and ([ $targets.subscriptionProfiles[] | .claude == 0 ] | all)
      and ($targets.enforcement.scope == "eligible-chunks-per-run")
      and ($targets.enforcement.strategy == "deficit-round-robin")
      and ($targets.enforcement.flexibleBuckets == ["config","docs","mechanical-logic"])
      and ($targets.enforcement.fixedBuckets == ["logic","ui","integration"])
      and ($targets.enforcement.securityOverridesTarget == true)
      and ($targets.enforcement.toolCapabilityOverridesTarget == true)
      and ($targets.enforcement.varianceReceiptRequired == true)
      and ($targets.providerSplit == null)
  ' "$routing" >/dev/null || { printf "  FAIL  active subscription profile is the sole valid 100%% routing target\n"; failures=1; }
  jq -e '[.agentType[] | select(.fallbackProvider? != null) | .fallbackProvider == "codex"] | all' "$routing" >/dev/null || { printf "  FAIL  coding reviewer fallbacks return to Codex\n"; failures=1; }
  jq -e '
    .decisionLeverage as $d
    | ($d | type) == "object"
      and $d.scope == "workflow-depth-only"
      and $d.allowedLevels == ["low","medium","high"]
      and $d.legacyDefault == {
        "planningDepth":"current-standard-path",
        "verificationDepth":"current-standard-path",
        "receiptFlag":"decision_profile_defaulted=true",
        "semanticClaim":"unknown-not-low-low"
      }
      and $d.rules.lowLow == {
        "when":{"uncertainty":"low","consequence":"low"},
        "planningDepth":"standard",
        "verificationDepth":"standard",
        "optimized":true
      }
      and $d.rules.highUncertainty.planningDepth == "one-independent-opinion-plus-bounded-synthesis"
      and $d.rules.highUncertainty.verificationDepth == "standard-unless-high-consequence"
      and $d.rules.highConsequence.planningDepth == "standard-unless-high-uncertainty"
      and $d.rules.highConsequence.verificationDepth == "stronger-existing-independent-seam"
      and $d.rules.highHigh.planningDepth == "one-independent-opinion-plus-bounded-synthesis"
      and $d.rules.highHigh.verificationDepth == "stronger-existing-independent-seam"
      and ($d.rules | [.[] | .optimized] | any) == true
      and ($d.rules | [.[] | select(.when.uncertainty == "high") | .planningDepth == "one-independent-opinion-plus-bounded-synthesis"] | all)
      and ($d.rules | [.[] | select(.when.consequence == "high") | .verificationDepth == "stronger-existing-independent-seam"] | all)
  ' "$routing" >/dev/null || { printf "  FAIL  decision leverage has the exact depth-only mapping and legacy provenance\n"; failures=1; }
  jq -e '
    .decisionLeverage as $d
    | ([$d | paths as $p
        | ($p[-1] | tostring | ascii_downcase)
        | select(test("provider|model|executor|security"))] | length == 0)
      and
      ([$d | paths(scalars) as $p | getpath($p)
        | select(type == "string") | ascii_downcase
        | select(test("provider|model|executor|security"))] | length == 0)
  ' "$routing" >/dev/null || { printf "  FAIL  decision leverage contains no routing or security-control keys\n"; failures=1; }
fi

if [ -f "$routing" ] && [ -f "$delegation_policy" ]; then
  pipeline_security="$(jq -S -c '.security | del(._comment, .delegationSecurityPolicy)' "$routing")"
  openrouter_security="$(jq -S -c 'del(.schemaVersion)' "$delegation_policy")"
  if [ "$pipeline_security" = "$openrouter_security" ]; then
    printf "  OK    pipeline security mirror matches OpenRouter-owned delegation policy\n"
  else
    printf "  FAIL  pipeline security mirror drifted from OpenRouter-owned delegation policy\n"
    failures=1
  fi
else
  printf "  FAIL  OpenRouter delegation security policy exists\n"
  failures=1
fi

require_text "$schema" '`"openrouter"`' "manifest schema includes openrouter executor"
require_text "$schema" '| `integration` | `codex` |' "manifest schema maps integration to Codex"
require_text "$schema" "routingOverride" "manifest schema defines explicit routing overrides"
require_text "$schema" "splitAttempted" "manifest override records whether offline work was split"
require_text "$schema" '`decisionProfile`' "manifest schema requires an approved decision profile"
require_text "$schema" '`decision_profile_defaulted=true`' "manifest schema preserves legacy profile provenance"
require_text "$promptcraft" "routing-policy.json" "promptcraft reads shared routing policy"
require_text "$promptcraft" '`integration` -> `codex`' "promptcraft maps integration to Codex"
require_text "$promptcraft" "routingOverride" "promptcraft requires explicit executor override receipts"
require_text "$promptcraft" "splitAttempted" "promptcraft splits tool-dependent and offline work first"
require_text "$promptcraft" "one independent" "promptcraft bounds high-uncertainty planning depth"
require_text "$promptcraft" "decision_profile_defaulted=true" "promptcraft documents legacy standard-depth provenance"
require_text "$orchestrator" "MUST NOT implement it in-process" "orchestrator forbids absorbing externally routed chunks"
require_text "$orchestrator" 'integration) PRIMARY_RAIL="codex"' "orchestrator fallback maps integration to Codex"
require_text "$orchestrator" "implementedBy:" "orchestrator receipts record implementedBy"
require_text "$orchestrator" "providerSplit:" "orchestrator summary records providerSplit"
require_text "$orchestrator" "eligibleProviderSplit:" "orchestrator records eligible provider usage"
require_text "$orchestrator" "deficit-round-robin" "orchestrator applies routing pressure during dispatch"
require_text "$orchestrator" "routingOverride" "orchestrator rejects silent executor overrides"
require_text "$orchestrator" 'decide-validation-retry --reason deterministic_validation_failure' "orchestrator delegates retry policy to the kernel CLI"
require_text "$orchestrator" 'reason_code: deterministic_validation_failure' "orchestrator projects the exact ValidationFeedback reason"
require_text "$orchestrator" 'builder_session_continuity' "orchestrator records strict builder continuity"
require_text "$orchestrator" 'stage: browser_recovery' "browser recovery remains a separate blocked receipt"
require_text "$orchestrator" "final review must run on the provider that did not implement" "orchestrator enforces cross-provider final review"
require_text "$orchestrator" "Run Post-Mortem" "orchestrator includes run post-mortem step"
require_text "$orchestrator" "Claude JSONL delta" "postmortem measures Claude JSONL delta"
require_text "$orchestrator" "AWAITING APPROVAL" "postmortem recommendations are proposal-only"
require_text "$model_cascade" '"openrouter"' "model cascade defines OpenRouter class"
if [ -f "$model_cascade" ] && [ -f "$harness" ]; then
  jq -e '(.cascades | has("claude") | not) and ([.cascades[].ladder[]] | index("native_judgment") | not)' "$model_cascade" >/dev/null || { printf "  FAIL  coding cascades exclude Claude-native ladders\n"; failures=1; }
  jq -e '[.hosts[].roles.frontier_api.models[]? | startswith("anthropic/")] | any | not' "$harness" >/dev/null || { printf "  FAIL  OpenRouter coding ladders exclude Anthropic models\n"; failures=1; }
fi
# Note: the harness openrouter_exec rung and cascade dispatch are covered functionally by
# validate-openrouter-cascade.sh (dry-run descent test); not re-grepped here to avoid double-reporting.

# Cross-file SSOT: for every kind present in both files, routing-policy cascadeClass must equal
# model-cascade class_from_kind, so the shared kind->class mapping cannot silently drift.
if [ -f "$routing" ] && [ -f "$model_cascade" ]; then
  drift="$(jq -rs '
    (.[0].chunkKind) as $ck | (.[1].class_from_kind) as $cfk
    | [ $ck | to_entries[]
        | select(($cfk[.key] != null) and (.value | type == "object") and (.value.cascadeClass != $cfk[.key]))
        | .key ]
    | join(",")
  ' "$routing" "$model_cascade")"
  if [ -z "$drift" ]; then
    printf "  OK    routing-policy cascadeClass matches model-cascade class_from_kind\n"
  else
    printf "  FAIL  routing-policy/model-cascade class drift for kinds: %s\n" "$drift"
    failures=1
  fi
fi

require_text "$runner" "implementedBy: openrouter" "OpenRouter exec runner emits implementedBy receipt"
require_text "$runner" "usage" "OpenRouter exec runner preserves usage information"
require_text "$dm_review" "routing-policy.json" "dm-review reads shared routing policy"
require_absent "$dm_review" "Diff >5000 lines AND openrouter" "dm-review no longer gates OpenRouter on >5000 diff lines"
require_text "$dm_review" "OPENROUTER_API_KEY" "dm-review default-routes external reviewers when keys are set"
require_text "$dm_review" "OPENROUTER_SECURITY_POLICY_PATH" "dm-review resolves the installed OpenRouter security policy"
require_absent "$dm_review" "DEEPSEEK_API_KEY" "dm-review has no standalone DeepSeek credential path"
require_text "$dm_review" '**A0. If the agent is `openrouter-bulk-analyst`:**' "dm-review special-cases the bulk wrapper agent"
require_text "$dm_review" "Never launch this coding-review lane through a Claude" "dm-review keeps bulk review off Claude execution"
require_text "$dm_review" 'a Claude `Agent` call is not a valid Branch A launcher' "dm-review keeps generic OpenRouter review off Claude execution"
require_text "$dm_review" '--mode mechanical-review' "dm-review delegates the safe remainder of mixed diffs"
require_text "$agent_runner" 'set(canon) | set(configured)' "OpenRouter runner cannot weaken the minimum path denylist"
require_text "$agent_runner" "RUNNER DECLINED -- SENSITIVE CONTENT" "OpenRouter runner declines high-confidence secrets in added lines"
require_text "$agent_runner" 'neverRouteToOpenRouter' "OpenRouter runner reads the Codex-return security boundary"
require_text "$agent_runner" "Codex" "OpenRouter runner returns sensitive work to Codex"
require_text "$pipeline_cmd" "Codex + OpenRouter" "Phase 5 defaults to Codex plus OpenRouter lenses"
require_text "$pipeline_cmd" "PIPELINE_CLAUDE_ADVERSARY=1" "Claude adversary is optional third lens"
require_text "$pipeline_cmd" '--mode artifact-review' "Phase 5 allows safe sensitive-path references in review artifacts"
require_text "$assess" "ASSESS_EXECUTOR" "assess supports non-Claude executor knob"
require_text "$research" "RESEARCH_EXECUTOR" "research supports non-Claude executor knob"
require_text "$postmortem_schema" "providerSplit" "run postmortem schema documents providerSplit"
require_text "$postmortem_schema" "eligibleProviderSplit" "run postmortem schema separates eligible provider usage"
require_text "$postmortem_schema" "routingExclusions" "run postmortem schema records security and tool exclusions"
require_text "$postmortem_schema" "routingVariance" "run postmortem schema explains target variance"
require_text "$ledger" "providerSplit" "rolling metrics ledger exists"
require_text "$ledger" "eligibleProviderSplit" "rolling ledger tracks eligible OpenRouter utilization"

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
