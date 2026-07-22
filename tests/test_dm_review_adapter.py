import json
import copy
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

    def contribution(self, sequence, source_id="source-a", **changes):
        value = {
            "run_id": "review-contribution", "sequence": sequence,
            "stage": "finding_contribution", "status": "recorded",
            "node_id": "review-convergence", "attempt": 1,
            "occurred_at": f"2026-07-14T01:0{sequence}:00Z",
            "authoritative_receipt": f"receipts/contribution-{sequence}.json",
            "source_finding_id": source_id,
            "canonical_finding_id": "finding-v1-sha256-" + "a" * 64,
            "finding_disposition": "retained", "agreement": "unique",
            "decision_reason_code": "retained-unique", "reviewer": "security",
            "provider": "openai", "model": "gpt-5.6-sol",
            "evidence_ref": "raw/security.json",
        }
        value.update(changes)
        return value

    def test_finding_contributions_translate_one_event_per_stable_source_decision(self):
        receipts = [
            self.contribution(0),
            self.contribution(
                1, "source-b", finding_disposition="merged",
                agreement="corroborated", decision_reason_code="exact-duplicate",
                reviewer="architecture", provider=None, model=None,
                evidence_ref="raw/architecture.json",
            ),
        ]
        events = translate_review_receipts(receipts)
        self.assertEqual([event.payload["source_finding_id"] for event in events], ["source-a", "source-b"])
        self.assertEqual(events[1].payload["canonical_finding_id"], receipts[1]["canonical_finding_id"])
        self.assertEqual(events[1].payload["finding_disposition"], "merged")
        self.assertIn("raw/architecture.json", events[1].payload["evidence"])
        self.assertIsNone(events[1].payload["provider"])
        self.assertIsNone(events[1].payload["model"])

    def test_contribution_aliases_and_disputed_decisions_remain_literal(self):
        receipt = self.contribution(0)
        for snake, camel in (
            ("source_finding_id", "sourceFindingId"),
            ("canonical_finding_id", "canonicalFindingId"),
            ("finding_disposition", "findingDisposition"),
            ("decision_reason_code", "decisionReasonCode"),
            ("evidence_ref", "evidenceRef"),
        ):
            receipt[camel] = receipt.pop(snake)
        receipt.update({
            "agreement": "disputed", "decisionReasonCode": "retained-disagreement",
        })
        payload = translate_review_receipts([receipt])[0].payload
        self.assertEqual(payload["agreement"], "disputed")
        self.assertEqual(payload["decision_reason_code"], "retained-disagreement")

    def test_contributions_reject_duplicate_sources_invalid_decisions_and_unsafe_refs(self):
        with self.assertRaises(ValueError):
            translate_review_receipts([self.contribution(0), self.contribution(1)])
        mutations = (
            {"source_finding_id": ""}, {"canonical_finding_id": ""},
            {"finding_disposition": "deduped"}, {"agreement": "consensus"},
            {"decision_reason_code": "free-form"},
            {"finding_disposition": "discarded", "decision_reason_code": "retained-unique"},
            {"evidence_ref": "/private/raw.json"}, {"attempt": True},
        )
        for mutation in mutations:
            candidate = self.contribution(0)
            candidate.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                translate_review_receipts([candidate])

    def test_local_source_ids_are_scoped_to_artifact_with_reviewer_consistency(self):
        first = self.contribution(0, "finding-1", evidence_ref="raw/security-a.json")
        second = self.contribution(
            1, "finding-1", evidence_ref="raw/security-b.json",
            canonical_finding_id="finding-b",
        )
        events = translate_review_receipts([first, second])
        self.assertEqual(len(events), 2)
        inconsistent = self.contribution(
            1, "finding-2", evidence_ref="raw/security-a.json",
            reviewer="architecture",
        )
        with self.assertRaises(ValueError):
            translate_review_receipts([first, inconsistent])

    def test_browser_help_requires_blocked_shape_and_stable_case_identity(self):
        receipt = {
            "run_id": "review-help", "sequence": 0, "stage": "browser_recovery",
            "status": "blocked", "reason_code": "human_help_required",
            "node_id": "review-browser", "occurred_at": "2026-07-14T01:00:00Z",
            "authoritative_receipt": "receipts/browser-help.json",
            "human_intervention_id": "human-browser-a",
            "human_intervention_reason": "browser_evidence_unavailable",
            "missing_case_ids": ["persona-admin", "persona-member"],
        }
        payload = translate_review_receipts([receipt])[0].payload
        self.assertTrue(payload["human_intervention"])
        invalid = copy.deepcopy(receipt)
        invalid["missing_case_ids"] = []
        with self.assertRaises(ValueError):
            translate_review_receipts([invalid])
        wrong_reason = copy.deepcopy(receipt)
        wrong_reason["human_intervention_reason"] = "retry_budget_exhausted"
        with self.assertRaises(ValueError):
            translate_review_receipts([wrong_reason])
        invalid_id = copy.deepcopy(receipt)
        invalid_id["missing_case_ids"] = ["case/unsafe"]
        with self.assertRaises(ValueError):
            translate_review_receipts([invalid_id])

    def test_structured_record_receipts_preserve_bounded_refs_and_lane_gaps(self):
        finding = {
            "run_id": "review-records", "sequence": 0, "stage": "finding_record",
            "status": "recorded", "occurred_at": "2026-07-14T01:00:00Z",
            "authoritative_receipt": "receipts/finding-record.json",
            "record_ref": "records/findings/sha256-a.json", "record_digest": "sha256:" + "a" * 64,
            "source_finding_id": "security.finding-1",
            "lane_id": "security", "source_scope_digest": "sha256:" + "e" * 64,
            "canonical_finding_id": "finding-v1:sha256:" + "b" * 64,
            "rule_id": "authz.boundary", "category": "authorization",
            "severity": "P1", "path": "internal/auth.go", "anchor": "HandleAdmin",
            "source_agents": ["security-auditor"], "requested_provider": "openai",
            "attempted_provider": "openai", "implemented_by": "codex",
            "model": "gpt-5.6-sol", "attempt": 1,
            "build_binding_ref": "bindings/build.json", "browser_bundle_refs": [],
        }
        lane = {
            "run_id": "review-records", "sequence": 1, "stage": "lane_record",
            "status": "recorded", "occurred_at": "2026-07-14T01:01:00Z",
            "authoritative_receipt": "receipts/lane-record.json",
            "record_ref": "records/lanes/sha256-c.json", "record_digest": "sha256:" + "c" * 64,
            "lane_id": "visual", "state": "degraded", "expected_coverage": ["persona-admin"],
            "missing_case_ids": ["persona-admin"], "partial_output": True,
            "output_ref": "raw/visual-partial.md", "coverage_gap_reason": "browser unavailable",
            "source_agents": ["visual-reviewer"], "requested_provider": "openai",
            "attempted_provider": None, "implemented_by": None, "model": None, "attempt": 1,
            "build_binding_ref": "bindings/build.json", "browser_bundle_refs": ["browser/recovery.json"],
            "finding_refs": ["records/findings/sha256-a.json"],
        }
        events = translate_review_receipts([finding, lane])
        self.assertEqual(events[0].payload["record_digest"], finding["record_digest"])
        self.assertEqual(events[1].payload["missing_case_ids"], ("persona-admin",))
        self.assertTrue(events[1].payload["partial_output"])
        self.assertIn("browser/recovery.json", events[1].payload["evidence"])
        conflict = copy.deepcopy(lane); conflict["record_digest"] = "sha256:" + "d" * 64
        conflict["sequence"] = 2
        with self.assertRaises(ValueError):
            translate_review_receipts([finding, lane, conflict])
        unsafe = copy.deepcopy(finding); unsafe["record_ref"] = "/private/finding.json"
        with self.assertRaises(ValueError):
            translate_review_receipts([unsafe])


if __name__ == "__main__":
    unittest.main()
