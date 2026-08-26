#!/usr/bin/env bash
# Read-only human-facing recommendation projection. Never dispatches a model.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$DIR/role-policy.json"
MATRIX=""
AVAILABILITY_FILE=""
WORKFLOW_KERNEL_LAUNCHER=""
ROLE=""
EFFORT=""
FORMAT=markdown
CAPABILITIES=()

usage() {
  printf '%s\n' 'usage: operator-recommendation --role ROLE --capability CAP [--capability CAP ...] --effort EFFORT --matrix-file PATH [--availability-file PATH | --workflow-kernel PATH] [--format markdown|json]' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --role) [ "$#" -ge 2 ] || usage; ROLE="$2"; shift 2 ;;
    --capability) [ "$#" -ge 2 ] || usage; CAPABILITIES+=("$2"); shift 2 ;;
    --effort) [ "$#" -ge 2 ] || usage; EFFORT="$2"; shift 2 ;;
    --matrix-file) [ "$#" -ge 2 ] || usage; MATRIX="$2"; shift 2 ;;
    --availability-file) [ "$#" -ge 2 ] || usage; AVAILABILITY_FILE="$2"; shift 2 ;;
    --workflow-kernel) [ "$#" -ge 2 ] || usage; WORKFLOW_KERNEL_LAUNCHER="$2"; shift 2 ;;
    --policy-file)
      [ "${MODEL_ROUTER_TEST_MODE:-0}" = 1 ] && [ "$#" -ge 2 ] || usage
      POLICY="$2"; shift 2 ;;
    --format) [ "$#" -ge 2 ] || usage; FORMAT="$2"; shift 2 ;;
    *) usage ;;
  esac
done

case "$ROLE" in architect|plan-critic|builder-fast|builder-deep|review-fast|review-deep|security-review|research-fast|editorial) ;; *) usage ;; esac
case "$EFFORT" in low|medium|high|max) ;; *) usage ;; esac
case "$FORMAT" in markdown|json) ;; *) usage ;; esac
[ -r "$POLICY" ] && [ ! -L "$POLICY" ] && jq -e '.schemaVersion == 1' "$POLICY" >/dev/null || usage
[ -r "$MATRIX" ] && [ ! -L "$MATRIX" ] && jq -e '.schema_version == 1 and (.snapshot_date | type) == "string"' "$MATRIX" >/dev/null || usage
[ -z "$AVAILABILITY_FILE" ] || [ -z "$WORKFLOW_KERNEL_LAUNCHER" ] || usage

CAPABILITIES_JSON='[]'
for capability in "${CAPABILITIES[@]}"; do
  case "$capability" in read-repository|write-repository|tool-use|browser|long-context|structured-output|independent-family) ;; *) usage ;; esac
  CAPABILITIES_JSON="$(printf '%s' "$CAPABILITIES_JSON" | jq -c --arg value "$capability" '. + [$value] | unique | sort')"
done

if [ -n "$AVAILABILITY_FILE" ]; then
  [ -r "$AVAILABILITY_FILE" ] && [ ! -L "$AVAILABILITY_FILE" ] || usage
  AVAILABILITY="$(jq -c . "$AVAILABILITY_FILE")" || usage
