# Final Requirements Cross-Check

Feature: ai-developer-workflow-kernel
Date: 2026-07-15
Branch: codex/ai-developer-workflow-kernel-implementation
executionMode: codex_native

| # | Requirement | Addressed In | Evidence |
|---|---|---|---|
| 1 | Deliver the complete workflow-kernel improvement set rather than one isolated recommendation. | Chunks 01–06; `plugins/workflow-kernel/` | test:`FailureScenarioTests.test_failure_matrix_is_complete_strict_and_deterministically_replayable` -> passed in the 692-test Python 3.12 suite |
| 2 | Use the literal Depot pipeline with design, assessment, research, planning, adversarial review, execution, dm-review, verification, and cleanup gates. | `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py`; `plugins/pipeline/agents/workflow/execution-orchestrator.md` | grep:`rg -n 'deterministic_validation|evaluation_gate|browser_verification|merge_disposition|chunk_cleanup|requirements_cross_check' plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py` -> all six executable terminal-stage identities present; canonical Markdown retains earlier design through execution gates |
| 3 | Decompose delivery into safe, testable slices while preserving existing pipeline and dm-review compatibility. | `plans/ai-developer-workflow-kernel/manifest.json`; compatibility fixtures | test:`CompatibilityTests.test_claude_codex_and_generic_receipts_have_equal_semantics` -> passed |
| 4 | Build an executable control plane rather than adding orchestration prose alone. | `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/`; runtime CLI | test:`RuntimeCliTests.test_observe_pipeline_writes_shadow_artifact_only` -> passed |
| 5 | Preserve Claude/Codex behavior, provider security boundaries, evidence receipts, and honest degradation. | host authorization, receipt translation, compatibility suite | test:`HostCapabilityTests.test_incoherent_or_credential_like_routes_fail_closed` and `CompatibilityTests.test_missing_runtime_can_fall_back_without_changing_shadow_default` -> passed |
| 6 | Validate transitions and failure paths behaviorally, not only with text-contract checks. | transition, replay, state, and failure-scenario suites | test:`FailureScenarioTests.test_replay_derives_behavior_without_trusting_fixture_outcome_fields` -> passed |
| 7 | Deliver a clean feature branch with requirement-level evidence. | all six chunk receipts; this cross-check; release validator | build:passed — `git diff --check`, 692-test Python 3.12 suite, workflow-kernel validator, and full composition validation passed before final receipt publication |
| 8 | Use an additive Python standard-library kernel with shadow, enforce, and opt-in native modes. | `workflow_kernel/schema.py`; `workflow_kernel/promotion.py` | test:`PromotionTests.test_shadow_to_enforce_fails_closed_then_allows_complete_fixture_evidence` and `PromotionTests.test_native_default_is_always_separate_human_decision` -> passed |
| 9 | Keep the epic repo-local; do not add a daemon or external ticket ingestion. | `plugins/workflow-kernel/`; plugin manifests | grep:`rg -n 'requests|httpx|aiohttp|slack|notion|github' plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel -g '*.py'` -> no external service client or ticket-ingestion dependency present |
| 10 | Track and clean owned Git and Docker resources; automatically remove only Depot-labeled Docker resources older than 24 hours. | `workflow_kernel/resources.py`; Docker/Git adapters; cleanup contracts | test:`DockerLifecycleTests.test_stale_sweep_requires_both_label_and_inspected_age_to_exceed_ttl` and `DockerLifecycleTests.test_current_cleanup_requires_kind_id_and_nonempty_exact_label_snapshot` -> passed |
| 11 | Discover project UX suites and make declared personas blocking for UI/integration completion. | persona adapter, verification profile, Assembly fixtures | test:`PersonaGateTests.test_complete_set_requires_every_required_case_not_a_sample_count` and `PersonaGateTests.test_project_persona_adapter_executes_through_injected_executor` -> passed |
| 12 | On required-browser failure, capture evidence, restart the primary browser, try another browser engine, then require human help. | browser adapter, recovery schema, visual-review contracts | test:`BrowserRecoveryTests.test_failure_is_preserved_then_primary_process_quit_fresh_launch_and_retry` and `BrowserRecoveryTests.test_exhausted_secondary_blocks_for_human_with_exact_missing_case` -> passed |

Result: 12/12 addressed; 0 deferred; 0 unresolved.
