"""Isolated direct/Pipeline candidate mechanics; no live participant claims."""
import json
import subprocess
from pathlib import Path

import unittest
import test_review_closeout as fixture
from workflow_kernel.review_closeout import source_identity


class AutoReviewCandidateTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve
    def exercise_path(self, workflow):
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", str(remote)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "push", "--quiet", "origin", "HEAD:refs/heads/candidate"], check=True)
        run, paths = self.make_run(workflow, "candidate-" + workflow)
        initial = self.preserve(run, paths)
        self.assertEqual("complete", initial["status"])
        # A retained finding is repaired, committed and pushed to an isolated
        # remote. Old source evidence must not become final-head evidence.
        (self.repo / "source.txt").write_text("repaired source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "repair retained fixture finding"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "push", "--quiet", "origin", "HEAD:refs/heads/candidate"], check=True)
        _, head = source_identity(self.repo)
        remote_head = subprocess.check_output(["git", "-C", str(self.repo), "ls-remote", "origin", "refs/heads/candidate"], text=True).split()[0]
        self.assertEqual(head, remote_head)
        stale = self.preserve(run, paths)
        self.assertEqual("incomplete", stale["status"])
        # Existing sealed inputs stay immutable. Recheck produces fresh owned
        # evidence for the new head rather than relabeling the old receipt.
        recheck, current = self.make_run(workflow, "candidate-recheck-" + workflow)
        final = self.preserve(recheck, current)
        self.assertEqual("complete", final["status"])
        retained = Path(final["evidence_path"])
        self.assertEqual(head, json.loads((retained / "review/request.json").read_text())["source_head"])
        retry = self.preserve(recheck, current)
        self.assertEqual(final["evidence_path"], retry["evidence_path"])
        self.assertEqual("complete", retry["status"])
        # Evidence survives disposable-output cleanup; foreign ignored data in
        # the product checkout is not swept.
        foreign = self.repo / ".foreign-ignored"
        foreign.write_text("another owner's data\n")
        recheck.finish("succeeded", retain_diagnostics=True)
        self.assertTrue((retained / "review/raw-lane-outputs.json").is_file())
        self.assertTrue(foreign.is_file())

    def test_direct_loop_repair_push_and_final_head_closeout(self):
        self.exercise_path("dm-review-loop")

    def test_pipeline_owner_repair_push_and_final_head_closeout(self):
        self.exercise_path("pipeline")
