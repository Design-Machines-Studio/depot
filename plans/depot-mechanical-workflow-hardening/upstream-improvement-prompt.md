# Depot Upstream Improvement Run

Run this work through the full `/pipeline` workflow in the Design-Machines/depot repository.
Preserve this prompt as `original-prompt.md` and run a fresh final review.

## Authority and compatibility fences

- The structured upstream-improvements.json report is authoritative; this Markdown is a projection.
- Do not merge, release, edit marketplace data, or mutate installed plugin caches.
- Preserve Claude/Codex compatibility and do not invent savings or unavailable telemetry.

## Evidence-backed candidates

### improvement-v1:sha256:9d702688ba864ef7e8aef071bc50ff750761e6cf89f88a2f0357afb9e8350f3f

- Category: `existing_check_repair`
- Status: `recurring`
- Observed problem: A live sibling declaration error again collapsed an otherwise clean Depot-owned release suite into one opaque nonzero result.
- Evidence: plans/adaptive-fusion-verification/run-postmortem.md, plans/depot-mechanical-workflow-hardening/run-postmortem.md
- Owner: `workflow-kernel`
- Proposed surfaces: tools/validate-workflow-kernel.py, tools/validate-composition.sh
- Mechanical work: Emit separate named Depot-owned release and live sibling compatibility results while preserving a nonzero combined result when either required lane fails.
- Agent/human judgment retained: Humans retain authority to decide whether a sibling compatibility failure blocks a particular release; the tool only separates evidence.
- Acceptance tests: A Depot-owned failure is reported in the owned lane.; A malformed live sibling declaration is reported only in the sibling integration lane.; The combined release result remains nonzero when either required lane fails.
- Safety boundary: Do not weaken or skip the live sibling compatibility check and do not mutate the sibling repository.
- Compatibility: Preserve Claude and Codex validator entry points and current stable exit behavior.
- Benefit basis: `qualitative`
- Benefit outcome: `improved_observability`
- Benefit rationale: Separate evidence shortens diagnosis while keeping both authority boundaries visible.

### improvement-v1:sha256:a92d272031e2f16120128ec5d604f72b423f430d2829c8b5a876524067632b05

- Category: `new_deterministic_check`
- Status: `one-off`
- Observed problem: The terminal observer consumed all receipts but could not prove the prediction binding, and the gap was not diagnosed until closeout.
- Evidence: plans/depot-mechanical-workflow-hardening/pipeline-shadow-observation.json
- Owner: `pipeline`
- Proposed surfaces: plugins/pipeline/commands/pipeline.md, plugins/pipeline/agents/workflow/execution-orchestrator.md
- Mechanical work: After sealing prediction evidence, run a read-only binding verification and persist an exact failure category before the first authoritative action.
- Agent/human judgment retained: The self-check reports binding state only; Pipeline Markdown and human gates remain authoritative and no automatic rebind is permitted.
- Acceptance tests: A valid pre-start binding reports usable before run.started.; A mismatched state directory fails before authoritative actions.; No command can repair or rebind prediction evidence after actions begin.
- Safety boundary: Observation only; never advance workflow state, rewrite prediction evidence, or authorize merge or cleanup.
- Compatibility: Preserve shadow-mode behavior and stable Claude/Codex command adapters.
- Benefit basis: `qualitative`
- Benefit outcome: `improved_observability`
- Benefit rationale: Earlier binding diagnosis avoids terminal-only parity investigation without claiming token savings.
