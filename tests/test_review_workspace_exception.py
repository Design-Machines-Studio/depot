"""Finite assembly workspace controls; fixtures never establish live coverage."""
from __future__ import annotations
import json
import subprocess
import unittest
from unittest import mock
from tests import test_review_closeout as fixture
from workflow_kernel import review_closeout as review
from workflow_kernel import owned_run

class ReviewWorkspaceExceptionTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve

    def setup_case(self, consumer="governance", pr=False):
        subprocess.run(("git", "-C", str(self.repo), "config", "remote.origin.url",
                        f"https://github.com/Fixture/{consumer}.git"), check=True)
        # The workflow does not require PR publication metadata at assembly.
        run, paths = self.make_run(run_id="workspace-" + consumer)
        if pr:
            (run.root / "review/published-pr.json").write_text(json.dumps({
                "url": f"https://github.com/Fixture/{consumer}/pull/29"}))
        kwargs = dict(run_root=run.root, repository_root=self.repo,
                      request_path=paths["request"], receipts_path=paths["receipts"],
                      input_path=paths["coverage_input"])
        return run, paths, kwargs

    def inventory(self, directory):
        return {p.name: p.read_bytes() for p in directory.iterdir()}

    def test_pre_pr_governance_and_existing_pr_livewires_with_valid_retention(self):
        for consumer, pr in (("governance", False), ("livewires", True)):
            with self.subTest(consumer=consumer):
                run, paths, kwargs = self.setup_case(consumer, pr)
                evidence = run.root / "review/evidence"
                for i in range(1058):
                    (evidence / f"partial-{i}.json").write_text("{}")
                before = self.inventory(evidence)
                value = json.loads(paths["coverage_input"].read_text())
                value["pass_id"] = "fresh-large-workspace"
                paths["coverage_input"].write_text(json.dumps(value))
                first = review.assemble_review_evidence(**kwargs)
                self.assertEqual("complete", first["status"])
                self.assertFalse(first["reused"])
                after = self.inventory(evidence)
                self.assertTrue(review.assemble_review_evidence(**kwargs)["reused"])
                self.assertEqual(after, self.inventory(evidence))
                result = self.preserve(run, paths)
                self.assertEqual("complete", result["status"])
                self.assertEqual(after, self.inventory(evidence))
                for name, data in before.items(): self.assertEqual(data, after[name])
                # Retention uses validated closure; uncommitted partials have no authority.
                retained = review.validate_preserved_review_evidence(run.root / "diagnostic", run=owned_run.ExactOwnedRun.open(run.root))
                self.assertLess(retained["retention"]["required_review"]["actual_files"], 1024)
                self.assertEqual(2048, retained["retention"]["required_review"]["allowed_files"])

    def test_workspace_success_does_not_waive_final_retention(self):
        run, paths, kwargs = self.setup_case()
        value = json.loads(paths["coverage_input"].read_text()); value["pass_id"] = "large-required-closure"
        refs = []
        for i in range(1024):
            ref = f"review/evidence/case-{i}.json"
            (run.root / ref).write_text(json.dumps({"case": i})); refs.append(ref)
        value["required_case_refs"] = refs
        paths["coverage_input"].write_text(json.dumps(value))
        self.assertEqual("complete", review.assemble_review_evidence(**kwargs)["status"])
        before = self.inventory(run.root / "review/evidence")
        with self.assertRaises(review.EvidenceAssemblyError) as caught:
            self.preserve(run, paths)
        self.assertEqual("retention_limit", caught.exception.reason)
        self.assertEqual("required_review", caught.exception.measurement["category"])
        self.assertEqual(before, self.inventory(run.root / "review/evidence"))

    def test_workspace_exact_and_one_over_file_and_byte_limits(self):
        directory = self.root / "workspace"; directory.mkdir()
        for i in range(4096): (directory / str(i)).write_bytes(b"")
        self.assertEqual((4096, 0), review._check_evidence_bound(directory))
        (directory / "extra").write_bytes(b"")
        with self.assertRaises(review.EvidenceAssemblyError) as caught:
            review._check_evidence_bound(directory)
        self.assertEqual("workspace_limit", caught.exception.reason)
        self.assertEqual(4097, caught.exception.measurement["actual_files"])
        self.assertFalse(caught.exception.measurement["measurement_complete"])
        for p in directory.iterdir(): p.unlink()
        big = directory / "big"
        with big.open("wb") as f: f.truncate(201326592)
        self.assertEqual((1, 201326592), review._check_evidence_bound(directory))
        with big.open("ab") as f: f.write(b"x")
        with self.assertRaises(review.EvidenceAssemblyError) as caught:
            review._check_evidence_bound(directory)
        self.assertEqual("assembly_workspace", caught.exception.measurement["category"])
        self.assertEqual(201326593, caught.exception.measurement["actual_bytes"])

    def test_failure_retries_do_not_grow_full_workspace(self):
        run, paths, kwargs = self.setup_case(); directory = run.root / "review/evidence"
        for i in range(4096 - len(list(directory.iterdir()))):
            (directory / f"partial-{i}.json").write_text("{}")
        value = json.loads(paths["coverage_input"].read_text()); value["pass_id"] = "new-at-cap"
        paths["coverage_input"].write_text(json.dumps(value)); before = self.inventory(directory)
        for _ in range(3):
            with self.assertRaises(review.EvidenceAssemblyError) as caught:
                review.assemble_review_evidence(**kwargs)
            self.assertEqual("workspace_limit", caught.exception.reason)
            self.assertEqual(before, self.inventory(directory))

    def test_uncommitted_record_is_reused_after_append_failure(self):
        run, paths, kwargs = self.setup_case(); kwargs["input_path"] = paths["input"]
        value = json.loads(paths["input"].read_text()); value["pass_id"] = "append-interrupted"
        paths["input"].write_text(json.dumps(value)); directory = run.root / "review/evidence"
        from workflow_kernel import cli
        with mock.patch.object(cli, "_append_receipts_locked", side_effect=OSError("fixture interruption")):
            with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs)
            before = self.inventory(directory)
            for _ in range(2):
                with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs)
                self.assertEqual(before, self.inventory(directory))
        result = review.assemble_review_evidence(**kwargs)
        self.assertEqual("complete", result["status"])
        self.assertEqual(before, self.inventory(directory))
        self.assertTrue(review.assemble_review_evidence(**kwargs)["reused"])

    def test_interrupted_literal_seal_preserves_authentic_files(self):
        run, paths, kwargs = self.setup_case(); directory = run.root / "review/evidence"
        before = self.inventory(directory)
        with mock.patch.object(review.os, "write", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                review._seal_evidence(run.root, "literal", b"new authentic literal", literal=True)
        self.assertEqual(before, self.inventory(directory))
        ref = review._seal_evidence(run.root, "literal", b"new authentic literal", literal=True)
        self.assertEqual(b"new authentic literal", (run.root / ref).read_bytes())

    def test_interruption_after_atomic_rename_keeps_complete_seal_for_retry(self):
        run, paths, kwargs = self.setup_case(); directory = run.root / "review/evidence"
        before = self.inventory(directory)
        from workflow_kernel._files import PinnedDirectory
        original = PinnedDirectory.replace
        def interrupt_after_replace(directory, source, target):
            original(directory, source, target)
            raise KeyboardInterrupt
        with mock.patch.object(PinnedDirectory, "replace", interrupt_after_replace):
            with self.assertRaises(KeyboardInterrupt):
                review._seal_evidence(run.root, "literal", b"complete interrupted literal", literal=True)
        after = self.inventory(directory)
        self.assertEqual(len(before) + 1, len(after))
        for name, data in before.items(): self.assertEqual(data, after[name])
        ref = review._seal_evidence(run.root, "literal", b"complete interrupted literal", literal=True)
        self.assertEqual(b"complete interrupted literal", (run.root / ref).read_bytes())
        self.assertEqual(after, self.inventory(directory))

    def test_wrong_run_repository_head_and_corrupted_reference_remain_rejected(self):
        run, paths, kwargs = self.setup_case(); kwargs["input_path"] = paths["input"]
        original = paths["input"].read_bytes()
        for field, val in (("run_id", "wrong"), ("repository", "github.com/Other/repo"), ("head", "0" * 40)):
            value = json.loads(original); value["pass_id"] = "bad-" + field
            if field == "run_id": value[field] = val
            else: value["source"][field] = val
            paths["input"].write_text(json.dumps(value))
            with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs)
        paths["input"].write_bytes(original)
        (run.root / "raw/security.md").write_bytes(b"corrupted")
        with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs)

    def test_final_required_exact_and_one_over_bounded_limits(self):
        for files, size, valid in ((2048,201326592,True),(2049,1,False),(1,201326593,False)):
            # Mechanical boundary oracle; integration failure is proved above.
            projection = {"required_review": {"actual_files":files,"actual_bytes":size,
                           "allowed_files":2048,"allowed_bytes":201326592}}
            if valid: owned_run._require_retention_projection(projection)
            else:
                with self.assertRaises(owned_run.BoundedDiagnosticLimitError):
                    owned_run._require_retention_projection(projection)
