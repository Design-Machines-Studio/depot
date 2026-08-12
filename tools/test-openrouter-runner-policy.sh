#!/usr/bin/env bash
# Focused configured-key OpenRouter runner regressions. Network activity is
# restricted to the loopback fixture in tests/test_openrouter_noninteractive.py.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/tests/test_openrouter_noninteractive.py" -v
printf '%s\n' "OK    configured-key OpenRouter runner policy fixtures passed"
