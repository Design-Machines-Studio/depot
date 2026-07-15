import json
import unittest
from pathlib import Path

from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.schema import RunState
from workflow_kernel.shadow import ReceiptSet, ShadowComparator


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


def state(evidence):
    return RunState.from_dict({
        "schema_version": 1, "revision": 1, "run_id": "pipeline-1", "mode": "shadow", "status": "running",
        "created_at": "2026-07-14T00:00:00Z", "updated_at": "2026-07-14T00:10:00Z",
        "nodes": {}, "evidence": evidence, "cleanup_reconciled": False,
    })


class ShadowParityTests(unittest.TestCase):
    def load(self, name):
        return translate_pipeline_receipts(json.loads((FIXTURES / name).read_text()))

    def test_known_claude_codex_mechanisms_are_explained_when_semantics_match(self):
        claude = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        codex = ReceiptSet.from_events(self.load("pipeline-codex.json"))
        report = ShadowComparator().compare_receipt_sets(codex, claude)
        self.assertEqual(report.reason, "explained_host_difference")
        self.assertTrue(report.semantic_match)
        self.assertFalse(report.safe_to_promote)

    def test_missing_authoritative_evidence_is_unsafe(self):
        authoritative = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        report = ShadowComparator().compare(state(()), authoritative)
        self.assertIn(report.reason, ("kernel_prediction_gap", "missing_authoritative_evidence"))
        self.assertFalse(report.safe_to_promote)

    def test_exact_authoritative_evidence_matches(self):
        authoritative = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        refs = tuple(event.payload["authoritative_receipt"] for event in authoritative.events)
        report = ShadowComparator().compare(state(refs), authoritative)
        self.assertEqual(report.reason, "match")
        self.assertTrue(report.semantic_match)


if __name__ == "__main__":
    unittest.main()
