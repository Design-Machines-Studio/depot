import json
import unittest

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.ci_evidence import build_ci_evidence, evaluate_ci_gate, validate_ci_evidence


SHA = "a" * 40
NOW = "2026-07-22T13:00:00Z"


def raw(**changes):
    value = {
        "provider": "github", "adapter_version": "1", "mapping_version": "github-v1",
        "event_scope": "pull_request", "ref": "refs/pull/12/merge", "base_sha": "b" * 40,
        "pr_head_sha": SHA, "test_merge_sha": "c" * 40, "subject_sha": SHA,
        "subject_kind": "pr_head", "run_id": "100", "check_id": "101", "job_id": "102",
        "attempt": 1, "check_kind": "check_run", "context": "Test / unit",
        "app_identity": "github-actions", "raw_status": "completed", "raw_conclusion": "success",
        "started_at": "2026-07-22T12:58:00Z", "completed_at": "2026-07-22T12:59:00Z",
        "observed_at": NOW, "evidence_ref": "ci/run-100.json", "requirement_source": "branch-policy-v3",
        "satisfies_provider_merge_rule": True,
    }
    value.update(changes)
    return value


def requirement(**changes):
    value = {
        "provider": "github", "event_scope": "pull_request", "subject_kind": "pr_head",
        "subject_sha": SHA, "ref": "refs/pull/12/merge", "check_kind": "check_run",
        "context": "Test / unit", "app_identity": "github-actions",
        "allowed_conclusions": ["success"], "max_age_seconds": 600,
        "requirement_source": "branch-policy-v3",
    }
    value.update(changes)
    return value


class CIEvidenceTests(unittest.TestCase):
    def test_github_preserves_raw_and_distinguishes_accepted_conclusions(self):
        records = [build_ci_evidence(raw(raw_conclusion=item)) for item in ("success", "skipped", "neutral")]
        self.assertEqual(["success", "skipped", "neutral"], [item["normalized_conclusion"] for item in records])
        schema = json.loads((KERNEL_REFERENCES / "ci-evidence-schema.json").read_text())
        self.assertTrue(schema_matches(records[0], schema))
        gate = evaluate_ci_gate([requirement(allowed_conclusions=["success", "skipped", "neutral"])], records, now=NOW)
        self.assertEqual("passed", gate["status"])
        self.assertTrue(records[1]["satisfies_provider_merge_rule"])

    def test_incomplete_github_check_has_no_conclusion_and_filtered_lane_is_absent(self):
        with self.assertRaises(ValueError):
            build_ci_evidence(raw(raw_status="queued", raw_conclusion="success", completed_at=None))
        pending = build_ci_evidence(raw(raw_status="queued", raw_conclusion=None, completed_at=None))
        self.assertEqual("unresolved", evaluate_ci_gate([requirement()], [pending], now=NOW)["status"])
        missing = evaluate_ci_gate([requirement(context="workflow-filtered")], [pending], now=NOW)
        self.assertEqual("required_lane_absent", missing["checks"][0]["reason"])

    def test_failure_family_wrong_app_scope_subject_and_staleness_do_not_pass(self):
        for conclusion in ("failure", "cancelled", "timed_out", "stale", "action_required"):
            with self.subTest(conclusion=conclusion):
                record = build_ci_evidence(raw(raw_conclusion=conclusion, satisfies_provider_merge_rule=False))
                self.assertEqual("failed", evaluate_ci_gate([requirement()], [record], now=NOW)["status"])
        record = build_ci_evidence(raw())
        for changed in (
            {"app_identity": "foreign-app"}, {"event_scope": "schedule"},
            {"subject_kind": "test_merge", "subject_sha": "c" * 40}, {"ref": "refs/heads/main"},
        ):
            self.assertEqual("unresolved", evaluate_ci_gate([requirement(**changed)], [record], now=NOW)["status"])
        stale = evaluate_ci_gate([requirement(max_age_seconds=1)], [record], now="2026-07-22T14:00:00Z")
        self.assertEqual("observation_stale", stale["checks"][0]["reason"])

    def test_test_merge_and_pr_head_are_not_interchangeable(self):
        merge = build_ci_evidence(raw(subject_kind="test_merge", subject_sha="c" * 40))
        self.assertEqual("unresolved", evaluate_ci_gate([requirement()], [merge], now=NOW)["status"])

    def test_blueprint_requires_explicit_mapping_and_subject_capability(self):
        blueprint = raw(provider="blueprint", mapping_version=None, raw_status="done", raw_conclusion="ok")
        opaque = build_ci_evidence(blueprint)
        self.assertFalse(opaque["mapping_authoritative"])
        req = requirement(provider="blueprint")
        self.assertEqual("unresolved", evaluate_ci_gate([req], [opaque], now=NOW)["status"])
        mapping = {"provider": "blueprint", "version": "1", "capabilities": ["subject_identity"],
                   "statuses": {"done": "completed"}, "conclusions": {"ok": "success"}}
        mapped = build_ci_evidence(blueprint, mapping=mapping)
        self.assertEqual("passed", evaluate_ci_gate([req], [mapped], now=NOW)["status"])

    def test_provider_merge_rule_fact_does_not_upgrade_failed_test(self):
        record = build_ci_evidence(raw(raw_conclusion="failure", satisfies_provider_merge_rule=True))
        self.assertEqual("failed", evaluate_ci_gate([requirement()], [record], now=NOW)["status"])

    def test_policy_cannot_admit_terminal_failure_as_success(self):
        record = build_ci_evidence(raw(raw_conclusion="failure", satisfies_provider_merge_rule=True))
        gate = evaluate_ci_gate([requirement(allowed_conclusions=["failure"])], [record], now=NOW)
        self.assertEqual("failed", gate["status"])
        self.assertEqual("terminal_conclusion_is_not_success", gate["checks"][0]["reason"])

    def test_subject_and_lifecycle_bindings_reject_contradictory_records(self):
        with self.assertRaises(ValueError):
            build_ci_evidence(raw(subject_sha="d" * 40))
        record = build_ci_evidence(raw())
        record["completed_at"] = None
        with self.assertRaises(ValueError):
            validate_ci_evidence(record)

    def test_latest_observation_uses_instant_not_timestamp_lexicography(self):
        older = build_ci_evidence(raw(observed_at="2026-07-22T14:00:00+02:00", raw_conclusion="failure"))
        newer = build_ci_evidence(raw(observed_at="2026-07-22T12:30:00Z", raw_conclusion="success", check_id="new"))
        gate = evaluate_ci_gate([requirement()], [older, newer], now="2026-07-22T12:31:00Z")
        self.assertEqual("passed", gate["status"])


if __name__ == "__main__":
    unittest.main()
