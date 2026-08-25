#!/usr/bin/env bash
# Translate an approved historical manifest in memory. Never rewrites it.
set -euo pipefail
POLICY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/routing-policy.json"
[ "$#" -eq 1 ] && [ -r "$1" ] || { printf '%s\n' 'usage: translate-legacy-executor.sh MANIFEST' >&2; exit 2; }
jq --slurpfile policy "$POLICY" '
  .chunks |= map(
    if (.executorRole? != null) then .
    elif (.executor? | type) == "string" and $policy[0].legacyExecutorTranslation[.executor] != null then
      .executor as $legacy
      | del(.executor) + $policy[0].legacyExecutorTranslation[$legacy]
        + {legacyExecutorTranslation:{occurred:true,sourceField:"executor"}}
    else . end
  )' "$1"
