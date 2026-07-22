#!/usr/bin/env bash
#
# validate-dm-review-codex-perspective.sh -- Ensure dm-review keeps the
# Codex second-opinion reviewer and verify-before-close gates documented.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

failures=0

require_text() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if grep -Fq "$pattern" "$file"; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

reject_text() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if grep -Fq "$pattern" "$file"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
}

sha256_hex() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  else
    printf 'ERROR: sha256sum or shasum is required\n' >&2
    return 1
  fi
}

normalize_fixture_text() {
  LC_ALL=C tr '[:upper:]' '[:lower:]' | awk '{$1=$1; print}'
}

fixture_finding_id() {
  # Arguments 6-11 deliberately model excluded dimensions: reviewer, provider,
  # model, severity, remediation, and discovery order.
  local path anchor line_span category root_cause normalized_key digest
  path=$(printf '%s' "$1" | normalize_fixture_text)
  anchor=$(printf '%s' "$2" | normalize_fixture_text)
  line_span=$(printf '%s' "$3" | normalize_fixture_text)
  category=$(printf '%s' "$4" | normalize_fixture_text)
  root_cause=$(printf '%s' "$5" | normalize_fixture_text)

  if [ -z "$anchor" ]; then
    case "$line_span" in
      *-*) anchor="lines=$line_span" ;;
      *) anchor="lines=$line_span-$line_span" ;;
    esac
  fi

  normalized_key=$(printf 'path=%s\nanchor=%s\ncategory=%s\nroot_cause=%s' \
    "$path" "$anchor" "$category" "$root_cause")
  digest=$(printf '%s' "$normalized_key" | sha256_hex)
  printf 'finding-v1:sha256(%s)' "$digest"
}

