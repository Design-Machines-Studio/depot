import json
import unittest
from pathlib import Path

from workflow_kernel.metrics import MetricsAggregator
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class MetricsTests(unittest.TestCase):
    def test_aggregates_reliability_dimensions_without_mutating_events(self):
        events = translate_pipeline_receipts(json.loads((FIXTURES / "pipeline-claude.json").read_text()))
        before = tuple(event.to_dict() for event in events)
        report = MetricsAggregator().aggregate(events)
        self.assertEqual(report.workflow_classes, {"feature": 11})
        self.assertEqual(report.hosts, {"claude": 11})
        self.assertEqual(report.validation_first_pass_rate, 1.0)
        self.assertEqual(report.persona_expected, 2)
        self.assertEqual(report.persona_passed, 2)
        self.assertEqual(report.cleanup_removed, 2)
        self.assertEqual(report.tokens, 1200)
        self.assertAlmostEqual(report.cost_usd, 0.24)
        self.assertTrue(all(item["human_approval_required"] for item in report.proposals))
        self.assertEqual(before, tuple(event.to_dict() for event in events))

    def test_empty_report_has_zero_rates(self):
        report = MetricsAggregator().aggregate(())
        self.assertEqual(report.completion_rate, 0.0)
        self.assertEqual(report.fallback_rate, 0.0)
        self.assertEqual(report.cleanup_reliability, 0.0)


if __name__ == "__main__":
    unittest.main()
