#!/usr/bin/env bash
# ui-review-contract.sh -- deterministic source/rendered UI disposition and case selection.
#
# This helper does not start applications, navigate browsers, or dispatch models.
# It projects one shared readiness result into the three existing logical UI
# lanes and selects a bounded browser case set from explicit review inputs.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

ACTION="${1:-}"
[ "$#" -gt 0 ] && shift
REQUEST_FILE=""
READINESS_FILE=""
EVIDENCE_VALIDATION_FILE=""

usage() {
  printf '%s\n' 'ui-review-contract: invalid invocation' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --request) [ "$#" -ge 2 ] || usage; REQUEST_FILE="$2"; shift 2 ;;
    --readiness-result) [ "$#" -ge 2 ] || usage; READINESS_FILE="$2"; shift 2 ;;
    --evidence-validation-result) [ "$#" -ge 2 ] || usage; EVIDENCE_VALIDATION_FILE="$2"; shift 2 ;;
    *) usage ;;
  esac
done

case "$ACTION" in plan|select-cases) ;; *) usage ;; esac
command -v jq >/dev/null 2>&1 || exit 76
[ -f "$REQUEST_FILE" ] && [ ! -L "$REQUEST_FILE" ] || usage

if [ "$ACTION" = plan ]; then
  [ -f "$READINESS_FILE" ] && [ ! -L "$READINESS_FILE" ] || usage
  jq -e '
    type == "object" and
    (keys | sort) == (["applicableLanes","renderedEvidenceRequired","schemaVersion","templateExtensionsOnly"] | sort) and
    .schemaVersion == 1 and
    (.renderedEvidenceRequired | type) == "boolean" and
    (.templateExtensionsOnly | type) == "boolean" and
    (.applicableLanes | type == "array" and length > 0 and length <= 3 and length == (unique | length) and
      all(.[]; . == "ui-standards-reviewer" or . == "ux-quality-reviewer" or . == "visual-browser-tester"))
  ' "$REQUEST_FILE" >/dev/null 2>&1 || usage

  readiness_reason="$(jq -r '.reason // "browser_transport_unavailable"' "$READINESS_FILE")"
  case "$readiness_reason" in
    available|visual_target_unavailable|dev_server_unavailable|browser_transport_unavailable|model_participant_unavailable|resource_cleanup_failed) ;;
    *) readiness_reason=browser_transport_unavailable ;;
  esac
  rendered_required="$(jq -r '.renderedEvidenceRequired' "$REQUEST_FILE")"
  applicable_lanes="$(jq -c '.applicableLanes' "$REQUEST_FILE")"
  evidence_ref=""
  if [ "$readiness_reason" = available ] && [ -n "$EVIDENCE_VALIDATION_FILE" ] &&
     [ -f "$EVIDENCE_VALIDATION_FILE" ] && [ ! -L "$EVIDENCE_VALIDATION_FILE" ]; then
    evidence_ref="$(jq -r 'select(.status == "accepted") | .evidenceRef // empty' "$EVIDENCE_VALIDATION_FILE")"
  fi

  if [ -n "$evidence_ref" ]; then
    jq -cn --arg evidence_ref "$evidence_ref" --argjson applicable "$applicable_lanes" '
      {schemaVersion:1,readinessDecision:"available",reviewDisposition:"completed",
       lanes:([
         {lane:"ui-standards-reviewer",status:"RUN",evidenceMode:"source+rendered",evidenceRef:$evidence_ref},
         {lane:"ux-quality-reviewer",status:"RUN",evidenceMode:"source+rendered",evidenceRef:$evidence_ref},
         {lane:"visual-browser-tester",status:"RUN",evidenceMode:"rendered",evidenceRef:$evidence_ref}
       ] | map(select(.lane as $lane | $applicable | index($lane) != null))),browserCoverage:null,nextActions:[]}'
    exit 0
  fi

  # A ready target with rejected/missing packet is an evidence transport gap;
  # source-capable analysis still runs and rendered proof remains honest.
  [ "$readiness_reason" != available ] || readiness_reason=browser_transport_unavailable
  if [ "$rendered_required" = true ]; then
    case "$readiness_reason" in
      visual_target_unavailable) next_action='supply one exact target URL, declared start target, or matching completed evidence packet' ;;
      dev_server_unavailable) next_action='restore the one exact declared application consumer or supply matching completed evidence' ;;
      browser_transport_unavailable) next_action='attach one local interactive browser or supply the explicit matching completed evidence packet' ;;
      model_participant_unavailable) next_action='restore one eligible provider-neutral UI analysis participant' ;;
      resource_cleanup_failed) next_action='run only the recorded repository-owned cleanup and inspect that resource' ;;
    esac
    jq -cn --arg reason "$readiness_reason" --arg next_action "$next_action" --argjson applicable "$applicable_lanes" '
      {schemaVersion:1,readinessDecision:$reason,reviewDisposition:"REVIEW INCOMPLETE",
       lanes:([
         {lane:"ui-standards-reviewer",status:"RUN",evidenceMode:"source-only",evidenceRef:null},
         {lane:"ux-quality-reviewer",status:"RUN",evidenceMode:"source-only",evidenceRef:null},
         {lane:"visual-browser-tester",status:"NOT RUN",evidenceMode:"rendered",evidenceRef:null}
       ] | map(select(.lane as $lane | $applicable | index($lane) != null))),browserCoverage:{reason:$reason,status:"REVIEW INCOMPLETE"},nextActions:[$next_action]}'
  else
    jq -cn --arg reason "$readiness_reason" --argjson applicable "$applicable_lanes" '
      {schemaVersion:1,readinessDecision:$reason,reviewDisposition:"completed",
       lanes:([
         {lane:"ui-standards-reviewer",status:"RUN",evidenceMode:"source-only",evidenceRef:null},
         {lane:"ux-quality-reviewer",status:"RUN",evidenceMode:"source-only",evidenceRef:null},
         {lane:"visual-browser-tester",status:"NOT RUN",evidenceMode:"rendered",evidenceRef:null}
       ] | map(select(.lane as $lane | $applicable | index($lane) != null))),browserCoverage:{reason:$reason,status:"NOT RUN"},nextActions:[]}'
  fi
  exit 0
