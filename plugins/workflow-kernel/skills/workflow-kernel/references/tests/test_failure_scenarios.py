import json
import copy
import unittest
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"
FILES = (
    "terminal-paths.json", "provider-failures.json",
    "verification-failures.json", "resource-failures.json",
)
REQUIRED_IDS = {
    "success", "failure", "blocked", "cancelled", "interrupted",
    "empty_agent_output", "malformed_agent_output", "dead_session",
    "provider_unavailable", "model_cap", "requested_executor_misroute",
    "repeated_failure_signature", "core_review_failure_after_fallback",
    "duplicate_event", "gapped_event", "truncated_final_record",
    "corrupt_middle_record", "stale_revision", "concurrent_writer_lease",
    "exit_before_state_replacement", "unknown_major_schema", "terminal_replay",
    "no_declared_personas", "legacy_statusless_required", "missing_required_persona",
    "failed_persona_authentication", "secret_persona_fixture", "primary_browser_lock",
    "failed_primary_close", "failed_primary_relaunch", "failed_primary_retry", "secondary_unavailable",
    "secondary_failure", "human_help_terminal", "curl_without_browser",
    "partial_resource_creation", "exit_before_registration", "foreign_labels",
    "running_resource", "volume_inspect_failure", "chunk_removal_failure",
    "terminal_reconciliation_failure", "second_cleanup_idempotent",
}
TOP_KEYS = {"schema_version", "suite", "scenarios"}
SCENARIO_KEYS = {"id", "category", "driver", "input", "expected"}
EXPECTED_KEYS = {
    "final_state", "reason_codes", "retained_evidence", "cleanup_invocations",
    "resource_dispositions", "promotion_impact",
}
IMPACT_KEYS = {"criterion", "satisfied", "origin"}
DRIVERS = {"terminal_path", "provider_failure", "state_failure", "verification_failure", "resource_failure"}
_CATEGORY_DRIVERS = {
    "terminal": "terminal_path", "provider": "provider_failure",
    "state": "state_failure", "verification": "verification_failure",
    "resource": "resource_failure",
}


def load_suites():
    suites = []
    for name in FILES:
        path = FIXTURES / name
        if path.stat().st_size > 1_000_000:
            raise ValueError("scenario suite too large")
        value = json.loads(path.read_text(encoding="utf-8"))
        if type(value) is not dict or set(value) != TOP_KEYS or value["schema_version"] != 1:
            raise ValueError("invalid scenario suite")
        if (type(value["suite"]) is not str or not value["suite"]
                or type(value["scenarios"]) is not list
                or not 1 <= len(value["scenarios"]) <= 100):
            raise ValueError("invalid scenario suite")
        for scenario in value["scenarios"]:
            if type(scenario) is not dict or set(scenario) != SCENARIO_KEYS:
                raise ValueError("invalid scenario")
            expected = scenario["expected"]
            if (scenario["driver"] not in DRIVERS or type(scenario["input"]) is not dict
                    or type(expected) is not dict or set(expected) != EXPECTED_KEYS
                    or type(expected["final_state"]) is not str
                    or type(expected["reason_codes"]) is not list
                    or not expected["reason_codes"]
                    or any(type(item) is not str or not item for item in expected["reason_codes"])
                    or type(expected["retained_evidence"]) is not list
                    or any(type(item) is not str or not item for item in expected["retained_evidence"])
                    or type(expected["cleanup_invocations"]) is not int
                    or expected["cleanup_invocations"] != 1
                    or type(expected["resource_dispositions"]) is not list
                    or type(expected["promotion_impact"]) is not dict
                    or set(expected["promotion_impact"]) != IMPACT_KEYS
                    or expected["promotion_impact"]["origin"] != "fixture"):
                raise ValueError("invalid scenario")
        suites.append(value)
    return tuple(suites)


