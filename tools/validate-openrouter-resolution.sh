#!/usr/bin/env bash
# Validate canonical live OpenRouter/Pipeline bundle consumers.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="${1:---canonical}"
case "$MODE" in --canonical|--all) ;; *) echo "usage: $0 [--canonical|--all]" >&2; exit 2;; esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
failures=0

consumers=(
  plugins/openrouter/commands/openrouter.md
  plugins/openrouter/skills/openrouter-delegate/SKILL.md
  plugins/openrouter/skills/openrouter-delegate/references/invocation-protocol.md
  plugins/openrouter/skills/openrouter-delegate/references/prompt-templates.md
  plugins/openrouter/agents/workflow/openrouter-agent-runner.md
  plugins/dm-review/skills/review/SKILL.md
  plugins/airlift/commands/airlift-in.md
  plugins/airlift/prompts/airlift-in.md
  plugins/pipeline/references/cascade-dispatch.sh
  plugins/pipeline/references/openrouter-exec.sh
  plugins/pipeline/agents/workflow/execution-orchestrator.md
)

is_configured_key_script() {
  case "$1" in
    plugins/pipeline/references/cascade-dispatch.sh|plugins/pipeline/references/openrouter-exec.sh) return 0 ;;
    *) return 1 ;;
  esac
}

if [ "$MODE" = "--all" ]; then
  consumers+=(plugins/openrouter/skills/openrouter/SKILL.md)
fi

