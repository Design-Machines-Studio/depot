import hashlib
import inspect
import json
import threading
import unittest
from unittest.mock import patch

from tests import (
    canonical_harness_profile, detail_digest,
    snapshot_during_validated_mutation,
)
from workflow_kernel.model import (
    BuilderObservation, BuilderOutcome, BuilderSessionDecision, GateDecision,
    AttemptLedger, HostCapabilities,
    HostCapability, HostRoute, NodeSpec, ResumeStateContext, SessionHandle, SessionResult,
    ValidationFeedback, ResumeStateBlob,
)
from workflow_kernel.adapters.host import BuilderSessionManager, FakeHostAdapter
from workflow_kernel.adapters.host import capabilities_from_harness_profile
from workflow_kernel.schema import InvalidSchemaError, RunState, WorkflowEvent
from workflow_kernel.transitions import TransitionEngine
from workflow_kernel.workflows import WorkflowTemplates
from workflow_kernel.model import WorkflowClass, WorkflowContext
import workflow_kernel.model as kernel_model


NOW = "2026-07-14T00:00:00Z"


def receipt_context(
    node="build", *, run="run-1", attempt="attempt-1", provider="openai",
    rail="native", capability=HostCapability.CODEX_EXECUTION,
):
    return ResumeStateContext(run, node, attempt, provider, rail, capability)


def handle(
    host="codex", value="opaque-token-value", *, resumable=True, created_at=NOW,
    context=None,
):
    return SessionHandle(
        host, value, created_at, resumable, context or receipt_context(),
    )


def session_result(status="succeeded", evidence=(), reason_code=None, *, context=None):
    return SessionResult(
        status, context or receipt_context(), evidence, reason_code,
    )


def host_capabilities(name="codex"):
    return HostCapabilities(name, (
        HostCapability.SESSION_RESUME,
    ), routes=frozenset({
        HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
    }))


def builder_node(**changes):
    values = {
        "node_id": "build", "executor": "codex",
        "required_capability": HostCapability.CODEX_EXECUTION,
        "required_dispatch_capability": HostCapability.NATIVE_DISPATCH,
    }
    values.update(changes)
    return NodeSpec(**values)


