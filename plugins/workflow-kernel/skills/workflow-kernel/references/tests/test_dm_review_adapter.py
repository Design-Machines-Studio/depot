import json
import unittest
from pathlib import Path

from workflow_kernel.model import HostCapabilities, WorkflowClass
from workflow_kernel.dm_review_adapter import ReviewRequest, translate_review, translate_review_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class DmReviewAdapterTests(unittest.TestCase):
    def test_request_translates_required_lanes_without_selecting_actions(self):
        request = ReviewRequest("review-1", ("security", "architecture", "visual"), "full", WorkflowClass.BUG, "codex_native", False)
        spec = translate_review(request, HostCapabilities("codex", frozenset()))
        self.assertEqual(spec.run_id, "review-1")
        self.assertEqual(spec.workflow_class, WorkflowClass.BUG)
        self.assertEqual(spec.required_lanes, ("security", "architecture", "visual"))
        self.assertEqual(spec.execution_mode, "codex_native")
        self.assertFalse(spec.workflow_class_defaulted)
        node_ids = {node.node_id for node in spec.nodes}
        self.assertTrue({"review-request", "review-lane-security", "review-convergence", "review-browser-verification", "review-cleanup", "review-terminal"} <= node_ids)
        self.assertFalse(hasattr(spec, "execute"))

    def test_mapping_tracks_legacy_workflow_class_default_provenance(self):
        request = ReviewRequest.from_mapping({"run_id": "review-legacy", "requested_lanes": ["architecture"], "executionMode": "full_cli"})
        spec = translate_review(request, HostCapabilities("claude", frozenset()))
        self.assertTrue(spec.workflow_class_defaulted)
        self.assertEqual(spec.workflow_class, WorkflowClass.FEATURE)
        self.assertEqual(spec.execution_mode, "full_cli")

    def test_mapping_preserves_explicit_provenance_on_round_trip(self):
        legacy = ReviewRequest.from_mapping({
            "run_id": "review-legacy", "requested_lanes": ["architecture"],
            "workflow_class": "feature", "workflow_class_defaulted": True,
        })
        self.assertTrue(legacy.workflow_class_defaulted)
        round_tripped = ReviewRequest.from_mapping(legacy.to_dict())
        self.assertEqual(round_tripped, legacy)
        self.assertTrue(round_tripped.workflow_class_defaulted)
        explicit = ReviewRequest.from_mapping({
            "run_id": "review-1", "requested_lanes": ["architecture"],
            "workflowClass": "bug", "workflowClassDefaulted": False,
        })
        self.assertFalse(explicit.workflow_class_defaulted)
        for invalid in (
            {"run_id": "r", "requested_lanes": [], "workflow_class_defaulted": "true"},
            {"run_id": "r", "requested_lanes": [], "workflow_class_defaulted": False},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ReviewRequest.from_mapping(invalid)

    def test_mapping_dual_keys_reject_conflicting_spellings(self):
        with self.assertRaises(ValueError):
            ReviewRequest.from_mapping({
                "run_id": "review-1", "requested_lanes": [],
                "execution_mode": "generic", "executionMode": "codex_native",
            })
        agreeing = ReviewRequest.from_mapping({
            "run_id": "review-1", "requested_lanes": [],
            "execution_mode": "codex_native", "executionMode": "codex_native",
        })
        self.assertEqual(agreeing.execution_mode, "codex_native")

    def test_mapping_requires_an_exact_lane_collection(self):
        for lanes in ("security", {"security": True}, (value for value in ("security",))):
            with self.subTest(lanes=type(lanes).__name__), self.assertRaises(ValueError):
                ReviewRequest.from_mapping({"run_id": "review-1", "requested_lanes": lanes})

    def test_receipts_preserve_fallback_findings_coverage_convergence_and_terminal(self):
        receipts = json.loads((FIXTURES / "dm-review.json").read_text())
        events = translate_review_receipts(receipts)
        by_stage = {event.payload["stage"]: event for event in events}
        self.assertEqual(by_stage["review_dispatch"].payload["fallback_reason"], "runtime_unavailable")
        self.assertEqual(by_stage["finding"].payload["finding_id"], "P1-auth-boundary")
        self.assertEqual(by_stage["coverage_matrix"].payload["unavailable_lanes"], ("visual",))
        self.assertEqual(by_stage["convergence"].payload["prior_findings_signature"], "sha256:" + "a" * 64)
        self.assertEqual(by_stage["review_terminal"].payload["status"], "findings")
        self.assertTrue(all(event.payload["authoritative_receipt"] in event.payload["evidence"] for event in events))


if __name__ == "__main__":
    unittest.main()