for relative in "${consumers[@]}"; do
  file="$ROOT/$relative"
  if [ ! -f "$file" ]; then
    echo "  FAIL  missing canonical resolver consumer: $relative"
    failures=1
    continue
  fi
  if ! is_configured_key_script "$relative" && ! grep -Fq 'resolve-plugin-bundle' "$file"; then
    echo "  FAIL  resolver contract absent: $relative"
    failures=1
  fi
  if ! is_configured_key_script "$relative" && grep -Eq 'ls -t[d]? .*openrouter|ls -t[d]? .*pipeline|OPENROUTER_EXEC_WRAPPER_PATH|OPENROUTER_EXEC_CMD|WRAPPER_CMD|security_policy_path' "$file"; then
    echo "  FAIL  independent or caller-selected OpenRouter/Pipeline asset lookup: $relative"
    failures=1
  fi
  if grep -Fq '"$WORKFLOW_KERNEL" resolve-plugin-bundle' "$file"; then
    grep -Fq -- '--active-host' "$file" || {
      echo "  FAIL  live resolver call lacks active-host binding: $relative"
      failures=1
    }
  fi
  openrouter_calls="$(grep -Fc 'resolve-plugin-bundle --plugin openrouter' "$file" || true)"
  if [ "$openrouter_calls" -gt 0 ]; then
    case "$relative" in
      plugins/openrouter/agents/workflow/openrouter-agent-runner.md) openrouter_floor="1.14.0" ;;
      plugins/dm-review/skills/review/SKILL.md) openrouter_floor="1.14.2" ;;
      plugins/openrouter/commands/openrouter.md|plugins/openrouter/skills/openrouter/SKILL.md|plugins/openrouter/skills/openrouter-delegate/SKILL.md|plugins/openrouter/skills/openrouter-delegate/references/invocation-protocol.md) openrouter_floor="1.14.0" ;;
      plugins/airlift/*) openrouter_floor="1.14.0" ;;
      plugins/pipeline/*) openrouter_floor="1.14.0" ;;
      plugins/openrouter/*) openrouter_floor="1.8.0" ;;
      *) openrouter_floor="1.7.0" ;;
    esac
    floor_calls="$(grep -Fc -- "--minimum-version $openrouter_floor" "$file" || true)"
    if [ "$floor_calls" -ne "$openrouter_calls" ]; then
      echo "  FAIL  every OpenRouter resolver call must require exact floor $openrouter_floor: $relative"
      failures=1
    fi
  fi
  pipeline_calls="$(grep -Fc 'resolve-plugin-bundle --plugin pipeline' "$file" || true)"
  if [ "$pipeline_calls" -gt 0 ]; then
    floor_calls="$(grep -Fc -- '--minimum-version 1.36.1' "$file" || true)"
    if [ "$floor_calls" -ne "$pipeline_calls" ]; then
      echo "  FAIL  every Pipeline resolver call must require exact floor 1.36.1: $relative"
      failures=1
    fi
  fi
  if ! is_configured_key_script "$relative" && grep -Fq 'skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file"; then
    grep -Fq -- '--required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file" &&
    ! grep -Fq -- '--required-asset skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file" || {
      echo "  FAIL  OpenRouter wrapper is not declared executable-only: $relative"
      failures=1
    }
  fi
  if grep -Fq 'skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file"; then
    grep -Fq -- '--required-asset skills/openrouter-delegate/references/openrouter-credential.sh' "$file" || {
      echo "  FAIL  OpenRouter credential loader is not bound into the coherent bundle: $relative"
      failures=1
    }
  fi
  if ! is_configured_key_script "$relative" && grep -Fq 'skills/openrouter-delegate/references/delegation-boundary.sh' "$file"; then
    grep -Fq -- '--required-executable skills/openrouter-delegate/references/delegation-boundary.sh' "$file" &&
    ! grep -Fq -- '--required-asset skills/openrouter-delegate/references/delegation-boundary.sh' "$file" || {
      echo "  FAIL  OpenRouter boundary is not declared executable-only: $relative"
      failures=1
    }
  fi
  if [ "$pipeline_calls" -gt 0 ]; then
    for executable in \
      references/cascade-dispatch.sh \
      references/openrouter-exec.sh \
      references/usage-probe.sh
    do
      grep -Fq -- "--required-executable $executable" "$file" &&
      ! grep -Fq -- "--required-asset $executable" "$file" || {
        echo "  FAIL  Pipeline executable is not mode-bound: $relative ($executable)"
        failures=1
      }
    done
  fi
done

validate_active_cache_consumers() {
  local dm_review_file="$1" pipeline_file="$2" consumer_failures=0

  grep -Fq 'resolve-plugin-bundle \' "$dm_review_file" &&
  grep -Fq -- '--plugin "$PLUGIN" --minimum-version "$PLUGIN_MINIMUM_VERSION"' "$dm_review_file" &&
  grep -Fq -- 'CACHE_ACTIVE_HOST_ARGS=(--active-host "$CACHE_ACTIVE_HOST")' "$dm_review_file" &&
  grep -Fq 'DM_REVIEW_REQUIRED_ASSETS=(' "$dm_review_file" &&
  grep -Fq '"agents/workflow/review-consolidator.md"' "$dm_review_file" &&
  grep -Fq '"agents/workflow/review-memory-recorder.md"' "$dm_review_file" &&
  grep -Fq 'append_selected_asset() {' "$dm_review_file" &&
  grep -Fq 'local agent_plugin="$1" agent_asset="$2"' "$dm_review_file" &&
  grep -Fq 'dm-review) DM_REVIEW_REQUIRED_ASSETS+=("$agent_asset") ;;' "$dm_review_file" &&
  grep -Fq 'append_selected_asset "$AGENT_PLUGIN" "$AGENT_ASSET"' "$dm_review_file" &&
  grep -Fq -- 'REQUIRED_ASSET_ARGS+=(--required-asset "$ASSET")' "$dm_review_file" &&
  grep -Fq 'dm-review) DM_REVIEW_BUNDLE_ROOT="$PLUGIN_BUNDLE_ROOT" ;;' "$dm_review_file" &&
  grep -Fq 'CONSOLIDATOR_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-consolidator.md"' "$dm_review_file" &&
  grep -Fq 'RECORDER_PATH="$DM_REVIEW_BUNDLE_ROOT/agents/workflow/review-memory-recorder.md"' "$dm_review_file" &&
  grep -Fq 'SKIP: optional plugin bundle unavailable: $PLUGIN' "$dm_review_file" || consumer_failures=1

  if grep -Fq 'declare -A' "$dm_review_file" ||
     grep -Fq 'SELECTED_ASSETS_BY_PLUGIN' "$dm_review_file" ||
     grep -Fq 'SELECTED_PLUGINS' "$dm_review_file" ||
     grep -Fq 'PLUGIN_BUNDLE_ROOTS' "$dm_review_file" ||
     grep -Fq 'AGENT_PATH=$(ls -t "$CACHE_ROOT"/<plugin>/*/agents/' "$dm_review_file" ||
     grep -Fq 'CONSOLIDATOR_PATH=$(ls -t "$CACHE_ROOT"/dm-review/*/agents/workflow/review-consolidator.md' "$dm_review_file" ||
     grep -Fq 'RECORDER_PATH=$(ls -t "$CACHE_ROOT"/dm-review/*/agents/workflow/review-memory-recorder.md' "$dm_review_file"; then
    consumer_failures=1
  fi

  grep -Fq 'resolve-plugin-asset \' "$pipeline_file" &&
  grep -Fq -- '--plugin dm-review' "$pipeline_file" &&
  grep -Fq -- '--asset skills/review/references/repo-cleanup-contract.md' "$pipeline_file" &&
  grep -Fq -- '--minimum-version 1.62.0' "$pipeline_file" &&
  grep -Fq 'CLEANUP_ACTIVE_HOST_ARGS=(--active-host "$CLEANUP_ACTIVE_HOST")' "$pipeline_file" || consumer_failures=1

  if grep -Fq 'CONTRACT=$(ls -t "$CACHE"/dm-review/*/skills/review/references/repo-cleanup-contract.md' "$pipeline_file" ||
     grep -Fq 'CONTRACT="plugins/dm-review/skills/review/references/repo-cleanup-contract.md"' "$pipeline_file"; then
    consumer_failures=1
  fi

  [ "$consumer_failures" -eq 0 ]
}