validate_synthesis_fixture() {
  local fixture="$1"

  grep -Fqx '### Synthesis Decisions' "$fixture" || return 1
  grep -Eq '^finding_id=finding-v1:sha256\([0-9a-f]{64}\)$' "$fixture" || return 1
  grep -Fqx 'identity_dimensions=path,anchor,category,root_cause' "$fixture" || return 1
  grep -Eq '^identity_dimensions=.*(reviewer|provider|model|severity|remediation|discovery_order)' "$fixture" && return 1
  grep -Eq '^agreement=(unique|corroborated|disputed)$' "$fixture" || return 1

  awk -F= '
    function nonblank(value) {
      return value ~ /[^[:space:]]/
    }
    function valid_finding_id(value) {
      return length(value) == 83 && value ~ /^finding-v1:sha256\([0-9a-f][0-9a-f]*\)$/
    }
    function complete_source() {
      if (!source_seen) return 1
      if (source_id_count != 1 || !nonblank(source_id_value)) return 0
      if (lane_count != 1 || !lane || requested_provider_count != 1 || !requested_provider) return 0
      if (attempted_provider_count != 1 || !attempted_provider || implemented_by_count != 1 || !implemented_by) return 0
      if (model_count != 1 || !model || agent_count != 1 || !agent) return 0
      if (severity_count != 1 || severity !~ /^P[123]$/) return 0
      if (evidence_count != 1 || !evidence || raw_ref_count != 1 || !raw_ref) return 0
      if (disposition_count != 1 || !disposition || reason_count != 1 || !reason) return 0
      if (rationale_count != 1 || !rationale) return 0
      if (disposition !~ /^(retained|merged|discarded)$/) return 0
      if (disposition == "retained" && reason !~ /^retained-(unique|corroborated|disagreement)$/) return 0
      if (disposition == "retained" && agreement == "unique" && reason != "retained-unique") return 0
      if (disposition == "retained" && agreement == "corroborated" && reason != "retained-corroborated") return 0
      if (disposition == "retained" && agreement == "disputed" && reason != "retained-disagreement") return 0
      if (disposition == "merged" && reason !~ /^(exact-duplicate|same-root-cause-merge)$/) return 0
      if (disposition == "discarded" && reason !~ /^(superseded-by-stronger-evidence|out-of-scope|not-reproducible|agent-findings-cap)$/) return 0
      return 1
    }
    /^finding_id=/ { finding_id_count++; finding_id_value=$2; next }
    /^linked_finding_id=/ {
      linked_id_count++
      if (!valid_finding_id($2) || $2 == finding_id_value || linked_ids[$2]++) invalid=1
      next
    }
    /^linked_source=/ {
      linked_source_count++
      if (split($2, linked_source, /\|/) != 2 || !valid_finding_id(linked_source[1]) || !nonblank(linked_source[2])) invalid=1
      if (linked_source_ids[linked_source[2]]++) invalid=1
      linked_source_finding[linked_source[2]]=linked_source[1]
      linked_sources_by_finding[linked_source[1]]++
      next
    }
    /^identity_dimensions=/ { identity_count++; next }
    /^agreement=/ { agreement_count++; agreement=$2; next }
    /^dispute_scope=/ { dispute_scope_count++; dispute_scope=$2; next }
    /^cross_id_link=/ {
      link_count++
      if (split($2, pair, /\|/) != 2 || !valid_finding_id(pair[1]) || !valid_finding_id(pair[2]) || pair[1] == pair[2]) invalid=1
      key=pair[1] SUBSEP pair[2]
      if (links[key]++) invalid=1
      if (pair[1] == finding_id_value || pair[2] == finding_id_value) primary_linked=1
      next
    }
    /^contradiction=/ {
      contradiction_count++; contradiction=nonblank($2)
      if (split($2, positions, /\|/) < 2) invalid=1
      for (position_index in positions) {
        position=positions[position_index]
        if (position !~ /:P[123]$/) invalid=1
        contradiction_source=substr(position, 1, length(position) - 3)
        if (!nonblank(contradiction_source) || contradiction_ids[contradiction_source]++) invalid=1
      }
      next
    }
    /^chosen_severity=/ { chosen_severity_count++; chosen_severity=$2; next }
    /^severity_rationale=/ { severity_rationale_count++; severity_rationale=length($2) > 0; next }
    /^source_id=/ {
      if (source_seen && !complete_source()) exit 1
      source_seen=1; source_count++; source_id_count=1; source_id_value=$2
      if (!nonblank(source_id_value) || seen_source_ids[source_id_value]++) invalid=1
      lane_count=0; lane=0; requested_provider_count=0; requested_provider=0
      attempted_provider_count=0; attempted_provider=0; implemented_by_count=0; implemented_by=0
      model_count=0; model=0; agent_count=0; agent=0; severity_count=0; severity=""
      evidence_count=0; evidence=0; raw_ref_count=0; raw_ref=0
      disposition_count=0; disposition=""; reason_count=0; reason=""; rationale_count=0; rationale=0
      next
    }
    /^lane=/ { lane_count++; lane=length($2) > 0; next }
    /^requested_provider=/ { requested_provider_count++; requested_provider=length($2) > 0; next }
    /^attempted_provider=/ { attempted_provider_count++; attempted_provider=length($2) > 0; next }
    /^implemented_by=/ { implemented_by_count++; implemented_by=length($2) > 0; next }
    /^model=/ { model_count++; model=length($2) > 0; next }
    /^agent=/ { agent_count++; agent=length($2) > 0; next }
    /^source_severity=/ { severity_count++; severity=$2; next }
    /^evidence=/ { evidence_count++; evidence=length($2) > 0; next }
    /^raw_ref=/ { raw_ref_count++; raw_ref=length($2) > 0; next }
    /^finding_disposition=/ { disposition_count++; disposition=$2; next }
    /^decision_reason_code=/ { reason_count++; reason=$2; next }
    /^decision_rationale=/ { rationale_count++; rationale=length($2) > 0; next }
    END {
      if (invalid || finding_id_count != 1 || !valid_finding_id(finding_id_value) || identity_count != 1 || agreement_count != 1) exit 1
      if (!source_seen || !complete_source()) exit 1
      if (agreement == "unique" && source_count != 1) exit 1
      if (agreement == "corroborated" && source_count < 2) exit 1
      if (agreement != "disputed" && (contradiction_count || chosen_severity_count || severity_rationale_count || dispute_scope_count || linked_id_count || linked_source_count || link_count)) exit 1
      if (agreement == "disputed" && (contradiction_count != 1 || !contradiction || chosen_severity_count != 1 || chosen_severity !~ /^P[123]$/ || severity_rationale_count != 1 || !severity_rationale)) exit 1
      if (agreement == "disputed" && dispute_scope_count != 1) exit 1
      if (dispute_scope == "cross-id" && (source_count < 1 || linked_id_count < 1 || linked_source_count < 1 || link_count < 2 || !primary_linked)) exit 1
      if (dispute_scope == "within-id" && (source_count < 2 || linked_id_count || linked_source_count || link_count)) exit 1
      if (agreement == "disputed" && dispute_scope !~ /^(cross-id|within-id)$/) exit 1
      for (contradiction_source in contradiction_ids) {
        if (!seen_source_ids[contradiction_source] && !linked_source_ids[contradiction_source]) exit 1
      }
      for (linked_source_id in linked_source_finding) {
        linked_target=linked_source_finding[linked_source_id]
        if (!linked_ids[linked_target] || seen_source_ids[linked_source_id] || !contradiction_ids[linked_source_id]) exit 1
        if (!links[finding_id_value SUBSEP linked_target] || !links[linked_target SUBSEP finding_id_value]) exit 1
      }
      for (linked_id in linked_ids) {
        if (!linked_sources_by_finding[linked_id]) exit 1
      }
      for (link in links) {
        split(link, endpoints, SUBSEP)
        reverse=endpoints[2] SUBSEP endpoints[1]
        if (!links[reverse]) exit 1
        if (endpoints[1] != finding_id_value && !linked_ids[endpoints[1]]) exit 1
        if (endpoints[2] != finding_id_value && !linked_ids[endpoints[2]]) exit 1
      }
    }
  ' "$fixture"
}

