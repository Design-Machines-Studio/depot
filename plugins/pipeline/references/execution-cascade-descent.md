# Cascade descent (capped or unavailable primary rail)

Loaded at Step 3d only after a live cap/unavailability result, or a current
proactive probe, proves the selected primary rail cannot run. A chunk whose
primary rail has headroom completes at Step 3d.2 and never loads this file.

**Step 3d.3 -- Cap/unavailable: consult the cascade.** Log `"Primary rail capped for chunk [id]; consulting cascade."` then invoke the decision engine with kind and prompt on stdin. Airlift on cap fires inside `cascade-dispatch.sh` -- do not call Airlift here. Export `OPENROUTER_EXEC_ALLOWED_PATHS` as the exact complete owned-path allowlist consumed by the bounded adapter.

```bash
case "<executor>" in
  openrouter) PRIMARY_RAIL="openrouter" ;;
  codex) PRIMARY_RAIL="codex" ;;
  claude) PRIMARY_RAIL="codex" ;; # legacy manifest compatibility; Claude is non-coding-only
  *) case "<kind>" in
    config) PRIMARY_RAIL="openrouter" ;;
    logic) PRIMARY_RAIL="codex" ;;
    integration) PRIMARY_RAIL="codex" ;;
    ui) PRIMARY_RAIL="codex" ;;
    *) PRIMARY_RAIL="codex" ;;
  esac ;;
esac
PRIMARY_RAIL_STATUS="ready"
# Set this closed state only after a live cap/unavailability result or a current
# proactive probe proves the selected primary cannot run.
# PRIMARY_RAIL_STATUS="capped-or-unavailable"
OPENROUTER_EXEC_ALLOWED_PATHS="$CHUNK_FILES_TO_MODIFY_NEWLINE"
OPENROUTER_ATTEMPT_RECEIPT_DIR="plans/<feature-slug>/receipts/openrouter/<chunk-id>-cascade-<n>"
OPENROUTER_ATTEMPT_RECEIPT_TEMPLATE="$OPENROUTER_ATTEMPT_RECEIPT_DIR/provider-{attempt}.json"
mkdir -p "$OPENROUTER_ATTEMPT_RECEIPT_DIR"
OPENROUTER_RUN_ID="<run-id>"
OPENROUTER_LANE_ID="<chunk-id>"
export OPENROUTER_EXEC_ALLOWED_PATHS OPENROUTER_RUN_ID OPENROUTER_LANE_ID
run_cascade() {
  local exhausted_rail="${1:-}"
  if [ -n "$exhausted_rail" ]; then
    printf '%s' "$CHUNK_PROMPT" | "$CASCADE_DISPATCH" \
      --kind "<kind>" --prompt - --phase execute --timeout 3600 \
      --exhausted-rail "$exhausted_rail" \
      --attempt-receipt-template "$OPENROUTER_ATTEMPT_RECEIPT_TEMPLATE"
  else
    printf '%s' "$CHUNK_PROMPT" | "$CASCADE_DISPATCH" \
      --kind "<kind>" --prompt - --phase execute --timeout 3600 \
      --attempt-receipt-template "$OPENROUTER_ATTEMPT_RECEIPT_TEMPLATE"
  fi
}
CASCADE_EXHAUSTED_RAIL=""
case "$PRIMARY_RAIL_STATUS" in
  ready) ;;
  capped-or-unavailable) CASCADE_EXHAUSTED_RAIL="$PRIMARY_RAIL" ;;
  *) echo "invalid primary rail status: $PRIMARY_RAIL_STATUS" >&2; exit 1 ;;
esac
CASCADE_OUT=$(run_cascade "$CASCADE_EXHAUSTED_RAIL")
CASCADE_RC=$?
```

Automated OpenRouter rungs never enter payload approval: a coherent installed bundle plus either supported configured key input makes the rail available, and the adapter screens exact outbound bytes. Broker state and caller-supplied approval modes are ignored. Always pass the observed exhausted primary rail. Never parse model names -- the script owns class->ladder->role->rail resolution (`model-cascade.json` + `harness-profile.json`).

**Step 3d.4 -- Route the cascade result by exit code.**

