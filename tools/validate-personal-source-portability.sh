#!/usr/bin/env bash
#
# validate-personal-source-portability.sh -- Keep private research sources optional.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

failures=0

pass() {
  printf '  OK    %s\n' "$1"
}

fail() {
  printf '  FAIL  %s\n' "$1"
  failures=1
}

require_text() {
  local file="$1" text="$2" label="$3"
  if grep -Fq -- "$text" "$file"; then
    pass "$label"
  else
    fail "$label"
  fi
}

require_absent() {
  local file="$1" text="$2" label="$3"
  if grep -Fq -- "$text" "$file"; then
    fail "$label"
  else
    pass "$label"
  fi
}

personal_absence_directive_present() {
  local file="$1"
  python3 - "$file" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
normalized = re.sub(r"\s+", " ", text)
fragments = re.split(r"(?<=[.!?])\s+", normalized)

for fragment in fragments:
    lower = fragment.lower()
    source = re.search(r"\b(ai-memory|rag)\b", lower)
    absent = re.search(r"\b(unavailable|not available|absent|missing)\b|\bno\s+(ai-memory|rag)\b", lower)
    directive = re.search(r"\b(note|record|append|include|report|emit|surface|mark|add|skip|skipped)\b", lower)
    explicit = re.search(r"\b(explicit|explicitly)\b.{0,50}\b(user|request|requested|operation)\b", lower)
    negated = re.search(r"\b(never|do not|don't|omit|silent|silently|without (a |any )?(notice|mention|entry))\b", lower)
    if source and absent and directive and not explicit and not negated:
        raise SystemExit(0)

raise SystemExit(1)
PY
}

require_no_incidental_personal_absence_directive() {
  local file="$1" label="$2"
  if personal_absence_directive_present "$file"; then
    fail "$label"
  else
    pass "$label"
  fi
}

pipeline_manifest="$REPO_ROOT/plugins/pipeline/.claude-plugin/plugin.json"
review_manifest="$REPO_ROOT/plugins/dm-review/.claude-plugin/plugin.json"
research="$REPO_ROOT/plugins/pipeline/skills/research/SKILL.md"
assessment="$REPO_ROOT/plugins/pipeline/skills/assess/SKILL.md"
assessment_protocol="$REPO_ROOT/plugins/pipeline/skills/assess/references/code-assessment-protocol.md"
pipeline_command="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
pipeline_run_command="$REPO_ROOT/plugins/pipeline/commands/pipeline-run.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
lifecycle="$REPO_ROOT/plugins/pipeline/references/artifact-lifecycle.md"
postmortem="$REPO_ROOT/plugins/pipeline/references/run-postmortem-schema.md"
review="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
review_recorder="$REPO_ROOT/plugins/dm-review/agents/workflow/review-memory-recorder.md"
patterns="$REPO_ROOT/docs/orchestration-patterns.md"

for manifest in "$pipeline_manifest" "$review_manifest"; do
  name="$(jq -r '.name' "$manifest")"
  if jq -e '
    (.pluginDependencies.ned? == null)
    and (.optionalPluginDependencies.ned | type == "string")
  ' "$manifest" >/dev/null; then
    pass "$name treats ned as an optional plugin dependency"
  else
    fail "$name must not hard-depend on ned"
  fi
done

