#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
PIPELINE_POLICY="$ROOT/plugins/pipeline/references/routing-policy.json"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/provider-neutral-routing.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'provider-neutral-routing: %s\n' "$1" >&2; exit 1; }

# Closed roles, capabilities, effort, no inactive GLM, focused Kimi use, and
# no invented Codex candidate-to-allowance mapping.
jq -e '
  (.roles | keys | sort) == (["architect","builder-deep","builder-fast","editorial","plan-critic","research-fast","review-deep","review-fast","security-review"] | sort) and
  (.effort.vocabulary == ["low","medium","high","max"]) and
  all(.roles[]; any(.[]; .transport == "openrouter")) and
  ([.roles[][] | .capabilities[] | select(IN("read-repository","write-repository","tool-use","browser","long-context","structured-output","independent-family") | not)] | length == 0) and
  ([.roles[][] | .model | select(test("glm";"i"))] | length == 0) and
  all(.roles[][] | select(.transport == "codex-cli"); has("rateLimitId") | not) and
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
# Public web search is not local interactive browser authority. No current
# transport advertises browser, and OpenRouter invocation pins web search off.
jq -e '([.roles[][] | select(.capabilities | index("browser") != null)] | length) == 0' \
  "$POLICY" >/dev/null || fail 'a transport falsely advertises local browser access'
grep -Fq 'OPENROUTER_WEB_SEARCH=0' \
  "$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh" ||
  fail 'OpenRouter web search is not pinned off for routed local-browser semantics'
grep -Fq 'browser_transport_unavailable' \
  "$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh" ||
  fail 'browser requests lack an actionable closed reason'
grep -Fq 'test fixture hooks require MODEL_ROUTER_TEST_MODE=1' \
  "$ROOT/plugins/model-router/skills/model-router/references/role-dispatch.sh" ||
  fail 'production role dispatch does not reject unguarded fixture hooks'

ui_readiness="$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md"
ui_helper="$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.sh"
full_lane="$ROOT/plugins/dm-review/skills/review/references/full-lane-dispatch.md"
grep -Fq 'Keep browser interaction host-owned' "$full_lane" ||
  fail 'dm-review does not keep local browser interaction host-owned'
grep -Fq 'OpenRouter web search is remote public-web retrieval.' "$ui_readiness" ||
  fail 'dm-review does not distinguish web search from local browser access'
grep -Fq '`dev_server_unavailable`' "$ui_readiness" ||
  fail 'dm-review lacks the dev-server closed reason'
grep -Fq '`browser_transport_unavailable`' "$ui_readiness" ||
  fail 'dm-review lacks the browser-transport closed reason'
grep -Fq '`model_participant_unavailable`' "$ui_readiness" ||
  fail 'dm-review lacks the model-participant closed reason'
grep -Fq 'confirm-browser' "$ui_readiness" &&
  grep -Fq 'app_ready' "$ui_helper" &&
  grep -Fq 'cleanupArgv' "$ui_helper" ||
  fail 'dm-review lacks the two-phase browser gate or exact cleanup snapshot'
grep -Fq 'optional tracked `<repository>/.dm/ui-review.json`' "$ui_readiness" ||
  fail 'dm-review still treats UI configuration as mandatory'