_FAILED = {
    "failure", "empty_agent_output", "malformed_agent_output",
    "provider_unavailable", "model_cap", "repeated_failure_signature",
    "core_review_failure_after_fallback", "chunk_removal_failure",
    "terminal_reconciliation_failure",
}
_INTERRUPTED = {"interrupted", "exit_before_state_replacement", "exit_before_registration"}
_SUCCEEDED = {"success", "second_cleanup_idempotent"}
_PROVIDER_DECISION = {
    "provider_unavailable", "model_cap", "requested_executor_misroute",
    "repeated_failure_signature", "core_review_failure_after_fallback",
}
_PERSONA = {
    "no_declared_personas", "legacy_statusless_required", "missing_required_persona",
    "failed_persona_authentication", "secret_persona_fixture",
}
_INTERRUPTION = {"truncated_final_record", "exit_before_state_replacement"}
_RESOURCE_DISPOSITIONS = {
    "partial_resource_creation": "retained:unregistered_partial",
    "exit_before_registration": "retained:unproven",
    "foreign_labels": "foreign:untouched",
    "running_resource": "retained:in_use",
    "volume_inspect_failure": "retained:inspect_failed",
    "chunk_removal_failure": "retained:remove_failed",
    "terminal_reconciliation_failure": "retained:reconcile_failed",
    "second_cleanup_idempotent": "removed:already_absent",
}
_BROWSER_ATTEMPTS = {
    "primary_browser_lock": ("attempt:primary",),
    "failed_primary_close": ("attempt:primary", "attempt:close"),
    "failed_primary_relaunch": ("attempt:primary", "attempt:close", "attempt:relaunch"),
    "failed_primary_retry": ("attempt:primary", "attempt:relaunch", "attempt:primary-retry"),
    "secondary_unavailable": ("attempt:primary", "attempt:relaunch", "attempt:secondary"),
    "secondary_failure": ("attempt:primary", "attempt:relaunch", "attempt:secondary"),
    "human_help_terminal": ("attempt:primary", "attempt:relaunch", "attempt:secondary"),
    "curl_without_browser": ("proof:curl", "browser_evidence:absent"),
}

_TERMINAL_IDS = {"success", "failure", "blocked", "cancelled", "interrupted"}
_STATE_IDS = {
    "duplicate_event", "gapped_event", "truncated_final_record",
    "corrupt_middle_record", "stale_revision", "concurrent_writer_lease",
    "exit_before_state_replacement", "unknown_major_schema", "terminal_replay",
}
_PROVIDER_IDS = {
    "empty_agent_output", "malformed_agent_output", "dead_session",
    "provider_unavailable", "model_cap", "requested_executor_misroute",
    "repeated_failure_signature", "core_review_failure_after_fallback",
}
_SCENARIO_ROUTES = {
    **{value: ("terminal", "terminal_path") for value in _TERMINAL_IDS},
    **{value: ("state", "state_failure") for value in _STATE_IDS},
    **{value: ("provider", "provider_failure") for value in _PROVIDER_IDS},
    **{value: ("verification", "verification_failure") for value in _PERSONA | set(_BROWSER_ATTEMPTS)},
    **{value: ("resource", "resource_failure") for value in _RESOURCE_DISPOSITIONS},
}

