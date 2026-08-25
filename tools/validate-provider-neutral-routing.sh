#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
PIPELINE_POLICY="$ROOT/plugins/pipeline/references/routing-policy.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/provider-neutral-routing.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'provider-neutral-routing: %s\n' "$1" >&2; exit 1; }

# Closed roles, capabilities, effort, no inactive GLM, and focused Kimi use.
jq -e '
  (.roles | keys | sort) == (["architect","builder-deep","builder-fast","editorial","plan-critic","research-fast","review-deep","review-fast","security-review"] | sort) and
  (.effort.vocabulary == ["low","medium","high","max"]) and
  all(.roles[]; any(.[]; .transport == "openrouter")) and
  ([.roles[][] | .capabilities[] | select(IN("read-repository","write-repository","tool-use","browser","long-context","structured-output","independent-family") | not)] | length == 0) and
  ([.roles[][] | .model | select(test("glm";"i"))] | length == 0) and
  ([.roles | to_entries[] | select(.key != "security-review") | .value[] | .model | select(test("kimi";"i"))] | length == 0)
' "$POLICY" >/dev/null || fail 'role policy is not closed'

# OpenRouter is a first-class configured rail for every ordinary Pipeline chunk.
# Add interactive capabilities only when a specific manifest actually needs them.
jq -e '
  all(.chunkKinds[];
    (.executorCapabilities | index("tool-use") | not) and
    (.executorCapabilities | index("browser") | not)
  ) and
  all(.legacyExecutorTranslation[];
    (.executorCapabilities | index("tool-use") | not) and
    (.executorCapabilities | index("browser") | not)
  )
' "$PIPELINE_POLICY" >/dev/null || fail 'Pipeline defaults unnecessarily gate OpenRouter'

# OpenRouter candidate drift: every external candidate exists in its authority.
jq -r '.roles[][] | select(.transport == "openrouter") | .model' "$POLICY" | sort -u > "$TMP/router-models"
jq -r '.models[] | .slug' "$MATRIX" | sort -u > "$TMP/matrix-models"
missing="$(comm -23 "$TMP/router-models" "$TMP/matrix-models")"
[ -z "$missing" ] || fail "OpenRouter candidate missing from matrix: $missing"
jq -e '
  (.roles["research-fast"][] | select(.model == "google/gemini-3.7-flash")
    | .capabilities | index("browser")) != null
' "$POLICY" >/dev/null || fail 'research-fast lacks its matrix-backed browser candidate'
jq -e '.models[] | select(.slug == "google/gemini-3.7-flash")
  | (.web_search_usd_per_request | type) == "number"' "$MATRIX" >/dev/null ||
  fail 'browser candidate lacks OpenRouter web-search evidence'
grep -Fq 'OPENROUTER_WEB_SEARCH="$web_search"' \
  "$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh" ||
  fail 'browser capability is not wired to the provider adapter'

# Pipeline policy may express only role intent and legacy translation.
jq -e '
  .schemaVersion == 4 and
  ([.chunkKinds[].executorRole | select(. != "builder-fast" and . != "builder-deep")] | length == 0) and
  ([.routingOverride.forbiddenKeys[]] | index("model") != null and index("provider") != null) and
  ([paths(scalars) as $p | select(($p[-1] == "model" or $p[-1] == "provider" or $p[-1] == "transport") and ($p[0] != "routingOverride" and $p[0] != "decisionLeverage"))] | length == 0)
' "$PIPELINE_POLICY" >/dev/null || fail 'Pipeline routing policy contains concrete selection'

# Orchestrator-facing runtime files cannot pin or invoke concrete participants.
runtime_files=(
  "$ROOT/plugins/pipeline/commands/pipeline.md"
  "$ROOT/plugins/pipeline/commands/pipeline-run.md"
  "$ROOT/plugins/pipeline/commands/pipeline-prompts.md"
  "$ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
  "$ROOT/plugins/pipeline/skills/promptcraft/references/manifest-schema.md"
  "$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
  "$ROOT/plugins/pipeline/agents/workflow/plan-adversary.md"
  "$ROOT/plugins/pipeline/references/artifact-lifecycle.md"
  "$ROOT/plugins/pipeline/references/codex-native-execution-adapter.md"
  "$ROOT/plugins/pipeline/references/execution-validation-feedback.md"
  "$ROOT/plugins/pipeline/references/openrouter-authorization-contract.md"
  "$ROOT/plugins/pipeline/references/run-postmortem-schema.md"
  "$ROOT/plugins/dm-review/skills/review/SKILL.md"
  "$ROOT/plugins/dm-review/skills/review/references/full-lane-dispatch.md"
  "$ROOT/plugins/dm-review/skills/review/references/agent-registry.md"
  "$ROOT/plugins/dm-review/skills/review/references/graceful-degradation.md"
  "$ROOT/plugins/dm-review/skills/review/references/guardrails.md"
  "$ROOT/plugins/dm-review/skills/review/references/independent-family-lanes.md"
  "$ROOT/plugins/dm-review/skills/review/references/lane-fallback.md"
  "$ROOT/plugins/dm-review/skills/review/references/reviewer-prompt-template.md"
  "$ROOT/plugins/dm-review/skills/review/references/output-format.md"
  "$ROOT/plugins/dm-review/skills/review/references/selective-lane-allowlist.md"
  "$ROOT/plugins/dm-review/skills/review/references/selective-lane-rerun.md"
  "$ROOT/plugins/project-manager/skills/assembly-coordinator/SKILL.md"
  "$ROOT/plugins/project-manager/skills/assembly-coordinator/references/planning-opinions.md"
)
if grep -Ein -- '(deepseek/|qwen/|x-ai/|moonshotai/|gpt-5\.|claude-fable|(^|[^[:alnum:]_])(fable|kimi|opus|sonnet|haiku)([^[:alnum:]_]|$)|openrouter/model/agent|codex-fallback/agent|kimi-security|claude-planner|/openrouter[^[:cntrl:]]*--model|codex[[:space:]]+exec([^[:alnum:]_-]|$)|claude[[:space:]]+-p([^[:alnum:]_-]|$))' "${runtime_files[@]}" > "$TMP/leaks"; then
  sed -n '1,20p' "$TMP/leaks" >&2
  fail 'concrete participant leaked into orchestrator-facing runtime files'
