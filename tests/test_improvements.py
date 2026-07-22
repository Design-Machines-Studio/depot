import copy
import json
import unittest

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.improvements import (
    build_candidate, build_improvement_report, build_input_index,
    render_upstream_prompt, validate_improvement_report, validate_input_index,
)


class ImprovementScoutTests(unittest.TestCase):
    def input(self, **changes):
        value = {
            "evidence_id": "validator.failure.1",
            "artifact_ref": "plans/feature/evidence/validator.json",
            "artifact_digest": "sha256:" + "1" * 64,
            "source_run": "feature-run-1", "source_stage": "validation",
            "source_chunk": "chunk-1", "observation_category": "guardrail_failure",
            "observed_at": "2026-07-14T00:00:00Z",
            "classification_rule": "safe-redacted-json",
            "availability": "available",
            "redaction_status": "approved_safe_reference_only",
        }
        value.update(changes)
        return value

    def index(self, inputs=None):
        return build_input_index(
            run_id="feature-run-1", feature_slug="feature-run",
            sealed_at="2026-07-14T01:00:00Z",
            inputs=[self.input()] if inputs is None else inputs,
        )

    def candidate(self, **changes):
        value = {
            "category": "new_deterministic_check",
            "observed_problem": "A validator failure required repeated manual diagnosis.",
            "evidence_refs": ["plans/feature/evidence/validator.json"],
            "source_runs": ["feature-run-1"], "source_stages": ["validation"],
            "source_chunks": ["chunk-1"], "recurrence_count": 1,
            "status": "one-off", "dedupe_key": "validator:canonical-launch",
            "dedupe_reason": "No matching completed control exists.",
            "existing_control_refs": [], "owner_plugin": "pipeline",
            "target_surfaces": ["plugins/pipeline/references/verification.md"],
            "mechanical_work": "Add a deterministic launch-command validator.",
            "judgment_boundary": "Agents still decide whether a command is appropriate.",
            "acceptance_tests": ["Reject a noncanonical launch command."],
            "confidence": "medium",
            "safety_boundary": "Proposal only; no source or release mutation.",
            "compatibility_notes": "Preserve Claude and Codex receipt semantics.",
            "benefit_basis": "qualitative",
            "expected_benefit": "Reduce repeated manual command-selection friction.",
            "benefit_evidence_refs": [],
        }
        value.update(changes)
        return build_candidate(**value)

    def outcomes(self):
        cleanup = [{
            "domain": domain, "disposition": "removed", "count": 0,
            "tier": "2" if domain == "artifact" else None,
            "sensitivity": "safe" if domain == "artifact" else None,
            "evidence_ref": f"plans/feature/cleanup/{domain}.json",
        } for domain in ("docker", "artifact", "git")]
        shadow = {
            "availability": "available", "category": "match", "reasons": [],
            "missing_authority": [],
            "evidence_refs": ["plans/feature/shadow-report.json"],
        }
        metrics = [{
            "name": name, "availability": "unavailable", "value": None,
            "unit": None, "evidence_ref": "plans/feature/metrics.json",
        } for name in (
            "duration_seconds", "wait_seconds", "attempt_count",
            "provider_attempt_count", "finding_contribution_count", "usage_count",
        )]
        return cleanup, shadow, metrics

    def report(self, candidates):
        cleanup, shadow, metrics = self.outcomes()
        return build_improvement_report(
            input_index=self.index(), finalized_at="2026-07-14T02:00:00Z",
            cleanup_outcomes=cleanup, shadow_outcome=shadow, metrics=metrics,
            candidates=candidates,
        )

    def test_safe_index_is_sorted_sealed_and_matches_strict_schema(self):
        second = self.input(
            evidence_id="browser.recovery.2", source_stage="browser_recovery",
            artifact_ref="plans/feature/evidence/browser.json",
            artifact_digest="sha256:" + "2" * 64,
        )
        index = self.index([self.input(), second])
        self.assertEqual([item["evidence_id"] for item in index["inputs"]],
                         ["browser.recovery.2", "validator.failure.1"])
        schema = json.loads((KERNEL_REFERENCES / "improvement-input-index-schema.json").read_text())
        self.assertTrue(schema_matches(index, schema))
        tampered = copy.deepcopy(index); tampered["inputs"][0]["availability"] = "unavailable"
        with self.assertRaises(ValueError):
            validate_input_index(tampered)

    def test_index_rejects_unsafe_secret_private_and_unclassified_inputs(self):
        for mutation in (
            {"artifact_ref": "../private.json"},
            {"artifact_ref": "plans/secret.json#token=ghp_" + "x" * 36},
            {"redaction_status": "not-reviewed"},
            {"artifact_digest": "sha256:short"},
            {"availability": "maybe"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.index([self.input(**mutation)])

    def test_dedupe_recurrence_and_completed_controls_stay_out_of_prompt(self):
        first = self.candidate()
        repeated = self.candidate(
            evidence_refs=["plans/feature/evidence/validator-2.json"],
            source_runs=["feature-run-2"], source_chunks=["chunk-2"],
        )
        report = self.report([repeated, first])
        self.assertEqual(report["deduped_candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["recurrence_count"], 2)
        self.assertEqual(report["candidates"][0]["status"], "recurring")
        prompt = render_upstream_prompt(report)
        self.assertEqual(prompt, render_upstream_prompt(copy.deepcopy(report)))
        self.assertIn("full `/pipeline`", prompt)
        self.assertIn("validator:canonical-launch", report["candidates"][0]["dedupe_key"])

        completed = self.candidate(
            status="completed", dedupe_key="provider:attempt-receipts",
            existing_control_refs=["docs/pipeline-metrics/ledger.md"],
            observed_problem="Provider attempt receipts were previously incomplete.",
        )
        completed_report = self.report([completed])
        self.assertEqual(completed_report["candidates"][0]["status"], "completed")
        self.assertNotIn(completed["candidate_id"], render_upstream_prompt(completed_report))

    def test_empty_report_is_successful_and_unavailable_metrics_stay_unavailable(self):
        report = self.report([])
        self.assertEqual(report["empty_reason"], "no_evidence_backed_improvement")
        self.assertEqual(report["candidates"], [])
        self.assertTrue(all(item["value"] is None for item in report["metrics"]))
        schema = json.loads((KERNEL_REFERENCES / "improvement-report-schema.json").read_text())
        self.assertTrue(schema_matches(report, schema))
        self.assertIn("No eligible upstream implementation candidates", render_upstream_prompt(report))

    def test_candidates_require_evidence_honest_recurrence_and_no_authority(self):
        invalid = (
            {"evidence_refs": []}, {"status": "standing", "recurrence_count": 2},
            {"status": "one-off", "recurrence_count": 2},
            {"benefit_basis": "measured", "benefit_evidence_refs": []},
            {"benefit_basis": "qualitative", "benefit_evidence_refs": ["metrics.json"]},
            {"merge_release_authority": True},
        )
        for mutation in invalid:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.candidate(**mutation)
        report = self.report([self.candidate()])
        extra = copy.deepcopy(report); extra["authority"] = "merge"
        with self.assertRaises(ValueError):
            validate_improvement_report(extra)


if __name__ == "__main__":
    unittest.main()