expect_fixture_rejected() {
  local fixture="$1"
  local label="$2"

  if validate_synthesis_fixture "$fixture"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
}

review_skill="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
consolidator="$REPO_ROOT/plugins/dm-review/agents/workflow/review-consolidator.md"
registry="$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md"
codex_agent="$REPO_ROOT/plugins/dm-review/agents/review/codex-perspective.md"
guardrails="$REPO_ROOT/plugins/dm-review/skills/review/references/guardrails.md"
output_format="$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md"
issue_tracking="$REPO_ROOT/plugins/dm-review/skills/review/references/issue-tracking.md"
graceful_degradation="$REPO_ROOT/plugins/dm-review/skills/review/references/graceful-degradation.md"

require_text "$review_skill" "codex-perspective" "review skill selects codex-perspective reviewer"
require_text "$review_skill" "codex exec -s read-only -c service_tier=fast --skip-git-repo-check" "review skill documents known-good Codex invocation"
require_text "$review_skill" "service_tier=fast" "review skill forces fast tier override"
require_text "$review_skill" "Verify-before-close" "review skill gates stale/already-fixed dispositions"
require_text "$review_skill" "code-evidence re-verification at HEAD" "review skill requires HEAD evidence before stale closeout"
require_text "$consolidator" "merge findings from both" "consolidator merges dual-perspective findings"
require_text "$consolidator" "a finding from either coding provider is in-scope" "consolidator treats either coding provider as actionable"
require_text "$registry" "codex-perspective" "agent registry includes codex-perspective"
require_text "$codex_agent" "Normalize output to P1/P2/P3" "codex-perspective agent normalizes output"
require_text "$consolidator" 'finding-v1:sha256(<normalized-key>)' "consolidator defines canonical finding ID"
require_text "$consolidator" "lowercase POSIX path" "consolidator normalizes POSIX path"
require_text "$consolidator" "smallest stable structural anchor" "consolidator prefers stable structural anchor"
require_text "$consolidator" "normalized line span only if no anchor exists" "consolidator limits line-span identity fallback"
require_text "$consolidator" "Exclude reviewer, provider, model, severity, remediation, and discovery order" "identity excludes unstable dimensions"
require_text "$consolidator" 'agreement: unique' "consolidator separates agreement classification"
require_text "$consolidator" 'finding_disposition: retained|merged|discarded' "consolidator records independent source disposition"
require_text "$consolidator" 'exact-duplicate' "consolidator closes exact duplicate reason"
require_text "$consolidator" 'same-root-cause-merge' "consolidator closes root-cause merge reason"
require_text "$consolidator" 'superseded-by-stronger-evidence' "consolidator closes stronger-evidence reason"
require_text "$consolidator" 'out-of-scope' "consolidator closes out-of-scope reason"
require_text "$consolidator" 'not-reproducible' "consolidator closes non-reproducible reason"
require_text "$consolidator" 'agent-findings-cap' "consolidator closes findings-cap reason"
require_text "$consolidator" 'retained-disagreement' "consolidator retains unresolved disagreement"
require_text "$consolidator" "Contradictions never disappear" "consolidator preserves contradictions"
require_text "$consolidator" 'cross_id_link=<finding-id>|<finding-id>' "consolidator links cross-ID disputes"
require_text "$consolidator" "Emit each unordered dispute pair in both directions" "cross-ID dispute links are reciprocal"
require_text "$consolidator" "severity disagreement changes the decision ledger, not identity" "severity disagreement does not change identity"
require_text "$consolidator" "test/runtime evidence" "deterministic evidence outranks consensus"
require_text "$consolidator" 'raw_ref' "consolidator requires raw artifact references"
require_text "$output_format" '### Synthesis Decisions' "report contains compact synthesis section"
require_text "$output_format" "implemented-by=\`Codex\`" "disputed example exposes fallback implementer"
require_text "$output_format" "evidence=\`runtime test reproduces unsafe write\`" "disputed example exposes source evidence"
require_text "$output_format" "rationale=\`runtime evidence establishes this root cause\`" "disputed example exposes per-source rationale"
require_text "$output_format" "\`decision_reason_code\`" "report exposes closed decision reasons"
require_text "$guardrails" "free-form reason codes" "guardrails reject invalid reason codes"
require_text "$guardrails" "cross-ID dispute links; flattened" "guardrails reject flattened contradictions"
require_text "$guardrails" "severity-derived IDs" "guardrails reject severity-derived IDs"
require_text "$guardrails" "missing raw refs" "guardrails reject missing raw references"
require_text "$guardrails" 'Synthesis Decisions' "guardrails reject missing synthesis section"
require_text "$review_skill" "Per chunk during pipeline execution" "ordinary Pipeline chunks remain quick-tier"
reject_text "$review_skill" "Per chunk during pipeline execution** | full \`dm-review\`" "ordinary Pipeline chunks do not require full review"
require_text "$issue_tracking" '{id}-{status}-{priority}-{slug}.md' "todo filename contract remains compatible"
require_text "$issue_tracking" 'source_agents:' "todo source_agents metadata remains compatible"
require_text "$consolidator" 'Coverage Gaps' "coverage gaps remain explicit"
require_text "$graceful_degradation" 'REVIEW INCOMPLETE' "core-lane incomplete behavior remains compatible"
require_text "$graceful_degradation" 'Degraded: all conditional agents unavailable' "degraded-lane behavior remains compatible"
require_text "$output_format" 'P3-only is NOT clean' "zero-deferral recommendation remains compatible"

