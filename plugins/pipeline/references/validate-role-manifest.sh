#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 1 ] && [ -r "$1" ] || { printf '%s\n' 'usage: validate-role-manifest.sh MANIFEST' >&2; exit 2; }
jq -e '
  type == "object" and (.chunks | type == "array" and length > 0) and
  ([paths(scalars) as $path
    | select($path[-1] == "executor" or $path[-1] == "model"
      or $path[-1] == "provider" or $path[-1] == "transport")]
    | length == 0) and
  all(.chunks[];
    (.executorRole == "builder-fast" or .executorRole == "builder-deep") and
    (.executorCapabilities | type == "array") and
    all(.executorCapabilities[]; . == "read-repository" or . == "write-repository" or . == "tool-use" or . == "browser" or . == "long-context" or . == "structured-output" or . == "independent-family") and
    (.executorEffort == "low" or .executorEffort == "medium" or .executorEffort == "high" or .executorEffort == "max") and
    (.executor? == null) and (.model? == null) and (.provider? == null) and (.transport? == null) and
    ((.routingOverride? // {}) | (keys - ["executorRole","executorCapabilities","executorEffort","reasonCode","reason"] | length) == 0)
  )' "$1" >/dev/null
