import json
import unittest

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.closeout import evaluate_closeout


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


def expected(**changes):
    value = {
        "local_head_sha": SHA, "reviewed_sha": SHA, "delivered_sha": SHA, "pr_head_sha": SHA,
        "base_branch": "main", "default_branch": "main", "draft": False,
        "claimed_paths": ["pkg/a.go"], "required_evidence_ids": ["receipt", "screenshot"],
        "closing_issue_ids": ["12"], "affected_surface": "install",
        "affected_surface_mapping_provenance": "github-label-query-v1",
    }
    value.update(changes)
    return value


def observed(**changes):
    artifacts = [{
        "id": item, "path": "evidence/" + item + ".json", "expected_digest": DIGEST,
        "observed_digest": DIGEST, "exists": True, "classification": "committable",
        "binding_valid": True,
    } for item in ("receipt", "screenshot")]
    value = {
        "actual_pr_head_sha": SHA, "merge_commit_sha": "c" * 40, "actual_base_branch": "main",
        "actual_draft": False, "changed_paths": ["pkg/a.go"],
        "ci_gate": {"schema_version": 1, "status": "passed", "checks": [
            {"context": "Test / unit", "status": "passed", "reason": "declared_policy_satisfied"}
        ]}, "unresolved_findings": [],
        "issue_references": [{"issue_id": "12", "mention": True, "closing_intent": True,
                              "resolved_entity_kind": "issue", "provider_closing_link": True,
                              "actual_state": "closed", "auto_close_policy": "enabled"}],
        "artifacts": artifacts,
        "open_issue_inventory": {"available": True, "surface": "install",
                                 "mapping_provenance": "github-label-query-v1", "issue_ids": []},
    }
    value.update(changes)
    return value


def reason(audit, check_id):
    return next(item["reason"] for item in audit["checks"] if item["id"] == check_id)


