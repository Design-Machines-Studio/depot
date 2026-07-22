import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from workflow_kernel.events import EventStore
from workflow_kernel.review_records import (
    build_finding_record, build_lane_record, canonical_finding_id,
    capture_review_boundary, compare_review_boundary, persist_review_record,
    project_review_markdown, project_todo_rows, validate_finding_record,
    validate_lane_record,
)
from workflow_kernel.state import RunLease


class ReviewFindingTests(unittest.TestCase):
    def finding(self, **changes):
        value = {
            "run_id": "review-1", "source_finding_id": "security.finding-1",
            "rule_id": "authz.boundary", "category": "Authorization Boundary",
            "severity": "P1", "path": "internal/auth/handler.go",
            "anchor": "HandleAdmin", "root_cause": "Caller role is not checked",
            "observed_evidence": "A member request reaches the admin mutation.",
            "proposed_fix": "Require the administrator capability before mutation.",
            "evidence_refs": ["evidence/auth-test.txt"],
            "raw_ref": "raw/security.md#finding-1", "source_agents": ["security-auditor"],
            "requested_provider": "openai", "attempted_provider": "openai",
            "implemented_by": "codex", "model": "gpt-5.6-sol", "attempt": 1,
            "agreement": "unique", "finding_disposition": "retained",
            "decision_reason_code": "retained-unique",
            "build_binding_ref": "bindings/build.json",
            "browser_bundle_refs": ["browser/admin.json"],
        }
        value.update(changes)
        return build_finding_record(**value)

    def lane(self, **changes):
        value = {
            "run_id": "review-1", "lane_id": "security", "state": "completed",
            "expected_coverage": ["authz", "input-validation"], "missing_case_ids": [],
            "partial_output": False, "output_ref": "raw/security.md",
            "source_agents": ["security-auditor"], "requested_provider": "openai",
            "attempted_provider": "openai", "implemented_by": "codex",
            "model": "gpt-5.6-sol", "attempt": 1, "coverage_gap_reason": None,
            "build_binding_ref": "bindings/build.json", "browser_bundle_refs": [],
        }
        value.update(changes)
        return build_lane_record(**value)

    def test_identity_is_order_independent_and_excludes_reviewer_provenance(self):
        first = self.finding()
        second = self.finding(source_agents=["architecture-reviewer"], model="other")
        self.assertEqual(first["canonical_finding_id"], second["canonical_finding_id"])
        self.assertEqual(first["canonical_finding_id"], canonical_finding_id(
            "internal/auth/handler.go", " HandleAdmin ",
            "authorization   boundary", "caller role is not checked",
        ))

    def test_records_are_strict_bounded_and_secret_safe(self):
        for mutation in (
            {"path": "../secret"}, {"evidence_refs": ["/private/evidence"]},
            {"observed_evidence": "sk-" + "x" * 40},
            {"source_agents": ["bad/agent"]}, {"severity": "critical"},
            {"observed_evidence": "x" * 4097},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.finding(**mutation)
        extra = self.finding(); extra["authority"] = True
        with self.assertRaises(ValueError):
            validate_finding_record(extra)
        with self.assertRaises(ValueError):
            self.lane(state="degraded", missing_case_ids=["persona-admin"],
                      partial_output=True, output_ref=None,
                      coverage_gap_reason="browser unavailable")

    def test_immutable_persistence_is_idempotent_and_survives_lane_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = EventStore(root / "state")
            finding = self.finding()
            with RunLease(store.state_path) as lease:
                first = persist_review_record(
                    finding, root / "artifacts", store, lease, 0,
                    run_id="review-1", occurred_at="2026-07-14T00:00:00Z",
                )
                second = persist_review_record(
                    finding, root / "artifacts", store, lease, 1,
                    run_id="review-1", occurred_at="2026-07-14T00:01:00Z",
                )
            self.assertEqual(first, second)
            self.assertEqual(len(store.replay()), 1)
            self.assertEqual(json.loads((root / "artifacts" / first["record_ref"]).read_text()), finding)
            self.assertEqual(store.replay()[0].payload["record_digest"], finding["record_digest"])
            # No lane record was written: the already-committed finding remains authoritative.
            self.assertFalse((root / "artifacts" / "records" / "lanes").exists())
            conflict = self.finding(category="Authentication Boundary")
            with RunLease(store.state_path) as lease, self.assertRaises(ValueError):
                persist_review_record(conflict, root / "artifacts", store, lease, 1,
                                      run_id="review-1", occurred_at="2026-07-14T00:02:00Z")

    def test_lane_partial_output_and_deterministic_views_preserve_evidence(self):
        finding = self.finding()
        lane = self.lane(state="degraded", missing_case_ids=["persona-admin"],
                         partial_output=True, output_ref="raw/security-partial.md",
                         coverage_gap_reason="browser unavailable")
        self.assertEqual(validate_lane_record(lane)["missing_case_ids"], ["persona-admin"])
        report = project_review_markdown([finding], [lane])
        self.assertEqual(report, project_review_markdown([copy.deepcopy(finding)], [copy.deepcopy(lane)]))
        row = project_todo_rows([finding])[0]
        row["problem"] = "edited projection"
        self.assertEqual(validate_finding_record(finding)["observed_evidence"],
                         "A member request reaches the admin mutation.")

    def test_read_only_boundary_allows_owned_artifacts_and_detects_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(("git", "init", "-q"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.email", "review@example.test"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.name", "Review Test"), cwd=root, check=True)
            product = root / "product.txt"; product.write_text("base\n")
            subprocess.run(("git", "add", "product.txt"), cwd=root, check=True)
            subprocess.run(("git", "commit", "-qm", "base"), cwd=root, check=True)
            artifacts = root / ".claude" / "ux-review"
            before = capture_review_boundary(root, artifacts)
            artifacts.mkdir(parents=True); (artifacts / "report.md").write_text("evidence\n")
            self.assertTrue(compare_review_boundary(before, capture_review_boundary(root, artifacts))["read_only"])

            product.write_text("changed\n")
            changed = compare_review_boundary(before, capture_review_boundary(root, artifacts))
            self.assertIn("product_status_digest", changed["changed"])
            subprocess.run(("git", "add", "product.txt"), cwd=root, check=True)
            staged = compare_review_boundary(before, capture_review_boundary(root, artifacts))
            self.assertIn("index_digest", staged["changed"])
            subprocess.run(("git", "commit", "-qm", "mutation"), cwd=root, check=True)
            committed = compare_review_boundary(before, capture_review_boundary(root, artifacts))
            self.assertIn("head", committed["changed"])
            clean = capture_review_boundary(root, artifacts)
            subprocess.run(("git", "branch", "review-mutated-ref"), cwd=root, check=True)
            self.assertIn("refs_digest", compare_review_boundary(clean, capture_review_boundary(root, artifacts))["changed"])
            provider_before = capture_review_boundary(root, artifacts, ["receipts/provider-before.json"])
            provider_after = capture_review_boundary(root, artifacts, ["receipts/provider-after.json"])
            self.assertIn("provider_receipts_digest", compare_review_boundary(provider_before, provider_after)["changed"])
            (root / "todos").mkdir(); (root / "todos" / "001-pending-p1.md").write_text("mutation\n")
            self.assertIn("product_status_digest", compare_review_boundary(clean, capture_review_boundary(root, artifacts))["changed"])

    def test_plain_review_prose_is_read_only_and_fix_paths_own_mutation(self):
        root = Path(__file__).parents[1]
        review = (root / "plugins/dm-review/skills/review/SKILL.md").read_text()
        proposal_phases = review.split("### Phase 5.5:", 1)[1].split("## Ecosystem Integration", 1)[0]
        external_phase = review.split("### Phase 7:", 1)[1].split("### Phase 8:", 1)[0]
        for forbidden in (
            "Apply simplification edits directly", "git add --", "gh issue create",
            "rm -- todos/", "Create todo files",
        ):
            self.assertNotIn(forbidden, proposal_phases)
        self.assertNotIn("notion-create-pages", external_phase)
        self.assertIn("Mechanical Read-only Boundary", review)
        self.assertIn("Simplification Proposals", review)
        self.assertIn("Tracking Proposals", review)
        for command in ("dm-review-fix.md", "dm-review-loop.md"):
            text = (root / "plugins/dm-review/commands" / command).read_text()
            self.assertIn("Explicit Mutation Authority", text)
            self.assertIn("simplification", text.lower())
            self.assertIn("tracking", text.lower())


if __name__ == "__main__":
    unittest.main()