fi
grep -En -- '^model:' "${runtime_files[@]}" | grep -Ev 'model: inherit$' > "$TMP/pins" || true
if [ -s "$TMP/pins" ]; then
  sed -n '1,20p' "$TMP/pins" >&2
  fail 'runtime card pins a concrete model'
fi

if grep -ERn --include='*.md' -- 'security-auditor-(codex-signoff|openrouter)' \
  "$ROOT/plugins/dm-review/skills/review" > "$TMP/retired-lanes"; then
  sed -n '1,20p' "$TMP/retired-lanes" >&2
  fail 'provider-bearing logical lane name remains in dm-review runtime'
fi

# Every routed operational card inherits participant selection.
while IFS= read -r card; do
  grep -qx 'model: inherit' "$card" || fail "routed card does not inherit: ${card#$ROOT/}"
done < <(find "$ROOT/plugins/pipeline/agents" "$ROOT/plugins/dm-review/agents" "$ROOT/plugins/assembly/agents" "$ROOT/plugins/openrouter/agents" -type f -name '*.md' | sort)

# Criteria cards used by neutral callers cannot carry retired tier aliases or
# concrete invocation instructions. OpenRouter's own transport cards remain in
# its explicit provider allowlist above this orchestration boundary.
while IFS= read -r card; do
  if grep -Ein -- '(model tier|(^|[^[:alnum:]_])(opus|sonnet|haiku|fable|kimi)([^[:alnum:]_]|$)|deepseek/|qwen/|x-ai/|moonshotai/|gpt-5\.|claude-fable|codex exec|claude -p)' "$card" > "$TMP/card-leaks"; then
    sed -n '1,10p' "$TMP/card-leaks" >&2
    fail "concrete participant leaked into routed card: ${card#$ROOT/}"
  fi
done < <(find "$ROOT/plugins/pipeline/agents" "$ROOT/plugins/dm-review/agents" "$ROOT/plugins/assembly/agents" -type f -name '*.md' | sort)

# New Pipeline manifests accept roles and reject model/provider keys.
jq -n '{chunks:[{executorRole:"builder-fast",executorCapabilities:["read-repository","write-repository","structured-output"],executorEffort:"medium"}]}' > "$TMP/valid.json"
"$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/valid.json" || fail 'valid role manifest rejected'
jq '.chunks[0].provider="example"' "$TMP/valid.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'provider-bearing manifest accepted'; fi
jq -n '{chunks:[{id:"a",executor:"openrouter"},{id:"b",executor:"codex"},{id:"c",executor:"claude"}]}' > "$TMP/legacy.json"
"$ROOT/plugins/pipeline/references/translate-legacy-executor.sh" "$TMP/legacy.json" > "$TMP/translated.json"
jq -e '.chunks[0].executorRole=="builder-fast" and .chunks[1].executorRole=="builder-deep" and .chunks[2].executorRole=="builder-deep" and all(.chunks[];.legacyExecutorTranslation.occurred==true and has("executor")|not)' "$TMP/translated.json" >/dev/null || fail 'legacy executor translation failed'
"$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/translated.json" || fail 'translated legacy manifest does not satisfy role contract'

# Coordinator triggers exactly the bounded opinion path and preserves routine work.
COORD="$ROOT/plugins/project-manager/skills/assembly-coordinator/SKILL.md"
OPINIONS="$ROOT/plugins/project-manager/skills/assembly-coordinator/references/planning-opinions.md"
grep -q 'Routine status checks' "$COORD" || fail 'routine coordinator no-panel rule missing'
grep -q 'exactly one `architect` and at most one independent' "$COORD" || fail 'bounded opinion count missing'
grep -q 'recommend exactly one next chunk' "$OPINIONS" || fail 'single synthesis recommendation missing'
grep -q 'Do not run debate, rebuttal, convergence, or a third opinion' "$OPINIONS" || fail 'debate guard missing'
grep -q 'approved high uncertainty' "$OPINIONS" || fail 'high-uncertainty opinion trigger missing'
grep -q 'routine planning proceeds normally' "$COORD" || fail 'unavailable router blocks routine coordination'
grep -q 'If an explicit comparison cannot obtain Plan B' "$OPINIONS" || fail 'explicit comparison limitation path missing'
for query in 'Compare these Assembly plans' 'Get an independent planning opinion' 'Have an architect challenge this Assembly delivery sequence' 'Assign execution roles to this Pipeline prompt' 'Compare two approaches before choosing the next Assembly chunk'; do
  jq -e --arg query "$query" 'any(.[]; (.query | startswith($query)) and .should_trigger == true)' "$ROOT/description-evals/project-manager-assembly-coordinator.json" >/dev/null || fail "coordinator eval missing: $query"
done

# Routing never weakens zero-deferral.
grep -q 'Every retained P1, P2, and P3 finding is mandatory work' "$ROOT/plugins/dm-review/skills/review/SKILL.md" || fail 'dm-review zero-deferral missing'
grep -q 'every retained P1/P2/P3 must be fixed and verified' "$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md" || fail 'Pipeline zero-deferral missing'

printf 'provider-neutral-routing: passed\n'
