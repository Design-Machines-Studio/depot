"""Task-bound workspace count controls; fixtures never establish live coverage."""
from __future__ import annotations
import hashlib
import json
import subprocess
import unittest
from unittest import mock
from pathlib import Path
from tests import test_review_closeout as fixture
from workflow_kernel import review_closeout as review
from workflow_kernel import owned_run

class ReviewWorkspaceExceptionTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve

    def setup_case(self):
        subprocess.run(("git", "-C", str(self.repo), "remote", "add", "origin", "https://github.com/Fixture/consumer.git"), check=True)
        run, paths = self.make_run(run_id="task-count")
        identity, head = review.source_identity(self.repo)
        fields = dict(repository=identity, run_id=run.run_id, source_head=head,
                      pull_request_url="https://github.com/Fixture/consumer/pull/29", max_files=4096)
        approval = dict(fields, schema_version=1, scope="assembly_workspace_file_count_only",
                        user_authorization="Fixture explicit operator count exception")
        ap = run.root / "review/approval.json"; ap.write_text(json.dumps(approval))
        ex = dict(fields, schema_version=1, approval_ref="review/approval.json",
                  approval_digest="sha256:" + hashlib.sha256(ap.read_bytes()).hexdigest())
        ep = run.root / "review/count-exception.json"; ep.write_text(json.dumps(ex))
        kwargs = dict(run_root=run.root, repository_root=self.repo,
                      request_path=paths["request"], receipts_path=paths["receipts"],
                      input_path=paths["coverage_input"])
        return run, paths, kwargs, ep

    def overflow(self, run, paths):
        inp = json.loads(paths["coverage_input"].read_text()); inp["pass_id"] = "task-count-overflow"
        refs = []
        for index in range(1024):
            ref = f"review/evidence/case-{index}.json"
            (run.root / ref).write_text(json.dumps({"case": index}))
            refs.append(ref)
        inp["required_case_refs"] = refs
        paths["coverage_input"].write_text(json.dumps(inp))

    def test_workspace_override_is_exact_and_does_not_waive_retention_or_leak(self):
        run, paths, kwargs, ep = self.setup_case(); self.overflow(run, paths)
        original = {p: p.read_bytes() for p in (run.root / "review/evidence").glob("case-*.json")}
        with self.assertRaises(review.EvidenceAssemblyError) as caught: review.assemble_review_evidence(**kwargs)
        self.assertEqual("retention_limit", caught.exception.reason)
        result = review.assemble_review_evidence(**kwargs, file_count_exception=ep)
        self.assertEqual("complete", result["status"])
        self.assertEqual(4096, result["assembly_file_count_exception"]["max_files"])
        self.assertTrue(result["assembly_file_count_exception"]["retention_limits_unchanged"])
        self.assertIsNone(review._ASSEMBLY_FILE_EXCEPTION.get())
        again = review.assemble_review_evidence(**kwargs, file_count_exception=ep)
        self.assertTrue(again["reused"])
        changed = json.loads(paths["coverage_input"].read_text()); changed["pass_id"] = "another-write-without-exception"
        paths["coverage_input"].write_text(json.dumps(changed))
        with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs)
        self.assertIsNone(review._ASSEMBLY_FILE_EXCEPTION.get())
        with self.assertRaises(review.EvidenceAssemblyError): self.preserve(run, paths)
        for p, data in original.items(): self.assertEqual(data, p.read_bytes())

    def test_bad_bindings_rejected_before_evidence_mutation(self):
        run, paths, kwargs, ep = self.setup_case()
        valid = ep.read_bytes(); evidence = run.root / "review/evidence"
        before = {p.name: p.read_bytes() for p in evidence.iterdir()}
        for key, value in [("repository", "github.com/Other/repo"), ("run_id", "wrong"),
                           ("source_head", "0" * 40), ("pull_request_url", "https://github.com/Other/repo/pull/29"),
                           ("max_files", True), ("max_files", 1024), ("max_files", 4097),
                           ("max_files", 2049), ("approval_digest", "sha256:" + "0" * 64),
                           ("approval_ref", "../outside.json"), ("unknown", "field")]:
            with self.subTest(key=key, value=value):
                doc=json.loads(valid); doc[key]=value; ep.write_text(json.dumps(doc))
                with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs, file_count_exception=ep)
                self.assertEqual(before, {p.name:p.read_bytes() for p in evidence.iterdir()})
                self.assertIsNone(review._ASSEMBLY_FILE_EXCEPTION.get())
        ep.write_bytes(valid)
        with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs, file_count_exception=ep, test_harness=True)

    def test_byte_and_safe_file_boundaries_remain_and_failure_resets_context(self):
        run, paths, kwargs, ep = self.setup_case()
        oversized = run.root / "review/evidence/oversized.bin"
        with oversized.open("wb") as f: f.truncate(134217729)
        with self.assertRaises(review.EvidenceAssemblyError) as caught: review.assemble_review_evidence(**kwargs, file_count_exception=ep)
        oversized.unlink()
        self.assertEqual("retention_limit", caught.exception.reason)
        self.assertIsNone(review._ASSEMBLY_FILE_EXCEPTION.get())
        outside = self.root / "outside.json"; outside.write_text("{}")
        link = run.root / "review/evidence/unsafe.json"; link.symlink_to(outside)
        with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs, file_count_exception=ep)
        self.assertIsNone(review._ASSEMBLY_FILE_EXCEPTION.get()); link.unlink()
        ap=run.root / "review/approval.json"; ap.unlink(); ap.symlink_to(outside)
        with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs, file_count_exception=ep)

    def test_count_bound_does_not_apply_to_another_directory(self):
        run, paths, kwargs, ep = self.setup_case()
        foreign=self.root / "foreign"; foreign.mkdir()
        for i in range(1025): (foreign / str(i)).write_text("{}")
        with mock.patch.object(review, "_assemble_review_evidence", side_effect=lambda **kw:review._check_evidence_bound(foreign)):
            with self.assertRaises(review.EvidenceAssemblyError): review.assemble_review_evidence(**kwargs, file_count_exception=ep)
        self.assertIsNone(review._ASSEMBLY_FILE_EXCEPTION.get())