printf "Synthesis identity fixtures\n"
base_id=$(fixture_finding_id \
  'plugins/dm-review/skills/review/SKILL.md' 'Phase 5: Consolidation' '620-640' \
  'Evidence Loss' 'Raw reviewer artifact is not retained' \
  'agent-a' 'Codex' 'gpt-5' 'P1' 'retain raw output' '1')
permuted_id=$(fixture_finding_id \
  'PLUGINS/DM-REVIEW/SKILLS/REVIEW/SKILL.MD' '  phase  5: consolidation ' '620-640' \
  ' evidence loss ' 'raw reviewer   artifact is not retained' \
  'agent-z' 'OpenRouter' 'z-ai/glm-5.2' 'P3' 'rewrite summary' '99')
severity_only_id=$(fixture_finding_id \
  'plugins/dm-review/skills/review/SKILL.md' 'Phase 5: Consolidation' '620-640' \
  'Evidence Loss' 'Raw reviewer artifact is not retained' \
  'agent-a' 'Codex' 'gpt-5' 'P2' 'different remediation' '2')
different_root_id=$(fixture_finding_id \
  'plugins/dm-review/skills/review/SKILL.md' 'Phase 5: Consolidation' '620-640' \
  'Evidence Loss' 'Raw reviewer artifact is deleted after consolidation' \
  'agent-a' 'Codex' 'gpt-5' 'P1' 'retain raw output' '1')
line_fallback_id=$(fixture_finding_id \
  'plugins/dm-review/skills/review/SKILL.md' '' '620' \
  'Evidence Loss' 'Raw reviewer artifact is not retained' \
  'agent-a' 'Codex' 'gpt-5' 'P1' 'retain raw output' '1')

if [ "$base_id" = "$permuted_id" ] && [ "$base_id" = "$severity_only_id" ]; then
  printf "  OK    excluded dimensions and input normalization preserve identity\n"
else
  printf "  FAIL  excluded dimensions and input normalization preserve identity\n"
  failures=1
fi
if [ "$base_id" != "$different_root_id" ]; then
  printf "  OK    distinct root causes remain separate\n"
else
  printf "  FAIL  distinct root causes remain separate\n"
  failures=1