grep -Fq 'one aggregated `visual_target_unavailable` coverage note' "$ui_readiness" ||
  fail 'dm-review duplicates missing visual readiness per lane'

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
jq -n '{feature:"fixture",workflowClass:"feature",decisionProfile:{uncertainty:"medium",consequence:"medium",rationale:"Bounded fixture."},renderedSurface:"not_applicable",baseBranch:"main",featureBranch:"feat/fixture",branchMode:"create",expectedFeatureHead:null,finalReviewMode:"full",finalReviewRationale:"Full review for fixture.",chunks:[{id:"a",level:0,title:"Fixture",prompt:"prompts/a.md",kind:"docs",renderedSurface:"not_applicable",renderedSurfaceRationale:"Unserved documentation.",executorRole:"builder-fast",executorCapabilities:["read-repository","write-repository","structured-output"],executorEffort:"medium",filesToModify:["docs/a.md"],dependsOn:[],companionSkills:[],estimatedComplexity:"low"}]}' > "$TMP/valid.json"
"$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/valid.json" || fail 'valid role manifest rejected'
jq '.renderedSurface="required" |
  .prototypeReference={status:"counterpart",canonicalRepository:"Design-Machines-Studio/assembly",commit:"0123456789abcdef0123456789abcdef01234567",authoritySource:"current PR",prototypeSourceFiles:["prototype/a.html"],targetSourceFiles:["templates/a.templ"],matchedCases:[{prototypeRoute:"/prototype/a",targetRoute:"/a",state:"default",viewports:[375,1440]}],intentionalDifferences:[]} |
  .chunks[0].kind="ui" |
  .chunks[0].renderedSurface="required" |
  .chunks[0].renderedSurfaceRationale="Declared prototype counterpart." |
  .chunks[0].prototypeParity=[{surface:"fixture",prototypeSourcePaths:["prototype/a.html"],targetSourcePaths:["templates/a.templ"],prototypeRoute:"/prototype/a",targetRoute:"/a",state:"default",viewports:[375,1440],sourceDecisions:{structure:["Heading precedes content."],classes:["stack"],copy:["Fixture"],actions:["Save is primary."]},sourceEvidenceStatus:"complete",renderedEvidenceStatus:"pending",intentionalDifferences:[]}]' \
  "$TMP/valid.json" > "$TMP/valid-prototype.json"
"$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/valid-prototype.json" || fail 'valid prototype manifest rejected'
jq '.prototypeReference={}' "$TMP/valid.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'malformed prototype reference accepted'; fi
jq '.chunks[0].prototypeReference=.prototypeReference | del(.prototypeReference)' "$TMP/valid-prototype.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'chunk-level prototype reference accepted'; fi
jq 'del(.chunks[0].prototypeParity)' "$TMP/valid-prototype.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'prototype counterpart without chunk parity accepted'; fi
jq '.chunks[0].prototypeParity[0].targetRoute="/different"' "$TMP/valid-prototype.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'conflicting prototype route accepted'; fi
jq '.prototypeReference.status="no_counterpart" | .prototypeReference.targetSourceFiles=[] | .prototypeReference.matchedCases=[] | del(.chunks[0].prototypeParity)' "$TMP/valid-prototype.json" > "$TMP/valid-no-counterpart.json"
"$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/valid-no-counterpart.json" || fail 'source-proven no-counterpart manifest rejected'
jq '.chunks[0].prototypeParity=[]' "$TMP/valid-no-counterpart.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'no-counterpart manifest with chunk parity accepted'; fi
jq '.chunks[0].provider="example"' "$TMP/valid.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'provider-bearing manifest accepted'; fi
for field in feature workflowClass decisionProfile renderedSurface baseBranch featureBranch branchMode expectedFeatureHead finalReviewMode finalReviewRationale; do
  jq --arg field "$field" 'del(.[$field])' "$TMP/valid.json" > "$TMP/invalid.json"
  if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail "manifest missing $field accepted"; fi
done
for field in id level title prompt kind renderedSurface renderedSurfaceRationale executorRole executorCapabilities executorEffort filesToModify dependsOn companionSkills estimatedComplexity; do
  jq --arg field "$field" 'del(.chunks[0][$field])' "$TMP/valid.json" > "$TMP/invalid.json"
  if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail "chunk missing $field accepted"; fi