class BuilderResumeTests(unittest.TestCase):
    def test_handle_identity_cannot_be_resealed_through_post_init(self):
        candidate = handle(value="opaque-one")
        object.__setattr__(candidate, "opaque_handle", "opaque-two")
        with self.assertRaises(ValueError):
            candidate.__post_init__()
        with self.assertRaises(InvalidSchemaError):
            candidate.to_dict()

    def test_hostile_session_scalars_are_secret_safe_and_exact_enums_reject_impostors(self):
        secret = "sk-secret-session-detail"

        class Hostile:
            def __eq__(self, other):
                raise RuntimeError(secret)

            def __ne__(self, other):
                raise RuntimeError(secret)

        context = receipt_context()
        cases = (
            ("result_status", lambda value: SessionResult(value, context)),
            ("decision_outcome", lambda value: BuilderSessionDecision(value, context)),
            (
                "event_run_id",
                lambda value: BuilderSessionDecision(
                    BuilderOutcome.NODE_GATE_BLOCKED, context,
                ).to_evidence_event(
                    run_id=value, sequence=1, node_id="build", occurred_at=NOW,
                ),
            ),
            (
                "event_node_id",
                lambda value: BuilderSessionDecision(
                    BuilderOutcome.NODE_GATE_BLOCKED, context,
                ).to_evidence_event(
                    run_id="run-1", sequence=1, node_id=value, occurred_at=NOW,
                ),
            ),
        )
        enum_cases = cases[:2]
        equality_cases = cases[2:]
        for name, action in cases:
            with self.subTest(name=name):
                with self.assertRaises(InvalidSchemaError) as raised:
                    action(Hostile())
                self.assertNotIn(secret, repr(raised.exception))

        class FatalConversion(BaseException):
            pass

        class Fatal:
            def __eq__(self, other):
                raise FatalConversion()

            def __ne__(self, other):
                raise FatalConversion()

        for name, action in enum_cases:
            with self.subTest(name=name):
                with self.assertRaises(InvalidSchemaError):
                    action(Fatal())
        for name, action in equality_cases:
            with self.subTest(name=name):
                with self.assertRaises(FatalConversion):
                    action(Fatal())

    def test_safe_equality_coerces_truth_inside_the_secret_safe_boundary(self):
        secret = "sk-secret-truth-detail"

        class Truth:
            def __bool__(self):
                raise RuntimeError(secret)

        class Hostile:
            def __eq__(self, other):
                return Truth()

        decision = BuilderSessionDecision(
            BuilderOutcome.NODE_GATE_BLOCKED, receipt_context(),
        )
        with self.assertRaises(InvalidSchemaError) as raised:
            decision.to_evidence_event(
                run_id=Hostile(), sequence=1, node_id="build", occurred_at=NOW,
            )
        self.assertNotIn(secret, repr(raised.exception))

        class FatalTruth(BaseException):
            pass

        class FatalBool:
            def __bool__(self):
                raise FatalTruth()

        class FatalHostile:
            def __eq__(self, other):
                return FatalBool()

        with self.assertRaises(FatalTruth):
            decision.to_evidence_event(
                run_id=FatalHostile(), sequence=1, node_id="build", occurred_at=NOW,
            )

    def test_resume_and_handle_snapshots_use_one_validated_capture(self):
        context = receipt_context()
        captured_context = snapshot_during_validated_mutation(
            context, kernel_model._snapshot_resume_context,
            lambda: object.__setattr__(context, "run_id", "run-2"),
        )
        self.assertEqual(captured_context.run_id, "run-1")

        original_context = receipt_context()
        candidate = handle(value="opaque-original", context=original_context)

        def mutate_handle():
            object.__setattr__(candidate, "opaque_handle", "opaque-replacement")
            object.__setattr__(candidate, "context", receipt_context(run="run-2"))

        captured_handle = snapshot_during_validated_mutation(
            candidate, kernel_model._snapshot_session_handle, mutate_handle,
        )
        self.assertEqual(captured_handle.opaque_handle, "opaque-original")
        self.assertEqual(captured_handle.context.run_id, "run-1")

    def test_builder_decision_captures_parent_fields_before_nested_snapshots(self):
        original_context_snapshot = kernel_model._snapshot_resume_context

        def interleave(decision, mutate):
            entered = threading.Event()
            release = threading.Event()
            result = []
            failure = []

            def pause_context(value):
                entered.set()
                release.wait(timeout=2)
                return original_context_snapshot(value)

            def run():
                try:
                    result.append(kernel_model._snapshot_builder_decision(decision))
                except BaseException as error:
                    failure.append(error)

            with patch.object(
                kernel_model, "_snapshot_resume_context",
                side_effect=pause_context,
            ):
                worker = threading.Thread(target=run)
                worker.start()
                self.assertTrue(entered.wait(timeout=2))
                mutate()
                release.set()
                worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            if failure:
                raise failure[0]
            return result[0][1]

        outcome = BuilderSessionDecision(
            BuilderOutcome.NODE_GATE_BLOCKED, receipt_context(),
        )
        captured = interleave(
            outcome,
            lambda: object.__setattr__(
                outcome, "outcome", BuilderOutcome.HOST_CAPABILITY_UNAVAILABLE,
            ),
        )
        self.assertIs(captured.outcome, BuilderOutcome.NODE_GATE_BLOCKED)

        original_handle = handle(value="opaque-original")
        handled = BuilderSessionDecision(
            BuilderOutcome.BUILDER_DISPATCHED, receipt_context(), original_handle,
        )
        captured = interleave(
            handled,
            lambda: object.__setattr__(
                handled, "handle", handle(value="opaque-replacement"),
            ),
        )
        self.assertEqual(captured.handle.opaque_handle, "opaque-original")

        original_result = session_result()
        resulted = BuilderSessionDecision(
            BuilderOutcome.SESSION_RESUMED, receipt_context(), handle(),
            original_result,
        )
        captured = interleave(
            resulted,
            lambda: object.__setattr__(
                resulted, "result", session_result(
                    evidence=("sha256:" + "0" * 64,),
                ),
            ),
        )
        self.assertEqual(captured.result.evidence, ())

    def test_module_seals_reject_nested_resume_and_decision_spoofing(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        expected = receipt_context()

        foreign_handle = handle(context=receipt_context(run="run-2"))
        object.__setattr__(foreign_handle, "context", expected)
        object.__setattr__(foreign_handle, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError) as resume_error:
            manager.resume_or_replace(
                builder_node(), foreign_handle,
                ValidationFeedback("build", "deterministic_validation_failure"),
                context=expected, now=NOW,
            )
        self.assertEqual(
            resume_error.exception.details["reason_code"],
            detail_digest("invalid_builder_resume_request"),
        )
        with self.assertRaises(InvalidSchemaError):
            manager.serialize_resume_state(foreign_handle)

        valid_handle = handle(context=expected)
        blob = manager.serialize_resume_state(valid_handle)
        foreign_expected = receipt_context(run="run-2")
        object.__setattr__(foreign_expected, "run_id", "run-1")
        object.__setattr__(foreign_expected, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError):
            manager.restore_resume_state(blob, foreign_expected)

        result = session_result(context=receipt_context(run="run-2"))
        object.__setattr__(result, "context", expected)
        object.__setattr__(result, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError):
            result.to_dict()

        decision = BuilderSessionDecision(
            BuilderOutcome.NODE_GATE_BLOCKED, receipt_context(run="run-2"),
        )
        object.__setattr__(decision, "context", expected)
        object.__setattr__(decision, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError):
            decision.to_evidence_event(
                run_id="run-1", sequence=1, node_id="build", occurred_at=NOW,
            )

        mutable_blob = ResumeStateBlob(b"original")
        object.__setattr__(mutable_blob, "_payload", b"replacement")
        object.__setattr__(mutable_blob, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError):
            mutable_blob.to_trusted_bytes()

        rewritten_context = receipt_context()
        object.__setattr__(rewritten_context, "rail", "codex_companion")
        object.__setattr__(rewritten_context, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError):
            _ = rewritten_context.route

    def test_nested_handle_identity_rewrites_fail_for_every_context_key(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        expected = receipt_context()
        cases = (
            ("run_id", receipt_context(run="run-2"), "run-1"),
            ("node_id", receipt_context(node="review"), "build"),
            ("attempt_id", receipt_context(attempt="attempt-2"), "attempt-1"),
        )
        for field, foreign, replacement in cases:
            candidate = handle(context=foreign)
            object.__setattr__(candidate.context, field, replacement)
            object.__setattr__(candidate.context, "_origin_seal", "spoofed")
            object.__setattr__(candidate, "_origin_seal", "spoofed")
            with self.subTest(field=field):
                with self.assertRaises(InvalidSchemaError) as resume_error:
                    manager.resume_or_replace(
                        builder_node(), candidate,
                        ValidationFeedback(
                            "build", "deterministic_validation_failure",
                        ),
                        context=expected, now=NOW,
                    )
                self.assertEqual(
                    resume_error.exception.details["reason_code"],
                    detail_digest("invalid_builder_resume_request"),
                )
                with self.assertRaises(InvalidSchemaError):
                    manager.serialize_resume_state(candidate)

    def test_hostile_iterators_are_secret_safe_at_public_boundaries(self):
        secret = "sk-secret-provider-detail"

        class HostileTuple(tuple):
            def __iter__(self):
                raise RuntimeError(secret)

        context = WorkflowContext()
        object.__setattr__(context, "changed_paths", HostileTuple())
        with self.assertRaises(InvalidSchemaError) as workflow_error:
            WorkflowTemplates().expand(WorkflowClass.CHORE, context)
        self.assertNotIn(secret, repr(workflow_error.exception))

        feedback = ValidationFeedback("build", "validation_failed")
        object.__setattr__(feedback, "evidence", HostileTuple())
        object.__setattr__(feedback, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError) as feedback_error:
            BuilderSessionManager(FakeHostAdapter(host_capabilities())).resume_or_replace(
                builder_node(), None, feedback, context=receipt_context(), now=NOW,
            )
        self.assertEqual(
            feedback_error.exception.details["reason_code"],
            detail_digest("invalid_builder_resume_request"),
        )
        self.assertNotIn(secret, repr(feedback_error.exception))

        result = session_result(reason_code="validation_failed")
        object.__setattr__(result, "evidence", HostileTuple())
        object.__setattr__(result, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError) as result_error:
            result.to_dict()
        self.assertNotIn(secret, repr(result_error.exception))

        class HostileMapping(dict):
            def items(self):
                raise RuntimeError(secret)

        with self.assertRaises(InvalidSchemaError) as ledger_error:
            AttemptLedger(HostileMapping(), {})
        self.assertNotIn(secret, repr(ledger_error.exception))

        class FatalIteration(BaseException):
            pass

        class FatalTuple(tuple):
            def __iter__(self):
                raise FatalIteration()

        with self.assertRaises(FatalIteration):
            ValidationFeedback("build", "validation_failed", FatalTuple())

        class FatalMapping(dict):
            def items(self):
                raise FatalIteration()

        with self.assertRaises(FatalIteration):
            AttemptLedger(FatalMapping(), {})

    def test_session_receipts_require_context_and_provenance(self):
        handle_parameters = inspect.signature(SessionHandle).parameters
        result_parameters = inspect.signature(SessionResult).parameters
        context_parameters = inspect.signature(ResumeStateContext).parameters
        node_parameters = inspect.signature(NodeSpec).parameters
        from workflow_kernel.model import BuilderSessionDecision
        decision_parameters = inspect.signature(BuilderSessionDecision).parameters
        self.assertIn("context", handle_parameters)
        self.assertIn("context", result_parameters)
        self.assertIn("capability", context_parameters)
        self.assertIn("required_dispatch_capability", node_parameters)
        self.assertIn("context", decision_parameters)

    def test_dispatch_rejects_same_host_wrong_rail_provenance(self):
        expected = receipt_context()
        wrapper = receipt_context(provider="openrouter", rail="wrapper")
        adapter = FakeHostAdapter(
            HostCapabilities("codex", (
            ), routes=frozenset({
                HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
                HostRoute("openrouter", HostCapability.CODEX_EXECUTION, "wrapper"),
            })),
            dispatch_handles=(handle(context=wrapper),),
        )
        decision = BuilderSessionManager(adapter).dispatch(builder_node(), expected)
        self.assertEqual(decision.reason_code, "invalid_session_handle")

    def test_resume_context_and_feedback_mismatch_fail_before_adapter_call(self):
        class NoAdapterCall:
            def capabilities(self):
                raise AssertionError("resume preflight reached adapter")

        manager = BuilderSessionManager(NoAdapterCall())
        cases = (
            (receipt_context(node="review"), ValidationFeedback(
                "build", "deterministic_validation_failure",
            )),
            (receipt_context(), ValidationFeedback(
                "review", "deterministic_validation_failure",
            )),
        )
        for context, feedback in cases:
            with self.subTest(context=context, feedback=feedback):
                with self.assertRaises(InvalidSchemaError) as raised:
                    manager.resume_or_replace(
                        builder_node(), handle(), feedback, context=context, now=NOW,
                    )
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_builder_resume_request"),
                )

    def test_resume_result_must_match_validated_receipt_context(self):
        original = handle()
        wrong = session_result(context=receipt_context(attempt="attempt-2"))
        replacement = handle(value="replacement")
        adapter = FakeHostAdapter(
            host_capabilities(), dispatch_handles=(replacement,), resume_results=(wrong,),
        )
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), original,
            ValidationFeedback("build", "deterministic_validation_failure"),
            context=receipt_context(), now=NOW,
        )
        self.assertEqual(decision.outcome, BuilderOutcome.REPLACEMENT_DISPATCHED)
        self.assertEqual(decision.handle, replacement)

    def test_validation_feedback_is_final_normalized_and_secret_safe(self):
        with self.assertRaises(TypeError):
            type("HostileValidationFeedback", (ValidationFeedback,), {})
        for values in (
            ("build", "Bad Reason", ()),
            ("build", "validation_failed", ("artifact/sk-provider-credential",)),
        ):
            with self.subTest(values=values), self.assertRaises(InvalidSchemaError):
                ValidationFeedback(*values)
        feedback = ValidationFeedback(
            "build", "validation_failed", ("https://example.test/report",),
        )
        self.assertTrue(feedback.evidence[0].startswith("url-sha256:"))
        self.assertNotIn("example.test", repr(feedback))

    def test_durable_public_boundaries_revalidate_hostile_mutation(self):
        context = ResumeStateContext(
            "run-1", "build", "attempt-1", "openai", "native",
            HostCapability.CODEX_EXECUTION,
        )
        object.__setattr__(context, "provider", object())
        with self.assertRaises(InvalidSchemaError):
            context.to_dict()
        self.assertEqual(repr(context), "ResumeStateContext([INVALID])")

        from workflow_kernel.model import BuilderSessionDecision, ResumeStateBlob

        blob = ResumeStateBlob(b"safe")
        object.__setattr__(blob, "_payload", object())
        with self.assertRaises(InvalidSchemaError):
            blob.to_dict()
        with self.assertRaises(InvalidSchemaError):
            blob.to_trusted_bytes()
        self.assertEqual(repr(blob), "ResumeStateBlob([INVALID])")

        decision = BuilderSessionDecision(
            BuilderOutcome.NODE_GATE_BLOCKED, receipt_context(),
        )
        object.__setattr__(decision, "outcome", "hostile")
        with self.assertRaises(InvalidSchemaError):
            decision.to_evidence_event(
                run_id="run-1", sequence=1, node_id="build", occurred_at=NOW,
            )
        self.assertEqual(repr(decision), "BuilderSessionDecision([INVALID])")

    def test_manager_snapshots_node_and_host_capability_boundaries(self):
        node = builder_node()
        object.__setattr__(node, "dependencies", object())
        with self.assertRaises(InvalidSchemaError) as rejected:
            BuilderSessionManager(FakeHostAdapter(host_capabilities())).dispatch(
                node, receipt_context(),
            )
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("invalid_node_spec"),
        )

        capabilities = host_capabilities()
        object.__setattr__(capabilities, "routes", object())
        decision = BuilderSessionManager(FakeHostAdapter(capabilities)).dispatch(
            builder_node(), receipt_context(),
        )
        self.assertEqual(decision.reason_code, "adapter_capabilities_failed")

    def test_manager_rejects_coordinated_and_nested_node_rewrites(self):
        companion = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "codex_companion",
        )
        adapter = FakeHostAdapter(
            HostCapabilities("codex", (), routes=(companion,)),
        )
        coordinated = NodeSpec(
            "security_build", executor="claude",
            required_capability=HostCapability.ANTHROPIC_NATIVE_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        object.__setattr__(coordinated, "executor", "codex")
        object.__setattr__(
            coordinated, "required_capability", HostCapability.CODEX_EXECUTION,
        )
        object.__setattr__(
            coordinated, "required_dispatch_capability",
            HostCapability.COMPANION_DISPATCH,
        )
        object.__setattr__(
            coordinated, "_origin_seal", (
                "security_build", (), None, (), "codex", None,
                (True, "gate_not_required", (), False),
                "codex_execution", "companion_dispatch", False,
            ),
        )

        blocked_gate = GateDecision(
            False, "missing_mandatory_evidence", ("security_review",),
        )
        nested = NodeSpec(
            "security_build", gate_kind="evidence",
            required_evidence=("security_review",), executor="codex",
            gate_decision=blocked_gate,
            required_capability=HostCapability.CODEX_EXECUTION,
            required_dispatch_capability=HostCapability.COMPANION_DISPATCH,
        )
        object.__setattr__(nested.gate_decision, "allowed", True)
        object.__setattr__(nested.gate_decision, "reason_code", "gate_satisfied")
        object.__setattr__(nested.gate_decision, "missing_evidence", ())
        object.__setattr__(
            nested, "_origin_seal", (
                "security_build", (), "evidence", ("security_review",),
                "codex", None, (True, "gate_satisfied", (), False),
                "codex_execution", "companion_dispatch", False,
            ),
        )

        context = receipt_context(node="security_build", rail="codex_companion")
        for candidate in (coordinated, nested):
            with self.subTest(candidate=candidate):
                try:
                    BuilderSessionManager(adapter).dispatch(candidate, context)
                except InvalidSchemaError as raised:
                    self.assertEqual(
                        raised.details["reason_code"],
                        detail_digest("invalid_node_spec"),
                    )
                except Exception as raised:
                    self.fail("manager leaked " + type(raised).__name__)
                else:
                    self.fail("manager accepted rewritten node")

    def test_authorized_context_translates_snapshot_failures_per_public_method(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        dispatch_context = receipt_context()
        object.__setattr__(dispatch_context, "node_id", object())
        with self.assertRaises(InvalidSchemaError) as dispatch_error:
            manager.dispatch(builder_node(), dispatch_context)
        self.assertEqual(
            dispatch_error.exception.details["reason_code"],
            detail_digest("invalid_builder_dispatch_request"),
        )

        resume_context = receipt_context()
        object.__setattr__(resume_context, "node_id", object())
        with self.assertRaises(InvalidSchemaError) as resume_error:
            manager.resume_or_replace(
                builder_node(), None,
                ValidationFeedback("build", "deterministic_validation_failure"),
                context=resume_context, now=NOW,
            )
        self.assertEqual(
            resume_error.exception.details["reason_code"],
            detail_digest("invalid_builder_resume_request"),
        )

    def test_resume_revalidates_handle_and_exact_aware_now_before_use(self):
        secret = "provider-detail://credential"

        class HostileTimestamp:
            def replace(self, *_args):
                raise RuntimeError(secret)

        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        mutated = handle()
        object.__setattr__(mutated, "created_at", HostileTimestamp())
        cases = (
            (mutated, NOW),
            (handle(), HostileTimestamp()),
            (handle(), "2026-07-14T00:00:00"),
            (handle(), 1),
        )
        for candidate, now in cases:
            with self.subTest(now=now):
                try:
                    manager.resume_or_replace(
                        builder_node(), candidate,
                        ValidationFeedback(
                            "build", "deterministic_validation_failure",
                        ),
                        context=receipt_context(), now=now,
                    )
                except InvalidSchemaError as raised:
                    self.assertEqual(
                        raised.details["reason_code"],
                        detail_digest("invalid_builder_resume_request"),
                    )
                    self.assertNotIn(secret, repr(raised))
                except Exception as raised:
                    self.fail(
                        "resume leaked non-schema exception: "
                        + type(raised).__name__,
                    )
                else:
                    self.fail("invalid resume request was accepted")

    def test_builder_evidence_event_rejects_foreign_run_or_node(self):
        from workflow_kernel.model import BuilderSessionDecision

        decision = BuilderSessionDecision(
            BuilderOutcome.NODE_GATE_BLOCKED, receipt_context(),
        )
        for run_id, node_id in (("run-2", "build"), ("run-1", "review")):
            with self.subTest(run_id=run_id, node_id=node_id), \
                    self.assertRaises(InvalidSchemaError) as rejected:
                decision.to_evidence_event(
                    run_id=run_id, sequence=1, node_id=node_id, occurred_at=NOW,
                )
            self.assertEqual(
                rejected.exception.details["reason_code"],
                detail_digest("invalid_builder_session_event_context"),
            )

    def test_builder_evidence_event_snapshots_context_before_projection(self):
        from workflow_kernel.model import BuilderSessionDecision

        decision = BuilderSessionDecision(
            BuilderOutcome.NODE_GATE_BLOCKED, receipt_context(),
        )
        object.__setattr__(decision, "context", object())
        with self.assertRaises(InvalidSchemaError) as rejected:
            decision.to_evidence_event(
                run_id="run-1", sequence=1, node_id="build", occurred_at=NOW,
            )
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("invalid_builder_session_decision"),
        )

    def test_real_handle_is_resumed_with_deterministic_validation_feedback(self):
        original = handle()
        result = session_result(evidence=("validation.txt",))
        adapter = FakeHostAdapter(host_capabilities(), resume_results=(result,))
        feedback = ValidationFeedback(
            "build", "deterministic_validation_failure", ("test-report.txt",),
        )
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), original, feedback, context=receipt_context(), now=NOW,
        )
        self.assertEqual(decision.status, "resumed")
        self.assertTrue(decision.resumed_original)
        self.assertIsNot(decision.handle, original)
        self.assertEqual(decision.handle, original)
        self.assertEqual(adapter.resume_calls, [(original, feedback)])
        recorded_feedback = adapter.resume_calls[0][1]
        object.__setattr__(feedback, "evidence", ("artifact/sk-mutated-credential",))
        self.assertEqual(recorded_feedback.evidence, ("test-report.txt",))
        self.assertNotIn("sk-mutated-credential", repr(recorded_feedback))
        self.assertEqual(decision.observations, (BuilderObservation.SESSION_RESUMED,))
        self.assertEqual(decision.outcome, BuilderOutcome.SESSION_RESUMED)

    def test_successful_resume_without_evidence_requires_replacement(self):
        adapter = FakeHostAdapter(
            host_capabilities(), resume_results=(session_result(evidence=()),),
        )
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), handle(),
            ValidationFeedback("build", "deterministic_validation_failure"),
            context=receipt_context(), now=NOW,
        )
        self.assertEqual(decision.status, "resume_unavailable")
        self.assertEqual(decision.reason_code, "session_resume_unavailable")
        self.assertIsNone(decision.result)
        self.assertEqual(len(adapter.resume_calls), 1)

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
                    context=receipt_context(), now=NOW,
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
            context=receipt_context(), now=NOW,
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
            ValidationFeedback("build", "deterministic_validation_failure"),
            context=receipt_context(), now=NOW,
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
            HostCapabilities("generic", ()),
            dispatch_handles=(handle(host="generic"),),
        )
        missing = BuilderSessionManager(adapter).dispatch(
            builder_node(), receipt_context(),
        )
        self.assertEqual(missing.status, "blocked")
        self.assertEqual(missing.reason_code, "host_capability_unavailable")
        self.assertEqual(adapter.dispatch_calls, [])

        blocked_node = builder_node(
            gate_kind="risk", required_evidence=("risk_assessment",),
            gate_decision=GateDecision(False, "missing_mandatory_evidence",
                                       ("risk_assessment",)),
        )
        blocked = BuilderSessionManager(FakeHostAdapter(host_capabilities())).dispatch(
            blocked_node, receipt_context(),
        )
        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(blocked.reason_code, "node_gate_blocked")

    def test_exact_route_not_aggregate_capability_authorizes_dispatch(self):
        context = receipt_context()
        wrong_tuple = HostCapabilities("codex", (), routes=frozenset({
            HostRoute("openai", HostCapability.CODEX_EXECUTION,
                      "codex_companion"),
        }))
        adapter = FakeHostAdapter(wrong_tuple, dispatch_handles=(handle(),))
        decision = BuilderSessionManager(adapter).dispatch(builder_node(), context)
        self.assertEqual(decision.reason_code, "host_capability_unavailable")
        self.assertEqual(adapter.dispatch_calls, [])

    def test_default_nodes_accept_any_declared_agentic_route_but_not_wrapper(self):
        node = builder_node(required_dispatch_capability=None)
        routes = (
            HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
            HostRoute("openai", HostCapability.CODEX_EXECUTION,
                      "codex_companion"),
            HostRoute("openrouter", HostCapability.CODEX_EXECUTION,
                      "openrouter_exec"),
        )
        for route in routes:
            with self.subTest(route=route):
                context = receipt_context(provider=route.provider, rail=route.rail)
                adapter = FakeHostAdapter(
                    HostCapabilities("codex", (), routes=frozenset({route})),
                    dispatch_handles=(handle(context=context),),
                )
                decision = BuilderSessionManager(adapter).dispatch(node, context)
                self.assertEqual(decision.outcome, BuilderOutcome.BUILDER_DISPATCHED)

        wrapper = HostRoute(
            "openrouter", HostCapability.CODEX_EXECUTION, "wrapper",
        )
        with self.assertRaises(InvalidSchemaError):
            BuilderSessionManager(FakeHostAdapter(
                HostCapabilities("codex", (), routes=frozenset({wrapper})),
            )).dispatch(
                node, receipt_context(provider="openrouter", rail="wrapper"),
            )

    def test_resume_preflight_blocks_gate_and_executor_capability_before_adapter_call(self):
        original = handle()
        feedback = ValidationFeedback("build", "deterministic_validation_failure")
        blocked_node = builder_node(
            gate_kind="risk", required_evidence=("risk_assessment",),
            gate_decision=GateDecision(False, "missing_mandatory_evidence",
                                       ("risk_assessment",)),
        )
        adapter = FakeHostAdapter(host_capabilities(),
                                  resume_results=(session_result(),))
        blocked = BuilderSessionManager(adapter).resume_or_replace(
            blocked_node, original, feedback, context=receipt_context(), now=NOW,
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
                    decision = manager.dispatch(blocked_node, receipt_context())
                else:
                    decision = manager.resume_or_replace(
                        blocked_node, original, feedback,
                        context=receipt_context(), now=NOW,
                    )
                self.assertEqual(decision.reason_code, "node_gate_blocked")

        adapter = FakeHostAdapter(
            HostCapabilities("codex", (HostCapability.SESSION_RESUME,)),
            resume_results=(session_result(),),
        )
        missing = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), original, feedback, context=receipt_context(), now=NOW,
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
                        capabilities_from_harness_profile(host, canonical_harness_profile()),
                        dispatch_handles=(handle(host=host),),
                    )
                    context = receipt_context(
                        node=node.node_id, provider="anthropic", rail="native",
                        capability=HostCapability.ANTHROPIC_NATIVE_EXECUTION,
                    )
                    decision = BuilderSessionManager(adapter).dispatch(node, context)
                    self.assertEqual(decision.reason_code, "host_capability_unavailable")
                    self.assertEqual(adapter.dispatch_calls, [])

    def test_builder_decision_outcome_enforces_coherent_payloads(self):
        from workflow_kernel.model import BuilderSessionDecision

        context = receipt_context()
        invalid = (
            (BuilderOutcome.SESSION_RESUMED, context, None, session_result()),
            (BuilderOutcome.SESSION_RESUMED, context, handle(), None),
            (BuilderOutcome.SESSION_RESUMED, context, handle(), session_result(
                context=receipt_context(attempt="attempt-2"),
            )),
            (BuilderOutcome.NODE_GATE_BLOCKED, context, handle(), None),
            (BuilderOutcome.BUILDER_DISPATCHED, context, None, None),
            (BuilderOutcome.BUILDER_DISPATCHED,
             receipt_context(attempt="attempt-2"), handle(), None),
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

            def dispatch(self, _node, _context):
                raise RuntimeError("provider-detail://credential")

            def resume(self, _handle, _feedback):
                raise AssertionError

        decision = BuilderSessionManager(DispatchFailure()).resume_or_replace(
            builder_node(), None,
            ValidationFeedback("build", "deterministic_validation_failure"),
            context=receipt_context(), now=NOW,
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

            def dispatch(self, _node, _context):
                self.dispatch_calls += 1
                if self.phase == "dispatch":
                    raise RuntimeError(secret)
                return handle(value="replacement")

            def resume(self, _handle, _feedback):
                raise RuntimeError(secret)

        capability_failure = BuilderSessionManager(RaisingAdapter("capabilities")).dispatch(
            builder_node(), receipt_context(),
        )
        self.assertEqual(capability_failure.reason_code, "adapter_capabilities_failed")
        dispatch_failure = BuilderSessionManager(RaisingAdapter("dispatch")).dispatch(
            builder_node(), receipt_context(),
        )
        self.assertEqual(dispatch_failure.reason_code, "adapter_dispatch_failed")
        resume_failure = BuilderSessionManager(RaisingAdapter("resume")).resume_or_replace(
            builder_node(), handle(),
            ValidationFeedback("build", "deterministic_validation_failure"),
            context=receipt_context(), now=NOW,
        )
        self.assertEqual(resume_failure.status, "replacement_dispatched")
        for decision in (capability_failure, dispatch_failure, resume_failure):
            self.assertNotIn(secret, repr(decision))

    def test_session_results_are_closed_snapshotted_and_secret_safe(self):
        for values in (
            ("unknown_status", (), None),
            ("succeeded", ("sk-provider-credential",), None),
            ("succeeded", ("artifact/sk-provider-credential",), None),
            ("failed", (), "provider://credential"),
        ):
            with self.subTest(values=values), self.assertRaises(InvalidSchemaError):
                SessionResult(values[0], receipt_context(), values[1], values[2])
        result = session_result(evidence=("validation/report",))
        adapter = FakeHostAdapter(host_capabilities(), resume_results=(result,))
        decision = BuilderSessionManager(adapter).resume_or_replace(
            builder_node(), handle(),
            ValidationFeedback("build", "deterministic_validation_failure"),
            context=receipt_context(), now=NOW,
        )
        object.__setattr__(result, "evidence", ("sk-mutated-credential",))
        self.assertNotIn("sk-mutated-credential", repr(decision))
        self.assertEqual(decision.result.evidence, ("validation/report",))

    def test_supported_resume_state_round_trips_and_rejects_corrupt_foreign_or_missing_state(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        original = handle(value="real-opaque-resume-value")
        context = receipt_context()
        durable = manager.serialize_resume_state(original)
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

    def test_restore_context_mismatch_fails_before_adapter_capability_probe(self):
        durable = BuilderSessionManager(
            FakeHostAdapter(host_capabilities()),
        ).serialize_resume_state(handle())

        class NoCapabilityProbe:
            def capabilities(self):
                raise AssertionError("foreign context reached adapter capability probe")

        with self.assertRaises(InvalidSchemaError) as rejected:
            BuilderSessionManager(NoCapabilityProbe()).restore_resume_state(
                durable, receipt_context(run="run-2"),
            )
        self.assertEqual(
            rejected.exception.details["reason_code"],
            detail_digest("foreign_session_resume_state"),
        )

    def test_resume_state_version_is_exact_and_checksum_protected(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        durable = manager.serialize_resume_state(handle())
        payload = json.loads(durable.to_trusted_bytes())
        checked = {
            "schema_version": payload["schema_version"],
            "context": payload["context"],
            "handle": payload["handle"],
        }
        self.assertEqual(
            payload["checksum"],
            hashlib.sha256(json.dumps(
                checked, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest(),
        )
        for version in (True, 2):
            mutation = json.loads(json.dumps(payload))
            mutation["schema_version"] = version
            raw = json.dumps(mutation, sort_keys=True, separators=(",", ":")).encode()
            with self.subTest(version=version), self.assertRaises(
                InvalidSchemaError,
            ) as rejected:
                manager.restore_resume_state(raw, receipt_context())
            self.assertEqual(
                rejected.exception.details["reason_code"],
                detail_digest("invalid_session_resume_state"),
            )

    def test_resume_state_rejects_wrong_same_host_context_and_oversize_or_deep_bytes(self):
        manager = BuilderSessionManager(FakeHostAdapter(host_capabilities()))
        context = receipt_context()
        durable = manager.serialize_resume_state(handle())
        replacements = (
            receipt_context(run="run-2"),
            receipt_context(node="review"),
            receipt_context(attempt="attempt-2"),
            ResumeStateContext(
                "run-1", "build", "attempt-1", "anthropic", "native",
                HostCapability.CLAUDE_EXECUTION,
            ),
            receipt_context(provider="openrouter", rail="wrapper"),
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
