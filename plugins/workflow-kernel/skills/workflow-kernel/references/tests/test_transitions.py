import unittest
import json
from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from unittest import mock

from tests import detail_digest
from workflow_kernel import schema, transitions
from workflow_kernel.schema import (
    IllegalTransitionError, KernelError, MissingEvidenceError, NodeState, NodeStatus,
    RunState, RunStatus, UnsafePayloadError, WorkflowEvent,
)
from workflow_kernel.transitions import TransitionEngine

NOW = "2026-07-14T00:00:00Z"


def event(sequence, kind, *, node_id=None, payload=None):
    return WorkflowEvent(1, sequence, "run-1", node_id, kind, NOW, payload or {})


class TransitionTests(unittest.TestCase):
    def test_reconstruction_work_limit_is_public(self):
        import workflow_kernel

        self.assertTrue(hasattr(transitions, "MAX_RECONSTRUCTION_WORK"))
        self.assertTrue(hasattr(workflow_kernel, "MAX_RECONSTRUCTION_WORK"))

    def test_public_apply_rejects_output_beyond_state_tree_item_limit(self):
        state = replace(
            RunState.new("run-1", NOW), revision=2, status=RunStatus.RUNNING,
            nodes={"a": NodeState("a"), "b": NodeState("b")},
        )
        with mock.patch.object(schema, "MAX_PAYLOAD_ITEMS", 2), \
                mock.patch.object(transitions, "MAX_PAYLOAD_ITEMS", 2), \
                self.assertRaises(UnsafePayloadError):
            self.engine.apply(state, event(2, "node.added", node_id="c"))

    def test_reconstruct_rejects_output_beyond_state_tree_item_limit(self):
        stream = [event(0, "run.initialized"), event(1, "run.started")]
        stream.extend(event(index + 2, "node.added", node_id=f"n-{index}")
                      for index in range(3))
        with mock.patch.object(schema, "MAX_PAYLOAD_ITEMS", 2), \
                mock.patch.object(transitions, "MAX_PAYLOAD_ITEMS", 2), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct(stream)

    def test_reconstruct_rejects_aggregate_state_text_overflow(self):
        stream = (
            event(0, "run.initialized"), event(1, "run.started"),
            event(2, "node.added", node_id="aaa"),
            event(3, "node.added", node_id="bbb"),
        )
        with mock.patch.object(schema, "MAX_TOTAL_STRING_BYTES", 10), \
                mock.patch.object(transitions, "MAX_TOTAL_STRING_BYTES", 10, create=True), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct(stream)

    def test_reconstruction_work_limit_stops_consuming_large_stream(self):
        reads = 0

        def stream():
            nonlocal reads
            values = [event(0, "run.initialized"), event(1, "run.started")]
            values.extend(event(index + 2, "node.added", node_id=f"n-{index}")
                          for index in range(50))
            for value in values:
                reads += 1
                yield value

        with mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", 10, create=True), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct(stream())
        self.assertLess(reads, 52)

    def test_reconstruction_charges_event_snapshot_before_exhausting_irrelevant_payload(self):
        class CountingList(list):
            def __init__(self, values):
                super().__init__(values)
                self.reads = 0

            def __iter__(self):
                for item in super().__iter__():
                    self.reads += 1
                    yield item

        values = CountingList(range(1_000))
        candidate = event(0, "run.initialized")
        object.__setattr__(candidate, "payload", {"irrelevant": values})
        with mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", 25), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct((candidate,))
        self.assertLess(values.reads, len(values))

    def test_reconstruction_charges_all_multibyte_scalar_event_fields(self):
        for field in ("run_id", "node_id", "kind", "occurred_at"):
            candidate = event(0, "run.initialized")
            object.__setattr__(candidate, field, "é" * 100)
            with self.subTest(field=field):
                with mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", 150), \
                        self.assertRaises(UnsafePayloadError) as raised:
                    self.engine.reconstruct((candidate,))
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("reconstruction_work_limit"),
                )

    def test_reconstruction_charges_repeated_event_and_node_update_work(self):
        stream = [
            event(0, "run.initialized"), event(1, "run.started"),
            event(2, "node.added", node_id="n"),
            event(3, "node.ready", node_id="n"),
            event(4, "node.started", node_id="n"),
        ]
        for _ in range(100):
            stream.append(event(len(stream), "node.waiting", node_id="n"))
            stream.append(event(len(stream), "node.started", node_id="n"))
        with mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", 450), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct(stream)

    def test_reconstruction_charges_new_evidence_before_materializing_it(self):
        references = [f"artifact-{index}" for index in range(500)]
        stream = (
            event(0, "run.initialized"),
            event(1, "evidence.recorded", payload={"evidence": references}),
        )
        with mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", 100), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct(stream)

    def test_reconstruction_charges_duplicate_evidence_copy_and_membership_work(self):
        references = [f"artifact-{index}" for index in range(500)]
        stream = (
            event(0, "run.initialized"),
            event(1, "evidence.recorded", payload={"evidence": references}),
            event(2, "evidence.recorded", payload={"evidence": references}),
        )
        for limit in (1_750, 2_250):
            with self.subTest(limit=limit), \
                    mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", limit), \
                    self.assertRaises(UnsafePayloadError):
                self.engine.reconstruct(stream)

    def test_reconstruction_charges_dependency_membership_scans(self):
        stream = [event(0, "run.initialized"), event(1, "run.started")]
        stream.extend(
            event(index + 2, "node.added", node_id=f"n-{index}")
            for index in range(10)
        )
        stream.append(event(
            12, "node.added", node_id="dependent",
            payload={"dependencies": [f"n-{index}" for index in range(10)]},
        ))
        with mock.patch.object(transitions, "MAX_RECONSTRUCTION_WORK", 80), \
                self.assertRaises(UnsafePayloadError):
            self.engine.reconstruct(stream)

    def setUp(self):
        self.engine = TransitionEngine()

    def test_apply_graph_validation_work_scales_with_input_graph(self):
        class CountingNodes(Mapping):
            def __init__(self, values):
                self.values = values
                self.accesses = 0

            def __iter__(self):
                for key in self.values:
                    self.accesses += 1
                    yield key

            def __len__(self):
                return len(self.values)

            def __getitem__(self, key):
                self.accesses += 1
                return self.values[key]

        nodes = CountingNodes({
            f"n-{index}": NodeState(f"n-{index}") for index in range(20)
        })
        state = RunState.new("run-1", NOW)
        object.__setattr__(state, "nodes", nodes)
        result = self.engine.apply(state, event(0, "run.initialized"))
        self.assertEqual(result.revision, 1)
        self.assertEqual(len(result.nodes), 20)
        self.assertLessEqual(nodes.accesses, 2 * len(nodes))

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

    def test_reducer_requires_exact_durable_schema_values(self):
        state = RunState.new("run-1", NOW)
        with self.assertRaises(UnsafePayloadError):
            self.engine.apply(object(), event(0, "run.initialized"))
        with self.assertRaises(UnsafePayloadError):
            self.engine.apply(state, object())

    def test_reducer_snapshots_mutated_exact_values_before_dispatch(self):
        base = RunState.new("run-1", NOW)
        mutations = (
            ("event-kind", base, event(0, "run.initialized"), "kind", object()),
            ("event-run", base, event(0, "run.initialized"), "run_id", object()),
            ("event-node", base, event(0, "run.initialized"), "node_id", object()),
            ("state-run", base, event(0, "run.initialized"), "run_id", object()),
            ("state-status", base, event(0, "run.initialized"), "status", object()),
            ("state-graph", base, event(0, "run.initialized"), "nodes", {"n": object()}),
        )
        for name, state, candidate, field, value in mutations:
            target = candidate if name.startswith("event") else state
            object.__setattr__(target, field, value)
            with self.subTest(name=name), self.assertRaises(KernelError):
                self.engine.apply(state, candidate)
            object.__setattr__(target, field, getattr(
                event(0, "run.initialized") if name.startswith("event") else RunState.new("run-1", NOW),
                field,
            ))

    def test_reconstruct_snapshots_first_event_before_initialization_checks(self):
        candidate = event(0, "run.initialized")
        object.__setattr__(candidate, "kind", object())
        with self.assertRaises(KernelError):
            self.engine.reconstruct((candidate,))

    def test_reconstruct_stops_streaming_at_explicit_event_bound(self):
        reads = 0

        def events():
            nonlocal reads
            sequence = 0
            while True:
                reads += 1
                if reads > 4:
                    raise AssertionError("event iterable was eagerly exhausted")
                kind = "run.initialized" if sequence == 0 else "run.started"
                yield event(sequence, kind)
                sequence += 1

        with mock.patch.object(transitions, "MAX_EVENT_ITEMS", 2):
            with self.assertRaises(UnsafePayloadError):
                self.engine.reconstruct(events())
        self.assertLessEqual(reads, 3)

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
        with self.assertRaises(KernelError):
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
        self.assertEqual(raised.exception.details["reason_code"], detail_digest("evidence_limit_exceeded"))
        self.assertEqual(raised.exception.details["limit_items"], 2)
        self.assertEqual(state.evidence, ("a",))
        self.assertEqual(state.nodes["n"].evidence, ("b",))
