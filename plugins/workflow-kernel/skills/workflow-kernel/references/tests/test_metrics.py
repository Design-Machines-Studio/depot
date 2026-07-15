import json
import copy
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
        self.assertEqual(report.proposals, ())
        self.assertEqual(before, tuple(event.to_dict() for event in events))

    def test_empty_report_has_zero_rates(self):
        report = MetricsAggregator().aggregate(())
        self.assertEqual(report.completion_rate, 0.0)
        self.assertEqual(report.fallback_rate, 0.0)
        self.assertEqual(report.cleanup_reliability, 0.0)
        self.assertIsNone(report.tokens)
        self.assertIsNone(report.cost_usd)
        self.assertIsNone(report.time_to_clean_seconds)
        self.assertEqual(report.proposals, ())

    def test_time_to_clean_uses_run_start_to_terminal_cleanup(self):
        events = translate_pipeline_receipts(json.loads((FIXTURES / "pipeline-claude.json").read_text()))
        report = MetricsAggregator().aggregate(events)
        self.assertEqual(report.time_to_clean_seconds, 540.0)

    def test_invalid_numeric_facts_raise_and_proposals_name_observed_rationale(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        invalid = copy.deepcopy(receipts); invalid[-1]["cost_usd"] = -1
        with self.assertRaises(ValueError):
            MetricsAggregator().aggregate(translate_pipeline_receipts(invalid))
        fallback = copy.deepcopy(receipts)
        fallback[2]["fallback_reason"] = "provider_unavailable"
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(fallback))
        self.assertEqual(report.proposals[0]["rationale"], "observed_fallback")
        self.assertEqual(report.proposals[0]["evidence_count"], 1)

    def test_replay_duplicate_gap_and_order_are_rejected(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        variants = []
        duplicate = copy.deepcopy(receipts); duplicate[1]["sequence"] = 0; variants.append(duplicate)
        gap = copy.deepcopy(receipts); gap[1]["sequence"] = 2; variants.append(gap)
        order = copy.deepcopy(receipts); order[0], order[1] = order[1], order[0]; variants.append(order)
        for value in variants:
            with self.assertRaises(ValueError):
                MetricsAggregator().aggregate(translate_pipeline_receipts(value))


if __name__ == "__main__":
    unittest.main()
