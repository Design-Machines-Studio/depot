import unittest

from tests import detail_digest
from workflow_kernel.adapters.base import (
    BuilderObservation, BuilderOutcome, GateDecision, HostCapabilities,
    HostCapability, NodeSpec, ResumeStateContext, SessionHandle, SessionResult,
    ValidationFeedback,
)
from workflow_kernel.adapters.host import BuilderSessionManager, FakeHostAdapter
from workflow_kernel.adapters.host import capabilities_from_harness_profile
from workflow_kernel.schema import InvalidSchemaError, RunState, WorkflowEvent
from workflow_kernel.transitions import TransitionEngine
from workflow_kernel.workflows import WorkflowTemplates
from workflow_kernel.adapters.base import WorkflowClass, WorkflowContext


NOW = "2026-07-14T00:00:00Z"


def handle(host="codex", value="opaque-token-value", *, resumable=True, created_at=NOW):
    return SessionHandle(host, value, created_at, resumable)


def host_capabilities(name="codex"):
    return HostCapabilities(name, (
        HostCapability.NATIVE_DISPATCH, HostCapability.SESSION_RESUME,
        HostCapability.CODEX_EXECUTION,
    ))


def builder_node(**changes):
    values = {
        "node_id": "build", "executor": "codex",
        "required_capability": HostCapability.CODEX_EXECUTION,
    }
    values.update(changes)
    return NodeSpec(**values)


