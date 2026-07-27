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
  plugins/openrouter/agents/review/openrouter-bulk-analyst.md
  plugins/dm-review/skills/review/SKILL.md
  plugins/airlift/commands/airlift-in.md
  plugins/airlift/prompts/airlift-in.md
  plugins/pipeline/references/cascade-dispatch.sh
  plugins/pipeline/references/openrouter-exec.sh
  plugins/pipeline/agents/workflow/execution-orchestrator.md
)

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
  if ! grep -Fq 'resolve-plugin-bundle' "$file"; then
    echo "  FAIL  resolver contract absent: $relative"
    failures=1
  fi
  if grep -Eq 'ls -t[d]? .*openrouter|ls -t[d]? .*pipeline|OPENROUTER_EXEC_WRAPPER_PATH|OPENROUTER_EXEC_CMD|WRAPPER_CMD|security_policy_path' "$file"; then
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
    floor_calls="$(grep -Fc -- '--minimum-version 1.6.0' "$file" || true)"
    if [ "$floor_calls" -ne "$openrouter_calls" ]; then
      echo "  FAIL  every OpenRouter resolver call must require exact floor 1.6.0: $relative"
      failures=1
    fi
  fi
  pipeline_calls="$(grep -Fc 'resolve-plugin-bundle --plugin pipeline' "$file" || true)"
  if [ "$pipeline_calls" -gt 0 ]; then
    floor_calls="$(grep -Fc -- '--minimum-version 1.33.0' "$file" || true)"
    if [ "$floor_calls" -ne "$pipeline_calls" ]; then
      echo "  FAIL  every Pipeline resolver call must require exact floor 1.33.0: $relative"
      failures=1
    fi
  fi
  if grep -Fq 'skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file"; then
    grep -Fq -- '--required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file" &&
    ! grep -Fq -- '--required-asset skills/openrouter-delegate/references/openrouter-wrapper.sh' "$file" || {
      echo "  FAIL  OpenRouter wrapper is not declared executable-only: $relative"
      failures=1
    }
  fi
  if grep -Fq 'skills/openrouter-delegate/references/delegation-boundary.sh' "$file"; then
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

grep -Fq 'openai/*|anthropic/*' \
  "$ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh" || {
    echo "  FAIL  final wrapper lacks native-vendor pre-network rejection"
    failures=1
  }
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
  grep -Fq -- '--content-file "$RESUME_SNAPSHOT" --content-file "$HANDOFF_SNAPSHOT"' "$file" &&
  grep -Fq 'OPENROUTER_SYSTEM="$(cat "$RESUME_SNAPSHOT")"' "$file" &&
  grep -Fq '< "$HANDOFF_SNAPSHOT"' "$file" || {
    echo "  FAIL  Airlift does not screen and delegate the same artifact snapshots: ${file#"$ROOT/"}"
    failures=1
  }
done

[ "$failures" -eq 0 ] || exit 1
echo "  OK    coherent OpenRouter/Pipeline resolver consumers valid ($MODE)"
