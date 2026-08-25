#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 1 ] && [ -r "$1" ] || { printf '%s\n' 'usage: validate-role-manifest.sh MANIFEST' >&2; exit 2; }
jq -e '
  type == "object" and
  (.feature | type == "string" and length > 0) and
  (.workflowClass | IN("chore","bug","feature","hotfix","security","investigation","migration")) and
  (.decisionProfile | type == "object" and
    (keys | sort) == (["consequence","rationale","uncertainty"] | sort) and
    (.uncertainty | IN("low","medium","high")) and
    (.consequence | IN("low","medium","high")) and
    (.rationale | type == "string" and length > 0)) and
  (.renderedSurface | IN("required","not_applicable")) and
  (.baseBranch | type == "string" and length > 0) and
  (.featureBranch | type == "string" and length > 0) and
  (.branchMode | IN("create","reuse")) and
  has("expectedFeatureHead") and
  ((.branchMode == "create" and (.expectedFeatureHead == null)) or
    (.branchMode == "reuse" and (.expectedFeatureHead | type == "string" and test("^[0-9a-f]{40}$")))) and
  (.finalReviewMode | IN("full","quick")) and
  (.finalReviewRationale | type == "string" and length > 0) and
  (.finalReviewMode != "quick" or .decisionProfile.consequence != "high") and
  (.chunks | type == "array" and length > 0) and
  ([paths(scalars) as $path
    | select($path[-1] == "executor" or $path[-1] == "model"
      or $path[-1] == "provider" or $path[-1] == "transport")]
    | length == 0) and
  all(.chunks[];
    (.id | type == "string" and length > 0) and
    (.level | type == "number" and floor == . and . >= 0) and
    (.title | type == "string" and length > 0) and
    (.prompt | type == "string" and length > 0) and
    (.kind | IN("docs","config","mechanical-logic","logic","ui","integration")) and
    (.renderedSurface | IN("required","not_applicable")) and
    (.renderedSurfaceRationale | type == "string" and length > 0) and
    (.executorRole == "builder-fast" or .executorRole == "builder-deep") and
    (.executorCapabilities | type == "array" and length > 0 and length == (unique | length)) and
    all(.executorCapabilities[]; . == "read-repository" or . == "write-repository" or . == "tool-use" or . == "browser" or . == "long-context" or . == "structured-output" or . == "independent-family") and
    (.executorEffort == "low" or .executorEffort == "medium" or .executorEffort == "high" or .executorEffort == "max") and
    (.filesToModify | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)) and
    (.dependsOn | type == "array" and all(.[]; type == "string" and length > 0)) and
    (.companionSkills | type == "array" and all(.[]; type == "string" and length > 0)) and
    (.estimatedComplexity | IN("low","medium","high")) and
    (.executor? == null) and (.model? == null) and (.provider? == null) and (.transport? == null) and
    ((.routingOverride? // {}) | type == "object" and
      (keys - ["executorRole","executorCapabilities","executorEffort","reasonCode","reason"] | length) == 0 and
      (if length == 0 then true else
        (.reasonCode | type == "string" and length > 0) and
        (.reason | type == "string" and length > 0) and
        (.executorRole == null or (.executorRole | IN("builder-fast","builder-deep"))) and
        (.executorEffort == null or (.executorEffort | IN("low","medium","high","max"))) and
        (.executorCapabilities == null or
          (.executorCapabilities | type == "array" and length > 0 and length == (unique | length) and
            all(.[]; IN("read-repository","write-repository","tool-use","browser","long-context","structured-output","independent-family"))))
       end))
  )' "$1" >/dev/null