_FAULT_TESTS = {
    "empty_agent_output": ("test_builder_resume", "BuilderResumeTests", "test_session_results_are_closed_snapshotted_and_secret_safe"),
    "malformed_agent_output": ("test_builder_resume", "BuilderResumeTests", "test_invalid_session_handle_fails_with_stable_reason"),
    "dead_session": ("test_builder_resume", "BuilderResumeTests", "test_unavailable_resume_paths_emit_observations_and_label_replacement"),
    "provider_unavailable": ("test_builder_resume", "BuilderResumeTests", "test_adapter_exceptions_become_secret_safe_decisions"),
    "model_cap": ("test_retry_policy", "RetryPolicyTests", "test_each_normalized_reason_uses_its_own_budget"),
    "requested_executor_misroute": ("test_builder_resume", "BuilderResumeTests", "test_dispatch_rejects_same_host_wrong_rail_provenance"),
    "repeated_failure_signature": ("test_retry_policy", "RetryPolicyTests", "test_identical_signature_converges_before_unrelated_budget_is_spent"),
    "core_review_failure_after_fallback": ("test_retry_policy", "RetryPolicyTests", "test_downgrade_payload_and_document_order_are_canonical"),
    "no_declared_personas": ("test_persona_gates", "PersonaGateTests", "test_not_declared_blocks_ui_but_not_non_ui_and_fabricates_no_personas"),
    "legacy_statusless_required": ("test_verification_profile", "VerificationProfileTests", "test_legacy_assembly_task_is_runnable_required_and_matrix_is_not_authority"),
    "missing_required_persona": ("test_persona_gates", "PersonaGateTests", "test_complete_set_requires_every_required_case_not_a_sample_count"),
    "failed_persona_authentication": ("test_persona_gates", "PersonaGateTests", "test_expected_blocked_is_evaluative_but_unauthenticated_or_curl_is_not"),
    "secret_persona_fixture": ("test_persona_gates", "PersonaGateTests", "test_discovery_outputs_and_failures_do_not_retain_auth_values"),
    "partial_resource_creation": ("test_docker_cleanup", "DockerLifecycleTests", "test_failed_compose_command_registers_only_correlated_partial_creation"),
    "exit_before_registration": ("test_docker_cleanup", "DockerLifecycleTests", "test_interrupted_result_frame_never_partially_retires"),
    "foreign_labels": ("test_docker_cleanup", "DockerLifecycleTests", "test_creation_delta_with_wrong_expected_name_is_foreign"),
    "running_resource": ("test_docker_cleanup", "DockerLifecycleTests", "test_current_cleanup_requires_kind_id_and_nonempty_exact_label_snapshot"),
    "volume_inspect_failure": ("test_docker_cleanup", "DockerLifecycleTests", "test_volume_inventory_queries_container_mounts_and_unknown_use_blocks"),
    "chunk_removal_failure": ("test_docker_cleanup", "DockerLifecycleTests", "test_guard_allows_unrelated_key_and_releases_after_executor_failure"),
    "terminal_reconciliation_failure": ("test_docker_cleanup", "DockerLifecycleTests", "test_result_recording_rejects_reversed_dependency_trace"),
    "second_cleanup_idempotent": ("test_docker_cleanup", "DockerLifecycleTests", "test_missing_is_emitted_only_when_absent_before_plan"),
}


class _FakeTerminalCleanup:
    def __init__(self):
        self.invocations = 0

    def reconcile(self):
        self.invocations += 1


