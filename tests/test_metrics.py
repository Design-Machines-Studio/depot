import json
import copy
import unittest
from pathlib import Path

from workflow_kernel.metrics import MetricsAggregator
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.dm_review_adapter import translate_review_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class MetricsTests(unittest.TestCase):
    def usage_receipt(self, sequence, attempt, **measurements):
        receipt = {
            "run_id": "economics-1", "sequence": sequence,
            "stage": "attempt_usage", "status": "observed",
            "node_id": "chunk-a", "chunk_id": "chunk-a",
            "occurred_at": f"2026-07-14T00:0{sequence}:00Z",
            "authoritative_receipt": f"receipts/attempt-{sequence}.json",
            "host": "codex", "provider": "openai", "model": "gpt-5.6-sol",
            "requested_provider": "openrouter", "attempted_provider": "openai",
            "implemented_by": "codex", "attempt": attempt,
            "duration_seconds": 1.0,
            "usage_scope": "attempt", "measurement_source": "provider_receipt",
            "usage_estimated": False,
        }
        receipt.update(measurements)
        return receipt

    def test_aggregates_reliability_dimensions_without_mutating_events(self):
        events = translate_pipeline_receipts(json.loads((FIXTURES / "pipeline-claude.json").read_text()))
        before = tuple(event.to_dict() for event in events)
        report = MetricsAggregator().aggregate(events)
        self.assertEqual(report.workflow_classes, {"feature": 11})
        self.assertEqual(report.hosts, {"claude-code": 11})
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
        self.assertIsNone(report.wall_clock_seconds)
        self.assertIsNone(report.active_compute_seconds)
        self.assertEqual(
            report.wait_seconds_by_category,
            {
                "human_gate": 0,
                "external_dependency": 0,
                "capacity": 0,
                "ci": 0,
            },
        )
        self.assertEqual(report.proposals, ())

    def test_time_to_clean_uses_run_start_to_terminal_cleanup(self):
        events = translate_pipeline_receipts(json.loads((FIXTURES / "pipeline-claude.json").read_text()))
        report = MetricsAggregator().aggregate(events)
        self.assertEqual(report.time_to_clean_seconds, 540.0)

    def test_wall_clock_separates_active_compute_from_typed_waits(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[1]["wait_category"] = "human_gate"
        receipts[1]["duration_seconds"] = 120
        receipts[4]["wait_category"] = "ci"
        receipts[4]["duration_seconds"] = 30
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(report.wall_clock_seconds, 600.0)
        self.assertEqual(report.active_compute_seconds, 450.0)
        self.assertEqual(report.wait_seconds_by_category["human_gate"], 120.0)
        self.assertEqual(report.wait_seconds_by_category["ci"], 30.0)

    def test_unknown_wait_category_is_rejected(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[1]["wait_category"] = "mystery"
        receipts[1]["duration_seconds"] = 1
        with self.assertRaises(ValueError):
            MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))

    def test_single_explicit_node_duration_replaces_timestamp_fallback(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2]["duration_seconds"] = 7.5
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(report.duration_seconds_by_node["chunk-a"], 7.5)

    def test_multiple_explicit_node_durations_are_summed(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2]["duration_seconds"] = 7.5
        receipts[3]["duration_seconds"] = 2.5
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(report.duration_seconds_by_node["chunk-a"], 10.0)

    def test_invalid_explicit_node_duration_is_rejected(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2]["duration_seconds"] = -0.1
        with self.assertRaises(ValueError):
            MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))

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

    def test_model_used_alias_feeds_the_model_metrics_dimension(self):
        # Finding 087: modelUsed evidence populates model metrics.
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2]["modelUsed"] = "claude-opus-4-8"
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(report.models, {"claude-opus-4-8": 1})

    def test_isolation_strategy_feeds_its_own_metrics_dimension(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        for receipt in receipts:
            receipt["isolationStrategy"] = "sequential-on-branch"
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(
            report.isolation_strategies,
            {"sequential-on-branch": len(receipts)},
        )

    def test_replay_duplicate_gap_and_order_are_rejected(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        variants = []
        duplicate = copy.deepcopy(receipts); duplicate[1]["sequence"] = 0; variants.append(duplicate)
        gap = copy.deepcopy(receipts); gap[1]["sequence"] = 2; variants.append(gap)
        order = copy.deepcopy(receipts); order[0], order[1] = order[1], order[0]; variants.append(order)
        for value in variants:
            with self.assertRaises(ValueError):
                MetricsAggregator().aggregate(translate_pipeline_receipts(value))

    def test_run_total_precedes_complete_attempt_breakdown_without_double_count(self):
        receipts = [
            self.usage_receipt(0, 1, usage_count=100, input_usage_count=60, cost_usd=0.1),
            self.usage_receipt(1, 2, usage_count=200, input_usage_count=120, cost_usd=0.2),
            {
                "run_id": "economics-1", "sequence": 2, "stage": "run_summary",
                "status": "succeeded", "node_id": None,
                "occurred_at": "2026-07-14T00:02:00Z",
                "authoritative_receipt": "receipts/run-total.json",
                "usage_scope": "run", "measurement_source": "billing_export",
                "usage_estimated": False, "usage_count": 250,
                "input_usage_count": 150, "cost_usd": 0.25,
            },
        ]
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(report.tokens, 250)
        self.assertEqual(report.usage_totals["input_usage_count"], 150)
        self.assertEqual(report.cost_usd, 0.25)
        self.assertEqual(report.usage_total_provenance["usage_count"], "authoritative_run_total")
        self.assertEqual(report.cost_total_provenance, "authoritative_run_total")
        self.assertEqual(report.usage_measurement_coverage["measured"], 2)
        self.assertEqual(len(report.attempt_economics), 2)

    def test_complete_attempts_derive_totals_and_partial_coverage_stays_unknown(self):
        complete = [
            self.usage_receipt(0, 1, usage_count=100, output_usage_count=40, cost_usd=0.1),
            self.usage_receipt(1, 2, usage_count=200, output_usage_count=80, cost_usd=0.2),
        ]
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(complete))
        self.assertEqual(report.tokens, 300)
        self.assertAlmostEqual(report.cost_usd, 0.3)
        self.assertEqual(report.usage_total_provenance["usage_count"], "derived_complete_attempts")
        self.assertEqual(report.usage_measurement_coverage["missing"], 0)

        missing = [complete[0], {
            **{key: value for key, value in complete[1].items() if key not in {
                "usage_scope", "measurement_source", "usage_estimated",
                "usage_count", "output_usage_count", "cost_usd",
            }},
            "stage": "dispatch",
        }]
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(missing))
        self.assertIsNone(report.tokens)
        self.assertIsNone(report.cost_usd)
        self.assertEqual(
            report.usage_measurement_coverage,
            {"expected": 2, "measured": 1, "estimated": 0, "missing": 1,
             "overlap": 0, "unassigned": 0},
        )

    def test_usage_and_cost_coverage_are_independent_and_estimation_is_visible(self):
        cost_only = self.usage_receipt(0, 1, cost_usd=0.3)
        cost_report = MetricsAggregator().aggregate(translate_pipeline_receipts([cost_only]))
        self.assertIsNone(cost_report.tokens)
        self.assertEqual(cost_report.cost_usd, 0.3)
        self.assertEqual(cost_report.usage_measurement_coverage["missing"], 1)
        self.assertEqual(cost_report.cost_measurement_coverage["measured"], 1)

        usage_only = self.usage_receipt(0, 1, usage_count=9, usage_estimated=True)
        usage_report = MetricsAggregator().aggregate(translate_pipeline_receipts([usage_only]))
        self.assertEqual(usage_report.tokens, 9)
        self.assertIsNone(usage_report.cost_usd)
        self.assertEqual(usage_report.usage_measurement_coverage["estimated"], 1)
        self.assertEqual(usage_report.cost_measurement_coverage["missing"], 1)

    def test_overlapping_attempt_measurements_do_not_create_a_total(self):
        receipts = [
            self.usage_receipt(0, 1, usage_count=10, cost_usd=0.1),
            self.usage_receipt(1, 1, usage_count=10, cost_usd=0.1),
        ]
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertIsNone(report.tokens)
        self.assertIsNone(report.cost_usd)
        self.assertEqual(report.usage_measurement_coverage["overlap"], 1)

    def test_coverage_identity_coalesces_dispatch_or_contribution_with_usage(self):
        usage = self.usage_receipt(
            1, 1, usage_count=10, reviewer="security", lane="security",
        )
        dispatch = {
            **{key: value for key, value in usage.items() if key not in {
                "usage_scope", "usage_count", "measurement_source",
                "usage_estimated", "duration_seconds",
            }},
            "sequence": 0, "stage": "dispatch",
            "occurred_at": "2026-07-14T00:00:00Z",
            "authoritative_receipt": "receipts/dispatch.json",
            "provider": "openrouter", "model": "requested-model",
        }
        for field in ("chunk_id", "reviewer", "lane"):
            dispatch.pop(field)
        report = MetricsAggregator().aggregate(
            translate_pipeline_receipts([dispatch, usage]),
        )
        self.assertEqual(report.usage_measurement_coverage["expected"], 1)
        self.assertEqual(report.usage_measurement_coverage["measured"], 1)
        self.assertEqual(report.tokens, 10)

        contribution = {
            "run_id": "economics-1", "sequence": 0,
            "stage": "finding_contribution", "status": "recorded",
            "node_id": "chunk-a", "chunk_id": "chunk-a", "attempt": 1,
            "reviewer": "security", "lane": "security",
            "source_finding_id": "source-a", "canonical_finding_id": "finding-a",
            "finding_disposition": "retained", "agreement": "unique",
            "decision_reason_code": "retained-unique",
            "provider": "openrouter", "model": "review-model",
            "evidence_ref": "raw/security.json",
            "occurred_at": "2026-07-14T00:00:00Z",
            "authoritative_receipt": "receipts/contribution.json",
        }
        report = MetricsAggregator().aggregate(translate_review_receipts([
            contribution, usage,
        ]))
        self.assertEqual(report.usage_measurement_coverage["expected"], 1)
        self.assertEqual(report.usage_measurement_coverage["missing"], 0)

    def test_generic_measurement_is_unassigned_when_reviewer_expectations_are_ambiguous(self):
        common = {
            "run_id": "ambiguous-coverage", "stage": "finding_contribution",
            "status": "recorded", "node_id": "review-convergence",
            "chunk_id": "chunk-a", "attempt": 1,
            "canonical_finding_id": "finding-a", "agreement": "corroborated",
            "evidence_ref": "raw/reviewer-a.json",
        }
        receipts = [
            {**common, "sequence": 0, "reviewer": "security", "lane": "security",
             "source_finding_id": "source-a", "finding_disposition": "retained",
             "decision_reason_code": "retained-corroborated",
             "occurred_at": "2026-07-14T00:00:00Z",
             "authoritative_receipt": "receipts/contribution-a.json"},
            {**common, "sequence": 1, "reviewer": "architecture", "lane": "architecture",
             "source_finding_id": "source-b", "finding_disposition": "merged",
             "decision_reason_code": "exact-duplicate",
             "evidence_ref": "raw/reviewer-b.json",
             "occurred_at": "2026-07-14T00:01:00Z",
             "authoritative_receipt": "receipts/contribution-b.json"},
            {
                "run_id": "ambiguous-coverage", "sequence": 2,
                "stage": "attempt_usage", "status": "observed",
                "node_id": "review-convergence", "chunk_id": "chunk-a", "attempt": 1,
                "requested_provider": "openrouter", "attempted_provider": "openai",
                "implemented_by": "codex", "provider": "openai",
                "model": "gpt-5.6-sol", "host": "codex", "duration_seconds": 1.0,
                "usage_scope": "attempt", "usage_count": 10,
                "measurement_source": "provider_receipt", "usage_estimated": False,
                "occurred_at": "2026-07-14T00:02:00Z",
                "authoritative_receipt": "receipts/generic-usage.json",
            },
        ]
        report = MetricsAggregator().aggregate(translate_review_receipts(receipts))
        self.assertEqual(report.usage_measurement_coverage, {
            "expected": 2, "measured": 0, "estimated": 0, "missing": 2,
            "overlap": 0, "unassigned": 1,
        })
        self.assertIsNone(report.tokens)

    def test_contributions_preserve_canonical_count_and_existing_yield(self):
        common = {
            "run_id": "review-economics", "stage": "finding_contribution",
            "status": "recorded", "node_id": "review-convergence",
            "canonical_finding_id": "finding-a",
            "agreement": "corroborated", "attempt": 1,
            "evidence_ref": "raw/findings.json",
        }
        receipts = [
            {**common, "sequence": 0, "occurred_at": "2026-07-14T00:00:00Z",
             "authoritative_receipt": "receipts/source-a.json", "source_finding_id": "source-a",
             "finding_disposition": "retained", "decision_reason_code": "retained-corroborated",
             "reviewer": "security", "provider": "openai", "model": "gpt-5.6-sol",
             "evidence_ref": "raw/security.json"},
            {**common, "sequence": 1, "occurred_at": "2026-07-14T00:01:00Z",
             "authoritative_receipt": "receipts/source-b.json", "source_finding_id": "source-b",
             "finding_disposition": "merged", "decision_reason_code": "exact-duplicate",
             "reviewer": "architecture", "provider": "anthropic", "model": "claude-opus",
             "evidence_ref": "raw/architecture.json"},
        ]
        report = MetricsAggregator().aggregate(translate_review_receipts(receipts))
        self.assertEqual(report.canonical_finding_count, 1)
        self.assertEqual(report.finding_contribution_count, 2)
        self.assertEqual(report.finding_contributions_by_reviewer["security"]["corroborated"], 1)
        self.assertEqual(report.finding_contributions_by_reviewer["architecture"]["merged"], 1)
        self.assertEqual(report.unique_reviewer_yield, 0)

    def test_human_interventions_dedupe_by_id_and_ignore_human_gate_wait(self):
        validation = {
            "run_id": "human-1", "sequence": 0, "stage": "deterministic_validation",
            "status": "blocked", "action": "human_help_required", "node_id": "chunk-a",
            "attempt": 2, "human_intervention_id": "human-validation-a",
            "human_intervention_reason": "retry_budget_exhausted",
            "occurred_at": "2026-07-14T00:00:00Z",
            "authoritative_receipt": "receipts/human-a.json",
        }
        receipts = [validation, {
            "run_id": "human-1", "sequence": 1, "stage": "run_summary",
            "status": "blocked", "node_id": None,
            "human_intervention_id": "human-validation-a",
            "human_intervention_reason": "retry_budget_exhausted",
            "occurred_at": "2026-07-14T00:01:00Z",
            "authoritative_receipt": "receipts/summary.json",
        }, {
            "run_id": "human-1", "sequence": 2, "stage": "progress",
            "status": "waiting", "node_id": None, "wait_category": "human_gate",
            "duration_seconds": 30, "occurred_at": "2026-07-14T00:02:00Z",
            "authoritative_receipt": "receipts/wait.json",
        }]
        report = MetricsAggregator().aggregate(translate_pipeline_receipts(receipts))
        self.assertEqual(report.human_intervention_count, 1)
        self.assertEqual(report.human_interventions_by_reason, {"retry_budget_exhausted": 1})
        self.assertEqual(report.human_intervention_attempts[0]["attempt"], 2)
        self.assertEqual(report.wait_seconds_by_category["human_gate"], 30)


if __name__ == "__main__":
    unittest.main()
