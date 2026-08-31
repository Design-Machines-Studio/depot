#!/usr/bin/env bash
set -euo pipefail
[ "$#" -eq 1 ] && [ -r "$1" ] || { printf '%s\n' 'usage: validate-role-manifest.sh MANIFEST' >&2; exit 2; }
jq -e '
  . as $manifest |
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
  ((has("prototypeParity") | not) and
    (if has("prototypeReference") then
      (.prototypeReference | type == "object" and
        (keys | sort) == (["status","canonicalRepository","commit","authoritySource","prototypeSourceFiles","targetSourceFiles","matchedCases","intentionalDifferences"] | sort) and
        (.status | IN("counterpart","no_counterpart")) and
        (.canonicalRepository | type == "string" and length > 0 and (startswith("/") | not)) and
        (.commit | type == "string" and test("^[0-9a-f]{40}$")) and
        (.authoritySource | type == "string" and length > 0) and
        (.prototypeSourceFiles | type == "array" and length > 0 and length == (unique | length) and all(.[]; type == "string" and length > 0)) and
        (.targetSourceFiles | type == "array" and length == (unique | length) and all(.[]; type == "string" and length > 0)) and
        (.matchedCases | type == "array" and length == (unique | length) and all(.[];
          type == "object" and
          (keys | sort) == (["prototypeRoute","targetRoute","state","viewports"] | sort) and
          (.prototypeRoute | type == "string" and length > 0) and
          (.targetRoute | type == "string" and length > 0) and
          (.state | type == "string" and length > 0) and
          (.viewports | type == "array" and length > 0 and length == (unique | length) and all(.[]; type == "number" and floor == . and . > 0)))) and
        (.intentionalDifferences | type == "array" and length == (unique | length) and all(.[]; type == "string" and length > 0)) and
        (if .status == "counterpart" then
          (.targetSourceFiles | length > 0) and (.matchedCases | length > 0)
        else
          (.targetSourceFiles | length == 0) and (.matchedCases | length == 0)
        end))
    else true end)) and
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
    (.prototypeReference? == null) and
    (if has("prototypeParity") then
      ($manifest.prototypeReference.status == "counterpart") and
      (.renderedSurface == "required") and
      (.prototypeParity | type == "array" and length > 0 and all(.[];
        type == "object" and
        (keys | sort) == (["surface","prototypeSourcePaths","targetSourcePaths","prototypeRoute","targetRoute","state","viewports","sourceDecisions","sourceEvidenceStatus","renderedEvidenceStatus","intentionalDifferences"] | sort) and
        (.surface | type == "string" and length > 0) and
        (.prototypeSourcePaths | type == "array" and length > 0 and length == (unique | length) and all(.[]; type == "string" and length > 0 and IN($manifest.prototypeReference.prototypeSourceFiles[]) )) and
        (.targetSourcePaths | type == "array" and length > 0 and length == (unique | length) and all(.[]; type == "string" and length > 0 and IN($manifest.prototypeReference.targetSourceFiles[]) )) and
        (.prototypeRoute | type == "string" and length > 0) and
        (.targetRoute | type == "string" and length > 0) and
        (.state | type == "string" and length > 0) and
        (.viewports | type == "array" and length > 0 and length == (unique | length) and all(.[]; type == "number" and floor == . and . > 0)) and
        (. as $parity | any($manifest.prototypeReference.matchedCases[];
          .prototypeRoute == $parity.prototypeRoute and
          .targetRoute == $parity.targetRoute and
          .state == $parity.state and
          .viewports == $parity.viewports)) and
        (.sourceDecisions | type == "object" and
          (keys | sort) == (["structure","classes","copy","actions"] | sort) and
          all(.[]; type == "array" and length == (unique | length) and all(.[]; type == "string" and length > 0))) and
        (.sourceEvidenceStatus | IN("pending","complete","unavailable")) and
        (.renderedEvidenceStatus | IN("pending","complete","unavailable")) and
        (.intentionalDifferences | type == "array" and length == (unique | length) and all(.[];
          type == "string" and length > 0 and IN($manifest.prototypeReference.intentionalDifferences[]) ))))
    else true end) and
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
  ) and
  (if has("prototypeReference") then
    if .prototypeReference.status == "counterpart" then
      any(.chunks[]; (.prototypeParity? | type == "array" and length > 0))
    else
      all(.chunks[]; has("prototypeParity") | not)
    end
  else
    all(.chunks[]; has("prototypeParity") | not)
  end)' "$1" >/dev/null