dm_review_consumer="$ROOT/plugins/dm-review/skills/review/SKILL.md"
pipeline_consumer="$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
if ! validate_active_cache_consumers "$dm_review_consumer" "$pipeline_consumer"; then
  echo "  FAIL  active dm-review/Pipeline consumers lack coherent host-aware resolution"
  failures=1
fi

consumer_fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/active-cache-consumers.XXXXXX")"
trap 'rm -rf "$consumer_fixture_root"' EXIT
cp "$dm_review_consumer" "$consumer_fixture_root/dm-review.md"
cp "$pipeline_consumer" "$consumer_fixture_root/pipeline.md"
awk '
  /<!-- active-cache-resolution-shell:start -->/ { capture=1; next }
  /<!-- active-cache-resolution-shell:end -->/ { exit }
  capture && /^```/ { next }
  capture { print }
' "$dm_review_consumer" > "$consumer_fixture_root/dm-review-resolution.sh"
cat > "$consumer_fixture_root/fake-workflow-kernel" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$RESOLVER_CALL_LOG"
printf '%s\n' '{"selected_root":"~/.codex/plugins/cache/depot/dm-review/1.62.1"}'
EOF
chmod +x "$consumer_fixture_root/fake-workflow-kernel"
if ! RESOLVER_CALL_LOG="$consumer_fixture_root/resolver-calls.log" \
  WORKFLOW_KERNEL="$consumer_fixture_root/fake-workflow-kernel" \
  AGENT_PLUGIN=dm-review \
  AGENT_ASSET=agents/review/pattern-recognition-specialist.md \
  bash "$consumer_fixture_root/dm-review-resolution.sh" >/dev/null; then
  echo "  FAIL  dm-review indexed resolver fixture did not execute"
  failures=1
elif ! grep -Fq -- '--required-asset agents/workflow/review-consolidator.md' "$consumer_fixture_root/resolver-calls.log" ||
     ! grep -Fq -- '--required-asset agents/workflow/review-memory-recorder.md' "$consumer_fixture_root/resolver-calls.log" ||
     ! grep -Fq -- '--required-asset agents/review/pattern-recognition-specialist.md' "$consumer_fixture_root/resolver-calls.log"; then
  echo "  FAIL  dm-review resolver ran without its populated coherent required-asset set"
  failures=1
fi
printf '%s\n' 'AGENT_PATH=$(ls -t "$CACHE_ROOT"/<plugin>/*/agents/review/<agent-id>.md 2>/dev/null | head -1)' >> "$consumer_fixture_root/dm-review.md"
if validate_active_cache_consumers "$consumer_fixture_root/dm-review.md" "$pipeline_consumer" >/dev/null 2>&1; then
  echo "  FAIL  dm-review first-root mutation escaped active-consumer validation"
  failures=1
fi
sed 's/SKIP: optional plugin bundle unavailable: \$PLUGIN/ERROR: optional plugin bundle unavailable: \$PLUGIN/' \
  "$dm_review_consumer" > "$consumer_fixture_root/dm-review-optional-abort.md"
if validate_active_cache_consumers "$consumer_fixture_root/dm-review-optional-abort.md" "$pipeline_consumer" >/dev/null 2>&1; then
  echo "  FAIL  dm-review optional-skip mutation escaped active-consumer validation"
  failures=1
fi
sed '/"agents\/workflow\/review-consolidator.md"/d' \
  "$dm_review_consumer" > "$consumer_fixture_root/dm-review-empty-required-assets.md"
if validate_active_cache_consumers "$consumer_fixture_root/dm-review-empty-required-assets.md" "$pipeline_consumer" >/dev/null 2>&1; then
  echo "  FAIL  dm-review empty required-asset mutation escaped active-consumer validation"
  failures=1
fi
cp "$dm_review_consumer" "$consumer_fixture_root/dm-review-bash4.md"
printf '%s\n' 'declare -A PLUGIN_BUNDLE_ROOTS' >> "$consumer_fixture_root/dm-review-bash4.md"
if validate_active_cache_consumers "$consumer_fixture_root/dm-review-bash4.md" "$pipeline_consumer" >/dev/null 2>&1; then
  echo "  FAIL  dm-review Bash-4-only mutation escaped active-consumer validation"
  failures=1
fi
printf '%s\n' 'CONTRACT=$(ls -t "$CACHE"/dm-review/*/skills/review/references/repo-cleanup-contract.md 2>/dev/null | head -1)' >> "$consumer_fixture_root/pipeline.md"
if validate_active_cache_consumers "$dm_review_consumer" "$consumer_fixture_root/pipeline.md" >/dev/null 2>&1; then
  echo "  FAIL  Pipeline first-root mutation escaped active-consumer validation"
  failures=1
fi

if ! "$ROOT/tools/test-openrouter-agent-runner-boundary.sh"; then
  echo "  FAIL  OpenRouter agent runner behavioral one-pass boundary regression"
  failures=1
fi

for relative in \
  plugins/pipeline/references/cascade-dispatch.sh \
  plugins/pipeline/references/openrouter-exec.sh
do
  file="$ROOT/$relative"
  grep -Fq 'resolve-plugin-bundle --plugin openrouter' "$file" &&
  grep -Fq -- '--minimum-version 1.14.0' "$file" &&
  grep -Fq 'WORKFLOW_KERNEL' "$file" &&
  ! grep -Eq 'ls -t[d]? .*openrouter' "$file" || {
    echo "  FAIL  configured-key consumer bypasses coherent semver OpenRouter resolution: $relative"
    failures=1
  }
done

authorization_contract="$ROOT/plugins/pipeline/references/openrouter-authorization-contract.md"
grep -Fq 'OPENROUTER_API_KEY_FILE' "$authorization_contract" &&
grep -Fq 'delegation-boundary.sh --mode artifact-delegation' "$authorization_contract" &&
grep -Fq 'configured-key path has no broker dependency' "$authorization_contract" || {
  echo "  FAIL  configured-key OpenRouter authorization contract absent"
  failures=1
}

for relative in \
  plugins/pipeline/commands/pipeline.md \
  plugins/pipeline/skills/research/SKILL.md \
  plugins/pipeline/skills/assess/SKILL.md
do
  file="$ROOT/$relative"
  grep -Fq -- '--plugin pipeline' "$file" &&
  grep -Fq -- '--minimum-version 1.36.1' "$file" &&
  grep -Fq -- '--required-asset' "$file" &&
  grep -Fq 'references/openrouter-authorization-contract.md' "$file" &&
  grep -Fq -- '--active-host' "$file" &&
  ! grep -Fq 'plugins/pipeline/references/openrouter-authorization-contract.md' "$file" &&
  ! grep -Fq 'compute each file'\''s SHA-256' "$file" || {
    echo "  FAIL  automated Pipeline OpenRouter caller lacks the shared authorization contract: $relative"
    failures=1
  }
done

bulk_criteria="$ROOT/plugins/openrouter/agents/review/openrouter-bulk-analyst.md"
grep -Fq 'generic `openrouter-agent-runner` is the only execution path' "$bulk_criteria" &&
! grep -Fq 'resolve-plugin-bundle' "$bulk_criteria" &&
! grep -Fq 'openrouter-wrapper.sh' "$bulk_criteria" || {
  echo "  FAIL  OpenRouter bulk analyst must remain criteria-only"
  failures=1
}

for relative in \
  plugins/openrouter/commands/openrouter.md \
  plugins/openrouter/agents/workflow/openrouter-agent-runner.md
do
  file="$ROOT/$relative"
  grep -Fq 'delegation-boundary.sh' "$file" &&
  grep -Fq -- '--mode artifact-delegation' "$file" || {
    echo "  FAIL  wrapper consumer lacks automatic private-file screening: $relative"
    failures=1
  }
done

for relative in \
  plugins/pipeline/references/cascade-dispatch.sh \
  plugins/pipeline/references/openrouter-exec.sh
do
  file="$ROOT/$relative"
  grep -Fq 'OPENROUTER_API_KEY_FILE' "$file" &&
  grep -Fq 'delegation-boundary.sh' "$file" &&
  grep -Fq -- '--mode artifact-delegation' "$file" &&
  ! grep -Fq 'dispatch-provider-request' "$file" &&
  ! grep -Fq 'OPENROUTER_PAYLOAD_AUTHORIZATION' "$file" &&
  ! grep -Fq 'OPENROUTER_PAYLOAD_APPROVAL_SHA256' "$file" || {
    echo "  FAIL  configured-key consumer does not use the coherent screened wrapper path: $relative"
    failures=1
  }
done
for relative in \
  plugins/openrouter/skills/openrouter-delegate/SKILL.md \
  plugins/openrouter/skills/openrouter-delegate/references/invocation-protocol.md \
  plugins/openrouter/skills/openrouter-delegate/references/prompt-templates.md \
  plugins/openrouter/skills/openrouter-delegate/references/model-selection.md
do
  file="$ROOT/$relative"
  if grep -Eq 'bash +"\$WRAPPER(_PATH)?"' "$file"; then
    echo "  FAIL  documentation teaches an unauthorized raw-wrapper call: $relative"
    failures=1
  fi
done

grep -Fq 'anthropic/*' \
  "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh" || {
    echo "  FAIL  final wrapper lacks Anthropic pre-network rejection"
    failures=1
  }
for origin_guard in \
  "plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh:candidate_origin=" \
  "plugins/openrouter/agents/workflow/openrouter-agent-runner.md:target_model_origin=" \
  "plugins/pipeline/references/openrouter-exec.sh:candidate_origin=" \
  "plugins/pipeline/references/cascade-dispatch.sh:model_origin="
do
  origin_file="${origin_guard%%:*}"
  origin_marker="${origin_guard#*:}"
  grep -Fq "$origin_marker" "$ROOT/$origin_file" || {
    echo "  FAIL  provider-origin guard is not case-normalized: $origin_file"
    failures=1
  }
done
grep -Fq -- '--plugin <name>' \
  "$ROOT/plugins/workflow-kernel/skills/workflow-kernel/SKILL.md" || {
    echo "  FAIL  workflow-kernel resolver is not neutral across plugin names"
    failures=1
  }
grep -Fq -- '--required-executable' \
  "$ROOT/plugins/workflow-kernel/skills/workflow-kernel/SKILL.md" &&
grep -Fq 'required_executables' \
  "$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/runtime_resolution.py" &&
grep -Fq '"--required-executable"' \
  "$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py" || {
    echo "  FAIL  workflow-kernel executable-asset contract is incomplete"
    failures=1
  }
grep -Fq 'OPENROUTER_BUNDLE_REF' \
  "$ROOT/plugins/dm-review/skills/review/SKILL.md" &&
grep -Fq '[ "$BUNDLE_REF" = "$openrouter_bundle_ref" ]' \
  "$ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md" &&
grep -Fq '[ "$RESOLVED_VERSION" = "$openrouter_bundle_version" ]' \
  "$ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md" &&
grep -Fq '[ "$RESOLVED_CLASS" = "$cache_class" ]' \
  "$ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md" || {
    echo "  FAIL  dm-review runner selection is not identity-bound across re-resolution"
    failures=1
  }
grep -Fq 'if type == "boolean" then tostring else error("invalid fallbackUsed") end' \
  "$ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md" || {
    echo "  FAIL  OpenRouter runner rejects a valid fallbackUsed:false receipt"
    failures=1
  }
for file in \
  "$ROOT/plugins/airlift/commands/airlift-in.md" \
  "$ROOT/plugins/airlift/prompts/airlift-in.md"
do
  grep -Fq -- '--content-file "$RESUME_COPY" --content-file "$HANDOFF_COPY"' "$file" &&
  grep -Fq 'env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$RESUME_COPY"' "$file" &&
  grep -Fq '< "$HANDOFF_COPY"' "$file" || {
    echo "  FAIL  Airlift does not screen and delegate the same private copies: ${file#"$ROOT/"}"
    failures=1
  }
done

[ "$failures" -eq 0 ] || exit 1
echo "  OK    coherent OpenRouter/Pipeline resolver consumers valid ($MODE)"
