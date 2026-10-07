"""Isolated direct/Pipeline candidate mechanics; no live participant claims."""
import json
import hashlib
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

    def test_absent_required_patch_diagnostic_names_its_safe_path(self):
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        value["requested"]["evidence_refs"].append("review/absent-required.patch")
        value["requested"]["required_evidence_refs"].append("review/absent-required.patch")
        self.write(paths["lanes"]["security"], value)
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(3, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("incomplete", output["status"])
        self.assertEqual(["review/absent-required.patch"], output["missing"])
        self.assertEqual([{"stage": "lane_input", "reason": "missing_evidence", "path": "review/absent-required.patch"}], output["diagnostics"])

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
        self.repair_recheck_reuse(("security", "patterns"))

    def test_synthetic_eight_production_lanes_capacity_lifecycle(self):
        self.repair_recheck_reuse(("code-simplicity", "pattern-recognition", "security", "architecture", "agent-native", "performance", "ai-slop", "second-perspective"), capacity=True)

    def repair_recheck_reuse(self, lanes, *, capacity=False):
        import shutil
        from workflow_kernel.owned_run import ExactOwnedRun
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _git_patch, _resolve_snapshot
        (self.repo / "other.txt").write_text("unaffected source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "other.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "unaffected fixture source"], check=True)
        if capacity:
            # Real Git inventory and actual fixture diff; outputs/receipts are
            # deliberately synthetic and never live participant proof.
            from workflow_kernel.review_closeout import _document_digest
            _, base = source_identity(self.repo)
            names = [f"plugins/fixture/skills/source/references/{index:04d}-" + "m" * 7 + ".md" for index in range(1157)]
            files = {"source.txt": {"mode": "100644", "oid": "0" * 40}, "other.txt": {"mode": "100644", "oid": "0" * 40}}
            files.update({name: {"mode": "100644", "oid": "0" * 40} for name in names})
            encoded = json.dumps({"head": base, "files": files}, sort_keys=True, separators=(",", ":")).encode()
            extra = 146742 - len(encoded)
            self.assertGreaterEqual(extra, 0)
            # Distribute padding into realistic source path lengths.
            for index, name in enumerate(names):
                padding = extra // len(names) + (index < extra % len(names))
                path = self.repo / (name[:-3] + "m" * padding + ".md")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture metadata source\n")

            subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "synthetic production-sized fixture"], check=True)
            _, base = source_identity(self.repo)
            body = "".join(f"fixture review data {index:05d}\n" for index in range(6000))
            (self.repo / "source.txt").write_text(body)
            from workflow_kernel.review_closeout import _working_patch
            padding = 183933 - len(_working_patch(self.repo, base))
            self.assertGreater(padding, 0)
            (self.repo / "source.txt").write_text(body[:-1] + "x" * padding + "\n")
            subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "large synthetic fixture diff"], check=True)
            _, sized_head = source_identity(self.repo)
            snapshot = _source_snapshot(self.repo, sized_head)
            self.assertEqual(1159, len(snapshot["files"]))
            self.assertEqual(146742, len(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()))
            common_patch = _git_patch(self.repo, base, sized_head)
            self.assertEqual(183933, len(common_patch))
        run, paths = self.prepare(lanes)
        if capacity:
            common_ref = "review/repository-evidence.md"
            common = ("SYNTHETIC TEST HARNESS: complete cached fixture scope.\n" + "\n".join(f"Requirement {index}: inspect fixture source and report supported defects." for index in range(1, 21)) + "\n").encode() + common_patch
            (run.root / common_ref).write_bytes(common)
            for lane in lanes:
                lane_value = json.loads(paths["lanes"][lane].read_text())
                prompt_ref = f"review/{lane}-prompt.md"
                (run.root / prompt_ref).write_text(f"SYNTHETIC TEST HARNESS: {lane}; inspect source.txt and other.txt; read {common_ref} completely.\n")
                lane_value["source"]["base"] = base
                lane_value["requested"]["paths"] = ["source.txt", "other.txt"]
                lane_value["requested"].update(designation="full", evidence_refs=[prompt_ref, common_ref], required_evidence_refs=[prompt_ref, common_ref])
                lane_value["inspected"]["paths"] = ["source.txt", "other.txt"]
                lane_value["provenance"]["source_refs"] = [prompt_ref, common_ref]
                self.write(paths["lanes"][lane], lane_value)
                output_ref = f"raw/{lane}.md"
                dispatch_ref = f"receipts/private/router/{lane}.json"
                lane_value["literal"].update(output_ref=output_ref, dispatch_receipt_ref=dispatch_ref)
                (run.root / output_ref).write_text(f"SYNTHETIC TEST HARNESS: {lane} fixture output.\n")
                self.write(run.root / dispatch_ref, {"schemaVersion": 1, "receiptId": "dispatch-" + hashlib.sha256(lane.encode()).hexdigest()[:24], "requested": {}, "fallback": False, "synthetic_test_harness": True, "served": None, "attempts": []})
                self.write(paths["lanes"][lane], lane_value)
            self.write(paths["router"] / "terminal-receipt-index.json", {"schemaVersion": 1, "receiptFiles": [f"{lane}.json" for lane in lanes]})
        value = json.loads(paths["lanes"]["security"].read_text())
        finding = {"source_finding_id": "fixture-unsafe-source", "reviewer": "security", "lane": "security", "source_severity": "P2", "evidence_ref": "raw/security.md", "finding_path": "source.txt", "finding_anchor": "line=1", "finding_category": "fixture", "finding_root_cause": "fixture source requires repair"}
        value["result"] = {"status": "findings", "findings": [finding], "incomplete_reasons": []}
        self.write(paths["lanes"]["security"], value)
        records = {lane: self.lane(run, paths, lane) for lane in lanes}
        # Host synthesis explicitly supplies the existing decision contract.
        record = json.loads((run.root / records["security"]).read_text())
        companion = json.loads((run.root / "review/security-companion.json").read_text())
        decision = dict(finding, evidence_ref=record["bindings"][finding["evidence_ref"]]["retained_ref"], finding_disposition="retained", agreement="unique", decision_reason_code="retained-unique", attempt=1, occurred_at="2026-09-01T00:02:00Z")
        decision.update({key: companion[key] for key in ("requested_provider", "attempted_provider", "implemented_by", "provider", "model", "implementer_family", "reviewer_family", "resolution_reason")})
        initial = self.coverage(run, paths, records, decisions=[decision])
        self.assertEqual(0, initial.returncode, initial.stderr)
        original_output = (run.root / "raw/security.md").read_bytes()
        before = _resolve_snapshot(run.root, record["source_snapshot"], shared=record["schema_version"] == 2)
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
        iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": "review/selection.json", "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["security"], "lanes_skipped": [lane for lane in lanes if lane != "security"], "rerun_reasons": {"security": ["a_prior_unresolved_finding", "b_fix_file_trigger"]}, "selection_fallback_reason": None}
        selection = {"schema_version": 1, "selected_full_set": list(lanes), "applied": True, "iteration": iteration, "finding_owner_lanes": ["security"], "file_trigger_lanes": ["security"], "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": None}
        if capacity:
            from workflow_kernel.review_closeout import _seal_evidence
            shared_before = {"snapshot_ref": _seal_evidence(replay.root, "source", before)}
            shared_after = {"snapshot_ref": _seal_evidence(replay.root, "source", after)}
            selection.update(schema_version=2, from_source=shared_before, to_source=shared_after)
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
        if capacity:
            transition.update(schema_version=2, from_source=shared_before, to_source=shared_after)
        self.write(replay.root / "review/reuse.json", transition)
        final_selection = [{"lane": lane, "record_ref": new_record if lane == "security" else records[lane], "history_refs": [records[lane]] if lane == "security" else [], "transition_refs": [] if lane == "security" else ["review/reuse.json"]} for lane in lanes]
        final = self.coverage(replay, current, {}, pass_id="final", selection=final_selection, resolutions=[{"source_finding_id": finding["source_finding_id"], "repair_ref": patch_ref, "verification_record_ref": new_record}])
        self.assertEqual(0, final.returncode, final.stderr)
        result = self.preserve(replay, current)
        self.assertEqual("complete", result["status"], result)
        retained = Path(result["evidence_path"])
        self.assertEqual(before["head"], json.loads((retained / records[next(lane for lane in lanes if lane != "security")]).read_text())["input"]["source"]["head"])
        self.assertEqual(original_output, (retained / record["bindings"]["raw/security.md"]["retained_ref"]).read_bytes())
        self.assertEqual([finding], json.loads((retained / records["security"]).read_text())["input"]["result"]["findings"])
        if capacity:
            from workflow_kernel.owned_run import _bounded_diagnostic
            from workflow_kernel.review_closeout import has_preserved_review_evidence
            count, size = _bounded_diagnostic(replay.root / "diagnostic")
            self.assertLessEqual(count, 128)
            self.assertLessEqual(size, 2097152)
            for ref in records.values():
                self.assertEqual((run.root / ref).read_bytes(), (retained / ref).read_bytes())
            retained_record = json.loads((retained / new_record).read_text())
            self.assertEqual(common, (retained / retained_record["bindings"][common_ref]["retained_ref"]).read_bytes())
            self.assertTrue(has_preserved_review_evidence(replay.root / "diagnostic"))
            print(f"SYNTHETIC scaling lifecycle: 8 logical lanes; 1159 paths; 146742 metadata bytes; {len(common_patch)} actual fixture diff bytes; retained {count}/128 files, {size}/2097152 bytes; original history/output and shared input unchanged.")
        replay.finish("succeeded", retain_diagnostics=True)

    def test_shared_snapshot_missing_tampered_malformed_and_wrong_head_rejected(self):
        from workflow_kernel.review_closeout import _seal_evidence, _seal_record
        for defect in ("missing", "tampered", "malformed", "wrong-head", "unsafe"):
            with self.subTest(defect=defect):
                run, paths = self.prepare()
                ref = self.lane(run, paths)
                record = json.loads((run.root / ref).read_text())
                source_ref = record["source_snapshot"]["snapshot_ref"]
                source_file = run.root / source_ref
                if defect == "missing":
                    source_file.unlink()
                elif defect == "tampered":
                    source_file.write_text('{}\n')
                elif defect == "unsafe":
                    source_file.unlink()
                    source_file.symlink_to(paths["request"])
                else:
                    source = json.loads(source_file.read_text())
                    if defect == "malformed":
                        source["files"]["source.txt"]["mode"] = "invalid"
                    else:
                        source["head"] = "f" * 40
                    record["source_snapshot"] = {"snapshot_ref": _seal_evidence(run.root, "source", source)}
                    ref = _seal_record(run.root, "lane", record)
                    receipts = json.loads(paths["receipts"].read_text())
                    receipts[-1]["authoritative_receipt"] = ref
                    self.write(paths["receipts"], receipts)
                before = paths["receipts"].read_bytes()
                result = self.coverage(run, paths, {"security": ref})
                self.assertEqual(2 if defect == "malformed" else 3, result.returncode, result.stderr)
                self.assertEqual({"missing": "missing_evidence", "tampered": "digest_mismatch", "malformed": "invalid_evidence", "wrong-head": "source_scope_mismatch", "unsafe": "unsafe_path"}[defect], json.loads(result.stderr)["error"]["details"]["reason"])
                self.assertEqual(before, paths["receipts"].read_bytes())

    def test_valid_inline_history_is_retained_without_rewriting(self):
        from unittest import mock
        from workflow_kernel import review_closeout as closeout
        run, paths = self.prepare()
        seal = closeout._seal_record

        def inline(root, role, value):
            value = dict(value)
            if role == "lane":
                value["source_snapshot"] = closeout._resolve_snapshot(root, value["source_snapshot"], shared=True)
                value["schema_version"] = 1
            return seal(root, role, value)

        with mock.patch.object(closeout, "_seal_record", side_effect=inline):
            result = closeout.assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=paths["request"], receipts_path=paths["receipts"], input_path=paths["lanes"]["security"], test_harness=True)
        ref = result["record_ref"]
        original = (run.root / ref).read_bytes()
        self.assertEqual(1, json.loads(original)["schema_version"])
        self.assertEqual(0, self.coverage(run, paths, {"security": ref}).returncode)
        retained = self.preserve(run, paths)
        self.assertEqual("complete", retained["status"])
        self.assertEqual(original, (Path(retained["evidence_path"]) / ref).read_bytes())
        self.assertEqual(ref, self.lane(run, paths))
        run.finish("succeeded", retain_diagnostics=True)

    def test_terminal_revalidates_shared_snapshot_closure(self):
        from workflow_kernel.review_closeout import has_preserved_review_evidence
        run, paths = self.prepare()
        ref = self.lane(run, paths)
        self.assertEqual(0, self.coverage(run, paths, {"security": ref}).returncode)
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        retained = Path(result["evidence_path"])
        source_ref = json.loads((retained / ref).read_text())["source_snapshot"]["snapshot_ref"]
        source_file = retained / source_ref
        original = source_file.read_bytes()
        for bad_bytes in (None, b"{}\n"):
            if bad_bytes is None:
                source_file.unlink()
            else:
                source_file.write_bytes(bad_bytes)
            self.assertFalse(has_preserved_review_evidence(run.root / "diagnostic"))
            source_file.write_bytes(original)
        self.assertTrue(has_preserved_review_evidence(run.root / "diagnostic"))
        run.finish("succeeded", retain_diagnostics=True)

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
        lanes = ("security", "patterns")
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _working_patch, _resolve_snapshot
        run, paths = self.prepare(("security", "patterns"))
        records = {lane: self.lane(run, paths, lane) for lane in ("security", "patterns")}
        _, head = source_identity(self.repo)
        snapshots = [_resolve_snapshot(run.root, json.loads((run.root / records["security"]).read_text())["source_snapshot"], shared=True)]
        chain, transitions = [records["security"]], []
        for number in (1, 2):
            (self.repo / "source.txt").write_text(f"uncommitted repair {number}\n")
            snapshots.append(_source_snapshot(self.repo, head, live=True))
            before, after = snapshots[-2], snapshots[-1]
            worktree_ref, patch_ref = f"review/worktree-{number}.patch", f"review/commit-{number}.patch"
            (run.root / worktree_ref).write_bytes(_working_patch(self.repo, head))
            (run.root / patch_ref).write_bytes(b"")
            selection_ref = f"review/selection-{number}.json"
            iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref, "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["security"], "lanes_skipped": [lane for lane in lanes if lane != "security"], "rerun_reasons": {"security": ["a_prior_unresolved_finding", "b_fix_file_trigger"]}, "selection_fallback_reason": None}
            self.write(run.root / selection_ref, {"schema_version": 1, "selected_full_set": list(lanes), "applied": True, "iteration": iteration, "finding_owner_lanes": ["security"], "file_trigger_lanes": ["security"], "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": worktree_ref})
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

    def test_nine_lane_pending_two_pass_producer_and_closeout(self):
        """Synthetic e605 -> 64 -> DD shape; no Governance consumer claim."""
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _git_patch, _seal_evidence
        code = ["patterns", "simplicity", "testcoverage", "gobuild"]
        carried = ["security", "architecture", "second"]
        docs = ["docsync", "voice"]
        lanes = code + carried + docs
        doc_paths = ["readiness.md", "receipt.md"]
        for path in doc_paths:
            (self.repo / path).write_text("original documentation\n")
        subprocess.run(["git", "-C", str(self.repo), "add", *doc_paths], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "synthetic documentation foundation"], check=True)
        run, paths = self.prepare(lanes)
        original_head = source_identity(self.repo)[1]
        originals = {}
        for lane in lanes:
            value = json.loads(paths["lanes"][lane].read_text())
            value["source"]["base"] = original_head
            scope = doc_paths if lane in docs else ["source.txt"]
            value["requested"].update(designation="scoped", paths=scope)
            value["inspected"]["paths"] = scope
            self.write(paths["lanes"][lane], value)
            originals[lane] = self.lane(run, paths, lane)
        original_bytes = {ref: (run.root / ref).read_bytes() for ref in originals.values()}
        before = _source_snapshot(self.repo, original_head)

        def transition(number, before, rerun, skipped, pending, changed):
            for path in changed:
                (self.repo / path).write_text(f"synthetic repair {number}\n")
            subprocess.run(["git", "-C", str(self.repo), "add", *changed], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", f"synthetic repair {number}"], check=True)
            head = source_identity(self.repo)[1]
            after = _source_snapshot(self.repo, head)
            request = json.loads(paths["request"].read_text())
            request["source_head"] = head
            paths["request"] = self.write(run.root / f"review/request-{number}.json", request)
            patch_ref = f"review/patch-{number}.bin"
            (run.root / patch_ref).write_bytes(_git_patch(self.repo, before["head"], head))
            selection_ref = f"review/selection-{number}.json"
            iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref, "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": rerun, "lanes_skipped": skipped, "lanes_pending": pending, "rerun_reasons": {lane: ["b_fix_file_trigger"] for lane in rerun}, "selection_fallback_reason": None}
            sources = {"from_source": {"snapshot_ref": _seal_evidence(run.root, "source", before)}, "to_source": {"snapshot_ref": _seal_evidence(run.root, "source", after)}}
            common = dict(schema_version=2, **sources, changed_paths=_changed_paths(before, after), patch_ref=patch_ref, worktree_ref=None)
            self.write(run.root / selection_ref, dict(common, selected_full_set=lanes, applied=True, iteration=iteration, finding_owner_lanes=pending, file_trigger_lanes=rerun + pending))
            ref = f"review/transition-{number}.json"
            self.write(run.root / ref, dict(common, selection_ref=selection_ref))
            return after, selection_ref, ref

        def recheck(lane, number, selection_ref, pending_refs):
            value = json.loads(paths["lanes"][lane].read_text())
            value.update(pass_id=f"recheck-{number}", attempt=2)
            value["source"].update(head=source_identity(self.repo)[1], request_ref=paths["request"].relative_to(run.root).as_posix())
            output_ref = f"raw/{lane}-{number}.md"
            (run.root / output_ref).write_text(f"Synthetic fresh {lane} judgment at pass {number}.\n")
            value["literal"]["output_ref"] = output_ref
            patch_ref = f"review/{lane}-{number}-cumulative.bin"
            (run.root / patch_ref).write_bytes(_git_patch(self.repo, original_head, value["source"]["head"], value["requested"]["paths"]))
            value["requested"].update(patch_ref=patch_ref)
            value["requested"]["evidence_refs"].append(patch_ref)
            value["requested"]["required_evidence_refs"].append(patch_ref)
            value["inspected"]["basis"] = "patch"
            value["recheck"] = dict(prior_record_ref=originals[lane], selection_ref=selection_ref, repair_refs=[patch_ref], pending_transition_refs=pending_refs)
            path = self.write(run.root / f"review/{lane}-{number}.json", value)
            result = self.cli(run, paths, path)
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)["record_ref"], path, value

        middle, first_selection, first_transition = transition(1, before, code, carried, docs, ["source.txt", *doc_paths])
        current = {lane: recheck(lane, 1, first_selection, [])[0] for lane in code}
        # Pending documentation cannot be carried as skipped, even with CLEAN prose.
        partial = [{"lane": lane, "record_ref": current.get(lane, originals[lane]), "history_refs": [originals[lane]] if lane in code else [], "transition_refs": [] if lane in code else [first_transition]} for lane in lanes]
        result = self.coverage(run, paths, {}, pass_id="unsettled", selection=partial)
        self.assertEqual(3, result.returncode)
        # Selection partition, trigger and overlap invariants fail before append.
        selection_path = run.root / first_selection
        saved_selection = selection_path.read_bytes()
        from workflow_kernel.review_closeout import _validate_selection
        for mutation in ({"lanes_pending": []}, {"lanes_pending": docs + [code[0]]}, {"lanes_skipped": carried + docs, "lanes_pending": []}, {"lanes_pending": docs + ["foreign"]}):
            with self.subTest(mutation=mutation):
                bad = json.loads(saved_selection)
                bad["iteration"].update(mutation)
                self.write(selection_path, bad)
                with self.assertRaises(ValueError):
                    _validate_selection(run.root, first_selection, lanes, before=before, after=middle, repository=self.repo)
        selection_path.write_bytes(saved_selection)
        final, final_selection, final_transition = transition(2, middle, docs, code + carried, [], doc_paths)
        # A valid skipped/unaffected selection is still invalid in a pending chain.
        from workflow_kernel.review_closeout import _transition_chain
        skipped_doc = json.loads(saved_selection)
        skipped_doc["iteration"].update(lanes_pending=[], lanes_skipped=carried + docs)
        skipped_doc.update(finding_owner_lanes=[], file_trigger_lanes=code)
        self.write(selection_path, skipped_doc)
        with self.assertRaises(ValueError):
            _transition_chain(run.root, [first_transition], before, middle, docs[0], lanes, self.repo, None, pending=True)
        selection_path.write_bytes(saved_selection)
        current_docs = {}
        for lane in docs:
            record, input_path, value = recheck(lane, 2, final_selection, [first_transition])
            current_docs[lane] = record
            receipt_bytes = paths["receipts"].read_bytes()
            # Same logical attempt with a changed pending chain is an append conflict.
            value["recheck"]["pending_transition_refs"] = []
            self.write(input_path, value)
            rejected = self.cli(run, paths, input_path)
            self.assertEqual("append_conflict", json.loads(rejected.stderr)["error"]["details"]["reason"])
            self.assertEqual(receipt_bytes, paths["receipts"].read_bytes())
            # A fresh attempt cannot omit, reverse, duplicate or carry a pending chain.
            for refs in ([final_transition], [first_transition, final_transition], [first_transition, first_transition]):
                bad = json.loads(json.dumps(value))
                bad.update(pass_id="invalid-pending", attempt=3)
                bad["recheck"]["pending_transition_refs"] = refs
                rejected = self.cli(run, paths, self.write(input_path, bad))
                self.assertEqual(2 if len(refs) != len(set(refs)) else 3, rejected.returncode, rejected.stderr)
                self.assertEqual(receipt_bytes, paths["receipts"].read_bytes())
            for mutation in ("wrong_selection", "wrong_base", "reduced_scope"):
                with self.subTest(mutation=mutation):
                    bad = json.loads(json.dumps(value))
                    bad.update(pass_id="invalid-pending-" + mutation, attempt=3)
                    bad["recheck"]["pending_transition_refs"] = [first_transition]
                    if mutation == "wrong_selection":
                        bad["recheck"]["selection_ref"] = first_selection
                    elif mutation == "wrong_base":
                        bad["source"]["base"] = middle["head"]
                    else:
                        bad["requested"]["paths"] = bad["inspected"]["paths"] = doc_paths[:1]
                    rejected = self.cli(run, paths, self.write(input_path, bad))
                    self.assertEqual(3, rejected.returncode, rejected.stderr)
                    self.assertEqual(receipt_bytes, paths["receipts"].read_bytes())
        final_rows = [{"lane": lane, "record_ref": current_docs.get(lane, current.get(lane, originals[lane])), "history_refs": [originals[lane]] if lane in code + docs else [], "transition_refs": [] if lane in docs else [final_transition] if lane in code else [first_transition, final_transition]} for lane in lanes]
        # Neither a partial roster nor an unresolved original judgment can settle.
        self.assertEqual(2, self.coverage(run, paths, {}, pass_id="final", selection=final_rows[:-1]).returncode)
        unresolved = json.loads(json.dumps(final_rows))
        unresolved[-1].update(record_ref=originals[docs[-1]], history_refs=[], transition_refs=[first_transition, final_transition])
        self.assertEqual(3, self.coverage(run, paths, {}, pass_id="final", selection=unresolved).returncode)
        # Sealed pending dependencies remain hash-bound even after lane append.
        transition_path = run.root / first_transition
        saved_transition = transition_path.read_bytes()
        transition_path.write_bytes(saved_transition + b"\n")
        rejected = self.coverage(run, paths, {}, pass_id="final", selection=final_rows)
        self.assertEqual("digest_mismatch", json.loads(rejected.stderr)["error"]["details"]["reason"])
        transition_path.write_bytes(saved_transition)
        result = self.coverage(run, paths, {}, pass_id="final", selection=final_rows)
        self.assertEqual(0, result.returncode, result.stderr)
        preserved = self.preserve(run, paths)
        self.assertEqual("complete", preserved["status"], preserved)
        retained = Path(preserved["evidence_path"])
        for ref, data in original_bytes.items():
            self.assertEqual(data, (retained / ref).read_bytes())
        self.assertEqual(saved_transition, (retained / first_transition).read_bytes())
        for ref in current_docs.values():
            record = json.loads((retained / ref).read_text())
            self.assertEqual(original_head, record["input"]["source"]["base"])
            self.assertEqual(doc_paths, record["input"]["inspected"]["paths"])
            for binding in record["bindings"].values():
                self.assertEqual(binding["digest"], "sha256:" + hashlib.sha256((retained / binding["retained_ref"]).read_bytes()).hexdigest())
        print("SYNTHETIC pending lifecycle: nine lanes; rerun4/skipped3/pending2 then rerun2/skipped7; original bytes retained; no live Governance claim.")

    def test_pending_optional_fields_leave_original_envelopes_unchanged(self):
        from workflow_kernel.dm_review_adapter import validate_evidence_input, ReviewRequest, translate_review_receipts
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        original = json.loads(json.dumps(value))
        request = ReviewRequest.from_mapping(json.loads(paths["request"].read_text()))
        validate_evidence_input(value, request)
        self.assertEqual(original, value)
        value["recheck"]["pending_transition_refs"] = []
        validate_evidence_input(value, request)
        value["recheck"]["pending_transition_refs"] = ["review/transition.json"]
        with self.assertRaises(ValueError):
            validate_evidence_input(value, request)
        iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": "review/selection.json", "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["code"], "lanes_skipped": ["security"], "rerun_reasons": {"code": ["b_fix_file_trigger"]}, "selection_fallback_reason": None}
        translate_review_receipts([iteration])
        self.assertNotIn("lanes_pending", iteration)
        pending = dict(iteration, lanes_pending=["docs"])
        events = translate_review_receipts([pending])
        self.assertEqual(("docs",), events[0].payload["lanes_pending"])
        for lanes_pending in (["code"], ["security"], ["docs", "docs"], None, "docs"):
            with self.subTest(lanes_pending=lanes_pending), self.assertRaises(ValueError):
                translate_review_receipts([dict(iteration, lanes_pending=lanes_pending)])

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