else
  case "$WORKFLOW_KERNEL_LAUNCHER" in /*/workflow-kernel-launcher.sh) ;; *) usage ;; esac
  [ -f "$WORKFLOW_KERNEL_LAUNCHER" ] && [ -x "$WORKFLOW_KERNEL_LAUNCHER" ] && [ ! -L "$WORKFLOW_KERNEL_LAUNCHER" ] || usage
  AVAILABILITY="$(WORKFLOW_KERNEL="$WORKFLOW_KERNEL_LAUNCHER" "$DIR/availability-probe.sh")" || AVAILABILITY='{}'
fi

candidate_status() {
  local candidate="$1" transport model rate_limit_id auth state
  transport="$(printf '%s' "$candidate" | jq -r '.transport')"
  model="$(printf '%s' "$candidate" | jq -r '.model')"
  case "$transport" in
    codex-cli)
      auth="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.authMode // .codex.auth_mode // "unknown"')"
      [ "$auth" = subscription ] || { printf unavailable; return; }
      rate_limit_id="$(printf '%s' "$candidate" | jq -r '.rateLimitId // empty')"
      if [ -n "$rate_limit_id" ]; then
        state="$(printf '%s' "$AVAILABILITY" | jq -r --arg id "$rate_limit_id" '.codex.allowances[$id].state // "unknown"')"
        case "$state" in ok) printf available ;; limited) printf unavailable ;; *) printf unknown ;; esac
      elif [ "$(printf '%s' "$AVAILABILITY" | jq -r '.codex.allowances? | type')" = object ] &&
           [ "$(printf '%s' "$AVAILABILITY" | jq -r '.codex.allowances | length')" -gt 0 ]; then
        if printf '%s' "$AVAILABILITY" | jq -e 'any(.codex.allowances[]; .state == "ok")' >/dev/null; then printf attemptable
        elif printf '%s' "$AVAILABILITY" | jq -e 'all(.codex.allowances[]; .state == "limited")' >/dev/null; then printf unavailable
        else printf unknown
        fi
      else
        state="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.state // "unknown"')"
        case "$state" in ok) printf available ;; limited|unavailable) printf unavailable ;; *) printf unknown ;; esac
      fi
      ;;
    claude-cli)
      auth="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.authMode // .claude.auth_mode // "unknown"')"
      state="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.state // "unknown"')"
      [ "$auth" = subscription ] || { printf unavailable; return; }
      if [ "$model" = fable ] && [ "$(printf '%s' "$AVAILABILITY" | jq -r '.claude.fable // "unknown"')" = exhausted ]; then
        printf unavailable
      else
        case "$state" in ok) printf available ;; unavailable) printf unavailable ;; *) printf unknown ;; esac
      fi
      ;;
    openrouter)
      state="$(printf '%s' "$AVAILABILITY" | jq -r '.openrouter.state // "unknown"')"
      case "$state" in ok) printf available ;; unavailable|limited) printf unavailable ;; *) printf unknown ;; esac
      ;;
  esac
}

CANDIDATES='[]'
while IFS= read -r candidate; do
  [ -n "$candidate" ] || continue
  if jq -en --argjson requested "$CAPABILITIES_JSON" --argjson candidate "$candidate" '
    ($requested - ["independent-family"]) as $needed
    | all($needed[]; . as $cap | $candidate.capabilities | index($cap) != null)
  ' >/dev/null; then
    status="$(candidate_status "$candidate")"
    CANDIDATES="$(printf '%s' "$CANDIDATES" | jq -c --argjson candidate "$candidate" --arg status "$status" '. + [$candidate + {availability:$status}]')"
  fi
done < <(jq -c --arg role "$ROLE" '.roles[$role][]' "$POLICY")

PRIMARY="$(printf '%s' "$CANDIDATES" | jq -c '([.[] | select(.availability == "available" or .availability == "attemptable")][0] // [.[] | select(.availability == "unknown")][0]) // empty')"
[ -n "$PRIMARY" ] && [ "$PRIMARY" != null ] || {
  jq -cn --arg role "$ROLE" '{recommendedStart:null,reason:"no_capability_compatible_candidate",role:$role}'
  exit 76
}
PRIMARY_MODEL="$(printf '%s' "$PRIMARY" | jq -r '.model')"
FALLBACK="$(printf '%s' "$CANDIDATES" | jq -c --arg model "$PRIMARY_MODEL" '([.[] | select(.model != $model and (.availability == "available" or .availability == "attemptable"))][0] // [.[] | select(.model != $model and .availability == "unknown")][0] // [.[] | select(.model != $model and .availability == "unavailable")][0]) // empty')"
[ -n "$FALLBACK" ] && [ "$FALLBACK" != null ] || {
  jq -cn --arg role "$ROLE" '{recommendedStart:null,reason:"no_concrete_fallback",role:$role}'
  exit 76
}

harness_for() {
  case "$1" in codex-cli) printf Codex ;; claude-cli) printf 'Claude Code' ;; openrouter) printf OpenRouter ;; esac
}
cost_for() {
  local candidate="$1" transport model alias price
  transport="$(printf '%s' "$candidate" | jq -r '.transport')"
  model="$(printf '%s' "$candidate" | jq -r '.model')"
  if [ "$transport" = openrouter ]; then
    price="$(jq -c --arg model "$model" --arg snapshot "$(jq -r '.snapshot_date' "$MATRIX")" '
      [.models[] | select(.slug == $model and .catalog_status == "available" and .snapshot_date == $snapshot)][0]
      | if . == null then null else {inputUsdPerM:.input_usd_per_m,outputUsdPerM:.output_usd_per_m,snapshotDate:.snapshot_date} end
    ' "$MATRIX")"
    jq -cn --argjson price "$price" '{label:"metered API",apiPrice:$price,apiEquivalent:null}'
  else
    alias="$(jq -r --arg model "$model" '.native_api_equivalent_cost.aliases[$model] // empty' "$MATRIX")"
    price="$(jq -c --arg alias "$alias" '[.native_api_equivalent_cost.models[] | select(.slug == $alias)][0] // null | if . == null then null else {inputUsdPerM:.input_usd_per_m,outputUsdPerM:.output_usd_per_m,snapshotDate:.snapshot_date,basis:.pricing_basis} end' "$MATRIX")"
    jq -cn --argjson price "$price" '{label:"included subscription",apiPrice:null,apiEquivalent:$price}'
  fi
}

PRIMARY_TRANSPORT="$(printf '%s' "$PRIMARY" | jq -r '.transport')"
FALLBACK_TRANSPORT="$(printf '%s' "$FALLBACK" | jq -r '.transport')"
PRIMARY_HARNESS="$(harness_for "$PRIMARY_TRANSPORT")"
FALLBACK_HARNESS="$(harness_for "$FALLBACK_TRANSPORT")"
PRIMARY_AVAILABILITY="$(printf '%s' "$PRIMARY" | jq -r '.availability')"
FALLBACK_AVAILABILITY="$(printf '%s' "$FALLBACK" | jq -r '.availability')"
EFFECTIVE_EFFORT="$(jq -r --arg transport "$PRIMARY_TRANSPORT" --arg effort "$EFFORT" '.effort.transports[$transport][$effort]' "$POLICY")"
CAPABILITY_TEXT="$(printf '%s' "$CAPABILITIES_JSON" | jq -r 'join(", ")')"
if [ "$PRIMARY_AVAILABILITY" = unknown ]; then
  WHY="Availability is unknown; this is the first current policy candidate for $ROLE matching $CAPABILITY_TEXT."
elif [ "$PRIMARY_AVAILABILITY" = attemptable ]; then
  WHY="Current subscription evidence makes this $ROLE candidate attemptable without attributing an allowance bucket; invocation will settle availability."
else
  WHY="This is the first currently available policy candidate for $ROLE matching $CAPABILITY_TEXT."
fi
PRIMARY_COST="$(cost_for "$PRIMARY")"
SNAPSHOT="$(jq -r '.snapshot_date' "$MATRIX")"

RESULT="$(jq -cn --arg model "$PRIMARY_MODEL" --arg harness "$PRIMARY_HARNESS" \
  --arg effort "$EFFECTIVE_EFFORT" --arg why "$WHY" --arg availability "$PRIMARY_AVAILABILITY" \
  --arg fallback_model "$(printf '%s' "$FALLBACK" | jq -r '.model')" \
  --arg fallback_harness "$FALLBACK_HARNESS" --arg fallback_availability "$FALLBACK_AVAILABILITY" \
  --arg snapshot "$SNAPSHOT" --argjson cost "$PRIMARY_COST" \
  '{recommendedStart:{model:$model,harness:$harness,effort:$effort,availability:$availability,why:$why,cost:$cost,
    fallback:{model:$fallback_model,harness:$fallback_harness,availability:$fallback_availability},matrixEvidence:$snapshot}}')"

if [ "$FORMAT" = json ]; then
  printf '%s\n' "$RESULT"
  exit 0
fi

cost_label="$(printf '%s' "$RESULT" | jq -r '.recommendedStart.cost.label')"
if [ "$cost_label" = 'metered API' ]; then
  price_text="$(printf '%s' "$RESULT" | jq -r 'if .recommendedStart.cost.apiPrice == null then "price unavailable in current matrix" else "$" + (.recommendedStart.cost.apiPrice.inputUsdPerM|tostring) + "/M input, $" + (.recommendedStart.cost.apiPrice.outputUsdPerM|tostring) + "/M output" end')"
  COST_TEXT="metered API; $price_text"
else
  equivalent_text="$(printf '%s' "$RESULT" | jq -r 'if .recommendedStart.cost.apiEquivalent == null then "API-equivalent unavailable in current matrix" else "API-equivalent $" + (.recommendedStart.cost.apiEquivalent.inputUsdPerM|tostring) + "/M input, $" + (.recommendedStart.cost.apiEquivalent.outputUsdPerM|tostring) + "/M output (" + .recommendedStart.cost.apiEquivalent.snapshotDate + ")" end')"
  COST_TEXT="included subscription; $equivalent_text"
fi
printf 'Recommended start\n\n'
printf -- '- Model: %s\n' "$PRIMARY_MODEL"
printf -- '- Harness/rail: %s\n' "$PRIMARY_HARNESS"
printf -- '- Effort: %s\n' "$EFFECTIVE_EFFORT"
printf -- '- Why: %s\n' "$WHY"
printf -- '- Cost: %s\n' "$COST_TEXT"
printf -- '- Fallback: %s via %s (availability: %s)\n' "$(printf '%s' "$FALLBACK" | jq -r '.model')" "$FALLBACK_HARNESS" "$FALLBACK_AVAILABILITY"
printf -- '- Matrix evidence: %s\n' "$SNAPSHOT"