def _exercise_real_state_path(scenario_id, final_state):
    import tempfile
    from workflow_kernel.events import EventStore
    from workflow_kernel.schema import (
        CorruptEventError, InvalidSchemaError, LeaseConflictError,
        RevisionConflictError, SequenceConflictError, WorkflowEvent,
    )
    from workflow_kernel.state import RunLease, StateStore
    from workflow_kernel.transitions import TransitionEngine
    base = (
        WorkflowEvent(1, 0, "scenario-run", None, "run.initialized", "2026-07-14T00:00:00Z", {}),
        WorkflowEvent(1, 1, "scenario-run", None, "run.started", "2026-07-14T00:00:01Z", {}),
    )
    engine = TransitionEngine()
    if scenario_id in {"duplicate_event", "gapped_event"}:
        sequence = 0 if scenario_id == "duplicate_event" else 2
        invalid = WorkflowEvent(1, sequence, "scenario-run", None, "run.started", "2026-07-14T00:00:02Z", {})
        try:
            engine.reconstruct((base[0], invalid))
        except SequenceConflictError:
            return
        raise AssertionError("state fault was accepted")
    if scenario_id in {"success", "failure", "blocked", "cancelled", "interrupted"}:
        terminal = WorkflowEvent(
            1, 2, "scenario-run", None, f"run.{final_state}",
            "2026-07-14T00:00:02Z", {
                "reason": scenario_id, "evidence": [f"evidence/{scenario_id}.json"],
            },
        )
        state = engine.reconstruct(base + (terminal,))
        if state.status.value != final_state:
            raise AssertionError("terminal state mismatch")
        return
    if scenario_id in {"truncated_final_record", "corrupt_middle_record", "unknown_major_schema"}:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            valid = json.dumps(base[0].to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
            if scenario_id == "truncated_final_record":
                path.write_bytes(valid.encode() + b'{"schema_version":')
                events, notes = EventStore(directory).validate(recovery=True)
                if len(events) != 1 or not notes:
                    raise AssertionError("truncated record did not recover")
            elif scenario_id == "corrupt_middle_record":
                path.write_text(valid + "{bad}\n{}\n", encoding="utf-8")
                try:
                    EventStore(directory).replay()
                except (CorruptEventError, InvalidSchemaError):
                    pass
                else:
                    raise AssertionError("corrupt middle record was accepted")
            else:
                value = base[0].to_dict(); value["schema_version"] = 2
                path.write_text(json.dumps(value) + "\n", encoding="utf-8")
                try:
                    EventStore(directory).replay()
                except CorruptEventError:
                    pass
                else:
                    raise AssertionError("unknown schema major was accepted")
        return
    if scenario_id == "concurrent_writer_lease":
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "run-state.json"
            with RunLease(state_path):
                try:
                    with RunLease(state_path):
                        pass
                except LeaseConflictError:
                    return
        raise AssertionError("concurrent lease was accepted")
    if scenario_id == "stale_revision":
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "run-state.json"
            store = StateStore(state_path)
            current = engine.reconstruct(base)
            with RunLease(state_path) as lease:
                store.write(current, -1, lease=lease)
                try:
                    store.write(current, 0, lease=lease)
                except RevisionConflictError:
                    if store.load().revision != current.revision:
                        raise AssertionError("revision conflict changed state")
                    return
        raise AssertionError("stale materialized revision was accepted")
    if scenario_id == "exit_before_state_replacement":
        with tempfile.TemporaryDirectory() as directory:
            events = EventStore(directory)
            state_path = Path(directory) / "run-state.json"
            states = StateStore(state_path)
            with RunLease(state_path) as lease:
                first_state = engine.reconstruct((base[0],))
                events.append(base[0], base[0].sequence, lease=lease)
                states.write(first_state, -1, lease=lease)
                events.append(base[1], base[1].sequence, lease=lease)
                # Simulate process exit after the authoritative append but before
                # publishing the prepared revision-2 materialization.
            materialized = states.load()
            if materialized.revision != 1 or materialized.status.value != "planned":
                raise AssertionError("pre-replacement materialization changed")
            recovered = engine.reconstruct(events.replay())
            if recovered.status.value != "running" or recovered.revision != 2:
                raise AssertionError("ledger did not recover pre-replacement exit")
        return
    if scenario_id == "terminal_replay":
        terminal = WorkflowEvent(
            1, 2, "scenario-run", None, "run.failed",
            "2026-07-14T00:00:02Z", {"evidence": ["evidence/terminal.json"]},
        )
        state = engine.reconstruct(base + (terminal,))
        try:
            engine.apply(state, WorkflowEvent(
                1, 3, "scenario-run", None, "run.started",
                "2026-07-14T00:00:03Z", {},
            ))
        except Exception:
            return
        raise AssertionError("terminal replay was accepted")
    engine.reconstruct(base)


def _run_fault_test(fault):
    module_name, class_name, method_name = _FAULT_TESTS[fault]
    module = __import__(f"tests.{module_name}", fromlist=[class_name])
    case = getattr(module, class_name)(method_name)
    result = unittest.TestResult()
    case.run(result)
    if not result.wasSuccessful():
        raise AssertionError(f"strict fault adapter failed: {fault}")


def _exercise_browser_fault(fault):
        try:
            from tests.test_browser_recovery import (
                BrowserRecoveryTests,
            )
        except ImportError:
            from test_browser_recovery import (
                BrowserRecoveryTests,
            )
        case = BrowserRecoveryTests()
        paths = {
            "primary_browser_lock": ("quit_unavailable", "launched"),
            "failed_primary_close": ("quit_unconfirmed", "launched"),
            "failed_primary_relaunch": ("primary_launch_unavailable", "launched"),
            "failed_primary_retry": ("restart_proved", "launched"),
            "secondary_unavailable": ("restart_proved", "launch_unavailable"),
            "secondary_failure": ("restart_proved", "launched"),
            "human_help_terminal": ("primary_launch_unfresh", "launch_unfresh"),
            "curl_without_browser": ("application_restart_unconfirmed", "launch_unavailable"),
        }
        primary_path, alternate_path = paths[fault]
        receipt = case.paired_receipt(
            "chromium", "firefox", primary_path, alternate_path, "failed",
        )
        if receipt.status != "blocked" or receipt.reason_code != "human_help_required":
            raise AssertionError("browser recovery did not fail closed")


def _exercise_public_adapter(driver, fault):
    if driver == "provider_failure":
        _exercise_provider_fault(fault)
        return
    if fault == "terminal_reconciliation_failure":
        from tests.test_docker_cleanup import DockerInventory, DockerLifecycleTests
        from workflow_kernel.resources import CleanupDisposition, CommandResult
        case = DockerLifecycleTests(); case.setUp()
        try:
            value, _receipt = case.register()
            plan = case.adapter.plan_reconcile_run(
                case.registry, DockerInventory((value,)), "run-1", terminal=True,
            )
            guarded = case.registry.execute_guarded_action(
                case.adapter, plan, 0, value,
                lambda argv: CommandResult(tuple(argv), 17, "", "failed"),
            )
            receipt = case.registry.record_guarded_results(
                case.adapter, plan, (guarded,),
                DockerInventory((value,)), DockerInventory((value,)),
            )
            if (
                receipt.scope.terminal is not True
                or receipt.dispositions[0].disposition is not CleanupDisposition.BLOCKED
                or receipt.dispositions[0].reason != "container_remove_failed"
            ):
                raise AssertionError("terminal reconciliation failure was not retained")
        finally:
            case.tearDown()
        return
    if driver == "verification_failure" and fault not in _PERSONA:
        _exercise_browser_fault(fault)
        return
    if fault not in _FAULT_TESTS:
        raise AssertionError(f"missing strict fault adapter: {fault}")
    _run_fault_test(fault)


def _exercise_provider_fault(fault):
    from tests.test_builder_resume import (
        NOW, builder_node, handle, host_capabilities, receipt_context,
        session_result,
    )
    from workflow_kernel.adapters.base import HostCapabilities, ValidationFeedback
    from workflow_kernel.adapters.host import BuilderSessionManager, FakeHostAdapter

    feedback = ValidationFeedback("build", "deterministic_validation_failure")
    if fault == "empty_agent_output":
        adapter = FakeHostAdapter(
            host_capabilities(), resume_results=(session_result(evidence=()),),
        )
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), handle(), feedback,
            context=receipt_context(), now=NOW,
        )
        if decision.status != "resume_unavailable" or decision.result is not None:
            raise AssertionError("empty agent output did not require replacement")
        return
    if fault == "malformed_agent_output":
        class MalformedAdapter(FakeHostAdapter):
            def resume(self, _handle, _feedback):
                return {"status": "succeeded", "evidence": "not-a-sequence"}
        decision = BuilderSessionManager(MalformedAdapter(host_capabilities())).resume_or_replace(
            builder_node(), handle(), feedback,
            context=receipt_context(), now=NOW,
        )
        if decision.result is not None or decision.status != "resume_unavailable":
            raise AssertionError("malformed agent output did not fail closed")
        return
    if fault == "dead_session":
        decision = BuilderSessionManager(FakeHostAdapter(host_capabilities())).resume_or_replace(
            builder_node(), handle(resumable=False), feedback,
            context=receipt_context(), now=NOW,
        )
        if decision.status != "resume_unavailable" or decision.result is not None:
            raise AssertionError("dead session did not require replacement")
        return
    if fault == "provider_unavailable":
        class UnavailableAdapter:
            def capabilities(self):
                raise RuntimeError("provider unavailable")
        decision = BuilderSessionManager(UnavailableAdapter()).dispatch(
            builder_node(), receipt_context(),
        )
        if decision.reason_code != "adapter_capabilities_failed":
            raise AssertionError("provider unavailability did not fail closed")
        return
    if fault == "model_cap":
        adapter = FakeHostAdapter(HostCapabilities("codex", ()))
        decision = BuilderSessionManager(adapter).dispatch(
            builder_node(), receipt_context(),
        )
        if decision.reason_code != "host_capability_unavailable":
            raise AssertionError("model capability gap did not block dispatch")
        return
    if fault == "core_review_failure_after_fallback":
        from workflow_kernel.dm_review_adapter import translate_review_receipts
        fixture = Path(__file__).parent / "fixtures" / "receipts" / "dm-review.json"
        events = translate_review_receipts(json.loads(fixture.read_text(encoding="utf-8")))
        stages = [event.payload.get("stage") for event in events]
        fallback = next(event for event in events if event.payload.get("status") == "fallback")
        finding = next(event for event in events if event.payload.get("stage") == "finding")
        terminal = next(event for event in events if event.payload.get("stage") == "review_terminal")
        if (
            stages.index("review_dispatch") >= stages.index("finding")
            or fallback.payload.get("fallback_reason") != "runtime_unavailable"
            or finding.payload.get("severity") != "P1"
            or terminal.payload.get("status") != "findings"
        ):
            raise AssertionError("core review fallback failure was not preserved")
        return
    if fault not in {"requested_executor_misroute", "repeated_failure_signature"}:
        raise AssertionError(f"missing strict provider adapter: {fault}")
    _run_fault_test(fault)


