import json
import copy
import hashlib
import unittest
from pathlib import Path

from workflow_kernel.model import HostCapabilities, WorkflowClass
from workflow_kernel.dm_review_adapter import (
    ReviewRequest, export_finding_contributions,
    require_complete_contribution_coverage, translate_review,
    translate_review_receipts,
)
from workflow_kernel._translation import canonical_finding_identity


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
        identity = {
            "finding_path": "internal/review.py",
            "finding_anchor": "review.finding",
            "finding_category": "trust boundary",
            "finding_root_cause": "caller supplied identity",
        }
        canonical_id, _ = canonical_finding_identity(*identity.values())
        value = {
            "run_id": "review-contribution", "sequence": sequence,
            "stage": "finding_contribution", "status": "recorded",
            "node_id": "review-convergence", "attempt": 1,
            "occurred_at": f"2026-07-14T01:0{sequence}:00Z",
            "authoritative_receipt": f"receipts/contribution-{sequence}.json",
            "source_finding_id": source_id,
            "canonical_finding_id": canonical_id, **identity,
            "finding_disposition": "retained", "agreement": "unique",
            "decision_reason_code": "retained-unique", "reviewer": "security",
            "source_severity": "P2",
            "lane": "security", "requested_provider": "openai",
            "attempted_provider": "openai", "implemented_by": "codex",
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
                reviewer="architecture", lane="openrouter-fallback",
                requested_provider="openrouter", attempted_provider="openrouter",
                implemented_by="codex", provider="openai", model="not_reported",
                evidence_ref="raw/architecture.json",
            ),
        ]
        events = translate_review_receipts(receipts)
        self.assertEqual([event.payload["source_finding_id"] for event in events], ["source-a", "source-b"])
        self.assertEqual(events[1].payload["canonical_finding_id"], receipts[1]["canonical_finding_id"])
        self.assertEqual(events[1].payload["finding_disposition"], "merged")
        self.assertIn("raw/architecture.json", events[1].payload["evidence"])
        self.assertEqual(events[1].payload["provider"], "openai")
        self.assertEqual(events[1].payload["model"], "not_reported")

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
            finding_root_cause="different caller supplied identity",
            canonical_finding_id=canonical_finding_identity(
                "internal/review.py", "review.finding", "trust boundary",
                "different caller supplied identity",
            )[0],
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
        from tests.test_browser_recovery import BrowserRecoveryTests
        helper = BrowserRecoveryTests(); helper.setUp()
        recovery = helper.blocked_with_unavailable_readiness()
        receipt = {
            "run_id": "review-help", "sequence": 0, "stage": "browser_recovery",
            "status": "blocked", "reason_code": "human_help_required",
            "node_id": "review-browser", "occurred_at": "2026-07-14T01:00:00Z",
            "authoritative_receipt": "receipts/browser-help.json",
            "human_intervention_id": "human-browser-a",
            "human_intervention_reason": "browser_evidence_unavailable",
            "missing_case_ids": ["case-1"],
            "recovery_receipts": [recovery.to_dict()],
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

        incomplete = copy.deepcopy(receipt)
        incomplete.pop("recovery_receipts")
        with self.assertRaises(ValueError):
            translate_review_receipts([incomplete])

    def test_review_request_preserves_explicit_decision_profile(self):
        profile = {
            "uncertainty": "high", "consequence": "medium",
            "rationale": "Review trust and observation seams.",
        }
        request = ReviewRequest.from_mapping({
            "run_id": "review-profile", "requested_lanes": ["security"],
            "decisionProfile": profile, "decisionProfileDefaulted": False,
        })
        self.assertEqual(request.to_dict()["decision_profile"], profile)
        spec = translate_review(request, HostCapabilities("codex", frozenset()))
        self.assertEqual(dict(spec.decision_profile), profile)
        self.assertFalse(spec.decision_profile_defaulted)

    def test_exporter_derives_ids_sequences_and_enforces_cardinality(self):
        request = ReviewRequest("review-export", ("security",), execution_mode="generic")
        decision = {
            key: value for key, value in self.contribution(0).items()
            if key in {
                "source_finding_id", "finding_path", "finding_anchor",
                "finding_category", "finding_root_cause",
                "finding_disposition", "agreement", "decision_reason_code",
                "reviewer", "lane", "requested_provider", "attempted_provider",
                "implemented_by", "provider", "model", "source_severity", "evidence_ref",
                "attempt", "occurred_at",
            }
        }
        decisions = {
            "schema_version": 1, "artifact_role": "synthesis_decisions",
            "run_id": request.run_id, "source_finding_count": 1,
            "occurred_at": "2026-07-14T01:00:00Z", "decisions": [decision],
        }
        raw_findings = {
            "schema_version": 1, "artifact_role": "raw_finding_inventory",
            "run_id": request.run_id,
            "findings": [{key: decision[key] for key in {
                "source_finding_id", "reviewer", "lane", "source_severity",
                "evidence_ref", "finding_path", "finding_anchor",
                "finding_category", "finding_root_cause",
            }}],
        }
        lane_receipts = {
            "schema_version": 1, "artifact_role": "review_lane_receipts",
            "run_id": request.run_id, "lanes": [{
                **{key: decision[key] for key in {
                    "reviewer", "lane", "requested_provider",
                    "attempted_provider", "implemented_by", "provider", "model",
                }},
                "evidence_refs": [decision["evidence_ref"]],
            }],
        }
        documents = {
            "decisions": ("synthesis-decisions", decisions),
            "raw_findings": ("raw-finding-inventory", raw_findings),
            "lane_receipts": ("lane-receipts", lane_receipts),
        }
        def make_references(values):
            references = {}
            for key, (role, document) in values.items():
                encoded = json.dumps(
                    document, sort_keys=True, separators=(",", ":"),
                ).encode()
                references[key] = (
                    "contribution-inputs/" + role + "-sha256-"
                    + hashlib.sha256(encoded).hexdigest() + ".json"
                )
            return references

        references = make_references(documents)
        exported = export_finding_contributions(
            request, decisions, raw_findings, lane_receipts, (), references,
        )
        self.assertEqual(exported[0]["sequence"], 0)
        self.assertEqual(exported[1]["stage"], "finding_contribution_coverage")
        self.assertTrue(exported[1]["coverage_complete"])
        self.assertRegex(
            exported[0]["canonical_finding_id"],
            r"^finding-v1:sha256\([0-9a-f]{64}\)$",
        )
        with self.assertRaises(ValueError):
            export_finding_contributions(
                request, {**decisions, "source_finding_count": 2},
                raw_findings, lane_receipts, (), references,
            )

        hostile = copy.deepcopy(decisions)
        hostile["decisions"][0]["provider"] = "anthropic"
        hostile_references = make_references({
            **documents, "decisions": ("synthesis-decisions", hostile),
        })
        with self.assertRaises(ValueError):
            export_finding_contributions(
                request, hostile, raw_findings, lane_receipts, (),
                hostile_references,
            )

        unsafe_decisions = copy.deepcopy(decisions)
        unsafe_lanes = copy.deepcopy(lane_receipts)
        unsafe_decisions["decisions"][0]["model"] = "sk-secret-model-value"
        unsafe_lanes["lanes"][0]["model"] = "sk-secret-model-value"
        unsafe_documents = {
            "decisions": ("synthesis-decisions", unsafe_decisions),
            "raw_findings": ("raw-finding-inventory", raw_findings),
            "lane_receipts": ("lane-receipts", unsafe_lanes),
        }
        with self.assertRaisesRegex(ValueError, "unsafe contribution input"):
            export_finding_contributions(
                request, unsafe_decisions, raw_findings, unsafe_lanes, (),
                make_references(unsafe_documents),
            )

        zero_decisions = {
            **decisions, "source_finding_count": 0, "decisions": [],
        }
        zero_raw = {**raw_findings, "findings": []}
        zero_documents = {
            "decisions": ("synthesis-decisions", zero_decisions),
            "raw_findings": ("raw-finding-inventory", zero_raw),
            "lane_receipts": ("lane-receipts", lane_receipts),
        }
        zero = export_finding_contributions(
            request, zero_decisions, zero_raw, lane_receipts, (),
            make_references(zero_documents),
        )
        self.assertEqual([value["stage"] for value in zero], [
            "finding_contribution_coverage",
        ])
        require_complete_contribution_coverage(zero)
        with self.assertRaisesRegex(ValueError, "missing finding contribution coverage"):
            require_complete_contribution_coverage(())
        incomplete = copy.deepcopy(zero)
        incomplete[0]["coverage_complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete finding contribution coverage"):
            require_complete_contribution_coverage(incomplete)

    def test_credential_shaped_free_form_values_are_not_durable(self):
        receipt = self.contribution(0, provider="sk-secret-provider")
        payload = translate_review_receipts([receipt])[0].payload
        self.assertNotIn("sk-secret-provider", repr(payload))


if __name__ == "__main__":
    unittest.main()
