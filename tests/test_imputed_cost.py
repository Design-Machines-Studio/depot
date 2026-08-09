"""Tests for subscription-rail API-equivalent cost imputation."""

import unittest

from workflow_kernel.cost_summary import (
    build_run_cost_summary,
    validate_run_cost_summary,
)
from workflow_kernel.imputed_cost import impute_attempt_cost
from workflow_kernel.schema import WorkflowEvent


MATRIX = {
    "snapshot_date": "2026-08-03",
    "models": [{
        "slug": "openai/gpt-test",
        "input_usd_per_m": 1.0,
        "output_usd_per_m": 2.0,
        "cache_read_usd_per_m": 0.5,
        "snapshot_date": "2026-08-03",
    }],
}


def _row(**overrides):
    row = {
        "model": "openai/gpt-test",
        "input_usage_count": 1_000_000,
        "output_usage_count": 500_000,
        "cache_read_usage_count": 250_000,
        "cost_usd": None,
        "measurement_source": "subscription_usage",
        "usage_estimated": False,
    }
    row.update(overrides)
    return row


class ImputedCostTests(unittest.TestCase):
    def test_priced_attempt_gains_cost_and_visible_provenance(self):
        result = impute_attempt_cost(_row(), MATRIX)
        self.assertEqual(result["cost_usd"], 2.125)
        self.assertEqual(
            result["measurement_source"],
            "subscription_usage+imputed_cost(model-matrix@2026-08-03)",
        )
        self.assertTrue(result["usage_estimated"])

    def test_unpriceable_model_is_unchanged(self):
        row = _row(model="missing/model")
        self.assertIs(impute_attempt_cost(row, MATRIX), row)

    def test_missing_required_price_is_unchanged(self):
        row = _row()
        matrix = {
            "models": [{
                "slug": "openai/gpt-test",
                "output_usd_per_m": 2.0,
                "cache_read_usd_per_m": 0.5,
                "snapshot_date": "2026-08-03",
            }],
        }
        self.assertIs(impute_attempt_cost(row, matrix), row)

    def test_present_cost_is_never_overwritten(self):
        row = _row(cost_usd=4.25)
        self.assertIs(impute_attempt_cost(row, MATRIX), row)
        self.assertEqual(row["cost_usd"], 4.25)

    def test_missing_counters_stay_missing_and_contribute_nothing(self):
        row = _row(output_usage_count=None, cache_read_usage_count=None)
        result = impute_attempt_cost(row, MATRIX)
        self.assertEqual(result["cost_usd"], 1.0)
        self.assertIsNone(result["output_usage_count"])
        self.assertIsNone(result["cache_read_usage_count"])

    def test_output_is_deterministic_and_input_is_not_mutated(self):
        row = _row()
        first = impute_attempt_cost(row, MATRIX)
        second = impute_attempt_cost(row, MATRIX)
        self.assertEqual(first, second)
        self.assertIsNone(row["cost_usd"])
        self.assertFalse(row["usage_estimated"])

    def test_summary_totals_identify_imputed_subscription_equivalent(self):
        event = WorkflowEvent(
            1, 0, "imputation-run", "chunk-1", "evidence.recorded",
            "2026-08-09T00:00:00Z",
            {
                "stage": "attempt_usage", "status": "observed",
                "chunk_id": "chunk-1", "lane": "implementation",
                "attempt": 1, "usage_scope": "attempt",
                "model": "openai/gpt-test", "host": "codex",
                "input_usage_count": 1_000_000,
                "output_usage_count": 500_000,
                "cache_read_usage_count": 250_000,
                "measurement_source": "subscription_usage",
                "usage_estimated": False,
            },
        )
        summary = build_run_cost_summary((event,), matrix=MATRIX)
        validate_run_cost_summary(summary)
        self.assertEqual(summary["totals"]["cost_usd"], 2.125)
        self.assertEqual(
            summary["totals"]["cost_provenance"],
            "imputed_subscription_equivalent",
        )
        self.assertEqual(summary["measurement_coverage"]["cost"]["estimated"], 1)
        self.assertEqual(summary["measurement_coverage"]["cost"]["missing"], 0)


if __name__ == "__main__":
    unittest.main()
