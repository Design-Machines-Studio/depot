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

routine_review_routes_valid() {
  local source="$1"
  jq -e '
    .agentType as $a
    | $a["pattern-recognition-specialist"]
    | .provider == "openrouter"
      and .model == "deepseek/deepseek-v4-pro-0813"
      and .fallbackModel == "qwen/qwen3.8-max"
      and .fallbackProvider == "codex"
      and ($a["code-simplicity-reviewer"]
        | .provider == "openrouter"
          and .model == "qwen/qwen3.8-max"
          and .fallbackModel == "deepseek/deepseek-v4-pro-0813"
          and .fallbackProvider == "codex")
      and ($a["doc-sync-reviewer"]
        | .provider == "openrouter"
          and .model == "deepseek/deepseek-v4-flash-0731"
          and .fallbackModel == "openai/gpt-5.6-luna"
          and .fallbackProvider == "codex")
      and ($a["test-coverage-reviewer"]
        | .provider == "openrouter"
          and .model == "deepseek/deepseek-v4-flash-0731"
          and .fallbackModel == "openai/gpt-5.6-luna"
          and .fallbackProvider == "codex")
  ' "$source" >/dev/null 2>&1
}

expect_routine_review_route_reject() {
  local label="$1"
  local filter="$2"
  local mutated

  if ! mutated="$(jq -c "$filter" "$routing")"; then
    printf "  FAIL  routine review mutation fixture builds: %s\n" "$label"
    failures=1
  elif printf '%s\n' "$mutated" | routine_review_routes_valid -; then
    printf "  FAIL  routine review routes reject mutation: %s\n" "$label"
    failures=1
  else
    printf "  OK    routine review routes reject mutation: %s\n" "$label"
  fi
}

routing="$REPO_ROOT/plugins/pipeline/references/routing-policy.json"
schema="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/manifest-schema.md"
promptcraft="$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
planning_html_fixture="$REPO_ROOT/tests/fixtures/routing/planning-html-docs.json"
served_html_fixture="$REPO_ROOT/tests/fixtures/routing/served-html-ui.json"
cascade="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
usage_probe="$REPO_ROOT/plugins/pipeline/references/usage-probe.sh"
usage_probe_fixture="$REPO_ROOT/tools/run-usage-probe-fixture.sh"
model_cascade="$REPO_ROOT/plugins/pipeline/references/model-cascade.json"
harness="$REPO_ROOT/plugins/pipeline/references/harness-profile.json"
runner="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
authorization_contract="$REPO_ROOT/plugins/pipeline/references/openrouter-authorization-contract.md"
runner_policy_test="$REPO_ROOT/tools/test-openrouter-runner-policy.sh"
noninteractive_test="$REPO_ROOT/tests/test_openrouter_noninteractive.py"
agent_runner="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
bulk_runner="$REPO_ROOT/plugins/openrouter/agents/review/openrouter-bulk-analyst.md"
delegation_policy="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
wrapper="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
mcp_control="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/mcp-control-plane.md"
dm_review="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
dm_review_cmd="$REPO_ROOT/plugins/dm-review/commands/dm-review.md"
model_selection="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-selection.md"
kernel_metrics="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/metrics.py"
kernel_pipeline_adapter="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py"
kernel_translation="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/_translation.py"
assess="$REPO_ROOT/plugins/pipeline/skills/assess/SKILL.md"
research="$REPO_ROOT/plugins/pipeline/skills/research/SKILL.md"
efficiency_plan="$REPO_ROOT/plans/depot-efficiency-program.md"
pipeline_cmd="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
postmortem_schema="$REPO_ROOT/plugins/pipeline/references/run-postmortem-schema.md"
ledger="$REPO_ROOT/docs/pipeline-metrics/ledger.md"

