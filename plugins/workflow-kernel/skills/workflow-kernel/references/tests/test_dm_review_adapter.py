import json
import unittest
from pathlib import Path

from workflow_kernel.adapters.base import HostCapabilities, WorkflowClass
from workflow_kernel.dm_review_adapter import ReviewRequest, translate_review, translate_review_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class DmReviewAdapterTests(unittest.TestCase):
    def test_request_translates_required_lanes_without_selecting_actions(self):
        request = ReviewRequest("review-1", ("security", "architecture", "visual"), "full", WorkflowClass.BUG)
        spec = translate_review(request, HostCapabilities("codex", frozenset()))
        self.assertEqual(spec.run_id, "review-1")
        self.assertEqual(spec.workflow_class, WorkflowClass.BUG)
        self.assertEqual(spec.required_lanes, ("security", "architecture", "visual"))
        self.assertFalse(hasattr(spec, "execute"))

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
