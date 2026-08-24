import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES
from workflow_kernel.owned_run import ExactOwnedRun, owned_temporary_directory
from workflow_kernel.owned_run import run_owned_command


class ExactOwnedRunTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name) / "state root"

    def tearDown(self):
        self.directory.cleanup()

    def test_success_removes_run_root_and_every_nested_disposable_resource(self):
        run = ExactOwnedRun.start("pipeline", "run-1", base=self.base)
        run.create_path("temporary-repository", "repository")
        run.create_path("cache", "cache")
        run.create_path("raw-output", "raw")
        root = run.root

        report = run.finish("succeeded")

        self.assertEqual("removed", report.status)
        self.assertFalse(root.exists())

    def test_failure_retains_only_one_bounded_diagnostic_root_and_exact_command(self):
        run = ExactOwnedRun.start("dm-review", "run-2", base=self.base)
        raw = run.create_path("raw-output", "raw")
        (raw / "review.txt").write_text("disposable", encoding="utf-8")
        diagnostic = run.create_path("diagnostic", "diagnostic")
        (diagnostic / "summary.txt").write_text("lane 2 failed", encoding="utf-8")

        report = run.finish(
            "failed", retain_diagnostics=True,
            reason="required reviewer exited non-zero",
            contains="compact failure summary and exact failing command",
        )

        self.assertEqual("retained", report.status)
        self.assertEqual(str(run.root), report.path)
        self.assertEqual(
            "rm -rf -- " + "'" + str(run.root) + "'",
            report.cleanup_command,
        )
        self.assertEqual(
            {".depot-owned-run.json", ".depot-owned-run.lock", "diagnostic", "CLEANUP.txt"},
            {item.name for item in run.root.iterdir()},
        )
        terminal = (run.root / "CLEANUP.txt").read_text(encoding="utf-8")
        self.assertIn(f"Retained diagnostic root: {run.root}", terminal)
        self.assertIn("Reason: required reviewer exited non-zero", terminal)
        self.assertIn("Contains: compact failure summary and exact failing command", terminal)
        self.assertIn(f"Cleanup: {report.cleanup_command}", terminal)
        ExactOwnedRun.open(run.root).finish("cancelled")

    def test_concurrent_runs_have_distinct_roots_and_cannot_remove_each_other(self):
        first = ExactOwnedRun.start("pipeline", "same-request", base=self.base)
        second = ExactOwnedRun.start("pipeline", "same-request", base=self.base)
        first_root, second_root = first.root, second.root
        self.assertNotEqual(first_root, second_root)

        first.finish("succeeded")

        self.assertFalse(first_root.exists())
        self.assertTrue(second_root.exists())
        second.finish("succeeded")

    def test_review_abort_before_execution_removes_empty_root(self):
        run = ExactOwnedRun.start("dm-review", "abort", base=self.base)
        root = run.root
        report = run.finish("review-aborted")
        self.assertEqual("removed", report.status)
        self.assertFalse(root.exists())

    def test_resume_retry_reuses_exact_root_and_tolerates_disappeared_resource(self):
        run = ExactOwnedRun.start("pipeline", "retry", base=self.base)
        vanished = run.create_path("temporary-directory", "attempt-1")
        shutil.rmtree(vanished)

        resumed = ExactOwnedRun.open(run.root)
        resumed.create_path("temporary-directory", "attempt-2")
        root = resumed.root
        report = resumed.finish("succeeded")

        self.assertEqual("removed", report.status)
        self.assertFalse(root.exists())

    def test_missing_recorded_resource_is_safe_during_failed_retention(self):
        run = ExactOwnedRun.start("assembly-release", "missing", base=self.base)
        vanished = run.create_path("cache", "cache")
        shutil.rmtree(vanished)
        report = run.finish(
            "blocked", retain_diagnostics=True,
            reason="provider state unavailable", contains="compact release state",
        )
        self.assertEqual("retained", report.status)
        self.assertTrue(run.root.is_dir())
        ExactOwnedRun.open(run.root).finish("cancelled")

    def test_kernel_execution_directory_uses_active_exact_owned_root(self):
        run = ExactOwnedRun.start("assembly-build", "execution", base=self.base)
        prior = os.environ.get("DEPOT_EXACT_RUN_ROOT")
        os.environ["DEPOT_EXACT_RUN_ROOT"] = str(run.root)
        try:
            with owned_temporary_directory(
                "temporary-directory", "workflow-kernel-home-",
            ) as directory:
                path = Path(directory)
                self.assertTrue(path.is_relative_to(run.root))
                self.assertTrue(path.is_dir())
            self.assertFalse(path.exists())
        finally:
            if prior is None:
                os.environ.pop("DEPOT_EXACT_RUN_ROOT", None)
            else:
                os.environ["DEPOT_EXACT_RUN_ROOT"] = prior
        run.finish("succeeded")

    def test_command_launch_failure_reconciles_root_without_retention(self):
        status, report = run_owned_command(
            "assembly-build", "launch-failure", ("/definitely/missing/command",),
            base=self.base,
        )
        self.assertEqual(127, status)
        self.assertEqual("removed", report.status)
        self.assertFalse(Path(report.path).exists())

    def test_only_one_top_level_diagnostic_path_is_permitted(self):
        run = ExactOwnedRun.start("dm-review", "diagnostics", base=self.base)
        run.create_path("diagnostic", "diagnostic")
        with self.assertRaises(ValueError):
            run.create_path("diagnostic", "other-diagnostic")
        run.finish("cancelled")

    def test_finish_cli_reports_already_missing_root_without_deleting_anything(self):
        missing = self.base / "already-gone"
        completed = subprocess.run(
            (
                sys.executable, "-m", "workflow_kernel", "owned-run-finish",
                "--run-root", str(missing), "--outcome", "succeeded",
            ),
            env=self.cli_environment(), capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode)
        self.assertEqual("missing", json.loads(completed.stdout)["status"])

    def test_sigint_and_sigterm_retain_one_root_and_print_cleanup_command(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=signal.Signals(signum).name):
                run_base = self.base / signal.Signals(signum).name
                child = (
                    "import os, pathlib, signal; "
                    "p=pathlib.Path(os.environ['DEPOT_EXACT_RUN_ROOT'])/'diagnostic'/'signal.txt'; "
                    "p.write_text('waiting'); print('READY', flush=True); signal.pause()"
                )
                process = subprocess.Popen(
                    (
                        sys.executable, "-m", "workflow_kernel", "owned-run-exec",
                        "--workflow", "signal-test", "--run-id", "run",
                        "--base", str(run_base), "--retain-on-failure",
                        "--contains", "signal diagnostic", "--",
                        sys.executable, "-c", child,
                    ),
                    env=self.cli_environment(), stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True,
                )
                self.assertEqual("READY\n", process.stdout.readline())
                os.kill(process.pid, signum)
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(128 + signum, process.returncode, stderr)
                report = json.loads(stdout.strip().splitlines()[-1])
                self.assertEqual("retained", report["status"])
                self.assertIn(signal.Signals(signum).name, report["reason"])
                self.assertEqual(
                    "rm -rf -- " + __import__("shlex").quote(report["path"]),
                    report["cleanup_command"],
                )
                ExactOwnedRun.open(Path(report["path"])).finish("cancelled")

    @staticmethod
    def cli_environment():
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(KERNEL_REFERENCES)
        return environment


if __name__ == "__main__":
    unittest.main()
