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
      plugins/openrouter/agents/workflow/openrouter-agent-runner.md|plugins/dm-review/skills/review/SKILL.md) openrouter_floor="1.14.0" ;;
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
grep -Fq 'has no effect on configured-key dispatch' "$authorization_contract" || {
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
  ! grep -Fq '/usr/local/bin/workflow-authority' "$file" &&
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