classify_fixture_kind() {
  local fixture="$1"
  local derived="config"
  local path
  while IFS= read -r path; do
    case "$path" in
      plans/*.html) ;;
      *.templ|*.twig|*.html|*.css|pages/*|*/pages/*|templates/*|*/templates/*|views/*|*/views/*)
        derived="ui"
        break
        ;;
      *.go|*.py|*.ts|*.php)
        derived="logic"
        ;;
    esac
  done < <(jq -r '.filesToModify[]' "$fixture")
  printf '%s\n' "$derived"
}

require_text "$usage_probe" 'select($data.total_credits | type == "number")' "OpenRouter probe requires numeric total credits"
require_text "$usage_probe" 'select($data.total_usage | type == "number")' "OpenRouter probe requires numeric total usage"
require_absent "$usage_probe" 'ccusage blocks --json' "Claude probe removes the incomplete ccusage fallback"
require_absent "$usage_probe" 'suppresses the ccusage fallback' "Claude probe removes stale ccusage control-flow prose"
require_text "$usage_probe" '.windowDurationMins == 10080' "Codex probe recognizes only the expected weekly duration"
require_absent "$usage_probe" 'USAGE_PROBE_TEST_MODE' "production usage probe has no fixture-mode switch"
require_absent "$usage_probe" 'USAGE_PROBE_CODEX_APP_SERVER_JSON' "production usage probe has no Codex fixture input"
require_absent "$usage_probe" 'USAGE_PROBE_CLAUDE_STATUSLINE_JSON' "production usage probe has no inline Claude fixture input"
require_absent "$usage_probe" 'USAGE_PROBE_CLAUDE_STATUSLINE_FILE' "production usage probe has no file-based Claude fixture input"
require_absent "$usage_probe" 'USAGE_PROBE_CLAUDE_STATUSLINE_STDIN' "production usage probe has no stdin Claude fixture input"
require_absent "$usage_probe" 'DM_OPERATOR_PROFILE_FILE' "production usage probe has no environment-selected profile path"
require_absent "$usage_probe" 'TEST FIXTURE MODE' "production usage probe has no fixture branch"
require_text "$usage_probe_fixture" 'FIXTURE-ONLY EVIDENCE; NOT LIVE CAPACITY' \
  "test wrapper conspicuously marks fixture-only execution"
require_text "$usage_probe_fixture" 'bash "$USAGE_PROBE"' \
  "test wrapper invokes the production usage probe"

codex_expected_windows='{"id":7,"result":{"rateLimits":{"primary":{"usedPercent":10,"windowDurationMins":300},"secondary":{"usedPercent":20,"windowDurationMins":10080}}}}'
codex_expected_result="$(printf '%s\n' "$codex_expected_windows" \
  | bash "$usage_probe_fixture")"
if printf '%s' "$codex_expected_result" | jq -e '
  .probe_source == "fixture"
    and .codex.state == "ok"
    and .codex.window == "weekly"
    and .codex.windows.five_hour.remaining_pct == 90
    and .codex.windows.weekly.remaining_pct == 80
' >/dev/null; then
  printf "  OK    Codex probe maps 300 and 10080 minute windows behaviorally\n"
else
  printf "  FAIL  Codex probe maps 300 and 10080 minute windows behaviorally\n"
  failures=1
fi

profile_fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/routing-profile-symlink.XXXXXX")"
trap 'rm -rf "$profile_fixture_root"' EXIT
mkdir -p "$profile_fixture_root/repository/config"
ln -s config "$profile_fixture_root/repository/.dm"
cat > "$profile_fixture_root/repository/config/operator-profile.local.json" <<'JSON'
{"operator":"fixture","updated":"2026-08-10","familyPreferenceOrder":[],"neverUse":[],"subscriptions":[{"rail":"escape","probe":["/usr/bin/printf","{\"state\":\"ok\",\"remaining_pct\":99,\"window\":\"weekly\"}"],"windows":["weekly"]}]}
JSON
(
  cd "$profile_fixture_root/repository"
  git init -q
  # Track only the redirecting parent. The destination profile must stay
  # untracked so the ordinary tracked-file guard cannot hide a regression in
  # the physical-parent check this fixture isolates.
  git add .dm
)
profile_symlink_result="$(cd "$profile_fixture_root/repository" && \
  OPENROUTER_API_KEY='' bash "$usage_probe")"
if printf '%s' "$profile_symlink_result" | jq -e 'has("escape") | not' >/dev/null; then
  printf "  OK    tracked symlinked operator-profile parents are refused\n"
else
  printf "  FAIL  tracked symlinked operator-profile parents are refused\n"
  failures=1
fi

mkdir -p "$profile_fixture_root/tracked/.dm"
cat > "$profile_fixture_root/tracked/.dm/operator-profile.local.json" <<'JSON'
{"operator":"fixture","updated":"2026-08-10","familyPreferenceOrder":[],"neverUse":[],"subscriptions":[{"rail":"tracked","probe":["/usr/bin/printf","{\"state\":\"ok\",\"remaining_pct\":99,\"window\":\"weekly\"}"],"windows":["weekly"]}]}
JSON
(
  cd "$profile_fixture_root/tracked"
  git init -q
  git add .dm/operator-profile.local.json
)
profile_tracked_result="$(cd "$profile_fixture_root/tracked" && \
  OPENROUTER_API_KEY='' bash "$usage_probe")"
if printf '%s' "$profile_tracked_result" | jq -e 'has("tracked") | not' >/dev/null; then
  printf "  OK    tracked operator profiles are refused\n"
else
  printf "  FAIL  tracked operator profiles are refused\n"
  failures=1
fi

mkdir -p "$profile_fixture_root/final-symlink/.dm" "$profile_fixture_root/final-symlink-target"
cat > "$profile_fixture_root/final-symlink-target/operator-profile.local.json" <<'JSON'
{"operator":"fixture","updated":"2026-08-10","familyPreferenceOrder":[],"neverUse":[],"subscriptions":[{"rail":"final_symlink","probe":["/usr/bin/printf","{\"state\":\"ok\",\"remaining_pct\":99,\"window\":\"weekly\"}"],"windows":["weekly"]}]}
JSON
ln -s "$profile_fixture_root/final-symlink-target/operator-profile.local.json" \
  "$profile_fixture_root/final-symlink/.dm/operator-profile.local.json"
git -C "$profile_fixture_root/final-symlink" init -q
profile_final_symlink_result="$(cd "$profile_fixture_root/final-symlink" && \
  OPENROUTER_API_KEY='' bash "$usage_probe")"
if printf '%s' "$profile_final_symlink_result" | jq -e 'has("final_symlink") | not' >/dev/null; then
  printf "  OK    symlinked operator profile files are refused\n"
else
  printf "  FAIL  symlinked operator profile files are refused\n"
  failures=1
fi

cat > "$profile_fixture_root/retired-probe.sh" <<SH
#!/bin/sh
touch "$profile_fixture_root/retired-profile-executed"
printf '%s\\n' '{"state":"ok","remaining_pct":99,"window":"weekly"}'
SH
chmod 755 "$profile_fixture_root/retired-probe.sh"
cat > "$profile_fixture_root/retired-profile.json" <<'JSON'
{"operator":"fixture","updated":"2026-08-10","familyPreferenceOrder":[],"neverUse":[],"subscriptions":[{"rail":"retired_env_escape","probe":["RETIRED_PROBE_PATH"],"windows":["weekly"]}]}
JSON
sed "s|RETIRED_PROBE_PATH|$profile_fixture_root/retired-probe.sh|" \
  "$profile_fixture_root/retired-profile.json" > "$profile_fixture_root/retired-profile.ready.json"
retired_env_result="$(USAGE_PROBE_TEST_MODE=1 \
  DM_OPERATOR_PROFILE_FILE="$profile_fixture_root/retired-profile.ready.json" \
  OPENROUTER_API_KEY='' bash "$usage_probe")"
if printf '%s' "$retired_env_result" | jq -e '
  .probe_source == "live" and (has("retired_env_escape") | not)
' >/dev/null && [ ! -e "$profile_fixture_root/retired-profile-executed" ]; then
  printf "  OK    retired environment pair cannot select or expose an arbitrary profile\n"
else
  printf "  FAIL  retired environment pair cannot select or expose an arbitrary profile\n"
  failures=1
fi

# A linked worktree is pipeline output, not the owner of executable operator
# configuration. The common checkout's untracked profile must win, and an
# equally valid worktree-local profile must remain invisible.
mkdir -p "$profile_fixture_root/common"
(
  cd "$profile_fixture_root/common"
  git init -q
  git -c user.name=fixture -c user.email=fixture@example.invalid \
    commit --allow-empty -qm initial
  git worktree add -qb chunk "$profile_fixture_root/chunk"
)
cat > "$profile_fixture_root/probe.sh" <<'SH'
#!/bin/sh
printf '%s\n' '{"state":"ok","remaining_pct":99,"window":"weekly"}'
SH
chmod 755 "$profile_fixture_root/probe.sh"
mkdir -p "$profile_fixture_root/common/.dm" "$profile_fixture_root/chunk/.dm"
cat > "$profile_fixture_root/common/.dm/operator-profile.local.json" <<JSON
{"operator":"fixture","updated":"2026-08-10","familyPreferenceOrder":[],"neverUse":[],"subscriptions":[{"rail":"common","probe":["$profile_fixture_root/probe.sh"],"windows":["weekly"]}]}
JSON
cat > "$profile_fixture_root/chunk/.dm/operator-profile.local.json" <<JSON
{"operator":"fixture","updated":"2026-08-10","familyPreferenceOrder":[],"neverUse":[],"subscriptions":[{"rail":"planted","probe":["$profile_fixture_root/probe.sh"],"windows":["weekly"]}]}
JSON
profile_worktree_result="$(cd "$profile_fixture_root/chunk" && \
  OPENROUTER_API_KEY='' bash "$usage_probe")"
if printf '%s' "$profile_worktree_result" | jq -e '
  .probe_source == "live"
    and .common.state == "ok" and (has("planted") | not)
' >/dev/null; then
  printf "  OK    operator profiles resolve from the common checkout, not chunk worktrees\n"
else
  printf "  FAIL  operator profiles resolve from the common checkout, not chunk worktrees\n"
  failures=1
fi

codex_unrecognized_window='{"id":7,"result":{"rateLimits":{"primary":{"usedPercent":10,"windowDurationMins":300},"secondary":{"usedPercent":20,"windowDurationMins":1440}}}}'
codex_unrecognized_result="$(printf '%s\n' "$codex_unrecognized_window" \
  | bash "$usage_probe_fixture")"
if printf '%s' "$codex_unrecognized_result" | jq -e '
  .codex.state == "unknown"
    and .codex.window == "weekly"
    and .codex.windows.five_hour.remaining_pct == 90
    and .codex.windows.weekly == {"state":"unknown","remaining_pct":0,"window":"weekly"}
' >/dev/null; then
  printf "  OK    Codex probe leaves unrecognized durations conservatively unknown\n"
else
  printf "  FAIL  Codex probe leaves unrecognized durations conservatively unknown\n"
  failures=1
fi

production_live_result="$(OPENROUTER_API_KEY='' bash "$usage_probe")"
if printf '%s' "$production_live_result" | jq -e '.probe_source == "live"' >/dev/null; then
  printf "  OK    ordinary production usage output remains live evidence\n"
else
  printf "  FAIL  ordinary production usage output remains live evidence\n"
  failures=1
fi

[ -f "$routing" ] || { printf "  FAIL  shared routing-policy.json exists\n"; failures=1; }
if [ -f "$routing" ]; then
  jq -e '.subscriptionFirst.invariant == "subscription rails first while live headroom clears the threshold for BOTH the weekly cap and the 5-hour window; API rails next from this policy\u0027s authoritative ordered role definitions after family exclusions; never start planned multi-chunk work that projected spend would push below threshold mid-run"' "$routing" >/dev/null || { printf "  FAIL  subscription-first invariant names ordered role definitions as API authority\n"; failures=1; }
  jq -e '.chunkKind.config.provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps config chunks to OpenRouter\n"; failures=1; }
  jq -e '.chunkKind.ui.provider == "codex" and .chunkKind.integration.provider == "codex"' "$routing" >/dev/null || { printf "  FAIL  UI and integration coding route to Codex\n"; failures=1; }
  jq -e '
    .agentType["security-auditor-openrouter"] as $external
    | .agentType["security-auditor-codex-signoff"] as $signoff
    | $external.provider == "openrouter"
      and $external.model == "moonshotai/kimi-k3"
      and $external.fallbackModel == "x-ai/grok-4.6"
      and $external.fallbackProvider == "codex"
      and $signoff == {
        "provider":"implementer-aware-independent-family",
        "preferredProviderWhenIndependent":"codex",
        "codexImplementerProvider":"openrouter",
        "codexImplementerModel":"moonshotai/kimi-k3",
        "codexImplementerFallbackModel":"x-ai/grok-4.6",
        "required":true,
        "inputScope":"full-diff",
        "reviewerFamilyConstraint":"must-differ-from-every-implementer-family",
        "failureResolution":{
          "runner_failure":"remaining-non-implementing-family-or-review-incomplete",
          "full_disclosure_decline":"remaining-non-implementing-family-or-review-incomplete",
          "partial_coverage":"remaining-non-implementing-family-or-review-incomplete"
        },
        "rationale":"Independent full-diff security completion is mandatory. The stable lane id does not select Codex when Codex implemented the diff."
      }
      and .agentType["second-perspective"] == {
        "provider":"implementer-aware-independent-family",
        "model":"qwen/qwen3.8-max",
        "fallbackModel":"x-ai/grok-4.6",
        "fallbackProvider":"implementer-aware-independent-family",
        "reviewerFamilyConstraint":"must-differ-from-every-implementer-family",
        "rationale":"After eligible subscription rails, ordinary independent review starts with Qwen Max rather than Kimi and preserves family independence."
      }
      and .agentType["architecture-reviewer"].provider == "codex"
  ' "$routing" >/dev/null || { printf "  FAIL  external security analysis and implementer-aware sign-off have separate lane identities\n"; failures=1; }
  jq -e '.agentType["doc-sync-reviewer"].provider == "openrouter"' "$routing" >/dev/null || { printf "  FAIL  routing policy maps doc-sync-reviewer to OpenRouter\n"; failures=1; }
  routine_review_routes_valid "$routing" || { printf "  FAIL  routine reviewers use the intended provider/model/fallback tuples\n"; failures=1; }
  expect_routine_review_route_reject "simplicity fallback model" '.agentType["code-simplicity-reviewer"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "simplicity fallback provider" '.agentType["code-simplicity-reviewer"].fallbackProvider = "claude"'
  expect_routine_review_route_reject "documentation fallback model" '.agentType["doc-sync-reviewer"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "documentation fallback provider" '.agentType["doc-sync-reviewer"].fallbackProvider = "claude"'
  expect_routine_review_route_reject "test fallback model" '.agentType["test-coverage-reviewer"].fallbackModel = "openai/gpt-5.6-terra"'
  expect_routine_review_route_reject "test fallback provider" '.agentType["test-coverage-reviewer"].fallbackProvider = "claude"'
  jq -e '
    .agentType["openrouter-bulk-analyst"]
    | .provider == "openrouter"
      and .model == "qwen/qwen3.8-max"
      and .fallbackModel == "deepseek/deepseek-v4-pro-0813"
      and .fallbackProvider == "codex"
  ' "$routing" >/dev/null || { printf "  FAIL  bulk analysis uses exact Qwen Max -> DeepSeek Pro -> Codex routing\n"; failures=1; }
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
  jq -e '[.agentType[] | select(.provider != "implementer-aware-independent-family") | select(.fallbackProvider? != null) | .fallbackProvider == "codex"] | all' "$routing" >/dev/null || { printf "  FAIL  ordinary coding reviewer fallbacks return to Codex\n"; failures=1; }
  jq -e '[.agentType[] | select(.provider == "implementer-aware-independent-family") | .fallbackProvider? // "implementer-aware-independent-family"] | all(. == "implementer-aware-independent-family")' "$routing" >/dev/null || { printf "  FAIL  independent reviewer fallbacks preserve family exclusion\n"; failures=1; }
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
if jq -e '
  .executor == "openrouter"
  and .renderedSurface == "not_applicable"
  and .routingOverride == null
  and (.filesToModify == ["plans/model-routing/notes.md", "plans/model-routing/work-paths.html"])
  and .expectedPrimaryModel == "deepseek/deepseek-v4-flash-0731"
' "$planning_html_fixture" >/dev/null &&
   grep -Fq 'plans/**/work-paths.html' "$promptcraft"; then
  planning_probe="$profile_fixture_root/planning-probe.json"
  printf '%s\n' '{"probe_source":"fixture","codex":{"state":"ok","remaining_pct":100},"openrouter":{"state":"ok","balance_usd":1}}' > "$planning_probe"
  planning_kind="$(classify_fixture_kind "$planning_html_fixture")"
  planning_result="$(CASCADE_EXHAUSTED_RAILS= "$cascade" --kind "$planning_kind" --prompt planning-fixture --host codex --dry-run --probe-file "$planning_probe")"
  planning_executor="$(printf '%s' "$planning_result" | jq -r '.kind // empty')"
  planning_model="$(printf '%s' "$planning_result" | jq -r '.model // empty')"
else
  planning_kind=""
  planning_executor=""
  planning_model=""
fi
if [ "$planning_executor" = "openrouter_exec" ] &&
   [ "$planning_model" = "$(jq -r '.expectedPrimaryModel' "$planning_html_fixture")" ] &&
   [ "$planning_kind" = "config" ] &&
   [ "$(classify_fixture_kind "$served_html_fixture")" = "ui" ] &&
   jq -e '.kind == "ui" and .executor == "codex" and .renderedSurface == "required" and .routingOverride == null' "$served_html_fixture" >/dev/null; then
  printf "  OK    unserved planning HTML plus Markdown remains OpenRouter-eligible without an override\n"
else
  printf "  FAIL  planning HTML regression fixture must remain OpenRouter-eligible without an override\n"
  failures=1
fi
require_absent "$dm_review" 'matrix quality-per-price' "dm-review does not let matrix rank select independent reviewers"
require_absent "$REPO_ROOT/plugins/dm-review/agents/review/codex-perspective.md" 'matrix quality-per-price' "second-perspective agent defers to its ordered role"
require_absent "$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md" 'matrix quality-per-price' "agent registry defers to ordered roles"
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
require_text "$orchestrator" "Full mode runs on the provider family that did not implement" "orchestrator enforces cross-provider full review"
require_text "$orchestrator" "Run Post-Mortem" "orchestrator includes run post-mortem step"
require_text "$orchestrator" "Claude JSONL delta" "postmortem measures Claude JSONL delta"
require_text "$orchestrator" "AWAITING APPROVAL" "postmortem recommendations are proposal-only"
require_text "$model_cascade" '"openrouter"' "model cascade defines OpenRouter class"
if [ -f "$model_cascade" ] && [ -f "$harness" ]; then
  jq -e '.cascades | has("claude") | not' "$model_cascade" >/dev/null || { printf "  FAIL  no Claude-native cascade class\n"; failures=1; }
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
fi
require_absent "$model_cascade" 'native_judgment' "model cascade removes the dormant native judgment rail"
require_absent "$harness" 'native_judgment' "harness removes the dormant native judgment role"
require_absent "$cascade" 'native_judgment' "dispatcher removes native judgment authorization machinery"
if [ -f "$routing" ]; then
  jq -e '.targets.enforcement.varianceReceiptRequired == true' "$routing" >/dev/null || { printf "  FAIL  routing policy requires variance receipts\n"; failures=1; }
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
require_text "$cascade" '--mode artifact-delegation' "pipeline wrapper rungs use configured-key automatic byte screening"
require_absent "$cascade" 'dispatch-provider-request' "pipeline wrapper rungs do not use broker transport"
require_text "$authorization_contract" 'request-envelope digest' "pipeline wrapper receipts retain request-envelope digest evidence"
require_text "$wrapper" "OPENROUTER_WORKLOAD" "OpenRouter wrapper accepts workload-aware provider routing"
require_text "$wrapper" "direct|bulk|mechanical)" "direct, bulk, and mechanical work share throughput routing"
require_text "$wrapper" "quality|security)" "quality and security work retain quality-first routing"
require_text "$wrapper" 'TIMEOUT="${3:-${OPENROUTER_OVERALL_TIMEOUT:-3600}}"' "OpenRouter wrapper defaults each generation to a one-hour completion budget"
require_text "$wrapper" 'FIRST_BYTE_TIMEOUT="${OPENROUTER_FIRST_BYTE_TIMEOUT:-600}"' "OpenRouter wrapper allows ten minutes for first response bytes"
require_text "$wrapper" 'IDLE_TIMEOUT="${OPENROUTER_IDLE_TIMEOUT:-600}"' "OpenRouter wrapper allows ten minutes between stream progress"
require_text "$runner" 'TIMEOUT="${OPENROUTER_EXEC_TIMEOUT:-3600}"' "Pipeline OpenRouter execution inherits the one-hour completion budget"
require_text "$cascade" 'openrouter-wrapper.sh' "pipeline cascade delegates request encoding to the canonical wrapper"
require_text "$runner" 'openrouter-wrapper.sh' "OpenRouter exec delegates request encoding to the canonical wrapper"
require_text "$dm_review" '| `security-auditor-openrouter` | `moonshotai/kimi-k3` | `x-ai/grok-4.6` | 3600s |' "dm-review security analysis receives a one-hour completion budget"
require_text "$dm_review" '| `pattern-recognition-specialist` | `deepseek/deepseek-v4-pro-0813` | `qwen/qwen3.8-max` | 1800s |' "dm-review routine analysis receives a 30-minute completion budget"
require_text "$dm_review" '7200s at or above 10K diff lines' "dm-review bulk analysis scales to a two-hour completion budget"
require_text "$model_selection" 'Routine pattern, simplicity, documentation, and test review lanes use 1800' "OpenRouter guidance preserves routine review timeouts"
require_text "$model_selection" 'Focused security and ordinary bulk analysis use 3600 seconds.' "OpenRouter guidance preserves security and bulk review timeouts"
require_text "$model_selection" 'analysis uses 7200 seconds at or above 10,000 diff lines.' "OpenRouter guidance preserves large-diff bulk timeouts"
require_text "$model_selection" '`OPENROUTER_ZDR=1` is opt-in' "OpenRouter model guidance preserves the ZDR privacy control"
require_text "$model_selection" 'If ZDR leaves no eligible Kimi endpoint, the ordered security fallback may serve Grok 4.6.' "OpenRouter model guidance preserves ZDR-aware security fallback behavior"
require_text "$efficiency_plan" 'Depot trusted baseline is the current `main` branch; live PR and Issue status remains GitHub-authoritative.' "efficiency plan avoids a mutable trusted-main hash"
require_text "$efficiency_plan" 'Grok 4.6 handles independent review escalation, and GLM-5.2 remains outside active routing.' "efficiency plan retains the enforced Grok and GLM routing doctrine"
require_absent "$efficiency_plan" 'Grok 4.5' "efficiency plan removes the retired Grok route"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md" 'model=`deepseek/deepseek-v4-pro-0813`, agent=`pattern-recognition-specialist`' "dm-review contribution example uses the current pattern-review primary"
if [ "$(grep -Fc -- '--minimum-version 1.15.0' "$dm_review")" -eq 2 ] &&
   ! grep -Fq -- '--minimum-version 1.14.2' "$dm_review"; then
  printf "  OK    dm-review resolves only OpenRouter bundles compatible with the 1.15.0 route contract\n"
else
  printf "  FAIL  dm-review resolves only OpenRouter bundles compatible with the 1.15.0 route contract\n"
  failures=1
fi
require_absent "$cascade" 'OPENROUTER_PAYLOAD_AUTHORIZATION' "pipeline cascade does not trust environment disclosure authority"
require_text "$authorization_contract" 'without an approval question' "pipeline preserves non-interactive native fallback"
require_text "$cascade" 'exit 76' "pipeline exposes ladder exhaustion"
require_absent "$cascade" 'rc -eq 75' "pipeline removes provider-terminal compatibility handling"
require_absent "$orchestrator" 'RC 75' "orchestrator removes provider-terminal compatibility instructions"
require_absent "$orchestrator" 'append the exact unmodified' "orchestrator removes active signed-broker receipt handling"
require_text "$runner_policy_test" 'test_openrouter_noninteractive.py' "runner policy uses controlled loopback configured-key fixtures"
require_text "$noninteractive_test" 'FixtureHandler.contacts' "configured-key fixtures count provider contacts"
require_text "$wrapper" "OPENROUTER_RECEIPT_FILE" "OpenRouter wrapper emits content-free provider receipts"
require_text "$wrapper" "servingProviderProvenance" "OpenRouter wrapper distinguishes absent provider identity from verified provenance"
require_text "$wrapper" "response omitted required generation provenance" "OpenRouter wrapper fails closed when model provenance is absent"
require_text "$mcp_control" "direct API runner remains authoritative" "MCP remains a control plane rather than the execution transport"
require_text "$mcp_control" "does not expose an authenticated workspace" "MCP workspace attribution gap is explicit"
require_text "$mcp_control" "observedAt" "MCP catalog freshness has a bounded observation contract"
require_text "$dm_review" "routing-policy.json" "dm-review reads shared routing policy"
require_absent "$dm_review" "Diff >5000 lines AND openrouter" "dm-review no longer gates OpenRouter on >5000 diff lines"
require_text "$dm_review" "OPENROUTER_API_KEY_FILE" "dm-review supports both configured key inputs"
require_text "$dm_review" "OPENROUTER_AVAILABLE=true" "dm-review enables eligible configured-key lanes"
require_text "$dm_review" "OPENROUTER_UNAVAILABLE_REASON=configured_key_or_bundle_unavailable" "dm-review records configured-key or bundle fallback"
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
require_text "$agent_runner" "--mode artifact-delegation" "OpenRouter runner scans private outbound files once"
require_text "$pipeline_cmd" "Codex is the required adversarial reviewer" "Phase 5 requires the Codex adversarial lens"
require_text "$pipeline_cmd" "Configured-key OpenRouter availability does not broaden this workload" "Phase 5 remains native by workload policy"
require_absent "$pipeline_cmd" "PIPELINE_CLAUDE_ADVERSARY=1" "Phase 5 has no duplicate optional adversarial lens"
require_absent "$pipeline_cmd" '--mode artifact-delegation' "Phase 5 does not prepare automated provider payloads"
require_text "$pipeline_cmd" 'openrouter-authorization-contract.md' "Phase 5 reads the shared fail-closed authorization contract"
require_text "$assess" 'native by workload policy' "assess remains native without invoking broker authorization"
require_text "$research" 'This phase remains native by' "research remains native without invoking broker authorization"
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