fi
if printf '%s' "$line_fallback_id" | grep -Eq '^finding-v1:sha256\([0-9a-f]{64}\)$'; then
  printf "  OK    line-span fallback produces canonical identity\n"
else
  printf "  FAIL  line-span fallback produces canonical identity\n"
  failures=1
fi

decision_order_a=$(printf '%s\n' 'source-z|merged|exact-duplicate' 'source-a|retained|retained-corroborated' | LC_ALL=C sort)
decision_order_b=$(printf '%s\n' 'source-a|retained|retained-corroborated' 'source-z|merged|exact-duplicate' | LC_ALL=C sort)
if [ "$decision_order_a" = "$decision_order_b" ]; then
  printf "  OK    input permutations preserve decision ordering\n"
else
  printf "  FAIL  input permutations preserve decision ordering\n"
  failures=1
fi

fixture_dir=$(mktemp -d "${TMPDIR:-/tmp}/dm-review-synthesis.XXXXXX")
trap 'rm -rf "$fixture_dir"' EXIT
cat >"$fixture_dir/valid" <<EOF
### Synthesis Decisions
finding_id=$base_id
identity_dimensions=path,anchor,category,root_cause
agreement=disputed
dispute_scope=cross-id
linked_finding_id=$different_root_id
linked_source=$different_root_id|source-linked
cross_id_link=$base_id|$different_root_id
cross_id_link=$different_root_id|$base_id
contradiction=source-a:P1|source-linked:P3
chosen_severity=P1
severity_rationale=runtime evidence outranks consensus
source_id=source-a
lane=codex-native
requested_provider=Codex
attempted_provider=Codex
implemented_by=Codex
model=gpt-5
agent=agent-a
source_severity=P1
evidence=reproducible runtime failure
raw_ref=raw/agent-a.md#finding-1
finding_disposition=retained
decision_reason_code=retained-disagreement
decision_rationale=runtime evidence retains this position
source_id=source-b
lane=openrouter
requested_provider=OpenRouter
attempted_provider=OpenRouter
implemented_by=OpenRouter
model=z-ai/glm-5.2
agent=agent-b
source_severity=P1
evidence=matching direct source inspection
raw_ref=raw/agent-b.md#finding-4
finding_disposition=merged
decision_reason_code=exact-duplicate
decision_rationale=normalized issue identity is identical
source_id=source-c
lane=openrouter-fallback
requested_provider=OpenRouter
attempted_provider=OpenRouter
implemented_by=Codex
model=gpt-5
agent=agent-c
source_severity=P3
evidence=non-reproducing static hypothesis
raw_ref=raw/agent-c.md#finding-2
finding_disposition=discarded
decision_reason_code=superseded-by-stronger-evidence
decision_rationale=runtime reproduction disproves the source position
EOF

if validate_synthesis_fixture "$fixture_dir/valid"; then
  printf "  OK    valid disputed reciprocal links accepted\n"
else
  printf "  FAIL  valid disputed reciprocal links accepted\n"
  failures=1
fi

sed '/^decision_reason_code=/d' "$fixture_dir/valid" >"$fixture_dir/missing-reason"
expect_fixture_rejected "$fixture_dir/missing-reason" "missing reason codes rejected"
sed '/^contradiction=/d' "$fixture_dir/valid" >"$fixture_dir/flat-contradiction"
expect_fixture_rejected "$fixture_dir/flat-contradiction" "flattened contradictions rejected"
sed 's/identity_dimensions=path,anchor,category,root_cause/identity_dimensions=path,anchor,category,root_cause,severity/' "$fixture_dir/valid" >"$fixture_dir/severity-id"
expect_fixture_rejected "$fixture_dir/severity-id" "severity-derived identity rejected"
awk 'BEGIN { skipped=0 } /^raw_ref=/ && !skipped { skipped=1; next } { print }' "$fixture_dir/valid" >"$fixture_dir/missing-raw-ref"
expect_fixture_rejected "$fixture_dir/missing-raw-ref" "missing raw references rejected"
sed '/^### Synthesis Decisions$/d' "$fixture_dir/valid" >"$fixture_dir/missing-section"
expect_fixture_rejected "$fixture_dir/missing-section" "missing synthesis section rejected"
awk 'BEGIN { changed=0 } /^decision_reason_code=retained-disagreement$/ && !changed { print "decision_reason_code=majority-wins"; changed=1; next } { print }' "$fixture_dir/valid" >"$fixture_dir/free-form-reason"
expect_fixture_rejected "$fixture_dir/free-form-reason" "free-form reason codes rejected"
awk 'BEGIN { changed=0 } /^source_id=source-a$/ && !changed { print "source_id="; changed=1; next } { print }' "$fixture_dir/valid" >"$fixture_dir/empty-source-id"
expect_fixture_rejected "$fixture_dir/empty-source-id" "empty source IDs rejected"
awk 'BEGIN { skipped=0 } /^source_severity=/ && !skipped { skipped=1; next } { print }' "$fixture_dir/valid" >"$fixture_dir/missing-source-severity"
expect_fixture_rejected "$fixture_dir/missing-source-severity" "missing source severity rejected"
awk '
  /^agreement=/ { print "agreement=corroborated"; next }
  /^dispute_scope=|^linked_finding_id=|^linked_source=|^cross_id_link=|^contradiction=|^chosen_severity=|^severity_rationale=/ { next }
  /^decision_reason_code=retained-disagreement$/ { print "decision_reason_code=retained-corroborated"; next }
  /^source_id=source-b$/ { exit }
  { print }
