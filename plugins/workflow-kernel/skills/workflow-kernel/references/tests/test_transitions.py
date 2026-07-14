import unittest
import json
from types import MappingProxyType
from unittest import mock

from workflow_kernel import transitions
from workflow_kernel.schema import (
    IllegalTransitionError, MissingEvidenceError, NodeState, NodeStatus,
    RunState, RunStatus, WorkflowEvent,
)
from workflow_kernel.transitions import TransitionEngine


NOW = "2026-07-14T00:00:00Z"


def event(sequence, kind, *, node_id=None, payload=None):
    return WorkflowEvent(1, sequence, "run-1", node_id, kind, NOW, payload or {})


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.engine = TransitionEngine()

    def test_run_and_node_legal_path(self):
        events = (
            event(0, "run.initialized", payload={"mode": "shadow"}),
            event(1, "run.started"),
            event(2, "node.added", node_id="build", payload={"dependencies": []}),
            event(3, "node.ready", node_id="build"),
            event(4, "node.started", node_id="build"),
            event(5, "node.succeeded", node_id="build", payload={"evidence": ["tests.txt"]}),
            event(6, "run.succeeded", payload={"evidence": ["receipt.json"]}),
        )
        state = self.engine.reconstruct(events)
        self.assertEqual(state.status, RunStatus.SUCCEEDED)
        self.assertEqual(state.nodes["build"].status, NodeStatus.SUCCEEDED)
        self.assertEqual(state.revision, 7)
        repeated = self.engine.reconstruct(events)
        self.assertEqual(json.dumps(state.to_dict(), sort_keys=True), json.dumps(repeated.to_dict(), sort_keys=True))

    def test_illegal_transition_and_missing_evidence(self):
        state = RunState.new("run-1", NOW)
        with self.assertRaises(IllegalTransitionError):
            self.engine.apply(state, event(0, "run.succeeded", payload={"evidence": ["x"]}))
        state = self.engine.apply(state, event(0, "run.initialized"))
        state = self.engine.apply(state, event(1, "run.started"))
        with self.assertRaises(MissingEvidenceError):
            self.engine.apply(state, event(2, "run.succeeded"))

    def test_interrupted_is_stable_terminal_and_allows_reconciliation(self):
        state = self.engine.reconstruct((
            event(0, "run.initialized"), event(1, "run.started"),
            event(2, "run.interrupted", payload={"reason": "signal"}),
        ))
        self.assertEqual(state.status, RunStatus.INTERRUPTED)
        with self.assertRaises(IllegalTransitionError):
            self.engine.apply(state, event(3, "run.started"))
        reconciled = self.engine.apply(state, event(3, "cleanup.reconciled", payload={"evidence": ["cleanup.json"]}))
        self.assertTrue(reconciled.cleanup_reconciled)

    def test_dependencies_must_succeed_before_ready(self):
        state = self.engine.reconstruct((
            event(0, "run.initialized"), event(1, "run.started"),
            event(2, "node.added", node_id="a"),
            event(3, "node.added", node_id="b", payload={"dependencies": ["a"]}),
        ))
        with self.assertRaises(IllegalTransitionError):
            self.engine.apply(state, event(4, "node.ready", node_id="b"))

    def test_unexpected_missing_dependency_is_a_stable_transition_error(self):
        state = self.engine.reconstruct((event(0, "run.initialized"), event(1, "run.started")))
        object.__setattr__(state, "nodes", MappingProxyType({
            "b": NodeState("b", dependencies=("missing",)),
        }))
        with self.assertRaises(IllegalTransitionError):
            self.engine.apply(state, event(2, "node.ready", node_id="b"))

    def test_aggregate_evidence_limit_accepts_boundary_and_rejects_overflow(self):
        self.assertTrue(hasattr(transitions, "MAX_EVIDENCE_ITEMS"))
        with mock.patch.object(transitions, "MAX_EVIDENCE_ITEMS", 2):
            state = self.engine.reconstruct((
                event(0, "run.initialized"), event(1, "run.started"),
                event(2, "node.added", node_id="n"),
            ))
            state = self.engine.apply(state, event(3, "evidence.recorded", payload={"evidence": ["a"]}))
            state = self.engine.apply(state, event(4, "evidence.recorded", node_id="n", payload={"evidence": ["b"]}))
            self.assertEqual(state.evidence, ("a",))
            self.assertEqual(state.nodes["n"].evidence, ("b",))
            with self.assertRaises(IllegalTransitionError) as raised:
                self.engine.apply(state, event(5, "evidence.recorded", payload={"evidence": ["c"]}))
        self.assertEqual(raised.exception.details["reason_code"], "evidence_limit_exceeded")
        self.assertEqual(raised.exception.details["limit_items"], 2)
        self.assertEqual(state.evidence, ("a",))
        self.assertEqual(state.nodes["n"].evidence, ("b",))
