"""Recovery never adopts replaced directories or weakens review coverage."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests import test_review_closeout as fixtures
from tests import KERNEL_REFERENCES
from workflow_kernel.owned_run import ExactOwnedRun, ChangedOwnedDirectoryError
from workflow_kernel.review_closeout import recover_review_evidence, EvidenceAssemblyError


class ReviewDirectoryRecoveryTests(unittest.TestCase):
    setUp = fixtures.ReviewCloseoutTests.setUp
    tearDown = fixtures.ReviewCloseoutTests.tearDown
    make_run = fixtures.ReviewCloseoutTests.make_run
    preserve = fixtures.ReviewCloseoutTests.preserve

    def broken_run(self):
        run, paths = self.make_run(workflow="pipeline")
        diagnostic = run.create_path("diagnostic", "gallery")
        original = dict(run._metadata["resources"][-1])
        # Holding the old directory avoids filesystem inode reuse.
        diagnostic.rename(run.root / "old-gallery")
        diagnostic.mkdir()
        (diagnostic / "retained.txt").write_text("original retained evidence\n")
        value = {"schema_version": 1, "operation": "preservation-destination",
                 "recovered_at": "2026-10-12T00:00:00Z", "request_ref": "review/request.json",
                 "original_registration": original}
        input_path = run.root / "review/destination-input.json"
        input_path.write_text(json.dumps(value))
        return run, paths, input_path, original

    def recover(self, run, input_path):
        return recover_review_evidence(run_root=run.root, repository_root=self.repo, input_path=input_path)

    def test_recreated_directory_diagnostic_recovery_and_preservation(self):
        run, paths, input_path, original = self.broken_run()
        history = list(run._metadata["resources"])
        original_files = {p.relative_to(run.root): p.read_bytes() for p in run.root.rglob("*")
                          if p.is_file() and p.name != ".depot-owned-run.json"}
        with self.assertRaises(ChangedOwnedDirectoryError) as raised:
            self.preserve(run, paths)
        diagnostic = raised.exception.to_dict()
        self.assertEqual("owned_directory_changed", diagnostic["error"]["code"])
        self.assertNotIn("gallery", json.dumps(diagnostic))
        result = self.recover(run, input_path)
        self.assertFalse(result["coverage_proof"])
        self.assertEqual(result, self.recover(run, input_path))
        opened = ExactOwnedRun.open(run.root)
        self.assertEqual(history, opened._metadata["resources"][:-1])
        self.assertEqual(run.run_id, opened.run_id)
        self.assertEqual("pipeline", opened.workflow)
        self.assertEqual(original, next(r for r in opened._metadata["resources"] if r["kind"] == "diagnostic"))
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        for p, data in original_files.items():
            self.assertEqual(data, (run.root / p).read_bytes())
        for outcome in ("failed", "succeeded", "cancelled"):
            with self.assertRaises(ChangedOwnedDirectoryError):
                opened.finish(outcome, retain_diagnostics=True)
        with self.assertRaises(ChangedOwnedDirectoryError):
            opened.finish("cancelled")
        self.assertTrue((run.root / "gallery/retained.txt").exists())

    def test_interruption_before_or_after_commit_retries_without_touching_originals(self):
        from workflow_kernel import owned_run
        for committed in (False, True):
            with self.subTest(committed=committed):
                run, paths, input_path, _ = self.broken_run()
                atomic = owned_run._atomic_metadata
                def interrupted(*args):
                    if committed:
                        atomic(*args)
                    raise KeyboardInterrupt()
                with mock.patch.object(owned_run, "_atomic_metadata", side_effect=interrupted):
                    with self.assertRaises(KeyboardInterrupt):
                        self.recover(run, input_path)
                self.assertEqual("original retained evidence\n", (run.root / "gallery/retained.txt").read_text())
                result = self.recover(run, input_path)
                self.assertEqual(result, self.recover(run, input_path))
                self.assertEqual(1, sum(r["kind"] == "review-preservation" for r in ExactOwnedRun.open(run.root)._metadata["resources"]))

    def test_concurrent_owner_rejected(self):
        run, _, input_path, _ = self.broken_run()
        with run._lock(create=False):
            with self.assertRaises(EvidenceAssemblyError) as raised:
                self.recover(run, input_path)
            self.assertEqual("append_conflict", raised.exception.reason)

    def test_cli_preservation_contention_is_retryable_and_leaves_evidence_intact(self):
        run, paths = self.make_run(workflow="pipeline")
        env = dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES))
        arguments = ["--run-root", run.root, "--repository-root", self.repo]
        for flag, key in (("request", "request"), ("receipts", "receipts"),
                          ("lane-receipts", "lane_receipts"), ("raw-lane-outputs", "raw_lane_outputs"),
                          ("raw-findings", "raw_findings"), ("decisions", "decisions"),
                          ("private-router-directory", "router"), ("report", "report")):
            arguments.extend(("--" + flag, paths[key]))
        before = {p.relative_to(run.root): p.read_bytes() for p in run.root.rglob("*") if p.is_file()}
        with run._lock(create=False):
            result = subprocess.run((sys.executable, "-m", "workflow_kernel", "preserve-review-evidence", *map(str, arguments)),
                                    env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(6, result.returncode, result.stderr)
        error = json.loads(result.stderr)["error"]
        self.assertEqual("state_conflict", error["code"])
        self.assertEqual("append_conflict", error["details"]["reason"])
        self.assertEqual(before, {p.relative_to(run.root): p.read_bytes() for p in run.root.rglob("*") if p.is_file()})
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_symlink_escape_missing_and_unreplaced_directories_rejected(self):
        for mutation in ("symlink", "missing", "restored", "wrong-registration", "wrong-source"):
            with self.subTest(mutation=mutation):
                run, _, input_path, _ = self.broken_run()
                if mutation in {"symlink", "missing", "restored"}:
                    shutil.rmtree(run.root / "gallery")
                    if mutation == "symlink":
                        (run.root / "gallery").symlink_to(self.repo, target_is_directory=True)
                    if mutation == "restored":
                        (run.root / "old-gallery").rename(run.root / "gallery")
                elif mutation == "wrong-registration":
                    value = json.loads(input_path.read_text())
                    value["original_registration"]["relative_path"] = "../escape"
                    input_path.write_text(json.dumps(value))
                else:
                    request = run.root / "review/request.json"
                    value = json.loads(request.read_text()); value["source_head"] = "f" * 40
                    request.write_text(json.dumps(value))
                before = (run.root / ".depot-owned-run.json").read_bytes()
                with self.assertRaises(EvidenceAssemblyError):
                    self.recover(run, input_path)
                self.assertEqual(before, (run.root / ".depot-owned-run.json").read_bytes())

    def test_replaced_recovery_destination_is_not_rebound(self):
        run, _, input_path, _ = self.broken_run()
        result = self.recover(run, input_path)
        destination = Path(result["path"])
        destination.rename(run.root / "old-destination")
        destination.mkdir()
        with self.assertRaises(EvidenceAssemblyError):
            self.recover(run, input_path)
        self.assertEqual(1, sum(r["kind"] == "review-preservation" for r in ExactOwnedRun.open(run.root)._metadata["resources"]))

    def test_changed_source_digests_and_invalid_coverage_still_fail(self):
        for mutation in ("digest", "coverage"):
            with self.subTest(mutation=mutation):
                run, paths, input_path, _ = self.broken_run()
                self.recover(run, input_path)
                if mutation == "digest":
                    record = json.loads((run.root / paths["record_ref"]).read_text())
                    retained = record["bindings"]["raw/security.md"]["retained_ref"]
                    (run.root / retained).write_text("changed sealed literal output")
                else:
                    rows = json.loads(paths["receipts"].read_text())
                    rows[-1]["completed_lanes"] = []
                    paths["receipts"].write_text(json.dumps(rows))
                try:
                    result = self.preserve(run, paths)
                except EvidenceAssemblyError:
                    pass
                else:
                    self.assertEqual("incomplete", result["status"])

    def test_browser_runs_recreate_child_and_keep_parent_identity(self):
        run = ExactOwnedRun.start("pipeline", "browser-output", base=self.state)
        parent = run.create_path("raw-output", "browser")
        identity = (parent.stat().st_dev, parent.stat().st_ino)
        for _ in range(3):
            output = run.browser_output("browser")
            self.assertEqual(parent / "playwright", output)
            # Playwright removes outputDir at each run.
            shutil.rmtree(output)
            output.mkdir()
            (output / "results.json").write_text("{}")
            self.assertEqual(identity, (parent.stat().st_dev, parent.stat().st_ino))
        run.record_path("raw-output", "browser/playwright")
        with self.assertRaises(ValueError):
            run.browser_output("browser")

    def test_browser_output_rejects_unsafe_parent_and_child(self):
        run = ExactOwnedRun.start("pipeline", "browser-unsafe", base=self.state)
        parent = run.create_path("raw-output", "browser")
        (parent / "playwright").symlink_to(self.repo, target_is_directory=True)
        with self.assertRaises(ValueError): run.browser_output("browser")
        (parent / "playwright").unlink()
        parent.rename(run.root / "old-browser"); parent.mkdir()
        with self.assertRaises(ChangedOwnedDirectoryError): run.browser_output("browser")
        with self.assertRaises(ValueError): run.browser_output("../browser")

    def test_cli_recovery_projection_and_safe_cleanup_diagnostic(self):
        run, paths, input_path, _ = self.broken_run()
        env = dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES))
        def cli(*args):
            return subprocess.run((sys.executable, "-m", "workflow_kernel", *map(str, args)),
                                  env=env, capture_output=True, text=True, timeout=30)
        arguments = ["--run-root", run.root, "--repository-root", self.repo]
        for flag, key in (("request", "request"), ("receipts", "receipts"),
                          ("lane-receipts", "lane_receipts"), ("raw-lane-outputs", "raw_lane_outputs"),
                          ("raw-findings", "raw_findings"), ("decisions", "decisions"),
                          ("private-router-directory", "router"), ("report", "report")):
            arguments.extend(("--" + flag, paths[key]))
        before = cli("project-review-evidence", *arguments)
        self.assertEqual(3, before.returncode)
        self.assertEqual("owned_directory_changed", json.loads(before.stderr)["error"]["code"])
        recovery = cli("recover-review-evidence", "--run-root", run.root,
                       "--repository-root", self.repo, "--input", input_path)
        self.assertEqual(0, recovery.returncode, recovery.stderr)
        for command in ("project-review-evidence", "preserve-review-evidence"):
            result = cli(command, *arguments)
            self.assertEqual(0, result.returncode, result.stderr)
        cleanup = cli("owned-run-finish", "--run-root", run.root, "--outcome", "cancelled")
        self.assertEqual(3, cleanup.returncode)
        self.assertEqual("owned_directory_changed", json.loads(cleanup.stderr)["error"]["code"])

    def test_publisher_owner_validation_accepts_fresh_destination_without_rebinding(self):
        run, _, input_path, _ = self.broken_run()
        self.recover(run, input_path)
        subprocess.run(("git", "-C", str(self.repo), "remote", "add", "origin",
                        "https://github.com/Fixture/consumer.git"), check=True)
        state = self.repo / ".workflow-kernel/runs" / run.run_id
        state.mkdir(parents=True)
        owner = {"repository": "Fixture/consumer", "workflow": run.workflow,
                 "run_id": run.run_id, "run_root": str(run.root), "state_dir": str(state)}
        helper = KERNEL_REFERENCES.parents[4] / "plugins/dm-review/skills/review/references/review-owner-context.sh"
        result = subprocess.run(("bash", "-c", 'source "$1"; review_owner_validate "$2" "$3"',
                                 "owner-test", str(helper), json.dumps(owner), str(self.repo)),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