' "$fixture_dir/valid" >"$fixture_dir/one-source-corroborated"
expect_fixture_rejected "$fixture_dir/one-source-corroborated" "one-source corroborated agreement rejected"
awk '
  /^agreement=/ { print "agreement=unique"; next }
  /^dispute_scope=|^linked_finding_id=|^linked_source=|^cross_id_link=|^contradiction=|^chosen_severity=|^severity_rationale=/ { next }
  /^decision_reason_code=retained-disagreement$/ { print "decision_reason_code=retained-unique"; next }
  { print }
' "$fixture_dir/valid" >"$fixture_dir/multi-source-unique"
expect_fixture_rejected "$fixture_dir/multi-source-unique" "multi-source unique agreement rejected"
awk '
  /^agreement=/ { print "agreement=unique"; next }
  /^decision_reason_code=retained-disagreement$/ { print "decision_reason_code=retained-unique"; next }
  /^source_id=source-b$/ { exit }
  { print }
' "$fixture_dir/valid" >"$fixture_dir/unique-with-contradiction"
expect_fixture_rejected "$fixture_dir/unique-with-contradiction" "unique agreement with contradiction metadata rejected"
awk 'BEGIN { inserted=0 } /^decision_reason_code=retained-disagreement$/ && !inserted { print "decision_reason_code=majority-wins"; inserted=1 } { print }' "$fixture_dir/valid" >"$fixture_dir/duplicate-unknown-reason"
expect_fixture_rejected "$fixture_dir/duplicate-unknown-reason" "duplicate reason field with unknown value rejected"
awk -v reverse="cross_id_link=$different_root_id|$base_id" '$0 != reverse { print }' "$fixture_dir/valid" >"$fixture_dir/one-way-cross-id"
expect_fixture_rejected "$fixture_dir/one-way-cross-id" "one-way cross-ID dispute rejected"
sed '/^cross_id_link=/d' "$fixture_dir/valid" >"$fixture_dir/missing-cross-id"
expect_fixture_rejected "$fixture_dir/missing-cross-id" "missing cross-ID dispute links rejected"
sed '/^linked_finding_id=/d' "$fixture_dir/valid" >"$fixture_dir/dangling-cross-id"
expect_fixture_rejected "$fixture_dir/dangling-cross-id" "cross-ID links to missing findings rejected"
sed 's/source-linked:P3/source-missing:P3/' "$fixture_dir/valid" >"$fixture_dir/unresolved-contradiction-source"
expect_fixture_rejected "$fixture_dir/unresolved-contradiction-source" "unresolved contradiction source IDs rejected"
awk -v reverse="cross_id_link=$different_root_id|$base_id" -v self="cross_id_link=$base_id|$base_id" '$0 == reverse { print self; next } { print }' "$fixture_dir/valid" >"$fixture_dir/self-cross-id"
expect_fixture_rejected "$fixture_dir/self-cross-id" "self-referential cross-ID dispute rejected"
sed 's/^source_id=source-b$/source_id=source-a/' "$fixture_dir/valid" >"$fixture_dir/duplicate-source-id"
expect_fixture_rejected "$fixture_dir/duplicate-source-id" "duplicate source IDs rejected"

if [ "$failures" -ne 0 ]; then
  printf "FIX  restore dm-review perspective and synthesis provenance contracts\n"
  exit 1
fi

printf "OK    dm-review codex-perspective reviewer documented\n"
