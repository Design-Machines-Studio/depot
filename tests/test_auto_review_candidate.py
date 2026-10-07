"""Isolated direct/Pipeline candidate mechanics; no live participant claims."""
import json
import subprocess
from pathlib import Path

import unittest
from tests import test_review_closeout as fixture
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
        (self.repo / ".git/info/exclude").write_text(".foreign-ignored\n")
        foreign.write_text("another owner's data\n")
        subprocess.run(["git", "-C", str(self.repo), "check-ignore", "--quiet", foreign.name], check=True)
        recheck.finish("succeeded", retain_diagnostics=True)
        self.assertTrue((retained / "review/raw-lane-outputs.json").is_file())
        self.assertTrue(foreign.is_file())

    def test_direct_loop_repair_push_and_final_head_closeout(self):
        self.exercise_path("dm-review-loop")

    def test_pipeline_owner_repair_push_and_final_head_closeout(self):
        self.exercise_path("pipeline")


class ReviewEvidenceProducerTests(unittest.TestCase):
    """Synthetic CLI lifecycle, distinct from live and installed consumer proof."""
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n")
        return path

    def prepare(self, lanes=("security",)):
        run, paths = self.make_run("dm-review-loop", "producer")
        request = json.loads(paths["request"].read_text())
        request["required_lanes"] = list(lanes)
        self.write(paths["request"], request)
        paths["receipts"].write_text("[]\n")
        for key in ("lane_receipts", "raw_lane_outputs", "raw_findings", "decisions"):
            paths[key].unlink()
        paths["lanes"] = {}
        original = json.loads(paths["input"].read_text())
        original_companion = json.loads((run.root / "review/companion.json").read_text())
        for lane in lanes:
            value = json.loads(json.dumps(original))
            value["lane"] = value["reviewer"] = lane
            value["literal"]["companion_ref"] = f"review/{lane}-companion.json"
            companion = dict(original_companion, lane=lane, reviewer=lane)
            self.write(run.root / value["literal"]["companion_ref"], companion)
            paths["lanes"][lane] = self.write(run.root / f"review/{lane}-input.json", value)
        return run, paths

    def cli(self, run, paths, input_path):
        import os
        import sys
        from tests import KERNEL_REFERENCES
        return subprocess.run([
            sys.executable, "-m", "workflow_kernel", "assemble-review-evidence",
            "--run-root", str(run.root), "--repository-root", str(self.repo),
            "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
            "--input", str(input_path), "--test-harness",
        ], env=dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES)), capture_output=True, text=True)

    def lane(self, run, paths, lane="security"):
        result = self.cli(run, paths, paths["lanes"][lane])
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)["record_ref"]

    def coverage(self, run, paths, records, **overrides):
        value = {"schema_version": 1, "operation": "coverage", "run_id": run.run_id,
                 "pass_id": "initial", "selection": [
                     {"lane": lane, "record_ref": record, "history_refs": [], "transition_refs": []}
                     for lane, record in records.items()],
                 "decisions": [], "occurred_at": "2026-09-01T00:02:00Z", "required_case_refs": [], "resolutions": []}
        value.update(overrides)
        path = self.write(run.root / "review/aggregate-input.json", value)
        return self.cli(run, paths, path)

    def test_zero_findings_cli_completion_retry_and_missing_companion_reconstruction(self):
        run, paths = self.prepare()
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(0, result.returncode, result.stderr)
        before = paths["receipts"].read_bytes()
        original_output = (run.root / "raw/security.md").read_bytes()
        retained = json.loads((run.root / record).read_text())["bindings"]["raw/security.md"]["retained_ref"]
        self.assertEqual(original_output, (run.root / retained).read_bytes())
        paths["raw_lane_outputs"].unlink()
        retry = self.coverage(run, paths, {"security": record})
        self.assertEqual(0, retry.returncode, retry.stderr)
        self.assertTrue(json.loads(retry.stdout)["reused"])
        self.assertEqual(before, paths["receipts"].read_bytes())
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        run.finish("succeeded", retain_diagnostics=True)

    def test_successful_dispatch_cannot_settle_incomplete_inspection(self):
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        value["result"] = {"status": "incomplete", "findings": [], "incomplete_reasons": ["required patch absent"]}
        value["inspected"]["paths"] = []
        self.write(paths["lanes"]["security"], value)
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(3, result.returncode, result.stderr)
        record = json.loads(result.stdout)["record_ref"]
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(3, result.returncode)
        self.assertEqual("incomplete_inspection", json.loads(result.stderr)["error"]["details"]["reason"])
        self.assertEqual(1, len(json.loads(paths["receipts"].read_text())))

    def test_missing_required_input_and_invalid_schema_are_distinct(self):
        run, paths = self.prepare()
        (run.root / "review/prompt.md").unlink()
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(3, result.returncode)
        self.assertIn("review/prompt.md", json.loads(result.stdout)["missing"])
        value = json.loads(paths["lanes"]["security"].read_text())
        value["unexpected"] = "malformed"
        self.write(paths["lanes"]["security"], value)
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(2, result.returncode)
        self.assertEqual("invalid_evidence", json.loads(result.stderr)["error"]["details"]["reason"])
        self.assertNotIn(str(run.root), result.stderr)

    def test_committed_identity_conflict_and_retained_digest_failure(self):
        run, paths = self.prepare()
        record = self.lane(run, paths)
        original = paths["receipts"].read_bytes()
        (run.root / "raw/security.md").write_text("different bytes\n")
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(6, result.returncode)
        self.assertEqual(original, paths["receipts"].read_bytes())
        retained = json.loads((run.root / record).read_text())["bindings"]["raw/security.md"]["retained_ref"]
        (run.root / retained).write_text("corruption\n")
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(3, result.returncode)
        self.assertEqual("digest_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])

    def test_concurrent_identical_and_distinct_lane_completions_preserve_sequences(self):
        from concurrent.futures import ThreadPoolExecutor
        run, paths = self.prepare(("security", "patterns"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda lane: self.cli(run, paths, paths["lanes"][lane]), ["security", "patterns", "security", "patterns"]))
        for result in results:
            self.assertEqual(0, result.returncode, result.stderr)
        receipts = json.loads(paths["receipts"].read_text())
        self.assertEqual([0, 1], [row["sequence"] for row in receipts])
        records = {lane: next(row["authoritative_receipt"] for row in receipts if row["lane"] == lane) for lane in ("security", "patterns")}
        result = self.coverage(run, paths, records)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["security", "patterns"], [row["lane"] for row in json.loads(paths["lane_receipts"].read_text())["lanes"]])

    def test_interrupted_seal_before_append_resumes_without_coverage(self):
        from unittest import mock
        from workflow_kernel.review_closeout import assemble_review_evidence, EvidenceAssemblyError
        run, paths = self.prepare()
        arguments = dict(run_root=run.root, repository_root=self.repo, request_path=paths["request"], receipts_path=paths["receipts"], input_path=paths["lanes"]["security"], test_harness=True)
        with mock.patch("workflow_kernel.cli._append_receipts_locked", side_effect=OSError("synthetic interruption")):
            with self.assertRaises(EvidenceAssemblyError):
                assemble_review_evidence(**arguments)
        self.assertEqual([], json.loads(paths["receipts"].read_text()))
        result = assemble_review_evidence(**arguments)
        self.assertEqual("complete", result["status"])
        self.assertEqual(1, len(json.loads(paths["receipts"].read_text())))

    def test_equal_head_does_not_hide_changed_worktree_bytes(self):
        run, paths = self.prepare()
        record = self.lane(run, paths)
        (self.repo / "source.txt").write_text("uncommitted repair\n")
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(3, result.returncode)
        self.assertEqual("source_scope_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])

    def test_cli_repair_recheck_and_justified_reuse_preserve_history(self):
        import shutil
        from workflow_kernel.owned_run import ExactOwnedRun
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _git_patch
        (self.repo / "other.txt").write_text("unaffected source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "other.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "unaffected fixture source"], check=True)
        run, paths = self.prepare(("security", "patterns"))
        value = json.loads(paths["lanes"]["security"].read_text())
        finding = {"source_finding_id": "fixture-unsafe-source", "reviewer": "security", "lane": "security", "source_severity": "P2", "evidence_ref": "raw/security.md", "finding_path": "source.txt", "finding_anchor": "line=1", "finding_category": "fixture", "finding_root_cause": "fixture source requires repair"}
        value["result"] = {"status": "findings", "findings": [finding], "incomplete_reasons": []}
        self.write(paths["lanes"]["security"], value)
        records = {lane: self.lane(run, paths, lane) for lane in ("security", "patterns")}
        # Host synthesis explicitly supplies the existing decision contract.
        record = json.loads((run.root / records["security"]).read_text())
        companion = json.loads((run.root / "review/security-companion.json").read_text())
        decision = dict(finding, evidence_ref=record["bindings"][finding["evidence_ref"]]["retained_ref"], finding_disposition="retained", agreement="unique", decision_reason_code="retained-unique", attempt=1, occurred_at="2026-09-01T00:02:00Z")
        decision.update({key: companion[key] for key in ("requested_provider", "attempted_provider", "implemented_by", "provider", "model", "implementer_family", "reviewer_family", "resolution_reason")})
        initial = self.coverage(run, paths, records, decisions=[decision])
        self.assertEqual(0, initial.returncode, initial.stderr)
        original_output = (run.root / "raw/security.md").read_bytes()
        before = record["source_snapshot"]
        (self.repo / "source.txt").write_text("repaired fixture source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "repair fixture finding"], check=True)
        _, head = source_identity(self.repo)
        after = _source_snapshot(self.repo, head)
        # Same-scope companion replacement is prohibited: use an owned replay,
        # retaining the committed stream and original sealed history.
        replay = ExactOwnedRun.start("dm-review-loop", run.run_id, base=self.state)
        replay.create_path("raw-output", "review")
        replay.create_path("raw-output", "receipts")
        shutil.copytree(run.root / "review", replay.root / "review", dirs_exist_ok=True)
        shutil.copytree(run.root / "receipts", replay.root / "receipts", dirs_exist_ok=True)
        shutil.copytree(run.root / "raw", replay.root / "raw")
        current = {key: replay.root / path.relative_to(run.root) if isinstance(path, Path) and path.is_relative_to(run.root) else path for key, path in paths.items()}
        for key in ("lane_receipts", "raw_lane_outputs", "raw_findings", "decisions"):
            current[key].unlink()
        request = json.loads(current["request"].read_text())
        request["source_head"] = head
        current["request"] = self.write(replay.root / "review/final-request.json", request)
        patch_ref = "review/repair.patch"
        (replay.root / patch_ref).write_bytes(_git_patch(self.repo, before["head"], head))
        iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": "review/selection.json", "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["security"], "lanes_skipped": ["patterns"], "rerun_reasons": {"security": ["a_prior_unresolved_finding", "b_fix_file_trigger"]}, "selection_fallback_reason": None}
        selection = {"schema_version": 1, "selected_full_set": ["security", "patterns"], "applied": True, "iteration": iteration, "finding_owner_lanes": ["security"], "file_trigger_lanes": ["security"], "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": None}
        self.write(replay.root / "review/selection.json", selection)
        recheck = json.loads(json.dumps(value))
        recheck.update(pass_id="recheck", attempt=2)
        recheck["source"].update(head=head, base=before["head"], request_ref="review/final-request.json")
        recheck["literal"]["output_ref"] = "raw/security-recheck.md"
        (replay.root / "raw/security-recheck.md").write_text("No findings after inspecting the fixture repair.\n")
        recheck["requested"]["evidence_refs"].append(patch_ref)
        recheck["requested"]["required_evidence_refs"].append(patch_ref)
        recheck["result"] = {"status": "no_findings", "findings": [], "incomplete_reasons": []}
        recheck["recheck"] = {"prior_record_ref": records["security"], "selection_ref": "review/selection.json", "repair_refs": [patch_ref]}
        recheck_path = self.write(replay.root / "review/recheck-input.json", recheck)
        result = self.cli(replay, current, recheck_path)
        self.assertEqual(0, result.returncode, result.stderr)
        new_record = json.loads(result.stdout)["record_ref"]
        transition = {"schema_version": 1, "from_source": before, "to_source": after, "changed_paths": ["source.txt"], "patch_ref": patch_ref, "selection_ref": "review/selection.json", "worktree_ref": None}
        self.write(replay.root / "review/reuse.json", transition)
        final_selection = [{"lane": "security", "record_ref": new_record, "history_refs": [records["security"]], "transition_refs": []}, {"lane": "patterns", "record_ref": records["patterns"], "history_refs": [], "transition_refs": ["review/reuse.json"]}]
        final = self.coverage(replay, current, {}, pass_id="final", selection=final_selection, resolutions=[{"source_finding_id": finding["source_finding_id"], "repair_ref": patch_ref, "verification_record_ref": new_record}])
        self.assertEqual(0, final.returncode, final.stderr)
        result = self.preserve(replay, current)
        self.assertEqual("complete", result["status"], result)
        retained = Path(result["evidence_path"])
        self.assertEqual(before["head"], json.loads((retained / records["patterns"]).read_text())["input"]["source"]["head"])
        self.assertEqual(original_output, (retained / record["bindings"]["raw/security.md"]["retained_ref"]).read_bytes())
        self.assertEqual([finding], json.loads((retained / records["security"]).read_text())["input"]["result"]["findings"])
        replay.finish("succeeded", retain_diagnostics=True)

    def test_wrong_patch_symlink_and_hardlink_are_refused_without_append(self):
        import os
        run, paths = self.prepare()
        value = json.loads(paths['lanes']['security'].read_text())
        patch_ref = 'review/required.patch'
        value['requested']['patch_ref'] = patch_ref
        value['requested']['evidence_refs'].append(patch_ref)
        value['requested']['required_evidence_refs'].append(patch_ref)
        self.write(paths['lanes']['security'], value)
        patch = run.root / patch_ref
        patch.write_text('wrong source bytes\n')
        result = self.cli(run, paths, paths['lanes']['security'])
        self.assertEqual(3, result.returncode)
        self.assertEqual('source_scope_mismatch', json.loads(result.stderr)['error']['details']['reason'])
        self.assertEqual([], json.loads(paths['receipts'].read_text()))
        patch.unlink()
        foreign = self.root / 'foreign.patch'
        foreign.write_text('foreign\n')
        patch.symlink_to(foreign)
        result = self.cli(run, paths, paths['lanes']['security'])
        self.assertEqual(3, result.returncode)
        self.assertEqual('unsafe_path', json.loads(result.stderr)['error']['details']['reason'])
        patch.unlink()
        os.link(foreign, patch)
        result = self.cli(run, paths, paths['lanes']['security'])
        self.assertEqual(3, result.returncode)
        self.assertEqual('unsafe_path', json.loads(result.stderr)['error']['details']['reason'])
        self.assertEqual('foreign\n', foreign.read_text())

    def test_production_invocation_cannot_settle_synthetic_lane(self):
        run, paths = self.prepare()
        from workflow_kernel.review_closeout import assemble_review_evidence, EvidenceAssemblyError
        with self.assertRaises(EvidenceAssemblyError) as caught:
            assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=paths['request'], receipts_path=paths['receipts'], input_path=paths['lanes']['security'])
        self.assertEqual('incomplete_inspection', caught.exception.reason)
        self.assertEqual([], json.loads(paths['receipts'].read_text()))

    def test_worktree_inspection_retains_content_and_changed_retry_cannot_relabel_it(self):
        from workflow_kernel.review_closeout import _working_patch
        run, paths = self.prepare()
        (self.repo / 'source.txt').write_text('dirty reviewed source\n')
        value = json.loads(paths['lanes']['security'].read_text())
        value['source']['worktree_ref'] = 'review/worktree.patch'
        (run.root / 'review/worktree.patch').write_bytes(_working_patch(self.repo, value['source']['head']))
        self.write(paths['lanes']['security'], value)
        record_ref = self.lane(run, paths)
        record = json.loads((run.root / record_ref).read_text())
        self.assertEqual(b'dirty reviewed source\n', (run.root / record['source_content']['source.txt']['retained_ref']).read_bytes())
        result = self.coverage(run, paths, {'security': record_ref})
        self.assertEqual(0, result.returncode, result.stderr)
        (self.repo / 'source.txt').write_text('further uncommitted change\n')
        result = self.coverage(run, paths, {'security': record_ref})
        self.assertEqual(3, result.returncode)
        self.assertEqual('source_scope_mismatch', json.loads(result.stderr)['error']['details']['reason'])

    def test_multiple_uncommitted_repairs_validate_history_against_sealed_patches(self):
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _working_patch
        run, paths = self.prepare(("security", "patterns"))
        records = {lane: self.lane(run, paths, lane) for lane in ("security", "patterns")}
        _, head = source_identity(self.repo)
        snapshots = [json.loads((run.root / records["security"]).read_text())["source_snapshot"]]
        chain, transitions = [records["security"]], []
        for number in (1, 2):
            (self.repo / "source.txt").write_text(f"uncommitted repair {number}\n")
            snapshots.append(_source_snapshot(self.repo, head, live=True))
            before, after = snapshots[-2], snapshots[-1]
            worktree_ref, patch_ref = f"review/worktree-{number}.patch", f"review/commit-{number}.patch"
            (run.root / worktree_ref).write_bytes(_working_patch(self.repo, head))
            (run.root / patch_ref).write_bytes(b"")
            selection_ref = f"review/selection-{number}.json"
            iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref, "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["security"], "lanes_skipped": ["patterns"], "rerun_reasons": {"security": ["a_prior_unresolved_finding", "b_fix_file_trigger"]}, "selection_fallback_reason": None}
            self.write(run.root / selection_ref, {"schema_version": 1, "selected_full_set": ["security", "patterns"], "applied": True, "iteration": iteration, "finding_owner_lanes": ["security"], "file_trigger_lanes": ["security"], "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": worktree_ref})
            transitions.append(f"review/transition-{number}.json")
            self.write(run.root / transitions[-1], {"schema_version": 1, "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "selection_ref": selection_ref, "worktree_ref": worktree_ref})
            recheck = json.loads(paths["lanes"]["security"].read_text())
            recheck.update(pass_id=f"recheck-{number}", attempt=number + 1)
            recheck["source"]["worktree_ref"] = worktree_ref
            recheck["literal"]["output_ref"] = f"raw/security-recheck-{number}.md"
            (run.root / recheck["literal"]["output_ref"]).write_text(f"No findings after repair {number}.\n")
            recheck["recheck"] = {"prior_record_ref": chain[-1], "selection_ref": selection_ref, "repair_refs": [worktree_ref]}
            result = self.cli(run, paths, self.write(run.root / f"review/recheck-{number}.json", recheck))
            self.assertEqual(0, result.returncode, result.stderr)
            chain.append(json.loads(result.stdout)["record_ref"])
        selection = [{"lane": "security", "record_ref": chain[-1], "history_refs": chain[:-1], "transition_refs": []},
                     {"lane": "patterns", "record_ref": records["patterns"], "history_refs": [], "transition_refs": transitions}]
        # The first dirty repair is no longer live; tampering with its patch must
        # still be caught against the bytes sealed when it was inspected.
        first = run.root / "review/worktree-1.patch"
        sealed = first.read_bytes()
        first.write_bytes(_working_patch(self.repo, head))
        result = self.coverage(run, paths, {}, pass_id="final", selection=selection)
        self.assertEqual(3, result.returncode)
        self.assertEqual("source_scope_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])
        first.write_bytes(sealed)
        result = self.coverage(run, paths, {}, pass_id="final", selection=selection)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_interruption_after_append_reconstructs_missing_companions(self):
        from unittest import mock
        from workflow_kernel.review_closeout import assemble_review_evidence, EvidenceAssemblyError
        from workflow_kernel import cli
        run, paths = self.prepare()
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        before = paths['receipts'].read_bytes()
        for key in ('lane_receipts', 'raw_lane_outputs', 'raw_findings', 'decisions'):
            paths[key].unlink()
        real_write = cli._write_json
        def interrupted(path, value):
            if Path(path).name == 'raw-lane-outputs.json':
                raise OSError('synthetic post-append interruption')
            return real_write(path, value)
        args = dict(run_root=run.root, repository_root=self.repo, request_path=paths['request'], receipts_path=paths['receipts'], input_path=run.root / 'review/aggregate-input.json', test_harness=True)
        with mock.patch('workflow_kernel.cli._write_json', side_effect=interrupted):
            with self.assertRaises(EvidenceAssemblyError):
                assemble_review_evidence(**args)
        self.assertEqual(before, paths['receipts'].read_bytes())
        result = assemble_review_evidence(**args)
        self.assertTrue(result['reused'])
        self.assertTrue(paths['decisions'].is_file())
        self.assertEqual(before, paths['receipts'].read_bytes())

    def test_unicode_host_extraction_seals_and_reconstructs_byte_identically(self):
        run, paths = self.prepare()
        value = json.loads(paths['lanes']['security'].read_text())
        value['inspected']['limitations'] = ['Static café example; runtime remains outside scope']
        self.write(paths['lanes']['security'], value)
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('complete', self.preserve(run, paths)['status'])

    def test_committed_coverage_reconstruction_works_from_retained_scope(self):
        from workflow_kernel.review_closeout import assemble_review_evidence, ReviewCloseoutValidationError
        run, paths = self.prepare()
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        paths['report'].write_text('[Missing](review/absent.md).\n')
        with self.assertRaises(ReviewCloseoutValidationError):
            self.preserve(run, paths)
        scope = next((run.root / 'diagnostic/review').iterdir())
        run.finish('failed', retain_diagnostics=True, reason='synthetic report repair', contains='committed source-bound history')
        input_value = json.loads((run.root / 'diagnostic/review' / scope.name / json.loads((scope / 'review/authoritative-receipts.json').read_text())[-1]['authoritative_receipt']).read_text())['input']
        recovery_input = self.write(scope / 'review/reconstructed-input.json', input_value)
        (scope / 'review/raw-lane-outputs.json').unlink()
        result = assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=scope / 'review/request.json', receipts_path=scope / 'review/authoritative-receipts.json', input_path=recovery_input, test_harness=True)
        self.assertTrue(result['reused'])
        self.assertTrue((scope / 'review/raw-lane-outputs.json').is_file())
        self.assertEqual(3, len(json.loads((scope / 'review/authoritative-receipts.json').read_text())))

    def test_receipts_preserve_bound_bug_class_execution_and_decision_context(self):
        run, paths = self.prepare()
        request = json.loads(paths['request'].read_text())
        request.update(workflow_class='bug', workflow_class_defaulted=False,
                       execution_mode='codex_native', decision_profile={'uncertainty': 'medium', 'consequence': 'high', 'rationale': 'Source-bound closeout must fail safely'},
                       decision_profile_defaulted=False)
        self.write(paths['request'], request)
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        for receipt in json.loads(paths['receipts'].read_text()):
            for field in ('workflow_class', 'workflow_class_defaulted', 'execution_mode', 'decision_profile', 'decision_profile_defaulted'):
                self.assertEqual(request[field], receipt[field])
        self.assertEqual('complete', self.preserve(run, paths)['status'])

    def test_router_public_companion_is_consumed_without_hand_materialized_lane_row(self):
        run, paths = self.prepare()
        value = json.loads(paths['lanes']['security'].read_text())
        private = json.loads((run.root / value['literal']['dispatch_receipt_ref']).read_text())
        private.update(participantId='security', transportStub=True,
                       requested={'role': 'review-deep', 'candidate': {'provider': 'openai'}},
                       served={'provider': 'openai', 'transport': 'codex', 'model': 'gpt-6.1-sol', 'family': 'openai'})
        self.write(run.root / value['literal']['dispatch_receipt_ref'], private)
        public = {'role': 'review-deep', 'capabilities': ['read-repository'], 'requestedEffort': 'high',
                  'normalizedEffort': 'high', 'effectiveEffort': 'high', 'transmittedEffort': 'high',
                  'effortStatus': 'transmitted', 'participantId': 'security', 'disposition': 'completed',
                  'fallback': False, 'evidenceSource': 'fixture', 'transportStub': True,
                  'familyIndependence': {'humanAuthored': False, 'excludedFamilyCount': 0}, 'output': 'raw/security.md'}
        self.write(run.root / value['literal']['companion_ref'], public)
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('complete', self.preserve(run, paths)['status'])