done
jq '.chunks[0].executorCapabilities += ["read-repository"]' "$TMP/valid.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'duplicate capabilities accepted'; fi
jq '.chunks[0].renderedSurface="not-applicable"' "$TMP/valid.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'open rendered-surface enum accepted'; fi
jq '.chunks[0].routingOverride={executorEffort:"high"}' "$TMP/valid.json" > "$TMP/invalid.json"
if "$ROOT/plugins/pipeline/references/validate-role-manifest.sh" "$TMP/invalid.json"; then fail 'routing override without reason accepted'; fi
jq '.chunks = [(.chunks[0] + {executor:"openrouter"} | del(.executorRole,.executorCapabilities,.executorEffort)), (.chunks[0] + {id:"b",executor:"codex"} | del(.executorRole,.executorCapabilities,.executorEffort)), (.chunks[0] + {id:"c",executor:"claude"} | del(.executorRole,.executorCapabilities,.executorEffort))]' "$TMP/valid.json" > "$TMP/legacy.json"
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

# The legacy cascade adapter preserves inline/stdin prompts, stdout output,
# historical option parsing, and a provider-neutral dry-run surface.
CASCADE="$ROOT/plugins/pipeline/references/cascade-dispatch.sh"
jq -n '{codex:{state:"ok",authMode:"subscription",windows:{five_hour:{remaining_pct:80},weekly:{remaining_pct:80}}},claude:{state:"unavailable"},openrouter:{state:"ok"}}' > "$TMP/cascade-availability.json"
printf '%s\n' '#!/usr/bin/env bash' 'while [ "$#" -gt 0 ]; do case "$1" in --output-file) output="$2"; shift 2 ;; *) shift 2 ;; esac; done' 'cat >/dev/null' '[ -z "${CASCADE_CONTACT_FILE:-}" ] || printf "contact\\n" >> "$CASCADE_CONTACT_FILE"' 'printf "compat-ok\\n" > "$output"' > "$TMP/cascade-transport"
chmod +x "$TMP/cascade-transport"
MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_AVAILABILITY_FILE="$TMP/cascade-availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/cascade-transport" \
  "$CASCADE" --class openrouter --prompt 'inline prompt' --workflow-kernel "$KERNEL" --host codex --phase execute --timeout 5 > "$TMP/cascade-inline"
grep -Fxq 'compat-ok' "$TMP/cascade-inline" || fail 'legacy inline prompt/stdout contract failed'
printf 'stdin prompt' | MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_AVAILABILITY_FILE="$TMP/cascade-availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/cascade-transport" \
  "$CASCADE" --kind logic --prompt - --workflow-kernel "$KERNEL" --probe-file "$TMP/cascade-availability.json" --exhausted-rail openrouter > "$TMP/cascade-stdin"
grep -Fxq 'compat-ok' "$TMP/cascade-stdin" || fail 'legacy stdin prompt contract failed'
"$CASCADE" --kind docs --prompt x --host codex --dry-run > "$TMP/cascade-dry-run"
jq -e '.compatibilityAdapter == true and .role == "builder-fast" and .disposition == "dry-run"' "$TMP/cascade-dry-run" >/dev/null || fail 'legacy dry-run compatibility failed'
touch "$TMP/cascade-contacts"
if CASCADE_CONTACT_FILE="$TMP/cascade-contacts" MODEL_ROUTER_TEST_MODE=1 MODEL_ROUTER_AVAILABILITY_FILE="$TMP/cascade-availability.json" \
  MODEL_ROUTER_TRANSPORT_STUB="$TMP/cascade-transport" \
  "$CASCADE" --class openrouter --prompt x --workflow-kernel "$KERNEL" --attempt-receipt-template invalid >/dev/null 2>&1; then
  fail 'invalid legacy receipt template accepted'
fi
[ ! -s "$TMP/cascade-contacts" ] || fail 'invalid legacy receipt template contacted a transport'

# Routing never weakens zero-deferral.
grep -q 'Every retained P1, P2, and P3 finding is mandatory work' "$ROOT/plugins/dm-review/skills/review/SKILL.md" || fail 'dm-review zero-deferral missing'
grep -q 'every retained P1/P2/P3 must be fixed and verified' "$ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md" || fail 'Pipeline zero-deferral missing'

printf 'provider-neutral-routing: passed\n'
