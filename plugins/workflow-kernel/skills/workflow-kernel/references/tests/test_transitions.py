import unittest
import json

from workflow_kernel.schema import (
    IllegalTransitionError, MissingEvidenceError, NodeStatus,
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
