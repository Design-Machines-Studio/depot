import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import workflow_kernel.review_records as review_records
from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.events import EventStore
from workflow_kernel.review_records import (
    build_finding_record, build_lane_record, canonical_finding_id,
    capture_review_boundary, compare_review_boundary, consolidate_findings,
    persist_review_record, project_review_markdown, project_todo_rows,
    source_scope_digest, validate_finding_record,
    validate_lane_record,
)
from workflow_kernel.state import RunLease


class ReviewFindingTests(unittest.TestCase):
    def finding(self, **changes):
        value = {
            "run_id": "review-1", "source_finding_id": "security.finding-1",
            "lane_id": "security", "cross_id_links": [],
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
            "finding_refs": ["records/findings/sha256-a.json"],
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
        schemas = {
            "review-finding-record-schema.json": self.finding(),
            "review-lane-record-schema.json": self.lane(),
        }
        for name, record in schemas.items():
            with self.subTest(schema=name):
                schema = json.loads((KERNEL_REFERENCES / name).read_text())
                self.assertTrue(schema_matches(record, schema))

    def test_immutable_persistence_is_idempotent_and_survives_lane_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = EventStore(root / "state")
            finding = self.finding()
            artifacts = store.root / "artifacts"
            with RunLease(store.state_path) as lease:
                first = persist_review_record(
                    finding, artifacts, store, lease, 0,
                    run_id="review-1", occurred_at="2026-07-14T00:00:00Z",
                )
                second = persist_review_record(
                    finding, artifacts, store, lease, 1,
                    run_id="review-1", occurred_at="2026-07-14T00:01:00Z",
                )
            self.assertEqual(first, second)
            self.assertEqual(len(store.replay()), 1)
            self.assertEqual(json.loads((artifacts / first["record_ref"]).read_text()), finding)
            self.assertEqual(store.replay()[0].payload["record_digest"], finding["record_digest"])
            # No lane record was written: the already-committed finding remains authoritative.
            self.assertFalse((artifacts / "records" / "lanes").exists())
            conflict = self.finding(category="Authentication Boundary")
            with RunLease(store.state_path) as lease, self.assertRaises(ValueError):
                persist_review_record(conflict, artifacts, store, lease, 1,
                                      run_id="review-1", occurred_at="2026-07-14T00:02:00Z")

            # The same local ID from a different lane/raw/provider attempt is distinct.
            other_scope = self.finding(
                lane_id="architecture", raw_ref="raw/architecture.md#finding-1",
                source_agents=["architecture-reviewer"], category="Authentication Boundary",
            )
            self.assertNotEqual(source_scope_digest(finding), source_scope_digest(other_scope))
            with RunLease(store.state_path) as lease:
                persist_review_record(other_scope, artifacts, store, lease, 1,
                                      run_id="review-1", occurred_at="2026-07-14T00:03:00Z")
            self.assertEqual(len(store.replay()), 2)

    def test_artifact_root_is_bound_to_event_store_and_parent_is_fsynced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); store = EventStore(root / "state")
            outside = root / "outside"; outside.mkdir()
            with RunLease(store.state_path) as lease, self.assertRaises(ValueError):
                persist_review_record(self.finding(), outside, store, lease, 0,
                                      run_id="review-1", occurred_at="2026-07-14T00:00:00Z")
            link = store.root / "linked-artifacts"; link.symlink_to(outside, target_is_directory=True)
            with RunLease(store.state_path) as lease, self.assertRaises(ValueError):
                persist_review_record(self.finding(), link, store, lease, 0,
                                      run_id="review-1", occurred_at="2026-07-14T00:00:00Z")
            original_bind = review_records.bind_durable_path
            swapped = store.root / "swapped-artifacts" / "records" / "findings"
            displaced = store.root / "displaced-findings"
            did_swap = False

            def swap_before_binding(path):
                nonlocal did_swap
                if not did_swap and Path(path).name.startswith("sha256-"):
                    did_swap = True
                    swapped.rename(displaced)
                    swapped.symlink_to(outside, target_is_directory=True)
                return original_bind(path)

            with mock.patch(
                    "workflow_kernel.review_records.bind_durable_path",
                    side_effect=swap_before_binding), \
                    RunLease(store.state_path) as lease, self.assertRaises(ValueError):
                persist_review_record(
                    self.finding(), store.root / "swapped-artifacts", store,
                    lease, 0, run_id="review-1",
                    occurred_at="2026-07-14T00:00:00Z",
                )
            swapped.unlink()
            displaced.rename(swapped)
            real_fsync = os.fsync; calls = []
            def observed_fsync(descriptor):
                calls.append(descriptor); return real_fsync(descriptor)
            with mock.patch("workflow_kernel.review_records.os.fsync", side_effect=observed_fsync), \
                    RunLease(store.state_path) as lease:
                persist_review_record(self.finding(), store.root / "artifacts", store, lease, 0,
                                      run_id="review-1", occurred_at="2026-07-14T00:00:00Z")
            self.assertGreaterEqual(len(calls), 2)

            nested = store.root / "nested" / "review-artifacts"
            synced_parents = []
            real_sync_directory = review_records._fsync_directory
            def observed_directory_sync(path):
                synced_parents.append(Path(path))
                return real_sync_directory(path)
            with mock.patch(
                    "workflow_kernel.review_records._fsync_directory",
                    side_effect=observed_directory_sync), RunLease(store.state_path) as lease:
                persist_review_record(self.finding(attempt=2), nested, store, lease, 1,
                                      run_id="review-1", occurred_at="2026-07-14T00:01:00Z")
            self.assertEqual(synced_parents, [
                store.root, store.root / "nested", nested,
                nested / "records",
            ])

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

    def test_canonical_projection_groups_sources_and_preserves_disputes_and_lane_refs(self):
        first = self.finding()
        second = self.finding(
            lane_id="architecture", raw_ref="raw/architecture.md#finding-1",
            source_agents=["architecture-reviewer"], severity="P2",
            attempted_provider="openrouter", model="z-ai/glm-5.2", attempt=2,
            agreement="corroborated", decision_reason_code="retained-corroborated",
        )
        lane = self.lane(finding_refs=[
            "records/findings/sha256-a.json", "records/findings/sha256-b.json",
        ])
        architecture_lane = self.lane(
            lane_id="architecture", source_agents=["architecture-reviewer"],
            output_ref="raw/architecture.md",
            finding_refs=["records/findings/sha256-b.json"],
        )
        canonical = consolidate_findings([second, first], [lane, architecture_lane])
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]["severity"], "P1")
        self.assertTrue(canonical[0]["severity_disputed"])
        self.assertEqual(len(canonical[0]["sources"]), 2)
        self.assertEqual(project_review_markdown(
            [first, second], [lane, architecture_lane],
        ).count("### ["), 1)
        row = project_todo_rows([second, first], [lane, architecture_lane])[0]
        self.assertEqual(len(row["source_record_digests"]), 2)
        self.assertEqual(row["source_record_digests"], sorted(row["source_record_digests"]))
        self.assertTrue(all(source["lane_finding_refs"] for source in canonical[0]["sources"]))

        other_id = canonical_finding_id(first["path"], first["anchor"],
                                        first["category"], "Different root cause")
        linked_first = self.finding(cross_id_links=[other_id], agreement="disputed",
                                    decision_reason_code="retained-disagreement")
        linked_other = self.finding(
            source_finding_id="security.finding-2", root_cause="Different root cause",
            canonical_finding_id=other_id, cross_id_links=[first["canonical_finding_id"]],
            agreement="disputed", decision_reason_code="retained-disagreement",
        )
        disputed = consolidate_findings([linked_other, linked_first])
        self.assertEqual([item["agreement"] for item in disputed], ["disputed", "disputed"])
        conflicting_scope = self.finding(severity="P2")
        with self.assertRaises(ValueError):
            consolidate_findings([first, conflicting_scope])

    def test_canonical_authority_excludes_discarded_and_retry_pseudocorroboration(self):
        retained = self.finding(severity="P2")
        retry = self.finding(
            severity="P2", attempt=2, attempted_provider="openrouter",
            model="z-ai/glm-5.2", raw_ref="raw/security-retry.md#finding-1",
            finding_disposition="merged",
            decision_reason_code="exact-duplicate",
        )
        discarded = self.finding(
            severity="P1", attempt=3, attempted_provider="deepseek",
            model="deepseek/v4", finding_disposition="discarded",
            decision_reason_code="not-reproducible", agreement="disputed",
        )
        canonical = consolidate_findings([discarded, retry, retained])[0]
        self.assertEqual(canonical["severity"], "P2")
        self.assertEqual(canonical["source_severities"], ["P2"])
        self.assertFalse(canonical["severity_disputed"])
        self.assertEqual(canonical["agreement"], "unique")
        self.assertEqual(len(canonical["sources"]), 3)
        self.assertIn("discarded", {
            source["finding_disposition"] for source in canonical["sources"]
        })
        independent = self.finding(
            severity="P3", lane_id="architecture",
            raw_ref="raw/architecture.md#finding-1",
            source_agents=["architecture-reviewer"],
        )
        corroborated = consolidate_findings([discarded, retry, retained, independent])[0]
        self.assertEqual(corroborated["agreement"], "corroborated")
        self.assertEqual(corroborated["source_severities"], ["P2", "P3"])

    def test_lane_missing_and_unknown_states_preserve_finding_references(self):
        for state in ("missing", "unknown"):
            lane = self.lane(state=state, partial_output=False, output_ref=None,
                             missing_case_ids=["case-a"],
                             coverage_gap_reason="lane produced no terminal evidence")
            self.assertEqual(validate_lane_record(lane)["finding_refs"],
                             ["records/findings/sha256-a.json"])

    def test_read_only_boundary_allows_owned_artifacts_and_detects_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(("git", "init", "-q"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.email", "review@example.test"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.name", "Review Test"), cwd=root, check=True)
            product = root / "product.txt"; product.write_text("base\n")
            subprocess.run(("git", "add", "product.txt"), cwd=root, check=True)
            subprocess.run(("git", "commit", "-qm", "base"), cwd=root, check=True)
            subprocess.run((
                "git", "remote", "add", "origin",
                "git@github.com:design-machines/review-test.git",
            ), cwd=root, check=True)
            artifacts = root / ".claude" / "ux-review"
            inventories = {name: [[]] for name, _suffix in review_records._GITHUB_INVENTORIES}
            calls = []
            def observed_gh(argv, cwd, **bounds):
                calls.append((tuple(argv), Path(cwd), bounds))
                endpoint = argv[4]
                name = next(name for name, suffix in review_records._GITHUB_INVENTORIES
                            if endpoint.endswith(suffix))
                return json.dumps(inventories[name]).encode()
            def boundary():
                return capture_review_boundary(root, artifacts)

            with mock.patch(
                    "workflow_kernel.review_records._run_bounded",
                    side_effect=observed_gh):
                before = boundary()
                artifacts.mkdir(parents=True)
                (artifacts / "report.md").write_text("evidence\n")
                self.assertTrue(compare_review_boundary(before, boundary())["read_only"])
                self.assertTrue(all(call[1] == root.resolve() for call in calls))
                self.assertTrue(all(call[2] == {
                    "timeout": 30.0, "output_limit": 8 * 1024 * 1024,
                } for call in calls))
                expected_endpoints = {
                    f"repos/design-machines/review-test/{suffix}"
                    for _name, suffix in review_records._GITHUB_INVENTORIES
                }
                self.assertEqual({call[0][4] for call in calls}, expected_endpoints)
                for argv, _cwd, _bounds in calls:
                    self.assertEqual(argv[:4], ("gh", "api", "--method", "GET"))
                    self.assertEqual(argv[5:7], ("--paginate", "--slurp"))

                product.write_text("changed\n")
                changed = compare_review_boundary(before, boundary())
                self.assertIn("product_status_digest", changed["changed"])
                subprocess.run(("git", "add", "product.txt"), cwd=root, check=True)
                staged = compare_review_boundary(before, boundary())
                self.assertIn("index_digest", staged["changed"])
                subprocess.run(("git", "commit", "-qm", "mutation"), cwd=root, check=True)
                committed = compare_review_boundary(before, boundary())
                self.assertIn("head", committed["changed"])
                clean = boundary()
                subprocess.run(("git", "branch", "review-mutated-ref"), cwd=root, check=True)
                self.assertIn("refs_digest", compare_review_boundary(clean, boundary())["changed"])

                inventories["issues"] = [[{"id": 1, "title": "provider mutation"}]]
                provider_change = compare_review_boundary(clean, boundary())
                self.assertIn("provider_receipts_digest", provider_change["changed"])
                inventories["issues"] = [[]]
                (root / "todos").mkdir()
                (root / "todos" / "001-pending-p1.md").write_text("mutation\n")
                self.assertIn("product_status_digest",
                              compare_review_boundary(clean, boundary())["changed"])

                product.write_text("dirty-one\n")
                dirty_before = boundary()
                product.write_text("dirty-two\n")
                dirty_change = compare_review_boundary(dirty_before, boundary())
                self.assertNotIn("product_status_digest", dirty_change["changed"])
                self.assertIn("product_content_digest", dirty_change["changed"])
                untracked = root / "untracked.txt"; untracked.write_text("one\n")
                untracked_before = boundary()
                untracked.write_text("two\n")
                self.assertIn("product_content_digest", compare_review_boundary(
                    untracked_before, boundary(),
                )["changed"])

            with self.assertRaises(TypeError):
                capture_review_boundary(
                    root, artifacts, provider_snapshot_ref="self-attested.json",
                )

            inventories["issues"] = [[{}], [{}]]
            with mock.patch(
                    "workflow_kernel.review_records._run_bounded",
                    side_effect=observed_gh):
                incomplete = boundary()
            incomplete_result = compare_review_boundary(incomplete, incomplete)
            self.assertFalse(incomplete_result["read_only"])
            self.assertIn("provider_state_incomplete",
                          incomplete_result["provider_state_reasons"])

            with mock.patch(
                    "workflow_kernel.review_records._run_bounded",
                    return_value=b"["):
                malformed = boundary()
            malformed_result = compare_review_boundary(malformed, malformed)
            self.assertFalse(malformed_result["read_only"])
            self.assertIn("provider_state_incomplete",
                          malformed_result["provider_state_reasons"])

            with mock.patch(
                    "workflow_kernel.review_records._run_bounded",
                    side_effect=review_records._ProviderIncomplete):
                unbounded = boundary()
            unbounded_result = compare_review_boundary(unbounded, unbounded)
            self.assertFalse(unbounded_result["read_only"])
            self.assertIn("provider_state_incomplete",
                          unbounded_result["provider_state_reasons"])

            with mock.patch(
                    "workflow_kernel.review_records._run_bounded",
                    side_effect=review_records._ProviderUnavailable):
                unavailable = boundary()
            unavailable_result = compare_review_boundary(unavailable, unavailable)
            self.assertFalse(unavailable_result["read_only"])
            self.assertIn("provider_state_unavailable",
                          unavailable_result["provider_state_reasons"])

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