fi

jq -e '
  type == "object" and
  (keys | sort) == (["acceptanceCaseIds","affectedEngines","affectedPersonas","affectedStates","affectedViewports","baselineCaseId","cases","changedRenderedFiles","changedRoutes","fullMatrixRequirement","prototypeParityCaseIds","reviewKind","schemaVersion"] | sort) and
  .schemaVersion == 1 and
  (.reviewKind == "ordinary" or .reviewKind == "full") and
  (.fullMatrixRequirement == "none" or .fullMatrixRequirement == "explicit-sweep" or
   .fullMatrixRequirement == "release-profile" or .fullMatrixRequirement == "shared-surface") and
  ([.changedRenderedFiles,.changedRoutes,.prototypeParityCaseIds,.acceptanceCaseIds,
    .affectedPersonas,.affectedStates,.affectedEngines,.affectedViewports] |
    all(.[]; type == "array" and length == (unique | length) and all(.[]; type == "string" and length > 0 and length <= 256))) and
  (.baselineCaseId == null or (.baselineCaseId | type == "string" and length > 0 and length <= 128)) and
  (.cases | type == "array" and length == (map(.id) | unique | length) and all(.[];
    type == "object" and
    (keys | sort) == (["engine","id","persona","renderedFiles","route","state","viewport"] | sort) and
    (.id,.engine,.persona,.route,.state,.viewport | type == "string" and length > 0 and length <= 256) and
    (.renderedFiles | type == "array" and length == (unique | length) and all(.[]; type == "string" and length > 0 and length <= 256))))
' "$REQUEST_FILE" >/dev/null 2>&1 || usage

jq -c '
  def intersects($a; $b): any($a[]; . as $x | any($b[]; . == $x));
  def allowed($value; $affected): ($affected | length == 0) or ($affected | index($value) != null);
  . as $r |
  ($r.fullMatrixRequirement != "none") as $full |
  [ $r.cases[] |
    . as $case |
    ((($r.prototypeParityCaseIds + $r.acceptanceCaseIds) | index($case.id)) != null) as $explicit |
    select($full or $explicit or
      (((($r.changedRoutes | index($case.route)) != null) or
        intersects($case.renderedFiles; $r.changedRenderedFiles) or
        ($r.baselineCaseId == $case.id)) and
      allowed($case.persona; $r.affectedPersonas) and
      allowed($case.state; $r.affectedStates) and
      allowed($case.engine; $r.affectedEngines) and
      allowed($case.viewport; $r.affectedViewports)))
  ] as $selected |
  {schemaVersion:1,selectionMode:(if $full then "full-matrix" else "affected-cases" end),
   fullMatrixReason:(if $full then $r.fullMatrixRequirement else null end),
   selectedCaseIds:($selected | map(.id) | sort),cases:($selected | sort_by(.id))}
' "$REQUEST_FILE"