for manifest in "$pipeline_manifest" "$review_manifest"; do
  name="$(jq -r '.name' "$manifest")"
  if jq -e '
    [.capabilities.skills[] | (.mcpDependencies // [])[]
      | select(. == "ai-memory" or . == "rag")]
    | length == 0
  ' "$manifest" >/dev/null; then
    pass "$name capabilities do not advertise personal MCPs as requirements"
  else
    fail "$name capabilities must not require ai-memory or RAG"
  fi
done

require_text "$research" \
  'tool-search result; never invoke a tool merely to probe whether it exists.' \
  "research discovers optional personal sources without probe calls"
require_text "$research" \
  'repository evidence plus any other available relevant sources.' \
  "repository evidence is sufficient for valid research"
require_text "$research" \
  'When an optional personal source is callable, continue using it for relevant' \
  "available personal research sources retain their current behavior"
require_text "$research" \
  'it. Only an explicit user request for an ai-memory or RAG operation makes an' \
  "explicit personal-source requests may report an unavailable capability"
require_absent "$research" 'Call `mcp__ai-memory__search_entities` with a test query' \
  "research does not probe ai-memory by invoking it"
require_absent "$research" 'Call `mcp__rag__rag_search` with a test query' \
  "research does not probe RAG by invoking it"
require_absent "$research" 'RAG search unavailable -- personal knowledge library not consulted' \
  "research briefs do not disclose incidental RAG absence"
require_absent "$research" 'Minimum viable research requires only ai-memory' \
  "research does not require ai-memory"

require_text "$assessment" \
  'If callable, ai-memory may enrich project history; otherwise omit it silently.' \
  "assessment treats ai-memory as silent optional enrichment"
require_absent "$assessment" 'No ai-memory MCP: Skip project history check, note in report' \
  "assessment reports do not disclose incidental ai-memory absence"
require_text "$assessment_protocol" \
  'Always inspect repository history; enrich it from ai-memory only when the' \
  "assessment history remains repository-backed without ai-memory"

require_absent "$orchestrator" 'caller-side ai-memory unavailable' \
  "orchestrator does not degrade delivery for missing personal memory"
require_text "$pipeline_command" \
  'observation internal. Determine availability from the callable-tool inventory' \
  "Pipeline caller detects ai-memory without a warning-producing probe"
require_text "$pipeline_command" \
  'If the tools are absent, omit the write and every receipt or summary mention.' \
  "Pipeline caller silently omits unavailable incidental memory"
require_text "$pipeline_run_command" \
  'If the tools are absent, omit the write and every receipt or summary mention.' \
  "pipeline-run silently omits unavailable incidental memory"
for file in "$pipeline_command" "$pipeline_run_command" "$lifecycle" "$postmortem"; do
  require_text "$file" 'Memory capture: failed -- <safe reason>' \
    "$(basename "$file") preserves nonblocking evidence for a callable-tool failure"
done
require_text "$orchestrator" \
  'When `ned:codify` is discoverable in the installed skill inventory, load it; otherwise apply the inline checklist below silently.' \
  "Pipeline codify remains functional without the optional ned plugin"

require_text "$review" \
  'ai-memory availability from the callable-tool inventory or tool search, never' \
  "dm-review detects personal sources without probe calls"
require_text "$review" \
  'When callable, preserve the existing RAG lookup and ai-memory write behavior.' \
  "dm-review retains available personal-source enrichment"
require_text "$review" \
  'Memory capture: failed -- <safe reason>' \
  "dm-review preserves nonblocking evidence for callable personal-memory failures"
require_absent "$review_recorder" 'report "Skipped -- ai-memory not available"' \
  "review memory recorder does not report incidental ai-memory absence"
require_text "$review_recorder" \
  'If the required tools are not present in the callable-tool inventory, return no' \
  "review memory recorder silently omits an unavailable incidental write"
require_text "$review_recorder" \
  'Memory capture: failed -- <safe reason>' \
  "review memory recorder reports callable-tool failures safely"

for file in \
  "$research" \
  "$assessment" \
  "$assessment_protocol" \
  "$pipeline_command" \
  "$pipeline_run_command" \
  "$orchestrator" \
  "$lifecycle" \
  "$postmortem" \
  "$REPO_ROOT/plugins/pipeline/skills/research/references/source-registry.md" \
  "$review" \
  "$review_recorder" \
  "$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md" \
  "$patterns"; do
  require_no_incidental_personal_absence_directive "$file" \
    "$(basename "$file") has no incidental personal-source absence report"
done

semantic_fixture="$(mktemp "${TMPDIR:-/tmp}/personal-source-semantics.XXXXXX")"
printf '%s\n' \
  'Never include ai-memory unavailable in the report.' \
  'If explicitly requested by the user, include a RAG unavailable notice.' \
  > "$semantic_fixture"
if personal_absence_directive_present "$semantic_fixture"; then
  fail "semantic absence check accepts prohibitions and explicit-request exceptions"
else
  pass "semantic absence check accepts prohibitions and explicit-request exceptions"
fi
printf '%s\n' 'Record skipped -- ai-memory unavailable in the receipt.' > "$semantic_fixture"
if personal_absence_directive_present "$semantic_fixture"; then
  pass "semantic absence check rejects affirmative incidental notices"
else
  fail "semantic absence check rejects affirmative incidental notices"
fi
printf '%s\n' 'Record skipped -- ai-memory absent in the receipt.' > "$semantic_fixture"
if personal_absence_directive_present "$semantic_fixture"; then
  pass "semantic absence check rejects absent-vocabulary notices"
else
  fail "semantic absence check rejects absent-vocabulary notices"
fi
rm -f "$semantic_fixture"

require_absent "$patterns" 'Caller records `skipped -- <reason>` in durable receipt/summary evidence' \
  "orchestration docs contain no contradictory memory-unavailable receipt policy"
require_text "$patterns" \
  'is the complete rule; do not infer identity from usernames, environment' \
  "orchestration docs forbid identity heuristics"

if [ "$failures" -ne 0 ]; then
  printf '\nFIX  restore optional personal-source portability\n'
  exit 1
fi

printf '\nPASS  personal-source portability contract intact\n'