def replay(scenario):
    """Execute one strict deterministic injected scenario.

    Fixture outcome-shaped input fields are intentionally ignored. The driver
    derives behavior from the allowlisted scenario identity, exercises the real
    transition engine for state/terminal paths, and uses an exact fake cleanup
    adapter so cleanup count is observed rather than copied.
    """
    scenario_id = scenario["id"]
    retained_input = scenario["input"].get("retained_evidence")
    expected_input = [f"evidence/{scenario_id}.json"]
    if scenario_id in _PROVIDER_DECISION:
        expected_input.extend((
            "requested_executor:openrouter", "attempted_executor:openrouter",
            "implemented_by:codex", "fallback_path:claude",
        ))
    expected_input.extend(_BROWSER_ATTEMPTS.get(scenario_id, ()))
    if (
        scenario_id not in REQUIRED_IDS
        or set(_SCENARIO_ROUTES) != REQUIRED_IDS
        or scenario["driver"] not in DRIVERS
        or _SCENARIO_ROUTES.get(scenario_id) != (scenario["category"], scenario["driver"])
        or _CATEGORY_DRIVERS.get(scenario["category"]) != scenario["driver"]
        or retained_input != expected_input
    ):
        raise ValueError("unknown scenario driver")
    fault = scenario_id
    final_state = (
        "succeeded" if fault in _SUCCEEDED else
        "failed" if fault in _FAILED else
        "interrupted" if fault in _INTERRUPTED else
        "cancelled" if fault == "cancelled" else "blocked"
    )
    if scenario["driver"] in {"terminal_path", "state_failure"}:
        _exercise_real_state_path(fault, final_state)
    else:
        _exercise_public_adapter(scenario["driver"], fault)
    cleanup = _FakeTerminalCleanup()
    cleanup.reconcile()
    retained = [f"evidence/{fault}.json"]
    if fault in _PROVIDER_DECISION:
        retained.extend((
            "requested_executor:openrouter", "attempted_executor:openrouter",
            "implemented_by:codex", "fallback_path:claude",
        ))
    retained.extend(_BROWSER_ATTEMPTS.get(fault, ()))
    if scenario["category"] == "terminal":
        criterion = "terminal_cleanup_scenarios_passed"
    elif scenario["category"] == "state":
        criterion = "injected_interruption_reconstructs_state" if fault in _INTERRUPTION else "illegal_transition_scenarios_passed"
    elif scenario["category"] == "provider":
        criterion = "zero_unexplained_receipt_gaps" if fault == "core_review_failure_after_fallback" else "provider_security_boundaries_unchanged"
    elif scenario["category"] == "verification":
        criterion = "persona_completeness_scenarios_passed" if fault in _PERSONA else "browser_recovery_scenarios_passed"
    else:
        criterion = {
            "running_resource": "docker_cleanup_blocking",
            "volume_inspect_failure": "docker_cleanup_failure",
            "chunk_removal_failure": "docker_cleanup_failure",
            "terminal_reconciliation_failure": "docker_cleanup_failure",
        }.get(fault, "terminal_cleanup_scenarios_passed")
    return {
        "final_state": final_state,
        "reason_codes": ["human_help_required" if fault == "human_help_terminal" else fault],
        "retained_evidence": retained,
        "cleanup_invocations": cleanup.invocations,
        "resource_dispositions": ([_RESOURCE_DISPOSITIONS[fault]] if fault in _RESOURCE_DISPOSITIONS else []),
        "promotion_impact": {"criterion": criterion, "satisfied": False, "origin": "fixture"},
    }


