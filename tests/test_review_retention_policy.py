"""Required closure, diagnostic separation and advisory projection boundaries."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import unittest
from tests import test_review_closeout as fixture
from tests import KERNEL_REFERENCES
from workflow_kernel import owned_run, review_closeout


class ReviewRetentionPolicyTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve
    def project(self, run, paths):
        return review_closeout.preserve_review_evidence(
            run_root=run.root, repository_root=self.repo,
            request_path=paths["request"], receipts_path=paths["receipts"],
            lane_receipts_path=paths["lane_receipts"], raw_lane_outputs_path=paths["raw_lane_outputs"],
            raw_findings_path=paths["raw_findings"], decisions_path=paths["decisions"],
            private_router_directory=paths["router"], report_path=paths["report"], projection_only=True)

    @staticmethod
    def bytes(root):
        return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    def test_projection_copies_all_report_links_and_never_writes(self):
        run, paths = self.make_run(run_id="project-all-links")
        linked = run.root / "review/final-proof.txt"
        linked.write_text("Actual final verification output.\n")
        paths["report"].write_text("# Review\n[Final proof](review/final-proof.txt)\n")
        before = self.bytes(run.root)
        directories = set(run.root.rglob("*"))
        projection = self.project(run, paths)
        self.assertFalse(projection["coverage_proof"])
        self.assertTrue(projection["within_limits"])
        self.assertEqual(before, self.bytes(run.root))
        self.assertEqual(directories, set(run.root.rglob("*")))
        preserved = self.preserve(run, paths)
        self.assertEqual((projection["files"], projection["bytes"]), (preserved["files"], preserved["bytes"]))
        scope = Path(preserved["evidence_path"])
        self.assertEqual(linked.read_bytes(), (scope / "review/final-proof.txt").read_bytes())
        validation = review_closeout.validate_preserved_review_evidence(run.root / "diagnostic", run=owned_run.ExactOwnedRun.open(run.root))
        self.assertEqual(projection["retention"], validation["retention"])
        run.finish("succeeded", retain_diagnostics=True)

    def test_projection_never_authorizes_changed_bound_inputs(self):
        run, paths = self.make_run(run_id="projection-stale")
        self.assertTrue(self.project(run, paths)["within_limits"])
        record = json.loads((run.root / paths["record_ref"]).read_text())
        ref = next(iter(record["bindings"].values()))["retained_ref"]
        (run.root / ref).write_text("Changed after size projection.\n")
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_projection_cli_and_growth_at_actual_copy_boundary(self):
        run, paths = self.make_run(run_id="cli-copy-growth")
        args = [sys.executable, "-m", "workflow_kernel", "project-review-evidence",
                "--run-root", str(run.root), "--repository-root", str(self.repo)]
        for flag, key in (("request", "request"), ("receipts", "receipts"),
                          ("lane-receipts", "lane_receipts"), ("raw-lane-outputs", "raw_lane_outputs"),
                          ("raw-findings", "raw_findings"), ("decisions", "decisions"),
                          ("private-router-directory", "router"), ("report", "report")):
            args.extend(("--" + flag, str(paths[key])))
        before = self.bytes(run.root)
        env = dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES))
        result = subprocess.run(args, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)["coverage_proof"])
        self.assertEqual(before, self.bytes(run.root))
        project = review_closeout._project_preservation

        def grow(*args, **kwargs):
            projection = project(*args, **kwargs)
            paths["report"].write_bytes(b"Required final conclusions.\n" +
                                      b"x" * (owned_run._MAX_REQUIRED_REVIEW_BYTES - 1024))
            return projection

        with mock.patch.object(review_closeout, "_project_preservation", side_effect=grow):
            with self.assertRaises(review_closeout.EvidenceAssemblyError) as caught:
                self.preserve(run, paths)
        self.assertEqual("retention_limit", caught.exception.reason)
        self.assertGreater(caught.exception.measurement["actual_bytes"],
                           caught.exception.measurement["allowed_bytes"])
        self.assertFalse(list((run.root / "diagnostic/review").glob("review-stage-*")))
        self.assertFalse((run.root / "CLEANUP.txt").exists())

    def test_complete_required_evidence_exceeds_diagnostics_and_finishes(self):
        run, paths = self.make_run(run_id="separate-required")
        paths["report"].write_bytes(b"Required case conclusions.\n" * 400000)
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertGreater(result["bytes"], owned_run._MAX_DIAGNOSTIC_BYTES)
        with self.assertRaises(owned_run.BoundedDiagnosticLimitError):
            owned_run._bounded_diagnostic(run.root / "diagnostic")
        first = run.finish("succeeded", retain_diagnostics=True)
        before = self.bytes(run.root)
        self.assertEqual(first.to_dict(), run.finish("succeeded").to_dict())
        self.assertEqual(before, self.bytes(run.root))

    def test_unreferenced_files_cannot_borrow_required_allowance(self):
        run, paths = self.make_run(run_id="unrelated-large")
        self.preserve(run, paths)
        unrelated = run.root / "diagnostic/review/looks-required.bin"
        unrelated.write_bytes(b"x" * (owned_run._MAX_DIAGNOSTIC_BYTES + 1))
        with self.assertRaises(review_closeout.RetainedReviewValidationError) as caught:
            run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual("diagnostic", caught.exception.measurement["category"])
        self.assertTrue((run.root / "review").exists())
        self.assertFalse((run.root / "CLEANUP.txt").exists())

    def test_real_namespace_prevents_diagnostic_membership_collision(self):
        run, paths = self.make_run(run_id="namespace-collision")
        (run.root / "outside").mkdir()
        (run.root / "outside/archive.log").write_text("Required small archive.\n")
        paths["report"].write_text("# Review\n[Archive](outside/archive.log)\n")
        self.preserve(run, paths)
        (run.root / "diagnostic/archive.log").write_bytes(b"x" * (owned_run._MAX_DIAGNOSTIC_BYTES + 1))
        projection = self.project(run, paths)
        self.assertFalse(projection["within_limits"])
        self.assertEqual(owned_run._MAX_DIAGNOSTIC_BYTES + 1,
                         projection["retention"]["diagnostic"]["actual_bytes"])
        with self.assertRaises(review_closeout.RetainedReviewValidationError) as caught:
            run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual("diagnostic", caught.exception.measurement["category"])
        self.assertTrue((run.root / "review").exists())

    def test_projection_counts_unrelated_diagnostics_beneath_review(self):
        run, paths = self.make_run(run_id="nested-diagnostics")
        self.preserve(run, paths)
        extra = run.root / "diagnostic/review/logs/extra.log"
        extra.parent.mkdir()
        extra.write_bytes(b"x" * (owned_run._MAX_DIAGNOSTIC_BYTES + 1))
        self.assertFalse(self.project(run, paths)["within_limits"])
        with self.assertRaises(review_closeout.EvidenceAssemblyError):
            self.preserve(run, paths)
        extra.write_text("Small unrelated diagnostic.\n")
        result = self.preserve(run, paths)
        validation = review_closeout.validate_preserved_review_evidence(
            run.root / "diagnostic", run=owned_run.ExactOwnedRun.open(run.root))
        self.assertEqual(1, validation["retention"]["diagnostic"]["actual_files"])
        self.assertEqual("complete", result["status"])
        self.assertTrue(extra.exists())
        first = run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(first.to_dict(), run.finish("succeeded").to_dict())
        self.assertTrue(extra.exists())

    @mock.patch.object(owned_run, "_MAX_REQUIRED_REVIEW_BYTES", 32 * 1024 * 1024)
    @mock.patch.object(review_closeout, "_MAX_REQUIRED_REVIEW_BYTES", 32 * 1024 * 1024)
    def test_router_copy_accepts_both_finite_allowances(self):
        run, paths = self.make_run(run_id="router-separated")
        indexed = paths["router"] / "security.json"
        value = json.loads(indexed.read_text())
        value["bounded_detail"] = "x" * (26 * 1024 * 1024)
        indexed.write_text(json.dumps(value) + "\n")
        extra = paths["router"] / "extra.json"
        extra.write_text(json.dumps({"diagnostic": "x" * (8 * 1024 * 1024)}) + "\n")
        projection = self.project(run, paths)
        self.assertTrue(projection["within_limits"])
        self.assertGreater(projection["bytes"], owned_run._MAX_REQUIRED_REVIEW_BYTES)
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        run.finish("succeeded", retain_diagnostics=True)

    def test_report_linked_router_files_use_complete_required_partition(self):
        run, paths = self.make_run(run_id="router-report-links")
        original = paths["report"].read_text()
        linked = original
        for index in range(owned_run._MAX_DIAGNOSTIC_FILES + 1):
            ref = f"receipts/private/router/report-proof-{index}.json"
            (run.root / ref).write_text("{}\n")
            linked += f"[Proof]({ref})\n"
        paths["report"].write_text(linked)
        projection = self.project(run, paths)
        self.assertTrue(projection["within_limits"])
        self.assertEqual(0, projection["retention"]["diagnostic"]["actual_files"])
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        paths["report"].write_text(original)
        self.assertFalse(self.project(run, paths)["within_limits"])
        with self.assertRaises(review_closeout.EvidenceAssemblyError):
            self.preserve(run, paths)
        paths["report"].write_text(linked)
        first = run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(first.to_dict(), run.finish("succeeded").to_dict())

    def test_invalid_report_projection_has_no_required_membership(self):
        for kind in ("empty", "missing-link"):
            with self.subTest(kind=kind):
                run, paths = self.make_run(run_id="report-projection-" + kind)
                paths["report"].write_text("" if kind == "empty" else "# Review\n[Missing](review/missing.txt)\n")
                result = self.project(run, paths)
                self.assertTrue(result["missing"])
                self.assertEqual(0, result["retention"]["required_review"]["actual_files"])
                self.assertFalse(result["coverage_proof"])

    def test_unindexed_router_files_remain_diagnostic(self):
        run, paths = self.make_run(run_id="router-extra")
        for index in range(owned_run._MAX_DIAGNOSTIC_FILES + 1):
            (paths["router"] / f"unindexed-{index}.json").write_text("{}")
        before = self.bytes(run.root)
        projected = self.project(run, paths)
        self.assertFalse(projected["within_limits"])
        self.assertEqual(417, projected["retention"]["diagnostic"]["actual_files"])
        with self.assertRaises(review_closeout.EvidenceAssemblyError) as caught:
            self.preserve(run, paths)
        self.assertEqual("diagnostic", caught.exception.measurement["category"])
        self.assertEqual(before, self.bytes(run.root))

    def test_required_file_overflow_is_actionable_and_no_copy_occurs(self):
        run, paths = self.make_run(run_id="required-count-limit")
        for index in range(owned_run._MAX_REQUIRED_REVIEW_FILES + 1):
            ref = f"review/final-{index}.txt"
            (run.root / ref).write_text("Verified.\n")
            with paths["report"].open("a") as report:
                report.write(f"[Proof]({ref})\n")
        projection = self.project(run, paths)
        self.assertFalse(projection["within_limits"])
        before = self.bytes(run.root)
        with self.assertRaises(review_closeout.EvidenceAssemblyError) as caught:
            self.preserve(run, paths)
        self.assertEqual("required_review", caught.exception.measurement["category"])
        self.assertEqual(1024, caught.exception.measurement["allowed_files"])
        self.assertEqual(before, self.bytes(run.root))

    def test_interrupted_copy_preserves_sources_and_retries(self):
        run, paths = self.make_run(run_id="interrupted-stage")
        before = self.bytes(run.root)
        with mock.patch.object(review_closeout, "_copy_file", side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                self.preserve(run, paths)
        for ref, data in before.items():
            if ref.name != ".depot-owned-run.json":
                self.assertEqual(data, (run.root / ref).read_bytes())
        self.assertFalse(list((run.root / "diagnostic/review").glob("review-stage-*")))
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_large_review_history_preserves_and_revalidates_without_more_diagnostics(self):
        run, paths = self.make_run(run_id="large-history-1118")
        proof = run.root / "review/large-history.txt"
        # 48 MiB: above the observed 42,625,283-byte assembly and old ceiling.
        with proof.open("wb") as output:
            for _ in range(48):
                output.write(b"x" * (1024 * 1024))
        paths["report"].write_text("# Review\n[Required history](review/large-history.txt)\n")
        projection = self.project(run, paths)
        self.assertTrue(projection["within_limits"])
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertEqual(projection["bytes"], result["bytes"])
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        first = run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(first.to_dict(), run.finish("succeeded").to_dict())
        self.assertEqual(9 * 1024 * 1024, owned_run._MAX_DIAGNOSTIC_BYTES)
        self.assertEqual(1024, owned_run._MAX_REQUIRED_REVIEW_FILES)

    def test_required_byte_boundary_is_inclusive_and_overflow_is_actionable(self):
        limit = owned_run._MAX_REQUIRED_REVIEW_BYTES
        projection = owned_run._retention_projection({"proof": limit}, {"proof"})
        owned_run._require_retention_projection(projection)
        projection = owned_run._retention_projection({"proof": limit + 1}, {"proof"})
        with self.assertRaises(owned_run.BoundedDiagnosticLimitError) as caught:
            owned_run._require_retention_projection(projection)
        self.assertEqual("required_review", caught.exception.measurement["category"])
        self.assertEqual(limit, caught.exception.measurement["allowed_bytes"])
        self.assertEqual(limit + 1, caught.exception.measurement["actual_bytes"])
