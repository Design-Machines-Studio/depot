#!/usr/bin/env bash
# external-finding-settlement.sh -- prove every selected external candidate was decided.
#
# Candidate selection and current-code evaluation are host judgment. This
# validator only enforces complete provenance, closed synthesis decisions, an
# exact-head binding, and a repair/evidence reference for every outcome.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

INTAKE=""
DECISIONS=""
CURRENT_HEAD=""

usage() {
  printf '%s\n' 'usage: external-finding-settlement.sh --intake FILE --decisions FILE --current-head SHA' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --intake) [ "$#" -ge 2 ] || usage; INTAKE="$2"; shift 2 ;;
    --decisions) [ "$#" -ge 2 ] || usage; DECISIONS="$2"; shift 2 ;;
    --current-head) [ "$#" -ge 2 ] || usage; CURRENT_HEAD="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[ -f "$INTAKE" ] && [ ! -L "$INTAKE" ] && [ -f "$DECISIONS" ] && [ ! -L "$DECISIONS" ] || usage
printf '%s' "$CURRENT_HEAD" | grep -Eq '^[0-9a-f]{40}$' || usage
command -v jq >/dev/null 2>&1 || exit 76

jq -e --arg head "$CURRENT_HEAD" '
  .schema_version == 1 and .artifact_role == "external_finding_intake" and
  .collection_status == "complete" and .inspected_head == $head and
  (.instructions_policy == "untrusted_evidence_only") and
  ([.pull_request.source_id, .surfaces[].items[].source_id] as $ids | ($ids | length) == ($ids | unique | length))
' "$INTAKE" >/dev/null || { printf '%s\n' 'external-finding-settlement: intake incomplete or head changed' >&2; exit 1; }

jq -e --arg head "$CURRENT_HEAD" --slurpfile intake "$INTAKE" '
  def source_ids: [$intake[0].pull_request.source_id, $intake[0].surfaces[].items[].source_id];
  def retained_code: . == "retained-unique" or . == "retained-corroborated" or . == "retained-disagreement";
  def merged_code: . == "exact-duplicate" or . == "same-root-cause-merge";
  def discarded_code: . == "superseded-by-stronger-evidence" or . == "out-of-scope" or . == "not-reproducible" or . == "agent-findings-cap";
  source_ids as $known_source_ids |
  .decisions as $decisions |
  .source_evidence_index as $source_index |
  (.schema_version == 1 and .artifact_role == "external_finding_decisions" and
  .repository == $intake[0].repository and .pr_number == $intake[0].pr_number and
  .inspected_head == $head and .collection_cutoff == $intake[0].collection_cutoff and
  (.decisions | type == "array" and length == (map(.source_finding_id) | unique | length)) and
  ($source_index | type == "array" and length == ($known_source_ids | length) and
    (map(.source_id) | sort) == ($known_source_ids | sort) and
    length == (map(.source_id) | unique | length) and
    all(.[]; . as $source |
      ($source.rationale | type == "string" and length > 0) and
      ($source.candidate_source_finding_ids | type == "array" and length == (unique | length) and
        all(.[]; . as $candidate_id |
          any($decisions[]; .source_finding_id == $candidate_id and (.source_ids | index($source.source_id) != null)))))) and
  all(.decisions[];
    . as $decision |
    ($decision.source_finding_id | type == "string" and length > 0) and
    ($decision.source_ids | type == "array" and length > 0 and length == (unique | length) and
      all(.[]; . as $source_id | ($known_source_ids | index($source_id)) != null and
        any($source_index[]; .source_id == $source_id and (.candidate_source_finding_ids | index($decision.source_finding_id) != null)))) and
    ($decision.finding_id | test("^finding-v1:sha256\\([0-9a-f]{64}\\)$")) and
    ($decision.evidence_ref | type == "string" and length > 0) and
    ($decision.current_head_evidence_ref | type == "string" and length > 0) and
    ($decision.rationale | type == "string" and length > 0) and
    if $decision.finding_disposition == "retained" then
      ($decision.decision_reason_code | retained_code) and ($decision.repair_ref | type == "string" and length > 0)
    elif $decision.finding_disposition == "merged" then
      ($decision.decision_reason_code | merged_code) and
      ($decision.merged_into_finding_id | test("^finding-v1:sha256\\([0-9a-f]{64}\\)$")) and
      ($decision.merged_into_finding_id != $decision.finding_id) and
      (any($decisions[]; .finding_disposition == "retained" and .finding_id == $decision.merged_into_finding_id) or
        ($decision.merged_target_evidence_ref | type == "string" and length > 0))
    elif $decision.finding_disposition == "discarded" then
      ($decision.decision_reason_code | discarded_code)
    else false end))
' "$DECISIONS" >/dev/null || { printf '%s\n' 'external-finding-settlement: unprocessed or invalid decision' >&2; exit 1; }

jq -c '{status:"settled",considered:(.decisions|length),retained:([.decisions[]|select(.finding_disposition=="retained")]|length),merged:([.decisions[]|select(.finding_disposition=="merged")]|length),discarded:([.decisions[]|select(.finding_disposition=="discarded")]|length)}' "$DECISIONS"
