"""Required large-package mechanics; fixture inspection, never live review proof."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from tests import KERNEL_REFERENCES
from tests import test_review_closeout as fixture
from workflow_kernel import review_closeout
from workflow_kernel import owned_run
from workflow_kernel.owned_run import ExactOwnedRun, _bounded_diagnostic


class LargeReviewRetentionTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve

    def large_run(self, run_id):
        # Case declarations and their inspected results are both required lane
        # evidence. No unrelated files, whitespace padding or live participants.
        source = self.repo / "security-cases.jsonl"
        cases = [
            {"case_id": index, "path": f"fixtures/case-{index:05d}.json",
             "mode": "0600", "links": 1}
            for index in range(18000)
        ]
        declarations = "".join(json.dumps(case) + "\n" for case in cases)
        if not source.exists():
            source.write_text(declarations)
            subprocess.run(("git", "-C", str(self.repo), "add", source.name), check=True)
            subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "required fixture cases"), check=True)
        self.assertEqual(declarations, source.read_text())

        self.assertEqual(b"reviewed source\n", (self.repo / "source.txt").read_bytes())
        results = []
        for index, line in enumerate(source.read_text().splitlines()):
            case = json.loads(line)
            path = PurePosixPath(case["path"])
            safe = not path.is_absolute() and ".." not in path.parts
            owner_only = case["mode"] == "0600"
            single_link = case["links"] == 1
            self.assertEqual(index, case["case_id"])
            self.assertTrue(safe and owner_only and single_link)
            results.append({"case_id": index, "safe_relative_path": safe,
                            "owner_only_mode": owner_only, "single_link": single_link})
        self.assertEqual(len(cases), len(results))
        output = "".join(json.dumps(result) + "\n" for result in results).encode()
        # Each input fits the former per-read cap. Their sum needs the new
        # whole-package allowance, even before the seals and other companions.
        self.assertLess(source.stat().st_size, 2 * 1024 * 1024)
        self.assertLess(len(output), 2 * 1024 * 1024)
        self.assertGreater(source.stat().st_size + len(output), 2 * 1024 * 1024)
        run, paths = self.make_run(
            run_id=run_id, required_source_path=source.name, literal_output=output,
        )
        record = json.loads((run.root / paths["record_ref"]).read_text())
        self.assertIn("review/required-input.jsonl", record["input"]["requested"]["required_evidence_refs"])
        self.assertEqual(["source.txt", source.name], record["input"]["inspected"]["paths"])
        self.assertEqual("recovery", record["input"]["provenance"]["kind"])
        self.assertIsNone(record["input"]["provenance"]["executed_at"])
        self.assertTrue(record["input"]["inspected"]["limitations"])
        self.assertTrue(record["eligible"])
        paths["payload_ref"] = record["bindings"]["review/required-input.jsonl"]["retained_ref"]
        # Register recovery before measuring byte immutability; preservation is
        # allowed to register this directory in owner metadata on its first call.
        run.create_path("diagnostic", "diagnostic")
        return run, paths

    @staticmethod
    def snapshot(root):
        return {path.relative_to(root): path.read_bytes()
                for path in root.rglob("*") if path.is_file()}

    def test_coverage_reuses_source_seal_and_retries_without_rewriting(self):
        run, paths = self.make_run(run_id="source-reference-reuse")
        record = json.loads((run.root / paths["record_ref"]).read_text())
        reference = record["source_snapshot"]["snapshot_ref"]
        before = (run.root / reference).read_bytes()
        value = json.loads(paths["coverage_input"].read_text())
        value["pass_id"] = "source-reference-reuse"
        value["required_case_refs"] = [reference]
        input_path = run.root / "review/reuse-input.json"
        input_path.write_text(json.dumps(value) + "\n")
        kwargs = dict(run_root=run.root, repository_root=self.repo,
                      request_path=paths["request"], receipts_path=paths["receipts"],
                      input_path=input_path)
        first = review_closeout.assemble_review_evidence(**kwargs)
        snapshot = json.loads((run.root / first["snapshot_ref"]).read_text())
        self.assertEqual(reference, snapshot["bindings"][reference]["retained_ref"])
        self.assertEqual(before, (run.root / reference).read_bytes())
        committed = (run.root / first["snapshot_ref"]).read_bytes()
        again = review_closeout.assemble_review_evidence(**kwargs)
        self.assertTrue(again["reused"])
        self.assertEqual(committed, (run.root / first["snapshot_ref"]).read_bytes())
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_new_file_count_boundary_remains_bounded(self):
        directory = self.root / "count-boundary"
        directory.mkdir()
        for index in range(416):
            (directory / f"evidence-{index}.json").write_bytes(b"{}\n")
        self.assertEqual((416, 1248), _bounded_diagnostic(directory))
        original = self.snapshot(directory)
        (directory / "overflow.json").write_bytes(b"{}\n")
        with self.assertRaises(owned_run.BoundedDiagnosticLimitError):
            _bounded_diagnostic(directory)
        for path, data in original.items():
            self.assertEqual(data, (directory / path).read_bytes())

    def test_former_two_mib_bound_rejects_the_required_large_fixture(self):
        # Prove this fixture exercises the repaired aggregate limit: both
        # required files fit 2 MiB, but assembly could not commit their lane.
        with mock.patch.object(owned_run, "_MAX_REQUIRED_REVIEW_BYTES", 2 * 1024 * 1024), \
                mock.patch.object(review_closeout, "_MAX_REQUIRED_REVIEW_BYTES", 2 * 1024 * 1024):
            with self.assertRaises(review_closeout.EvidenceAssemblyError) as caught:
                self.large_run("former-bound")
        self.assertEqual("retention_limit", caught.exception.reason)
        self.assertEqual(3, caught.exception.exit_code)
        roots = list(self.state.iterdir())
        self.assertEqual(1, len(roots))
        self.assertEqual([], json.loads((roots[0] / "review/authoritative-receipts.json").read_text()))
        self.assertTrue((roots[0] / "review/required-input.jsonl").is_file())
        self.assertTrue((roots[0] / "raw/security.md").is_file())

    def test_required_large_package_assembles_preserves_and_revalidates(self):
        run, paths = self.large_run("required-large")
        source_bytes = self.snapshot(run.root)
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"], result)
        evidence = Path(result["evidence_path"])
        files, size = _bounded_diagnostic(run.root / "diagnostic")
        self.assertEqual((result["files"], result["bytes"]), (files, size))
        self.assertLessEqual(files, 128)
        self.assertGreater(size, 2 * 1024 * 1024)
        self.assertLess(size, 4 * 1024 * 1024)
        for relative, data in source_bytes.items():
            self.assertEqual(data, (run.root / relative).read_bytes())
        record = json.loads((evidence / paths["record_ref"]).read_text())
        for binding in record["bindings"].values():
            retained = (evidence / binding["retained_ref"]).read_bytes()
            self.assertEqual("sha256:" + hashlib.sha256(retained).hexdigest(), binding["digest"])
            self.assertEqual(retained, (run.root / binding["retained_ref"]).read_bytes())
        before = self.snapshot(evidence)
        for _ in range(2):
            self.assertEqual("complete", self.preserve(run, paths)["status"])
            self.assertEqual(before, self.snapshot(evidence))
        finished = run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual("retained", finished.status)
        self.assertEqual(before, self.snapshot(evidence))
        # Terminal validation depends on retained required bytes, not a surviving
        # checkout or current HEAD inference.
        shutil.rmtree(self.repo)
        retained_run = self.snapshot(run.root)
        self.assertEqual(finished.to_dict(), ExactOwnedRun.open(run.root).finish("succeeded").to_dict())
        self.assertEqual(retained_run, self.snapshot(run.root))
        print(f"FIXTURE required large package: {files}/416 files, {size}/9437184 bytes; all case declarations inspected; no live review claim.")

    def test_four_to_five_mib_package_survives_upgrade_and_repeated_finish(self):
        self.assert_upgrade_survives(4, 10000, "five-mib-upgrade")

    def test_five_to_six_mib_package_survives_upgrade_and_repeated_finish(self):
        self.assert_upgrade_survives(5, 18000, "six-mib-upgrade")

    def assert_upgrade_survives(self, previous_mib, report_cases, run_id):
        run, paths = self.large_run(run_id)
        # Preserve under the prior supported contract first, then record actual
        # fixture-case conclusions in the required report at the upgraded cap.
        with mock.patch.object(owned_run, "_MAX_REQUIRED_REVIEW_BYTES", previous_mib * 1024 * 1024), \
                mock.patch.object(review_closeout, "_MAX_REQUIRED_REVIEW_BYTES", previous_mib * 1024 * 1024):
            self.assertEqual("complete", self.preserve(run, paths)["status"])
        with paths["report"].open("a") as report:
            for index in range(report_cases):
                report.write(f"Case {index:05d}: declared relative path is safe, mode is owner-only, link expectation is single; fixture declaration inspection passed.\n")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertGreater(result["bytes"], previous_mib * 1024 * 1024)
        self.assertLess(result["bytes"], (previous_mib + 1) * 1024 * 1024)
        evidence = Path(result["evidence_path"])
        before = self.snapshot(evidence)
        with mock.patch.object(owned_run, "_MAX_REQUIRED_REVIEW_BYTES", previous_mib * 1024 * 1024), \
                mock.patch.object(review_closeout, "_MAX_REQUIRED_REVIEW_BYTES", previous_mib * 1024 * 1024):
            with self.assertRaises(review_closeout.RetainedReviewValidationError):
                run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(before, self.snapshot(evidence))
        first = run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(first.to_dict(), ExactOwnedRun.open(run.root).finish("succeeded").to_dict())
        self.assertEqual(before, self.snapshot(evidence))

    def test_complete_package_over_required_allowance_fails_with_structured_reason(self):
        run, paths = self.large_run("required-too-large")
        first = self.preserve(run, paths)
        destination = Path(first["evidence_path"])
        before = self.snapshot(destination)
        # Individual report fits; its complete required package exceeds the bound.
        limit = owned_run._MAX_REQUIRED_REVIEW_BYTES
        with paths["report"].open("wb") as report:
            report.write(b"# Required case evidence\n")
            chunk = b"Required case inspected; original source retained.\n" * 16384
            remaining = limit - 1024 * 1024 - report.tell()
            while remaining:
                piece = chunk[:remaining]
                report.write(piece)
                remaining -= len(piece)
        self.assertLess(paths["report"].stat().st_size, limit)
        self.assertGreater(first["bytes"] - len(before[Path("report.md")]) + paths["report"].stat().st_size,
                           limit)
        sources = self.snapshot(run.root)
        completed = subprocess.run(
            (sys.executable, "-m", "workflow_kernel", "preserve-review-evidence",
             "--run-root", str(run.root), "--repository-root", str(self.repo),
             "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
             "--lane-receipts", str(paths["lane_receipts"]),
             "--raw-lane-outputs", str(paths["raw_lane_outputs"]),
             "--raw-findings", str(paths["raw_findings"]), "--decisions", str(paths["decisions"]),
             "--private-router-directory", str(paths["router"]), "--report", str(paths["report"])),
            # Match the repository runner's local runtime, without cache resolution.
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(KERNEL_REFERENCES)},
            capture_output=True, text=True, check=False, timeout=30,
        )
        self.assertEqual(3, completed.returncode, completed.stderr)
        self.assertEqual("", completed.stdout)
        error = json.loads(completed.stderr)["error"]
        self.assertEqual("evidence_limit_exceeded", error["code"])
        detail = error["details"]
        self.assertEqual("preservation_input", detail["stage"])
        self.assertEqual("retention_limit", detail["reason"])
        self.assertEqual(limit, detail["allowed_bytes"])
        self.assertGreater(detail["actual_bytes"], detail["allowed_bytes"])
        self.assertTrue(detail["next_action"])
        self.assertFalse(list(destination.parent.glob("review-stage-*")))
        self.assertEqual(before, self.snapshot(destination))
        self.assertEqual(sources, self.snapshot(run.root))

    def test_missing_altered_and_unsafe_large_required_bytes_reject(self):
        for kind in ("missing", "altered", "symlink", "hardlink"):
            with self.subTest(kind=kind):
                run, paths = self.large_run("large-corrupt-" + kind)
                result = self.preserve(run, paths)
                run.finish("succeeded", retain_diagnostics=True)
                evidence = Path(result["evidence_path"])
                target = evidence / paths["payload_ref"]
                original = target.read_bytes()
                receipts = (evidence / "review/authoritative-receipts.json").read_bytes()
                target.unlink()
                if kind == "altered":
                    target.write_bytes(original[:-1] + b"x")
                elif kind in {"symlink", "hardlink"}:
                    outside = self.root / (kind + "-payload")
                    outside.write_bytes(original)
                    if kind == "symlink":
                        target.symlink_to(outside)
                    else:
                        os.link(outside, target)
                with self.assertRaises(review_closeout.RetainedReviewValidationError) as caught:
                    ExactOwnedRun.open(run.root).finish("succeeded")
                error = caught.exception.to_dict()["error"]
                reason, role = {
                    "missing": ("missing_evidence", "review-coverage"),
                    "altered": ("digest_mismatch", "review-coverage"),
                    "symlink": ("unsafe_path", "retained-review"),
                    "hardlink": ("unsafe_path", "retained-review"),
                }[kind]
                self.assertEqual(reason, error["details"]["reason"])
                self.assertEqual(role, error["details"]["artifact_role"])
                self.assertEqual(3, caught.exception.exit_code)
                self.assertNotIn(str(self.root), json.dumps(error))
                self.assertTrue(run.root.is_dir())
                self.assertEqual(receipts, (evidence / "review/authoritative-receipts.json").read_bytes())

    def test_interrupted_large_staging_and_retries_leave_authoritative_bytes_unchanged(self):
        for prior in (False, True):
            with self.subTest(prior=prior):
                run, paths = self.large_run("large-interruption-" + str(int(prior)))
                first = self.preserve(run, paths) if prior else None
                destination = Path(first["evidence_path"]) if prior else None
                retained = self.snapshot(destination) if prior else None
                sources = self.snapshot(run.root)
                copy_file = review_closeout._copy_file
                staged_bytes = 0

                def interrupt_after_copy(source, target):
                    nonlocal staged_bytes
                    copied = copy_file(source, target)
                    self.assertTrue(any(part.startswith("review-stage-") for part in target.parts))
                    staged_bytes += copied
                    if staged_bytes > 2 * 1024 * 1024:
                        self.assertEqual(source.read_bytes(), target.read_bytes())
                        raise OSError("fixture interruption after actual large staging copy")
                    return copied

                with mock.patch.object(review_closeout, "_copy_file", side_effect=interrupt_after_copy):
                    with self.assertRaisesRegex(OSError, "fixture interruption"):
                        self.preserve(run, paths)
                self.assertGreater(staged_bytes, 2 * 1024 * 1024)
                self.assertFalse(list((run.root / "diagnostic/review").glob("review-stage-*")))
                for relative, data in sources.items():
                    self.assertEqual(data, (run.root / relative).read_bytes())
                if prior:
                    self.assertEqual(retained, self.snapshot(destination))
                else:
                    self.assertFalse(list((run.root / "diagnostic/review").iterdir()))
                retry = self.preserve(run, paths)
                self.assertEqual("complete", retry["status"], retry)
                evidence = Path(retry["evidence_path"])
                before_repeat = self.snapshot(evidence)
                self.assertEqual("complete", self.preserve(run, paths)["status"])
                self.assertEqual(before_repeat, self.snapshot(evidence))
                self.assertEqual(paths["receipts"].read_bytes(), (evidence / "review/authoritative-receipts.json").read_bytes())
                if prior:
                    self.assertEqual(retained, before_repeat)
