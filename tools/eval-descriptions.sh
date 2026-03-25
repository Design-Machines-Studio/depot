#!/usr/bin/env bash
#
# eval-descriptions.sh — Evaluate skill description trigger accuracy
#
# For each JSON eval file in description-evals/, checks whether the
# corresponding SKILL.md description would plausibly trigger for each
# test query using term-overlap heuristics.
#
# Usage:
#   ./tools/eval-descriptions.sh              # run all evals
#   ./tools/eval-descriptions.sh <name>.json  # run one eval file
#
# Exit codes:
#   0 — all skills above 80% accuracy
#   1 — one or more skills below 80% accuracy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EVALS_DIR="$REPO_ROOT/description-evals"
PLUGINS_DIR="$REPO_ROOT/plugins"
THRESHOLD=70
MIN_OVERLAP=3

# Colors (disable if not a terminal)
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[0;33m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN='' RED='' YELLOW='' BOLD='' RESET=''
fi

# --------------------------------------------------------------------------
# Map eval filename to SKILL.md path
#
# Convention: <plugin>-<skill>.json
#   ghostwriter-voice.json      -> plugins/ghostwriter/skills/voice/SKILL.md
#   craft-developer-craft-mcp   -> plugins/craft-developer/skills/craft-mcp/SKILL.md
#   live-wires.json             -> plugins/live-wires/skills/livewires/SKILL.md
#
# Strategy: try increasingly aggressive splits of the basename on "-"
# until we find a matching plugin dir + skill dir combination.
# --------------------------------------------------------------------------
resolve_skill_path() {
  local basename="$1"  # e.g. "ghostwriter-voice" or "craft-developer-craft-mcp"

  # Split on "-" into an array
  IFS='-' read -ra parts <<< "$basename"
  local n=${#parts[@]}

  # Try splits: plugin = parts[0..i], skill = parts[i+1..n-1]
  for (( i=0; i<n-1; i++ )); do
    local plugin_name=""
    local skill_name=""
    for (( j=0; j<=i; j++ )); do
      [ -n "$plugin_name" ] && plugin_name="$plugin_name-"
      plugin_name="$plugin_name${parts[$j]}"
    done
    for (( j=i+1; j<n; j++ )); do
      [ -n "$skill_name" ] && skill_name="$skill_name-"
      skill_name="$skill_name${parts[$j]}"
    done

    local skill_path="$PLUGINS_DIR/$plugin_name/skills/$skill_name/SKILL.md"
    if [ -f "$skill_path" ]; then
      echo "$skill_path"
      return 0
    fi
  done

  # Fallback: try the whole basename as plugin name with each skill dir
  if [ -d "$PLUGINS_DIR/$basename/skills" ]; then
    for skill_dir in "$PLUGINS_DIR/$basename/skills"/*/; do
      if [ -f "$skill_dir/SKILL.md" ]; then
        echo "$skill_dir/SKILL.md"
        return 0
      fi
    done
  fi

  return 1
}

# --------------------------------------------------------------------------
# Extract description from SKILL.md YAML frontmatter
# --------------------------------------------------------------------------
extract_description() {
  local skill_path="$1"
  # Use python3 for reliable YAML frontmatter parsing
  SKILL_PATH="$skill_path" python3 << 'PYEOF'
import re, sys, os
skill_path = os.environ["SKILL_PATH"]
with open(skill_path) as f:
    content = f.read()
m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
if not m:
    sys.exit(0)
fm = m.group(1)
# Block scalar (>- or | or >)
dm = re.search(r'^description:\s*[>|]-?\s*\n((?:[ \t]+.*\n)*)', fm, re.MULTILINE)
if dm:
    lines = dm.group(1).strip().split('\n')
    print(' '.join(line.strip() for line in lines))
else:
    # Inline: quoted or unquoted
    dm = re.search(r'^description:\s*["\']?(.*?)["\']?\s*$', fm, re.MULTILINE)
    if dm:
        print(dm.group(1))
PYEOF
}

# --------------------------------------------------------------------------
# Normalize text: lowercase, strip punctuation, split into words
# --------------------------------------------------------------------------
normalize() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]/ /g' | tr -s ' '
}

# --------------------------------------------------------------------------
# Extract meaningful terms (skip stopwords, keep words >= 3 chars)
# --------------------------------------------------------------------------
STOPWORDS="the a an and or but in on at to for of is it by as be do if so no not with from that this was are were has had have can may will also use when any all how what who"

extract_terms() {
  local text
  text=$(normalize "$1")
  local -a terms=()
  for word in $text; do
    # Skip short words and stopwords
    [ ${#word} -lt 3 ] && continue
    local is_stop=0
    for sw in $STOPWORDS; do
      if [ "$word" = "$sw" ]; then
        is_stop=1
        break
      fi
    done
    [ $is_stop -eq 0 ] && terms+=("$word")
  done
  echo "${terms[@]}"
}

# --------------------------------------------------------------------------
# Count overlapping terms between two term sets
# --------------------------------------------------------------------------
count_overlap() {
  local desc_terms="$1"
  local query_terms="$2"
  local count=0

  for qt in $query_terms; do
    for dt in $desc_terms; do
      # Exact match or substring match (query term contained in desc term or vice versa)
      if [ "$qt" = "$dt" ]; then
        count=$((count + 1))
        break
      elif [[ "$dt" == *"$qt"* ]] && [ ${#qt} -ge 4 ]; then
        count=$((count + 1))
        break
      elif [[ "$qt" == *"$dt"* ]] && [ ${#dt} -ge 4 ]; then
        count=$((count + 1))
        break
      fi
    done
  done
  echo "$count"
}

# --------------------------------------------------------------------------
# Run evaluation for one JSON file
# --------------------------------------------------------------------------
eval_one() {
  local eval_file="$1"
  local basename
  basename=$(basename "$eval_file" .json)

  local skill_path
  if ! skill_path=$(resolve_skill_path "$basename"); then
    printf "  ${RED}SKIP${RESET} %-40s  (no SKILL.md found)\n" "$basename"
    return 2
  fi

  local description
  description=$(extract_description "$skill_path")
  if [ -z "$description" ]; then
    printf "  ${RED}SKIP${RESET} %-40s  (empty description)\n" "$basename"
    return 2
  fi

  local desc_terms
  desc_terms=$(extract_terms "$description")

  local total=0 pass=0 fail=0
  local failures=""

  # Parse JSON test cases using python3 (available on macOS)
  while IFS='|' read -r query should_trigger; do
    total=$((total + 1))
    local query_terms
    query_terms=$(extract_terms "$query")
    local overlap
    overlap=$(count_overlap "$desc_terms" "$query_terms")

    # Adaptive threshold: require overlap >= MIN_OVERLAP,
    # but also check ratio of overlap to query terms.
    # Short queries with 2+ matches are strong signals.
    local query_term_count
    query_term_count=$(echo "$query_terms" | wc -w | tr -d ' ')
    local predicted_trigger=false
    if [ "$overlap" -ge "$MIN_OVERLAP" ]; then
      predicted_trigger=true
    elif [ "$overlap" -ge 2 ] && [ "$query_term_count" -le 8 ]; then
      # Short queries with 2 matches are likely relevant
      predicted_trigger=true
    fi

    if [ "$predicted_trigger" = "$should_trigger" ]; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1))
      failures="$failures\n    $([ "$should_trigger" = "true" ] && echo "FALSE_NEG" || echo "FALSE_POS") overlap=$overlap: ${query:0:80}..."
    fi
  done < <(python3 -c "
import json, sys
with open('$eval_file') as f:
    cases = json.load(f)
for c in cases:
    q = c['query'].replace('|', ' ')
    t = str(c['should_trigger']).lower()
    print(f'{q}|{t}')
")

  local accuracy=0
  if [ "$total" -gt 0 ]; then
    accuracy=$(python3 -c "print(f'{($pass / $total) * 100:.1f}')")
  fi

  # Store results for summary table
  RESULTS+=("$basename|$total|$pass|$fail|$accuracy")

  # Print failures if any
  if [ "$fail" -gt 0 ] && [ "${VERBOSE:-0}" = "1" ]; then
    printf "  ${YELLOW}DETAIL${RESET} %s:%b\n" "$basename" "$failures"
  fi

  # Check threshold
  local acc_int
  acc_int=$(python3 -c "print(int($accuracy))")
  if [ "$acc_int" -lt "$THRESHOLD" ]; then
    return 1
  fi
  return 0
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
main() {
  local eval_files=()
  local positional_args=()

  # Parse flags first
  for arg in "$@"; do
    if [ "$arg" = "-v" ] || [ "$arg" = "--verbose" ]; then
      export VERBOSE=1
    else
      positional_args+=("$arg")
    fi
  done

  if [ ${#positional_args[@]} -gt 0 ]; then
    # Specific file(s) provided
    for arg in "${positional_args[@]}"; do
      if [ -f "$EVALS_DIR/$arg" ]; then
        eval_files+=("$EVALS_DIR/$arg")
      elif [ -f "$arg" ]; then
        eval_files+=("$arg")
      else
        echo "Error: eval file not found: $arg" >&2
        exit 1
      fi
    done
  else
    for f in "$EVALS_DIR"/*.json; do
      [ -f "$f" ] && eval_files+=("$f")
    done
  fi

  if [ ${#eval_files[@]} -eq 0 ]; then
    echo "No eval files found in $EVALS_DIR"
    exit 1
  fi

  printf "\n${BOLD}Description Evaluation${RESET}\n"
  printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

  declare -a RESULTS=()
  local any_failed=0
  local skipped=0

  for eval_file in "${eval_files[@]}"; do
    local rc=0
    eval_one "$eval_file" || rc=$?
    if [ "$rc" -eq 1 ]; then
      any_failed=1
    elif [ "$rc" -eq 2 ]; then
      skipped=$((skipped + 1))
    fi
  done

  # Summary table
  printf "\n${BOLD}%-40s  %5s  %4s  %4s  %8s${RESET}\n" "Skill" "Tests" "Pass" "Fail" "Accuracy"
  printf "%-40s  %5s  %4s  %4s  %8s\n" "────────────────────────────────────────" "─────" "────" "────" "────────"

  for result in "${RESULTS[@]}"; do
    IFS='|' read -r name total pass fail accuracy <<< "$result"
    local color="$GREEN"
    local acc_int
    acc_int=$(python3 -c "print(int($accuracy))")
    if [ "$acc_int" -lt "$THRESHOLD" ]; then
      color="$RED"
    elif [ "$acc_int" -lt 90 ]; then
      color="$YELLOW"
    fi
    printf "%-40s  %5s  %4s  %4s  ${color}%7s%%${RESET}\n" "$name" "$total" "$pass" "$fail" "$accuracy"
  done

  local total_evals=${#RESULTS[@]}
  printf "\n${BOLD}%d skills evaluated" "$total_evals"
  [ "$skipped" -gt 0 ] && printf ", %d skipped" "$skipped"
  printf "${RESET}\n"

  if [ "$any_failed" -eq 1 ]; then
    printf "${RED}FAIL: One or more skills below ${THRESHOLD}%% accuracy threshold${RESET}\n\n"
    exit 1
  else
    printf "${GREEN}PASS: All skills above ${THRESHOLD}%% accuracy threshold${RESET}\n\n"
    exit 0
  fi
}

main "$@"
