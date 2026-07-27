#!/usr/bin/env bash
set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)
if [ -z "${PYTHON_BIN:-}" ]; then
  for candidate in python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'
    then
      PYTHON_BIN=$candidate
      break
    fi
  done
fi

if [ -z "${PYTHON_BIN:-}" ]; then
  printf 'QUALITY-PULSE status=failed reason=python_3_12_required\n' >&2
  exit 1
fi

export PYTHONPATH="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references"
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/depot-quality-pulse-pycache"

output=$(
  cd "$REPO_ROOT" &&
    "$PYTHON_BIN" -m unittest -v tests.test_quality_pulse_contract 2>&1
)
status=$?
printf '%s\n' "$output"

if [ "$status" -ne 0 ]; then
  printf '%s\n' "$output" |
    awk '
      /^(FAIL|ERROR): test_QP_[A-Z0-9_]+/ {
        kind = $1
        sub(/:$/, "", kind)
        case_id = $2
        sub(/^test_/, "", case_id)
        gsub(/_/, "-", case_id)
        reason = kind == "FAIL" ? "assertion_failed" : "unexpected_error"
        printf "QUALITY-PULSE case=%s status=failed reason=%s\n", case_id, reason
      }
    ' >&2
  printf 'QUALITY-PULSE status=failed reason=required_case_failed\n' >&2
  exit "$status"
fi

case_count=$(printf '%s\n' "$output" | grep -Ec 'test_QP_[A-Z0-9_]+ .* \.\.\. ok$' || true)
if [ "$case_count" -ne 49 ]; then
  printf 'QUALITY-PULSE status=failed reason=case_inventory_mismatch expected=49 actual=%s\n' "$case_count" >&2
  exit 1
fi

printf 'QUALITY-PULSE status=passed reason=all_required_cases_passed cases=%s\n' "$case_count"