class BuilderResumeTests(unittest.TestCase):
    def test_real_handle_is_resumed_with_deterministic_validation_feedback(self):
        original = handle()
        result = SessionResult("succeeded", ("validation.txt",))
        adapter = FakeHostAdapter(host_capabilities(), resume_results=(result,))
        feedback = ValidationFeedback(
            "build", "deterministic_validation_failure", ("test-report.txt",),
        )
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), original, feedback, now=NOW,
        )
        self.assertEqual(decision.status, "resumed")
        self.assertTrue(decision.resumed_original)
        self.assertIsNot(decision.handle, original)
        self.assertEqual(decision.handle, original)
        self.assertEqual(adapter.resume_calls, [(original, feedback)])
        self.assertEqual(decision.observations, (BuilderObservation.SESSION_RESUMED,))
        self.assertEqual(decision.outcome, BuilderOutcome.SESSION_RESUMED)

    def test_unavailable_resume_paths_emit_observations_and_label_replacement(self):
        cases = {
            "missing": None,
            "non_resumable": handle(resumable=False),
            "stale": handle(created_at="2026-07-13T00:00:00Z"),
            "foreign": handle(host="claude-code"),
        }
        for name, original in cases.items():
            with self.subTest(name=name):
                replacement = handle(value="replacement-value")
                adapter = FakeHostAdapter(host_capabilities(), dispatch_handles=(replacement,))
                decision = BuilderSessionManager(adapter, max_age_seconds=3600).resume_or_replace(
                    builder_node(), original,
                    ValidationFeedback("build", "deterministic_validation_failure"),
                    now=NOW,
                )
                self.assertEqual(decision.status, "replacement_dispatched")
                self.assertFalse(decision.resumed_original)
                self.assertIsNot(decision.handle, replacement)
                self.assertEqual(decision.handle, replacement)
                self.assertEqual(decision.reason_code, "session_resume_unavailable")
                self.assertEqual(
                    decision.observations,
                    (BuilderObservation.SESSION_RESUME_UNAVAILABLE,
                     BuilderObservation.BUILDER_REPLACEMENT_DISPATCHED),
                )
                self.assertEqual(adapter.resume_calls, [])

    def test_missing_replacement_handle_is_not_fabricated(self):
        adapter = FakeHostAdapter(host_capabilities())
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), None,
            ValidationFeedback("build", "deterministic_validation_failure"),
            now=NOW,
        )
        self.assertEqual(decision.status, "resume_unavailable")
        self.assertIsNone(decision.handle)
        self.assertEqual(
            decision.observations, (BuilderObservation.SESSION_RESUME_UNAVAILABLE,),
        )

    def test_builder_observations_project_to_legal_evidence_without_lifecycle_claims(self):
        engine = TransitionEngine()
        state = RunState.new("run-1", NOW)
        events = (
            WorkflowEvent(1, 0, "run-1", None, "run.initialized", NOW, {}),
            WorkflowEvent(1, 1, "run-1", None, "run.started", NOW, {}),
            WorkflowEvent(1, 2, "run-1", "build", "node.added", NOW,
                          {"dependencies": []}),
            WorkflowEvent(1, 3, "run-1", "build", "node.ready", NOW, {}),
            WorkflowEvent(1, 4, "run-1", "build", "node.started", NOW, {}),
            WorkflowEvent(1, 5, "run-1", "build", "evidence.recorded", NOW,
                          {"evidence": ["validation/failure-report"]}),
            WorkflowEvent(1, 6, "run-1", "build", "node.failed", NOW, {}),
        )
        for item in events:
            state = engine.apply(state, item)
        adapter = FakeHostAdapter(host_capabilities(), dispatch_handles=(handle(),))
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), None,
            ValidationFeedback("build", "deterministic_validation_failure"), now=NOW,
        )
        projected = decision.to_evidence_event(
            run_id="run-1", sequence=state.revision, node_id="build", occurred_at=NOW,
        )
        self.assertEqual(projected.kind, "evidence.recorded")
        state = engine.apply(state, projected)
        self.assertIn("builder-observation/session-resume-unavailable",
                      state.nodes["build"].evidence)

    def test_session_serialization_redacts_opaque_values_and_credentials(self):
        secret = "sk-provider-credential"
        value = "session:" + secret
        session = handle(value=value)
        serialized = session.to_dict()
        projected = repr(serialized) + repr(session)
        self.assertNotIn(value, projected)
        self.assertNotIn(secret, projected)
        self.assertTrue(serialized["opaque_digest"].startswith("sha256:"))
        self.assertEqual(serialized["host_name"], "codex")
        self.assertTrue(serialized["resume_capable"])

    def test_invalid_session_handle_fails_with_stable_reason(self):
        for invalid in (
            {"created_at": "not-a-timestamp"},
            {"created_at": "2026-07-14T00:00:00"},
            {"host": "host:credential"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(InvalidSchemaError) as raised:
                handle(**invalid)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_session_handle"),
            )

    def test_session_handle_is_final_and_revalidates_mutation_before_projection(self):
        with self.assertRaises(TypeError):
            type("HostileSessionHandle", (SessionHandle,), {})
        session = handle(value="safe-original")
        object.__setattr__(session, "opaque_handle", object())
        with self.assertRaises(InvalidSchemaError) as raised:
            session.to_dict()
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_session_handle"),
        )
        self.assertNotIn("safe-original", repr(session))

    def test_gated_node_requires_explicit_coherent_decision(self):
        with self.assertRaises(InvalidSchemaError) as raised:
            NodeSpec("risk_gate", gate_kind="risk", required_evidence=("risk",))
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("inconsistent_gate_decision"),
        )
        incoherent = []
        for values in (
            {"allowed": True, "reason_code": "missing_mandatory_evidence",
             "missing_evidence": ("risk",)},
            {"allowed": False, "reason_code": "gate_satisfied"},
            {"allowed": False, "reason_code": "human_approval_required",
             "human_required": False},
            {"allowed": True, "reason_code": "uncatalogued_gate_result"},
        ):
            decision = GateDecision(True, "gate_satisfied")
            for name, value in values.items():
                object.__setattr__(decision, name, value)
            incoherent.append(decision)
        for decision in incoherent:
            with self.subTest(decision=decision), self.assertRaises(InvalidSchemaError) as rejected:
                builder_node(
                    gate_kind="risk", required_evidence=("risk",),
                    gate_decision=decision,
                )
            self.assertEqual(
                rejected.exception.details["reason_code"],
                detail_digest("invalid_gate_decision"),
            )

    def test_dispatch_blocks_missing_capability_and_blocked_gate_without_adapter_call(self):
        adapter = FakeHostAdapter(
            HostCapabilities("generic", (HostCapability.OPENROUTER_EXECUTION,)),
            dispatch_handles=(handle(host="generic"),),
        )
        missing = BuilderSessionManager(adapter).dispatch(builder_node())
        self.assertEqual(missing.status, "blocked")
        self.assertEqual(missing.reason_code, "host_capability_unavailable")
        self.assertEqual(adapter.dispatch_calls, [])

        blocked_node = builder_node(
            gate_kind="risk", required_evidence=("risk_assessment",),
            gate_decision=GateDecision(False, "missing_mandatory_evidence",
                                       ("risk_assessment",)),
        )
        blocked = BuilderSessionManager(FakeHostAdapter(host_capabilities())).dispatch(blocked_node)
        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(blocked.reason_code, "node_gate_blocked")

    def test_resume_preflight_blocks_gate_and_executor_capability_before_adapter_call(self):
        original = handle()
        feedback = ValidationFeedback("build", "deterministic_validation_failure")
        blocked_node = builder_node(
            gate_kind="risk", required_evidence=("risk_assessment",),
            gate_decision=GateDecision(False, "missing_mandatory_evidence",
                                       ("risk_assessment",)),
        )
        adapter = FakeHostAdapter(host_capabilities(),
                                  resume_results=(SessionResult("succeeded"),))
        blocked = BuilderSessionManager(adapter).resume_or_replace(
            blocked_node, original, feedback, now=NOW,
        )
        self.assertEqual(blocked.reason_code, "node_gate_blocked")
        self.assertEqual(adapter.resume_calls, [])

        class NoAdapterCall:
            def capabilities(self):
                raise AssertionError("blocked gate reached adapter")

        for operation in ("dispatch", "resume"):
            manager = BuilderSessionManager(NoAdapterCall())
            with self.subTest(operation=operation):
                if operation == "dispatch":
                    decision = manager.dispatch(blocked_node)
                else:
                    decision = manager.resume_or_replace(
                        blocked_node, original, feedback, now=NOW,
                    )
                self.assertEqual(decision.reason_code, "node_gate_blocked")

        adapter = FakeHostAdapter(
            HostCapabilities("codex", (HostCapability.SESSION_RESUME,)),
            resume_results=(SessionResult("succeeded"),),
        )
        missing = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), original, feedback, now=NOW,
        )
        self.assertEqual(missing.reason_code, "host_capability_unavailable")
        self.assertEqual(adapter.resume_calls, [])

    def test_codex_and_generic_hosts_reject_sensitive_and_security_native_work(self):
        templates = WorkflowTemplates()
        security = templates.expand(
            WorkflowClass.SECURITY,
            WorkflowContext(
                evidence=("threat_model", "risk_assessment", "validation_evidence",
                          "security_review"), human_approved=True,
            ),
        )
        security_build = next(node for node in security if node.node_id == "security_build")
        sensitive = templates.expand(
            WorkflowClass.CHORE,
            WorkflowContext(changed_paths=("internal/auth/keys.py",)),
        )
        sensitive_build = next(node for node in sensitive if node.node_id == "build")
        for host in ("codex", "generic"):
            for node in (security_build, sensitive_build):
                with self.subTest(host=host, node=node.node_id):
                    adapter = FakeHostAdapter(
                        capabilities_from_harness_profile(host),
                        dispatch_handles=(handle(host=host),),
                    )
                    decision = BuilderSessionManager(adapter).dispatch(node)
                    self.assertEqual(decision.reason_code, "host_capability_unavailable")
                    self.assertEqual(adapter.dispatch_calls, [])

    def test_builder_decision_outcome_enforces_coherent_payloads(self):
        from workflow_kernel.adapters.base import BuilderSessionDecision

        invalid = (
            (BuilderOutcome.SESSION_RESUMED, None, SessionResult("succeeded")),
            (BuilderOutcome.SESSION_RESUMED, handle(), None),
            (BuilderOutcome.NODE_GATE_BLOCKED, handle(), None),
            (BuilderOutcome.BUILDER_DISPATCHED, None, None),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(InvalidSchemaError):
                BuilderSessionDecision(*values)
        with self.assertRaises(TypeError):
            type("HostileBuilderDecision", (BuilderSessionDecision,), {})

    def test_failed_replacement_preserves_resume_unavailable_observation(self):
        class DispatchFailure:
            def capabilities(self):
                return host_capabilities()

            def dispatch(self, _node):
                raise RuntimeError("provider-detail://credential")

            def resume(self, _handle, _feedback):
                raise AssertionError

        decision = BuilderSessionManager(DispatchFailure()).resume_or_replace(
            builder_node(), None,
            ValidationFeedback("build", "deterministic_validation_failure"), now=NOW,
        )
        self.assertEqual(decision.reason_code, "adapter_dispatch_failed")
        self.assertEqual(
            decision.observations,
            (BuilderObservation.SESSION_RESUME_UNAVAILABLE,
             BuilderObservation.DISPATCH_BLOCKED),
        )

    def test_adapter_exceptions_become_secret_safe_decisions(self):
        secret = "provider-detail://credential"

        class RaisingAdapter:
            def __init__(self, phase):
                self.phase = phase
                self.dispatch_calls = 0

            def capabilities(self):
                if self.phase == "capabilities":
                    raise RuntimeError(secret)
                return host_capabilities()

            def dispatch(self, _node):
                self.dispatch_calls += 1
                if self.phase == "dispatch":
                    raise RuntimeError(secret)
                return handle(value="replacement")

            def resume(self, _handle, _feedback):
                raise RuntimeError(secret)

        capability_failure = BuilderSessionManager(RaisingAdapter("capabilities")).dispatch(
            builder_node()
        )
        self.assertEqual(capability_failure.reason_code, "adapter_capabilities_failed")
        dispatch_failure = BuilderSessionManager(RaisingAdapter("dispatch")).dispatch(builder_node())
        self.assertEqual(dispatch_failure.reason_code, "adapter_dispatch_failed")
        resume_failure = BuilderSessionManager(RaisingAdapter("resume")).resume_or_replace(
            builder_node(), handle(),
            ValidationFeedback("build", "deterministic_validation_failure"), now=NOW,
        )
        self.assertEqual(resume_failure.status, "replacement_dispatched")
        for decision in (capability_failure, dispatch_failure, resume_failure):
            self.assertNotIn(secret, repr(decision))

    def test_session_results_are_closed_snapshotted_and_secret_safe(self):
        for values in (
            ("unknown_status", (), None),
            ("succeeded", ("sk-provider-credential",), None),
            ("failed", (), "provider://credential"),
        ):
            with self.subTest(values=values), self.assertRaises(InvalidSchemaError):
                SessionResult(*values)
        result = SessionResult("succeeded", ("validation/report",))
        adapter = FakeHostAdapter(host_capabilities(), resume_results=(result,))
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), handle(),
            ValidationFeedback("build", "deterministic_validation_failure"), now=NOW,
        )
        object.__setattr__(result, "evidence", ("sk-mutated-credential",))
        self.assertNotIn("sk-mutated-credential", repr(decision))
        self.assertEqual(decision.result.evidence, ("validation/report",))

    def test_supported_resume_state_round_trips_and_rejects_corrupt_foreign_or_missing_state(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        original = handle(value="real-opaque-resume-value")
        context = ResumeStateContext(
            "run-1", "build", "attempt-1", "openai", "codex-native",
        )
        durable = manager.serialize_resume_state(original, context)
        reloaded = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        restored = reloaded.restore_resume_state(durable, context)
        self.assertEqual(restored.opaque_handle, original.opaque_handle)
        self.assertNotIn(original.opaque_handle, repr(durable))
        self.assertIsNone(manager.restore_resume_state(None, context))
        with self.assertRaises(InvalidSchemaError) as corrupt:
            manager.restore_resume_state(durable.to_trusted_bytes()[:-1] + b"x", context)
        self.assertEqual(
            corrupt.exception.details["reason_code"],
            detail_digest("invalid_session_resume_state"),
        )
        foreign = BuilderSessionManager(FakeHostAdapter(host_capabilities("claude-code")))
        with self.assertRaises(InvalidSchemaError) as rejected:
            foreign.restore_resume_state(durable, context)
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("foreign_session_resume_state"),
        )

        class UnavailableAdapter:
            def capabilities(self):
                raise RuntimeError("provider-detail://must-not-leak")

        unavailable = BuilderSessionManager(UnavailableAdapter())
        with self.assertRaises(InvalidSchemaError) as rejected:
            unavailable.restore_resume_state(durable, context)
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("adapter_capabilities_failed"),
        )
        self.assertNotIn("must-not-leak", repr(rejected.exception))

    def test_resume_state_rejects_wrong_same_host_context_and_oversize_or_deep_bytes(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        context = ResumeStateContext(
            "run-1", "build", "attempt-1", "openai", "codex-native",
        )
        durable = manager.serialize_resume_state(handle(), context)
        replacements = (
            ResumeStateContext("run-2", "build", "attempt-1", "openai", "codex-native"),
            ResumeStateContext("run-1", "review", "attempt-1", "openai", "codex-native"),
            ResumeStateContext("run-1", "build", "attempt-2", "openai", "codex-native"),
            ResumeStateContext("run-1", "build", "attempt-1", "anthropic", "codex-native"),
            ResumeStateContext("run-1", "build", "attempt-1", "openai", "wrapper"),
        )
        for other in replacements:
            with self.subTest(other=other), self.assertRaises(InvalidSchemaError) as rejected:
                manager.restore_resume_state(durable, other)
            self.assertEqual(
                rejected.exception.details["reason_code"],
                detail_digest("foreign_session_resume_state"),
            )
        for raw in (b"[" * 2_000 + b"]" * 2_000, b"x" * 70_000,
                    b'\xff{"schema_version":1}'):
            with self.subTest(length=len(raw)), self.assertRaises(InvalidSchemaError) as rejected:
                manager.restore_resume_state(raw, context)
            self.assertEqual(
                rejected.exception.details["reason_code"],
                detail_digest("invalid_session_resume_state"),
            )


if __name__ == "__main__":
    unittest.main()