class CloseoutTests(unittest.TestCase):
    def test_exact_clean_closeout_is_closing_and_deterministic(self):
        first = evaluate_closeout(expected(), observed())
        second = evaluate_closeout(expected(), observed())
        self.assertEqual("passed", first["status"])
        self.assertEqual("closing", first["disposition"])
        self.assertEqual(first["audit_digest"], second["audit_digest"])
        schema = json.loads((KERNEL_REFERENCES / "closeout-audit-schema.json").read_text())
        self.assertTrue(schema_matches(first, schema))

    def test_head_draft_scope_ci_and_findings_are_independent_checks(self):
        audit = evaluate_closeout(expected(), observed(
            actual_pr_head_sha="d" * 40, actual_draft=True, changed_paths=["pkg/other.go"],
            ci_gate={"schema_version": 1, "status": "unresolved", "checks": [
                {"context": "Test / unit", "status": "unresolved", "reason": "required_lane_absent"}
            ]}, unresolved_findings=["P2: remaining"],
        ))
        self.assertEqual("failed", audit["status"])
        self.assertEqual("head_identity_mismatch", reason(audit, "head_identity"))
        self.assertEqual("draft_mismatch", reason(audit, "draft_state"))
        self.assertEqual("claimed_changed_scope_mismatch", reason(audit, "changed_scope"))
        self.assertEqual("ci_not_authoritatively_passed", reason(audit, "required_ci"))
        self.assertEqual("unresolved_findings_remain", reason(audit, "unresolved_findings"))

    def test_synthetic_merge_sha_cannot_replace_pr_head(self):
        merge = "c" * 40
        audit = evaluate_closeout(expected(pr_head_sha=merge), observed(actual_pr_head_sha=SHA, merge_commit_sha=merge))
        self.assertEqual("synthetic_merge_sha_substituted", reason(audit, "pr_head_not_merge_commit"))

    def test_artifact_missing_tampered_private_and_stale_are_distinct(self):
        cases = (
            ({"exists": False}, "artifact_missing"),
            ({"observed_digest": "sha256:" + "d" * 64}, "artifact_digest_mismatch"),
            ({"classification": "private_receipt"}, "artifact_not_safely_classified"),
            ({"binding_valid": False}, "artifact_binding_stale"),
        )
        for change, expected_reason in cases:
            items = observed()["artifacts"]
            items[0].update(change)
            with self.subTest(expected_reason=expected_reason):
                audit = evaluate_closeout(expected(), observed(artifacts=items))
                self.assertEqual(expected_reason, reason(audit, "artifact:receipt"))
        audit = evaluate_closeout(expected(), observed(artifacts=[]))
        self.assertEqual("artifact_snapshot_missing", reason(audit, "artifact:receipt"))

    def test_issue_mention_resolution_link_state_and_policy_remain_separate(self):
        base = observed()["issue_references"][0]
        cases = (
            ({"closing_intent": False, "actual_state": "open"}, "plain_mention_is_not_closure"),
            ({"resolved_entity_kind": "pull_request", "actual_state": "open"}, "reference_not_resolved_issue"),
            ({"provider_closing_link": False, "actual_state": "open"}, "provider_closure_not_guaranteed"),
            ({"auto_close_policy": "unknown", "actual_state": "open"}, "provider_closure_not_guaranteed"),
        )
        for change, expected_reason in cases:
            item = dict(base); item.update(change)
            with self.subTest(expected_reason=expected_reason):
                audit = evaluate_closeout(expected(), observed(issue_references=[item]))
                self.assertEqual(expected_reason, reason(audit, "issue:12"))
        item = dict(base); item["actual_state"] = "open"
        audit = evaluate_closeout(expected(base_branch="release"), observed(issue_references=[item], actual_base_branch="release"))
        self.assertEqual("non_default_base_cannot_guarantee_closure", reason(audit, "issue:12"))

    def test_surface_inventory_is_distinct_and_fail_closed(self):
        unavailable = evaluate_closeout(expected(), observed(open_issue_inventory={
            "available": False, "surface": "install", "mapping_provenance": "", "issue_ids": []}))
        self.assertEqual("surface_inventory_unavailable", reason(unavailable, "affected_surface_inventory"))
        populated = evaluate_closeout(expected(), observed(open_issue_inventory={
            "available": True, "surface": "install", "mapping_provenance": "github-label-query-v1", "issue_ids": ["99"]}))
        self.assertEqual(["99"], populated["remaining_open_issues"])
        self.assertEqual("surface_open_issues_remain", reason(populated, "affected_surface_inventory"))

    def test_contradictory_ci_summary_cannot_claim_passed(self):
        audit = evaluate_closeout(expected(), observed(ci_gate={
            "schema_version": 1, "status": "passed", "checks": [
                {"context": "Test / unit", "status": "failed", "reason": "failure"}
            ]}))
        self.assertEqual("ci_not_authoritatively_passed", reason(audit, "required_ci"))

    def test_closed_issue_still_requires_reference_intent_and_provider_link(self):
        item = observed()["issue_references"][0]
        for change, expected_reason in (
            ({"mention": False}, "issue_not_textually_referenced"),
            ({"closing_intent": False}, "plain_mention_is_not_closure"),
            ({"provider_closing_link": False}, "provider_closure_not_guaranteed"),
        ):
            candidate = dict(item); candidate.update(change)
            with self.subTest(expected_reason=expected_reason):
                audit = evaluate_closeout(expected(), observed(issue_references=[candidate]))
                self.assertEqual(expected_reason, reason(audit, "issue:12"))

    def test_surface_inventory_mapping_provenance_is_exactly_bound(self):
        audit = evaluate_closeout(expected(), observed(open_issue_inventory={
            "available": True, "surface": "install", "mapping_provenance": "other-query", "issue_ids": []}))
        self.assertEqual("surface_inventory_scope_mismatch", reason(audit, "affected_surface_inventory"))

    def test_unsafe_artifact_paths_and_secret_shaped_strings_are_rejected(self):
        items = observed()["artifacts"]
        items[0]["path"] = "../outside.json"
        with self.assertRaises(ValueError):
            evaluate_closeout(expected(), observed(artifacts=items))
        with self.assertRaises(ValueError):
            evaluate_closeout(expected(affected_surface="token=super-secret-value"), observed())


if __name__ == "__main__":
    unittest.main()
