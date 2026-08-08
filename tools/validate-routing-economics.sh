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

require_before() {
  local file="$1"
  local first="$2"
  local second="$3"
  local label="$4"
  local first_line second_line

  first_line="$(grep -nF -m1 -- "$first" "$file" 2>/dev/null | cut -d: -f1 || true)"
  second_line="$(grep -nF -m1 -- "$second" "$file" 2>/dev/null | cut -d: -f1 || true)"
  if [ -n "$first_line" ] && [ -n "$second_line" ] && [ "$first_line" -lt "$second_line" ]; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

decision_leverage_valid() {
  local source="$1"
  jq -e '
    {
      "scope":"workflow-depth-only",
      "allowedLevels":["low","medium","high"],
      "legacyDefault":{
        "planningDepth":"current-standard-path",
        "verificationDepth":"current-standard-path",
        "receiptFlag":"decision_profile_defaulted=true",
        "semanticClaim":"unknown-not-low-low"
      },
      "rules":{
        "lowLow":{
          "when":{"uncertainty":"low","consequence":"low"},
          "planningDepth":"standard",
          "verificationDepth":"standard",
          "optimized":true
        },
        "highUncertainty":{
          "when":{"uncertainty":"high"},
          "planningDepth":"one-independent-opinion-plus-bounded-synthesis",
          "verificationDepth":"standard-unless-high-consequence",
          "optimized":false
        },
        "highConsequence":{
          "when":{"consequence":"high"},
          "planningDepth":"standard-unless-high-uncertainty",
          "verificationDepth":"stronger-existing-independent-seam",
          "optimized":false
        },
        "highHigh":{
          "when":{"uncertainty":"high","consequence":"high"},
          "planningDepth":"one-independent-opinion-plus-bounded-synthesis",
          "verificationDepth":"stronger-existing-independent-seam",
          "optimized":false
        }
      },
      "invariants":[
        "routing-unchanged",
        "safety-gates-unchanged",
        "browser-and-persona-coverage-unchanged",
        "workflow-class-unchanged",
        "cleanup-unchanged",
        "economics-unchanged",
        "no-debate-or-per-chunk-full-review"
      ]
    } as $expected
    | .decisionLeverage as $d
    | ($d == $expected)
      and
      ([$d | paths as $p
        | ($p[-1] | tostring | ascii_downcase)
        | select(test("provider|model|executor|security|routingoverride|sensitivepathexception"))]
       | length == 0)
      and
      ([$d | paths(scalars) as $p | getpath($p)
        | select(type == "string") | ascii_downcase
        | select(test("provider|model|executor|security|routingoverride|sensitivepathexception"))]
       | length == 0)
  ' "$source" >/dev/null 2>&1
}

expect_decision_leverage_reject() {
  local label="$1"
  local filter="$2"
  local mutated

  if ! mutated="$(jq -c "$filter" "$routing")"; then
    printf "  FAIL  decision leverage mutation fixture builds: %s\n" "$label"
    failures=1
  elif printf '%s\n' "$mutated" | decision_leverage_valid -; then
    printf "  FAIL  decision leverage rejects mutation: %s\n" "$label"
    failures=1
  else
    printf "  OK    decision leverage rejects mutation: %s\n" "$label"
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
authorization_contract="$REPO_ROOT/plugins/pipeline/references/openrouter-authorization-contract.md"
runner_policy_test="$REPO_ROOT/tools/test-openrouter-runner-policy.sh"
agent_runner="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
bulk_runner="$REPO_ROOT/plugins/openrouter/agents/review/openrouter-bulk-analyst.md"
delegation_policy="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
wrapper="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
mcp_control="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/mcp-control-plane.md"
dm_review="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
dm_review_cmd="$REPO_ROOT/plugins/dm-review/commands/dm-review.md"
kernel_metrics="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/metrics.py"
kernel_pipeline_adapter="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py"
kernel_translation="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/_translation.py"
assess="$REPO_ROOT/plugins/pipeline/skills/assess/SKILL.md"
research="$REPO_ROOT/plugins/pipeline/skills/research/SKILL.md"
pipeline_cmd="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
postmortem_schema="$REPO_ROOT/plugins/pipeline/references/run-postmortem-schema.md"
ledger="$REPO_ROOT/docs/pipeline-metrics/ledger.md"

[ -f "$routing" ] || { printf "  FAIL  shared routing-policy.json exists\n"; failures=1; }
if [ -f "$routing" ]; then
  jq -e '.chunkKind.config.provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps config chunks to OpenRouter\n"; failures=1; }
  jq -e '.chunkKind.ui.provider == "codex" and .chunkKind.integration.provider == "codex"' "$routing" >/dev/null || { printf "  FAIL  UI and integration coding route to Codex\n"; failures=1; }
  jq -e '
    .agentType["security-auditor-openrouter"] as $external
    | .agentType["security-auditor-codex-signoff"] as $signoff
    | $external.provider == "openrouter"
      and $external.model == "moonshotai/kimi-k3"
      and $external.fallbackProvider == "codex"
      and $signoff == {
        "provider":"codex",
        "required":true,
        "inputScope":"full-diff",
        "rationale":"Independent full-diff security completion is mandatory and cannot be satisfied by the external security lens."
      }
      and .agentType["architecture-reviewer"].provider == "codex"
  ' "$routing" >/dev/null || { printf "  FAIL  external security analysis and independent Codex sign-off have separate lane identities\n"; failures=1; }
  jq -e '.agentType["doc-sync-reviewer"].provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps doc-sync-reviewer to OpenRouter\n"; failures=1; }
  jq -e '
    [
      .agentType["pattern-recognition-specialist"],
      .agentType["code-simplicity-reviewer"],
      .agentType["doc-sync-reviewer"],
      .agentType["test-coverage-reviewer"]
    ]
    | all(. == {
        "provider":"openrouter",
        "model":"openai/gpt-5.6-luna",
        "fallbackModel":"z-ai/glm-5.2",
        "fallbackProvider":"codex",
        "rationale": .rationale
      })
  ' "$routing" >/dev/null || { printf "  FAIL  mechanical reviewers use exact Luna -> GLM-5.2 -> Codex routing\n"; failures=1; }
  jq -e '
    .agentType["openrouter-bulk-analyst"]
    | .provider == "openrouter"
      and .model == "moonshotai/kimi-k3"
      and .fallbackModel == "openai/gpt-5.6-terra"
      and .fallbackProvider == "codex"
  ' "$routing" >/dev/null || { printf "  FAIL  bulk analysis uses exact Kimi K3 -> Terra -> Codex routing\n"; failures=1; }
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
  if decision_leverage_valid "$routing"; then
    printf "  OK    decision leverage is an exact closed depth-only policy\n"
  else
    printf "  FAIL  decision leverage is an exact closed depth-only policy\n"
    failures=1
  fi
  expect_decision_leverage_reject "highUncertainty selector" '.decisionLeverage.rules.highUncertainty.when = {"uncertainty":"medium"}'
  expect_decision_leverage_reject "highConsequence selector" '.decisionLeverage.rules.highConsequence.when = {"consequence":"medium"}'
  expect_decision_leverage_reject "highHigh selectors" '.decisionLeverage.rules.highHigh.when = {"uncertainty":"high","consequence":"medium"}'
  expect_decision_leverage_reject "extra rule" '.decisionLeverage.rules.unbounded = .decisionLeverage.rules.lowLow'
  expect_decision_leverage_reject "routingOverride authority" '.decisionLeverage.routingOverride = {"reason":"test"}'
  expect_decision_leverage_reject "sensitivePathException authority" '.decisionLeverage.sensitivePathException = true'
  expect_decision_leverage_reject "provider authority" '.decisionLeverage.rules.lowLow.provider = "codex"'
  expect_decision_leverage_reject "model authority" '.decisionLeverage.rules.lowLow.model = "test-model"'
  expect_decision_leverage_reject "executor authority" '.decisionLeverage.rules.lowLow.executor = "codex"'
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
require_text "$kernel_pipeline_adapter" '"decision_profile", "decisionProfile"' "kernel adapter reads the closed decision profile"
require_text "$kernel_translation" '"decision_profile", "decision_profile_defaulted"' "kernel RunSpec and receipts preserve decision profile provenance"
require_text "$kernel_metrics" 'decision_profiles' "kernel metrics expose decision profile observations"
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
require_text "$orchestrator" 'decide-validation-retry --state-dir .workflow-kernel/runs/<run-id> --reason deterministic_validation_failure' "orchestrator delegates retry policy to authoritative kernel run state"
require_text "$orchestrator" 'reason_code: deterministic_validation_failure' "orchestrator projects the exact ValidationFeedback reason"
require_text "$orchestrator" 'builder_session_continuity' "orchestrator records strict builder continuity"
require_text "$orchestrator" 'replacement_adapter_dispatch_failed' "orchestrator preserves replacement-dispatch failure reasons"
require_text "$orchestrator" '"failing_check_ids":' "orchestrator uses the canonical failing-check field"
require_absent "$orchestrator" '"ordered_failing_check_ids":' "orchestrator rejects the non-canonical failing-check field"
require_text "$orchestrator" '"fallback": true' "orchestrator feedback fallback is boolean"
require_absent "$orchestrator" '"fallback": "openrouter->codex"' "orchestrator feedback never encodes fallback as a transition string"
require_text "$orchestrator" 'stage: browser_recovery' "browser recovery remains a separate blocked receipt"
require_before "$orchestrator" 'bind-verification-contract --state-dir' '### 3d: Dispatch Implementation Subagent' "contract evidence precedes implementation dispatch"
require_text "$orchestrator" "final review must run on the provider that did not implement" "orchestrator enforces cross-provider final review"
require_text "$orchestrator" "Run Post-Mortem" "orchestrator includes run post-mortem step"
require_text "$orchestrator" "Claude JSONL delta" "postmortem measures Claude JSONL delta"
require_text "$orchestrator" "AWAITING APPROVAL" "postmortem recommendations are proposal-only"
require_text "$model_cascade" '"openrouter"' "model cascade defines OpenRouter class"
if [ -f "$model_cascade" ] && [ -f "$harness" ]; then
  # 2026-08-08 user directive: native_judgment is an executable LAST-RESORT coding rung.
  # Claude must still never be a cascade class of its own, and where the native rung is
  # present it must rank below premium_sub and openrouter_exec so both external rails are
  # tried first. This replaces the former absolute exclusion.
  jq -e '.cascades | has("claude") | not' "$model_cascade" >/dev/null || { printf "  FAIL  no Claude-native cascade class\n"; failures=1; }
  jq -e '
    [.cascades[]
      | .ladder as $l
      | select($l | index("native_judgment"))
      | ($l | index("native_judgment")) as $n
      | (($l | index("premium_sub")) // -1) as $p
      | (($l | index("openrouter_exec")) // -1) as $o
      | ($n > $p and $n > $o)]
    | all
  ' "$model_cascade" >/dev/null || { printf "  FAIL  native_judgment ranks below premium_sub and openrouter_exec in every cascade\n"; failures=1; }
  jq -e '
    [.hosts[].roles | to_entries[]
      | select(.value.kind == "wrapper" or .value.kind == "openrouter_exec")
      | .value.models[]?
      | select(test("^(openai|anthropic)/") or test("^gpt-") or test("^(opus|sonnet|haiku)$"))]
    | length == 0
  ' "$harness" >/dev/null || { printf "  FAIL  every OpenRouter rail excludes native-vendor primary and fallback identities\n"; failures=1; }
  jq -e '
    [.quality_rank | keys[] | select(test("^(openai|anthropic)/"))] | length == 0
  ' "$model_cascade" >/dev/null || { printf "  FAIL  model cascade excludes OpenRouter-prefixed native-vendor identities\n"; failures=1; }
  # Generic (non-Claude, non-Codex) harnesses still have NO native vendor rail: the native
  # rung must resolve to "none" there rather than being silently mapped onto OpenRouter.
  if ! jq -e '.hosts.generic.roles.native_judgment.kind == "none"' "$harness" >/dev/null; then
    printf "  FAIL  generic/native-vendor intent is unavailable rather than mapped to OpenRouter\n"
    failures=1
  fi
fi
# Note: the harness openrouter_exec rung and cascade dispatch are covered functionally by
# validate-openrouter-cascade.sh (dry-run descent test); not re-grepped here to avoid double-reporting.

# Cross-file SSOT: for every kind present in both files, routing-policy cascadeClass must equal
# model-cascade class_from_kind, so the shared kind->class mapping cannot silently drift.
if [ -f "$routing" ] && [ -f "$model_cascade" ]; then
  jq -e '
    .invariants.providerOrigin == {
      "schemaVersion":1,
      "openrouterForbiddenModelPrefixes":["anthropic/"],
      "nativeOpenAIExecution":"codex-cli-preferred-or-openrouter-api",
      "nativeAnthropicExecution":"claude-cli-only",
      "genericNativeVendorFallback":"unavailable",
      "appliesTo":["primary","fallback"],
      "failureMode":"fail-closed-before-provider-contact",
      "rationale":"Provider origin is receipted explicitly. OpenAI and third-party OpenRouter models remain eligible after disclosure and output controls; Anthropic remains native-only."
    }
  ' "$routing" >/dev/null || { printf "  FAIL  routing policy provider-origin invariant is missing or malformed\n"; failures=1; }
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

require_text "$runner" 'implementedBy:"openrouter"' "OpenRouter exec runner emits implementedBy receipt"
require_text "$runner" "usage" "OpenRouter exec runner preserves usage information"
require_text "$runner" "generationId" "OpenRouter exec runner preserves the provider generation ID"
require_text "$runner" 'FALLBACK_MODEL="${OPENROUTER_EXEC_FALLBACK_MODEL:-}"' "OpenRouter exec leaves cascade fallback ownership to its caller"
require_absent "$runner" 'grep -Fq "falling back to' "OpenRouter exec reads fallback provenance from the wrapper receipt"
require_text "$cascade" 'dispatch_wrapper "$model"; rc=$?' "pipeline cascade invokes wrapper without swallowing terminal evidence"
require_absent "$cascade" 'out="$(dispatch_wrapper "$model")"' "pipeline cascade does not hide wrapper terminal receipts in command substitution"
require_absent "$cascade" 'dispatch_wrapper "$model" "$fb"' "pipeline cascade does not retry the same model through two fallback owners"
require_text "$cascade" 'dispatch-provider-request' "pipeline wrapper rungs use broker-owned byte-bound dispatch"
require_text "$authorization_contract" 'exact request-body digest' "pipeline wrapper terminal receipts retain exact byte binding"
require_text "$wrapper" "OPENROUTER_WORKLOAD" "OpenRouter wrapper accepts workload-aware provider routing"
require_text "$wrapper" "direct|bulk|mechanical)" "direct, bulk, and mechanical work share throughput routing"
require_text "$wrapper" "quality|security)" "quality and security work retain quality-first routing"
require_text "$wrapper" 'TIMEOUT="${3:-${OPENROUTER_OVERALL_TIMEOUT:-3600}}"' "OpenRouter wrapper defaults each generation to a one-hour completion budget"
require_text "$wrapper" 'FIRST_BYTE_TIMEOUT="${OPENROUTER_FIRST_BYTE_TIMEOUT:-600}"' "OpenRouter wrapper allows ten minutes for first response bytes"
require_text "$wrapper" 'IDLE_TIMEOUT="${OPENROUTER_IDLE_TIMEOUT:-600}"' "OpenRouter wrapper allows ten minutes between stream progress"
require_text "$runner" 'TIMEOUT="${OPENROUTER_EXEC_TIMEOUT:-3600}"' "Pipeline OpenRouter execution inherits the one-hour completion budget"
require_text "$cascade" 'text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")' "pipeline cascade freezes JSON line-separator escaping"
require_text "$runner" 'text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")' "OpenRouter exec freezes JSON line-separator escaping"
require_text "$dm_review" '| `security-auditor-openrouter` | `moonshotai/kimi-k3` | `z-ai/glm-5.2` | 3600s |' "dm-review security analysis receives a one-hour completion budget"
require_text "$dm_review" '7200s at or above 10K diff lines' "dm-review bulk analysis scales to a two-hour completion budget"
require_absent "$cascade" 'OPENROUTER_PAYLOAD_AUTHORIZATION' "pipeline cascade does not trust environment disclosure authority"
require_text "$authorization_contract" '`70`, `71`, and `72` are unsigned pre-network outcomes' "pipeline preserves only proven pre-contact fallback"
require_text "$cascade" 'exit 76' "pipeline distinguishes ladder exhaustion from provider-terminal exit 75"
require_text "$orchestrator" 'Provider Terminal Persistence (RC 75)' "orchestrator consumes provider-terminal outcomes without retry"
require_text "$orchestrator" 'append the exact unmodified' "orchestrator preserves the signed terminal receipt as evidence"
require_text "$orchestrator" 'Record `result_verification_failed`' "orchestrator records unsigned post-dial failure without a receipt"
require_text "$runner_policy_test" '"$(cat "$AUTH_ROOT/request-count")" -eq 1' "terminal fixtures assert at most one provider invocation"
require_text "$runner_policy_test" '.outcome == "provider_failure" and .response_length == 0' "terminal fixtures assert signed receipt preservation"
require_text "$wrapper" "OPENROUTER_RECEIPT_FILE" "OpenRouter wrapper emits content-free provider receipts"
require_text "$wrapper" "servingProviderProvenance" "OpenRouter wrapper distinguishes absent provider identity from verified provenance"
require_text "$wrapper" "response omitted required generation provenance" "OpenRouter wrapper fails closed when model provenance is absent"
require_text "$mcp_control" "direct API runner remains authoritative" "MCP remains a control plane rather than the execution transport"
require_text "$mcp_control" "does not expose an authenticated workspace" "MCP workspace attribution gap is explicit"
require_text "$mcp_control" "observedAt" "MCP catalog freshness has a bounded observation contract"
require_text "$dm_review" "routing-policy.json" "dm-review reads shared routing policy"
require_absent "$dm_review" "Diff >5000 lines AND openrouter" "dm-review no longer gates OpenRouter on >5000 diff lines"
require_text "$dm_review" "OPENROUTER_API_KEY" "dm-review observes API-key presence without treating it as authority"
require_text "$dm_review" "OPENROUTER_AVAILABLE=false" "dm-review currently routes automated external criteria to Codex"
require_text "$dm_review" "OPENROUTER_UNAVAILABLE_REASON=host_authority_unavailable" "dm-review records the host-authority gap"
require_text "$dm_review" "OPENROUTER_SECURITY_POLICY_PATH" "dm-review resolves the installed OpenRouter security policy"
require_absent "$dm_review" "DEEPSEEK_API_KEY" "dm-review has no standalone DeepSeek credential path"
require_absent "$dm_review" '**A0. If the agent is `openrouter-bulk-analyst`:**' "dm-review does not duplicate bulk wrapper orchestration"
require_text "$dm_review" 'review criteria only; the generic runner is the single boundary,' "dm-review routes bulk criteria through the generic runner"
require_text "$dm_review" 'a Claude `Agent` call is not a valid Branch A launcher' "dm-review keeps generic OpenRouter review off Claude execution"
require_text "$dm_review" '--mode mechanical-review' "dm-review delegates the safe remainder of mixed diffs"
require_text "$dm_review_cmd" "contribution receipts" "dm-review exposes finding contribution receipts"
require_text "$dm_review_cmd" "observation-only economics evidence" "contributions cannot become routing authority"
require_text "$kernel_metrics" '"observation_only": True' "kernel economics output is observation-only"
require_text "$agent_runner" 'File names, security-looking directories' "OpenRouter runner forbids path-name disclosure classification"
require_text "$agent_runner" "RUNNER DECLINED -- SENSITIVE CONTENT" "OpenRouter runner declines high-confidence secrets in added lines"
require_text "$agent_runner" "Generation receipt:" "OpenRouter review lanes preserve generation provenance"
require_absent "$bulk_runner" 'resolve-plugin-bundle' "bulk analyst does not duplicate coherent bundle resolution"
require_absent "$bulk_runner" 'openrouter-wrapper.sh' "bulk analyst does not invoke the wrapper independently"
require_text "$bulk_runner" 'generic `openrouter-agent-runner` is the only execution path' "bulk analyst delegates all execution controls to the generic runner"
require_text "$agent_runner" "Codex" "OpenRouter runner returns sensitive work to Codex"
require_text "$agent_runner" "payload-authorization.sh" "OpenRouter runner binds user approval to exact payload bytes"
require_text "$pipeline_cmd" "Codex is the required adversarial reviewer" "Phase 5 requires the Codex adversarial lens"
require_text "$pipeline_cmd" "openrouter-perspective: host_authority_unavailable" "Phase 5 records unavailable automated OpenRouter coverage"
require_text "$pipeline_cmd" "PIPELINE_CLAUDE_ADVERSARY=1" "Claude adversary is optional third lens"
require_absent "$pipeline_cmd" '--mode artifact-delegation' "Phase 5 does not prepare automated provider payloads"
require_text "$pipeline_cmd" 'openrouter-authorization-contract.md' "Phase 5 reads the shared fail-closed authorization contract"
require_text "$assess" 'Ignore an `openrouter`' "assess rejects caller-selected OpenRouter execution"
require_text "$research" 'Ignore an `openrouter`' "research rejects caller-selected OpenRouter execution"
require_text "$postmortem_schema" "providerSplit" "run postmortem schema documents providerSplit"
require_text "$postmortem_schema" "eligibleProviderSplit" "run postmortem schema separates eligible provider usage"
require_text "$postmortem_schema" "routingExclusions" "run postmortem schema records security and tool exclusions"
require_text "$postmortem_schema" "routingVariance" "run postmortem schema explains target variance"
require_text "$ledger" "providerSplit" "rolling metrics ledger exists"
require_text "$ledger" "eligibleProviderSplit" "rolling ledger tracks eligible OpenRouter utilization"

if grep -R -n 'send-message' "$REPO_ROOT/plugins/dm-review" "$REPO_ROOT/plugins/pipeline" >/dev/null; then
  printf "  FAIL  automated review/pipeline paths must not invoke MCP send-message\n"
  failures=1
else
  printf "  OK    automated review/pipeline paths keep MCP control-plane access read-only\n"
fi

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
