import unittest

from tests import detail_digest
from workflow_kernel.adapters.base import (
    BuilderObservation, GateDecision, HostCapabilities, HostCapability, NodeSpec,
    SessionHandle, SessionResult, ValidationFeedback,
)
from workflow_kernel.adapters.host import BuilderSessionManager, FakeHostAdapter
from workflow_kernel.schema import InvalidSchemaError


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
        self.assertEqual(decision.transition_kinds, ("node.started",))

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
                self.assertEqual(decision.transition_kinds, ("node.waiting", "node.started"))
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
        self.assertEqual(decision.transition_kinds, ("node.waiting",))

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

    def test_private_resume_state_round_trips_and_rejects_corrupt_foreign_or_missing_state(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        original = handle(value="real-opaque-resume-value")
        durable = manager._serialize_resume_state(original)
        reloaded = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        restored = reloaded._restore_resume_state(durable)
        self.assertEqual(restored.opaque_handle, original.opaque_handle)
        self.assertNotIn(original.opaque_handle, repr(durable))
        self.assertIsNone(manager._restore_resume_state(None))
        with self.assertRaises(InvalidSchemaError) as corrupt:
            manager._restore_resume_state(durable[:-1] + b"x")
        self.assertEqual(
            corrupt.exception.details["reason_code"],
            detail_digest("invalid_session_resume_state"),
        )
        foreign = BuilderSessionManager(FakeHostAdapter(host_capabilities("claude-code")))
        with self.assertRaises(InvalidSchemaError) as rejected:
            foreign._restore_resume_state(durable)
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("foreign_session_resume_state"),
        )

        class UnavailableAdapter:
            def capabilities(self):
                raise RuntimeError("provider-detail://must-not-leak")

        unavailable = BuilderSessionManager(UnavailableAdapter())
        with self.assertRaises(InvalidSchemaError) as rejected:
            unavailable._restore_resume_state(durable)
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("adapter_capabilities_failed"),
        )
        self.assertNotIn("must-not-leak", repr(rejected.exception))


if __name__ == "__main__":
    unittest.main()