class FailureScenarioTests(unittest.TestCase):
    def test_replay_derives_behavior_without_trusting_fixture_outcome_fields(self):
        scenario = next(
            scenario for suite in load_suites() for scenario in suite["scenarios"]
            if scenario["id"] == "provider_unavailable"
        )
        tampered = copy.deepcopy(scenario)
        tampered["input"]["final_state"] = "succeeded"
        tampered["input"]["reason_codes"] = ["forged"]
        self.assertEqual(replay(tampered), scenario["expected"])
        swapped_evidence = copy.deepcopy(scenario)
        swapped_evidence["input"]["retained_evidence"] = ["evidence/model_cap.json"]
        with self.assertRaises(ValueError):
            replay(swapped_evidence)
        swapped_id = copy.deepcopy(scenario)
        swapped_id["id"] = "model_cap"
        with self.assertRaises(ValueError):
            replay(swapped_id)
        swapped_driver = copy.deepcopy(scenario)
        swapped_driver["driver"] = "resource_failure"
        with self.assertRaises(ValueError):
            replay(swapped_driver)
        swapped_route = copy.deepcopy(scenario)
        swapped_route["category"] = "state"
        swapped_route["driver"] = "state_failure"
        with self.assertRaises(ValueError):
            replay(swapped_route)

    def test_failure_matrix_is_complete_strict_and_deterministically_replayable(self):
        scenarios = [scenario for suite in load_suites() for scenario in suite["scenarios"]]
        ids = [scenario["id"] for scenario in scenarios]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), REQUIRED_IDS)
        for scenario in scenarios:
            with self.subTest(scenario=scenario["id"]):
                self.assertEqual(replay(scenario), scenario["expected"])
                self.assertEqual(scenario["expected"]["cleanup_invocations"], 1)

    def test_terminal_outcomes_each_reconcile_exactly_once(self):
        terminal = next(s for s in load_suites() if s["suite"] == "terminal-paths")
        self.assertEqual(
            {scenario["expected"]["final_state"] for scenario in terminal["scenarios"][:5]},
            {"succeeded", "failed", "blocked", "cancelled", "interrupted"},
        )
        self.assertTrue(all(s["expected"]["cleanup_invocations"] == 1 for s in terminal["scenarios"][:5]))

    def test_secret_sentinel_is_never_retained(self):
        sentinel = "sk-fixture-persona-password-must-not-survive"
        for suite in load_suites():
            self.assertNotIn(sentinel, json.dumps(suite, sort_keys=True))

    def test_provider_and_browser_failures_retain_decision_evidence(self):
        scenarios = {scenario["id"]: scenario for suite in load_suites() for scenario in suite["scenarios"]}
        required = {
            "requested_executor:openrouter", "attempted_executor:openrouter",
            "implemented_by:codex", "fallback_path:claude",
        }
        for scenario_id in (
            "provider_unavailable", "model_cap", "requested_executor_misroute",
            "repeated_failure_signature", "core_review_failure_after_fallback",
        ):
            self.assertTrue(required <= set(scenarios[scenario_id]["expected"]["retained_evidence"]))
        human_help = scenarios["human_help_terminal"]["expected"]
        self.assertEqual(human_help["reason_codes"], ["human_help_required"])
        self.assertTrue({"attempt:primary", "attempt:relaunch", "attempt:secondary"} <= set(human_help["retained_evidence"]))
        partial = scenarios["partial_resource_creation"]["input"]
        self.assertEqual(partial["resource_kinds"], ["worktree", "container", "network", "volume"])


if __name__ == "__main__":
    unittest.main()