| `CASCADE_RC` | Meaning | Orchestrator action |
|---|---|---|
| `64` | NATIVE rung. stdout is `{dispatch:"native",model,role,probe_rail}`. | Parse `model` and `role`. **Re-dispatch IN-PROCESS through the current host's native path**, then apply **Native Model Descent** below. Do NOT run anything from the script. Then proceed to Step 3e exactly as a normal dispatch. |
| `0` | `openrouter_exec`, wrapper, or codex-companion rung executed; stdout is produced text or a receipt. | If stdout includes `implementedBy: openrouter` or a JSON receipt with `"implementedBy": "openrouter"`, treat it as an agentic OpenRouter implementation receipt. Otherwise apply the **one-shot validity rule** below. |
| `76` | Ladder exhausted -- no configured rung above the quality floor had headroom. | Run **Step 3d.5 -- Rail-exhaustion ask gate** BEFORE any terminal receipt. The current exits are: **wait** -> parked resumable, `wait_category: human_gate` receipt carries the named reset time and resume instruction; **park, `PIPELINE_EXHAUSTION_ASK=0`, a fail-closed policy read, or any context that cannot reach the operator** -> flag the chunk failed and preserve resumable state. Do NOT silently ship partial output. |
| `77` | Missing/invalid key, unavailable provider/bundle, or automatic disclosure/output boundary decline. | Record the exact reason, then use the Codex fallback without prompting. |
| other | Bad args / engine error. | Fall back to Codex once. If Codex is unavailable, fail the chunk; do not route coding work to Claude. |

After every cascade settlement, inspect only the caller-owned numbered receipt files in that cascade attempt's fresh directory, in positive sequence order. Pair each rejected provider attempt with the corresponding content-free stable reason on stderr, then pass that file and its request-envelope digest to `record-attempt`. The last receipt is successful only when the cascade returned a committed `openrouter_exec` result. Do not copy prompt, response, or patch content into the chunk receipt. When a failed contacted attempt has no receipt, record it without `--openrouter-receipt`, producing `attempt_unmeasured`. Record the eventual Codex fallback as its own later attempt.

**Native Model Descent (RC 64).** The script emits a directive for the first model that clears the quality floor and exits 64. Walking the remainder is the orchestrator's job:

1. Resolve the native Codex path from `harness-profile.json` `_detect`: codex-companion from Claude Code, or `codex exec --model <model>` from Codex. Coding cascades never emit a Claude-native directive.
2. On model-unavailability, retry the next model in that role's native list. Unavailability is not a cap. Recognise at least:
   - `requires a newer version of Codex` -> next model (`gpt-5.5`).
   - `not supported when using Codex with a ChatGPT account` -> next model.
3. If the native list is exhausted, re-invoke `cascade-dispatch.sh` once with `--exhausted-rail <probe_rail>`, carrying forward prior exclusions. Loop guard: re-invoke with `--exhausted-rail` at most once per rail per chunk; a second RC 64 naming an already-failed model is treated as `76`.
4. Record the model in `modelUsed:`. `implementedBy:` remains `{codex|openrouter}`.

**One-shot validity rule (RC 0).** A wrapper rung is acceptable only for `kind: config` or `kind: doc` pure-text deliverables, or a cheap second-opinion that is not the implementation. For complex `logic`/`ui`/`integration`, a single-turn wrapper MUST fast-fail. Log `"Wrapper rung invalid for agentic chunk [id]; descending to Codex."` The agentic OpenRouter path is valid only when it writes files, performs fixed structural Git validation, commits, and emits an OpenRouter receipt. Executable project verification is always later native Codex review.

After a valid Codex or OpenRouter path produces a commit, write a receipt with `requestedProvider`, `attemptedProvider`, `implementedBy: {codex|openrouter}`, boolean `fallback`, `fallbackReason`, verification, and usage, then proceed to Step 3e. There is currently no executable `implementedBy: claude` exception.

**Step 3d.5 -- Rail-exhaustion ask gate.** RC 76 means every configured rail for this chunk is exhausted or gated. Capacity is recoverable. If the top-level interactive context can reach the operator, present the live rail status and offer exactly `wait` or `park`. Otherwise park resumably; `PIPELINE_EXHAUSTION_ASK=0` selects that behavior directly for headless CI.

The ask is scheduling only. It never selects a provider, authorizes another rail, broadens configured-key OpenRouter eligibility, weakens sensitive-path rules, or waives the final independent review. Record the measured pause with `wait_category: human_gate`; a wait receipt carries the named reset time and resume instruction.
