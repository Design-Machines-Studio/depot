from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workflow_kernel.dm_review_adapter import (
    _document_digest,
    ReviewRequest,
    validate_optional_contribution_coverage,
)
from workflow_kernel.cli import _validated_existing_review_contributions
from workflow_kernel.owned_run import ExactOwnedRun
from workflow_kernel.review_closeout import (
    ReviewCloseoutValidationError,
    bind_review_source,
    preserve_review_evidence,
    source_identity, assemble_review_evidence, EvidenceAssemblyError,
)
from workflow_kernel.schema import ErrorMessage


class ReviewCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "disposable-repository"
        self.repo.mkdir()
        subprocess.run(("git", "init", "--quiet", str(self.repo)), check=True)
        subprocess.run(("git", "-C", str(self.repo), "config", "user.name", "Fixture"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "config", "user.email", "fixture@example.test"), check=True)
        (self.repo / "source.txt").write_text("reviewed source\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "fixture"), check=True)
        self.state = self.root / "state"
        self.state.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def make_run(self, workflow="dm-review", run_id="closeout", *, legacy=False, synthetic=False):
        run = ExactOwnedRun.start(workflow, run_id, base=self.state)
        source = run.create_path("raw-output", "review")
        run.create_path("raw-output", "receipts")
        run.create_path("raw-output", "receipts/private")
        router = run.create_path("raw-output", "receipts/private/router")
        (router / "terminal-receipt-index.json").write_text(
            json.dumps({"schemaVersion": 1, "receiptFiles": ["security.json"]}) + "\n", encoding="utf-8",
        )
        (router / "security.json").write_text(
            json.dumps({
                "schemaVersion": 1, "receiptId": "dispatch-" + "a" * 24,
                "requested": {}, "attempts": [], "served": None, "fallback": False,
            }) + "\n",
            encoding="utf-8",
        )
        repository, head = source_identity(self.repo)
        request = {
            "run_id": run_id,
            "requested_lanes": ["security"],
            "mode": "full",
            "source_repository": repository,
            "source_head": head,
        }
        output = {"reviewer": "security", "lane": "security", "findings": []}
        output_digest = _document_digest(output)
        lane_receipt = {
            "reviewer": "security", "lane": "security",
            "requested_provider": "openai", "attempted_provider": "openai",
            "implemented_by": "codex", "provider": "openai",
            "model": "gpt-6.1-sol", "evidence_refs": ["raw/security.md"],
            "implementer_family": "openai", "reviewer_family": "openai",
            "resolution_reason": "same-family-standard-review",
            "raw_output_ref": (
                "contribution-inputs/raw-lane-output-sha256-"
                + output_digest.removeprefix("sha256:") + ".json"
            ),
            "raw_output_digest": output_digest,
            "finding_count": 0,
        }
        receipts = [
            {
                "run_id": run_id, "sequence": 0, "stage": "review_request",
                "status": "accepted", "node_id": None,
                "occurred_at": "2026-09-01T00:00:00Z",
                "authoritative_receipt": "review/request.json", "host": "codex",
                "workflow_class": "feature", "requested_lanes": ["security"],
            },
            {
                "run_id": run_id, "sequence": 1, "stage": "coverage_matrix",
                "status": "complete", "node_id": None,
                "occurred_at": "2026-09-01T00:01:00Z",
                "authoritative_receipt": "review/coverage.json", "host": "codex",
                "expected_lanes": ["security"], "completed_lanes": ["security"],
                "degraded_lanes": [], "unavailable_lanes": [],
            },
        ]
        paths = {
            "request": source / "request.json",
            "receipts": source / "authoritative-receipts.json",
            "lane_receipts": source / "review-lane-receipts.json",
            "raw_lane_outputs": source / "raw-lane-outputs.json",
            "raw_findings": source / "raw-finding-inventory.json",
            "decisions": source / "synthesis-decisions.json",
            "router": router,
        }
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        (source / "coverage.json").write_text("{}\n", encoding="utf-8")
        referenced = run.root / "raw" / "security.md"
        referenced.parent.mkdir(parents=True, exist_ok=True)
        referenced.write_text("Security lane evidence.\n", encoding="utf-8")
        receipts[0]["source_repository"] = repository
        receipts[0]["source_head"] = head
        receipts[1]["source_repository"] = repository
        receipts[1]["source_head"] = head
        receipts[1]["required_browser_cases"] = []
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        paths["lane_receipts"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "review_lane_receipts",
            "run_id": run_id, "lanes": [lane_receipt],
        }) + "\n", encoding="utf-8")
        paths["raw_lane_outputs"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "review_lane_raw_outputs",
            "run_id": run_id, "outputs": [output],
        }) + "\n", encoding="utf-8")
        paths["raw_findings"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "raw_finding_inventory",
            "run_id": run_id, "findings": [],
        }) + "\n", encoding="utf-8")
        paths["decisions"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "synthesis_decisions",
            "run_id": run_id, "source_finding_count": 0,
            "occurred_at": "2026-09-01T00:01:30Z", "decisions": [],
        }) + "\n", encoding="utf-8")
        report = self.repo / ".claude" / "ux-review" / "report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "## CLEAN\n\nRequired review coverage is complete. "
            "[Lane outputs](review/raw-lane-outputs.json).\n",
            encoding="utf-8",
        )
        paths["report"] = report
        if not legacy:
            # Production-shaped test data exercises the production boundary;
            # it is never external participant proof. Explicit synthetic
            # assembler fixtures keep their separate, honest provenance.
            if not synthetic:
                (router / "security.json").write_text(json.dumps({
                    "schemaVersion": 1, "receiptId": "dispatch-" + "a" * 24,
                    "requested": {}, "fallback": False,
                    "served": {"model": lane_receipt["model"], "provider": lane_receipt["provider"], "family": lane_receipt["reviewer_family"]},
                    "attempts": [{"status": "completed"}],
                    "publication": {"output": "published"}, "transportStub": False,
                }) + "\n")
            paths["receipts"].write_text("[]\n")
            for key in ("lane_receipts", "raw_lane_outputs", "raw_findings", "decisions"):
                paths[key].unlink()
            paths["request"].write_text(json.dumps(ReviewRequest.from_mapping(request).to_dict()) + "\n")
            (source / "companion.json").write_text(json.dumps(lane_receipt) + "\n")
            (source / "prompt.md").write_text("Inspect source.txt in the disposable repository.\n")
            lane_input = {
                "schema_version": 1, "operation": "lane", "run_id": run_id,
                "pass_id": "initial", "lane": "security", "attempt": 1, "reviewer": "security",
                "source": {"repository": repository, "head": head, "base": head, "worktree_ref": None, "request_ref": "review/request.json"},
                "requested": {"designation": "full", "patch_ref": None, "paths": ["source.txt"], "evidence_refs": ["review/prompt.md"], "required_evidence_refs": ["review/prompt.md"]},
                "inspected": {"paths": ["source.txt"], "basis": "repository", "limitations": [], "missing_evidence_refs": []},
                "literal": {"output_ref": "raw/security.md", "dispatch_receipt_ref": "receipts/private/router/security.json", "companion_ref": "review/companion.json"},
                "result": {"status": "no_findings", "findings": [], "incomplete_reasons": []},
                "provenance": {"kind": "synthetic_test" if synthetic else "live", "executed_at": None if synthetic else "2026-09-01T00:01:00Z", "source_refs": ["review/prompt.md"]},
                "recheck": {"prior_record_ref": None, "selection_ref": None, "repair_refs": []},
            }
            paths["input"] = source / "lane-input.json"
            paths["input"].write_text(json.dumps(lane_input) + "\n")
            lane_result = assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=paths["request"], receipts_path=paths["receipts"], input_path=paths["input"], test_harness=synthetic)
            paths["record_ref"] = lane_result["record_ref"]
            coverage = {"schema_version": 1, "operation": "coverage", "run_id": run_id, "pass_id": "initial",
                        "selection": [{"lane": "security", "record_ref": lane_result["record_ref"], "history_refs": [], "transition_refs": []}],
                        "decisions": [], "occurred_at": "2026-09-01T00:01:30Z", "required_case_refs": [], "resolutions": []}
            paths["coverage_input"] = source / "coverage-input.json"
            paths["coverage_input"].write_text(json.dumps(coverage) + "\n")
            assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=paths["request"], receipts_path=paths["receipts"], input_path=paths["coverage_input"], test_harness=synthetic)
        return run, paths

    def preserve(self, run, paths):
        return preserve_review_evidence(
            run_root=run.root,
            repository_root=self.repo,
            request_path=paths["request"],
            receipts_path=paths["receipts"],
            lane_receipts_path=paths["lane_receipts"],
            raw_lane_outputs_path=paths["raw_lane_outputs"],
            raw_findings_path=paths["raw_findings"],
            decisions_path=paths["decisions"],
            private_router_directory=paths["router"],
            report_path=paths.get("report"),
        )

    def test_actual_preservation_limits_are_closed_and_atomic(self):
        from tests import KERNEL_REFERENCES
        from workflow_kernel.owned_run import _MAX_DIAGNOSTIC_BYTES, _MAX_DIAGNOSTIC_FILES
        from workflow_kernel.review_closeout import has_preserved_review_evidence

        for kind in ("staging_files", "staging_bytes", "router_files", "router_bytes", "single_file_bytes"):
            for prior in (False, True):
                with self.subTest(kind=kind, prior=prior):
                    run, paths = self.make_run(run_id=f"limit-{kind.replace('_', '-')}-{int(prior)}")
                    first = self.preserve(run, paths)
                    destination = Path(first["evidence_path"])
                    original = {p.relative_to(destination): p.read_bytes()
                                for p in destination.rglob("*") if p.is_file()}
                    if not prior:
                        shutil.rmtree(destination)
                    if kind.endswith("files"):
                        count = (_MAX_DIAGNOSTIC_FILES - first["files"] + 1
                                 if kind == "staging_files" else _MAX_DIAGNOSTIC_FILES + 1)
                        for index in range(count):
                            (paths["router"] / f"extra-{index}.json").write_text("{}")
                    elif kind == "single_file_bytes":
                        paths["report"].write_bytes(b"x" * (_MAX_DIAGNOSTIC_BYTES + 1))
                    else:
                        size = (_MAX_DIAGNOSTIC_BYTES - first["bytes"] + 1
                                if kind == "staging_bytes" else _MAX_DIAGNOSTIC_BYTES + 1)
                        for index, amount in enumerate((size // 2, size - size // 2)):
                            (paths["router"] / f"extra-{index}.json").write_bytes(b"{}" + b" " * (amount - 2))
                    source_bytes = {p.relative_to(run.root): p.read_bytes()
                                    for p in run.root.rglob("*") if p.is_file()}
                    environment = os.environ.copy()
                    environment["PYTHONPATH"] = str(KERNEL_REFERENCES) + os.pathsep + environment.get("PYTHONPATH", "")
                    completed = subprocess.run(
                        (sys.executable, "-m", "workflow_kernel", "preserve-review-evidence",
                         "--run-root", str(run.root), "--repository-root", str(self.repo),
                         "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
                         "--lane-receipts", str(paths["lane_receipts"]),
                         "--raw-lane-outputs", str(paths["raw_lane_outputs"]),
                         "--raw-findings", str(paths["raw_findings"]), "--decisions", str(paths["decisions"]),
                         "--private-router-directory", str(paths["router"]), "--report", str(paths["report"])),
                        env=environment, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(3, completed.returncode, completed.stderr)
                    self.assertEqual("", completed.stdout)
                    self.assertEqual({"error": {
                        "code": "evidence_limit_exceeded",
                        "message": "required review evidence failed validation",
                        "details": {"stage": "preservation_input", "reason": "retention_limit",
                                    "path": "review/evidence.json"},
                    }}, json.loads(completed.stderr))
                    self.assertFalse(list(destination.parent.glob("review-stage-*")))
                    self.assertEqual(prior, destination.exists())
                    if prior:
                        self.assertEqual(original, {p.relative_to(destination): p.read_bytes()
                                                   for p in destination.rglob("*") if p.is_file()})
                    else:
                        self.assertFalse(has_preserved_review_evidence(run.root / "diagnostic"))
                        with self.assertRaises(ValueError):
                            run.finish("succeeded", retain_diagnostics=True)
                    for relative, data in source_bytes.items():
                        self.assertEqual(data, (run.root / relative).read_bytes())

    def test_bound_guard_distinguishes_unsafe_entries_from_exhaustion(self):
        from workflow_kernel.owned_run import BoundedDiagnosticLimitError, _bounded_diagnostic
        from workflow_kernel.review_closeout import _check_evidence_bound
        directory = self.root / "unsafe-diagnostic"
        directory.mkdir()
        (directory / "link").symlink_to(self.repo / "source.txt")
        with self.assertRaises(ValueError) as caught:
            _bounded_diagnostic(directory)
        self.assertNotIsInstance(caught.exception, BoundedDiagnosticLimitError)
        for stage in ("retained_validation", "preservation_input"):
            with self.assertRaises(EvidenceAssemblyError) as caught:
                _check_evidence_bound(directory, stage)
            self.assertEqual(3, caught.exception.exit_code)
            self.assertEqual("unsafe_payload", caught.exception.code)
            self.assertEqual({"stage": stage, "reason": "unsafe_path", "path": "review/evidence.json"},
                             caught.exception.detail())

    def test_absent_companion_is_classified_and_other_inputs_preserved(self):
        run, paths = self.make_run("dm-review", "absent-lane")
        paths["lane_receipts"].unlink()
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertIn({"stage": "preservation_input", "reason": "missing_evidence",
                       "path": "review/review-lane-receipts.json"}, result["diagnostics"])
        self.assertTrue(Path(result["evidence_path"], "review/request.json").is_file())

    def test_missing_evidence_diagnostic_keeps_only_safe_filenames(self):
        from workflow_kernel.review_closeout import _evidence_bytes
        for reference, reason, path in (
            ("review/absent-required.patch", "missing_evidence", "review/absent-required.patch"),
            ("../absent-required.patch", "unsafe_path", "review/evidence.json"),
        ):
            with self.subTest(reference=reference):
                with self.assertRaises(EvidenceAssemblyError) as caught:
                    _evidence_bytes(self.state, reference, "lane_input")
                self.assertEqual({"stage": "lane_input", "reason": reason, "path": path}, caught.exception.detail())
        self.assertEqual("review/evidence.json", EvidenceAssemblyError("lane_input", "missing_evidence", "/etc/passwd").role)

    def test_legacy_companions_cannot_establish_new_terminal_coverage(self):
        run, paths = self.make_run("dm-review", "legacy-terminal", legacy=True)
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertTrue(paths["raw_lane_outputs"].is_file())

    def test_non_ui_request_serializes_an_explicit_empty_browser_case_set(self):
        request = ReviewRequest.from_mapping({
            "run_id": "non-ui", "requested_lanes": ["security"],
            "source_repository": "github.com/acme/widget",
            "source_head": "a" * 40,
        })
        self.assertEqual([], request.to_dict()["required_browser_cases"])

    def test_null_browser_coverage_is_rejected_with_exact_field_and_preserved(self):
        run, paths = self.make_run("dm-review", "null-browser-cases")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[-1]["required_browser_cases"] = None
        original = (json.dumps(receipts) + "\n").encode()
        paths["receipts"].write_bytes(original)

        first = self.preserve(run, paths)
        self.assertEqual("incomplete", first["status"])
        self.assertEqual("invalid_evidence", first["diagnostics"][0]["reason"])
        retained = Path(first["evidence_path"]) / "review/authoritative-receipts.json"
        self.assertEqual(original, retained.read_bytes())

        retry = self.preserve(run, paths)
        self.assertEqual("incomplete", retry["status"])
        self.assertEqual(original, retained.read_bytes())

        corrected = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        corrected[-1]["required_browser_cases"] = []
        paths["receipts"].write_text(json.dumps(corrected) + "\n", encoding="utf-8")
        altered_retry = self.preserve(run, paths)
        self.assertEqual("incomplete", altered_retry["status"])
        self.assertIn(
            "authoritative review receipts changed outside append-only closeout",
            altered_retry["missing"],
        )
        self.assertEqual(original, retained.read_bytes())

    def test_omitted_browser_coverage_is_rejected_and_preserved(self):
        run, paths = self.make_run("dm-review", "omitted-browser-cases")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        del receipts[-1]["required_browser_cases"]
        original = (json.dumps(receipts) + "\n").encode()
        paths["receipts"].write_bytes(original)

        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertEqual("invalid_evidence", result["diagnostics"][0]["reason"])
        retained = Path(result["evidence_path"]) / "review/authoritative-receipts.json"
        self.assertEqual(original, retained.read_bytes())

    def test_required_evidence_survives_successful_closeout_and_worktree_removal(self):
        run, paths = self.make_run()
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        retained = run.finish(
            "succeeded", retain_diagnostics=True,
            reason="review evidence sealed", contains="coverage and lane source evidence",
        )
        self.assertEqual("retained", retained.status)
        evidence = Path(result["evidence_path"])
        shutil.rmtree(self.repo)
        self.assertTrue((evidence / "review/authoritative-receipts.json").is_file())
        self.assertTrue((evidence / "review/raw-lane-outputs.json").is_file())
        self.assertTrue((evidence / "receipts/private/router/security.json").is_file())
        self.assertTrue(list((evidence / "review/evidence").glob("literal-*.bin")))
        self.assertEqual(
            "## CLEAN\n\nRequired review coverage is complete. "
            "[Lane outputs](review/raw-lane-outputs.json).\n",
            (evidence / "report.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(retained.to_dict(), ExactOwnedRun.open(run.root).finish("succeeded").to_dict())

    def test_premature_success_cleanup_cannot_delete_review_evidence(self):
        run, paths = self.make_run()
        original = paths["raw_lane_outputs"].read_bytes()
        with self.assertRaisesRegex(ValueError, "review evidence must be retained"):
            run.finish("succeeded")
        self.assertTrue(run.root.is_dir())
        self.assertEqual(original, paths["raw_lane_outputs"].read_bytes())

    def test_failed_required_finalization_can_be_retained_for_recovery(self):
        run, paths = self.make_run()
        raw = json.loads(paths["raw_lane_outputs"].read_text(encoding="utf-8"))
        raw["outputs"] = []
        paths["raw_lane_outputs"].write_text(json.dumps(raw) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertTrue(result["missing"])
        retained = run.finish(
            "failed", retain_diagnostics=True,
            reason="required lane source is incomplete", contains="available lane receipts and retry inputs",
        )
        self.assertEqual("retained", retained.status)
        self.assertTrue(Path(retained.path, "CLEANUP.txt").is_file())
        self.assertTrue(Path(result["evidence_path"], "review/request.json").is_file())
        self.assertTrue(Path(result["recovery_path"]).is_dir())

    def test_incomplete_bound_coverage_is_retained_in_its_exact_head_scope(self):
        run, paths = self.make_run("dm-review", "bound-incomplete")
        raw = json.loads(paths["raw_lane_outputs"].read_text(encoding="utf-8"))
        raw["outputs"] = []
        paths["raw_lane_outputs"].write_text(json.dumps(raw) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertIn("repo-", Path(result["evidence_path"]).name)
        self.assertIn("-head-", Path(result["evidence_path"]).name)
        self.assertNotEqual("unbound", Path(result["evidence_path"]).name)

    def test_verified_bound_copy_retires_only_superseded_owned_scopes(self):
        run, paths = self.make_run("dm-review", "scope-retry")
        first = self.preserve(run, paths)
        stale = Path(first["recovery_path"]) / "review" / "unbound"
        stale.mkdir(mode=0o700)
        (stale / "incomplete.json").write_text("{}\n", encoding="utf-8")
        second = self.preserve(run, paths)
        self.assertEqual("complete", second["status"])
        self.assertFalse(stale.exists())
        self.assertTrue(Path(second["evidence_path"], "review/request.json").is_file())

    def test_failed_evidence_relocation_leaves_source_intact(self):
        run, paths = self.make_run()
        originals = {key: value.read_bytes() for key, value in paths.items() if isinstance(value, Path) and value.is_file()}
        with mock.patch("workflow_kernel.review_closeout.os.replace", side_effect=OSError("injected relocation failure")):
            with self.assertRaises(OSError):
                self.preserve(run, paths)
        self.assertTrue(run.root.is_dir())
        for key, content in originals.items():
            self.assertEqual(content, paths[key].read_bytes())

    def test_closeout_retry_reuses_exact_evidence_without_duplicate_receipts(self):
        run, paths = self.make_run()
        first = self.preserve(run, paths)
        second = self.preserve(run, paths)
        self.assertEqual("complete", first["status"])
        self.assertEqual(first["evidence_path"], second["evidence_path"])
        receipts = json.loads((Path(second["evidence_path"]) / "review/authoritative-receipts.json").read_text())
        self.assertEqual(3, len(receipts))
        self.assertEqual(1, len(list((Path(second["evidence_path"]) / "receipts/private/router").glob("*.json"))) - 1)

    def test_changed_head_cannot_complete_closeout(self):
        run, paths = self.make_run()
        (self.repo / "source.txt").write_text("changed head\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "changed"), check=True)
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_missing_required_lane_evidence_reference_cannot_complete_closeout(self):
        run, paths = self.make_run("dm-review", "missing-evidence-ref")
        record = json.loads((run.root / paths["record_ref"]).read_text())
        retained_ref = record["bindings"]["raw/security.md"]["retained_ref"]
        (run.root / retained_ref).unlink()
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertIn("missing_evidence", result["missing"])
        self.assertIn({"stage": "retained_validation", "reason": "missing_evidence",
                       "path": retained_ref}, result["diagnostics"])

    def test_assembler_missing_paths_name_safe_relative_files_only(self):
        run, paths = self.make_run("dm-review", "assembler-missing-paths")
        arguments = dict(run_root=run.root, repository_root=self.repo, request_path=paths["request"],
                         receipts_path=paths["receipts"], input_path=paths["input"], test_harness=True)
        for key, path, reason, role in (
            ("request_path", run.root / "review/absent-request.json", "missing_evidence", "review/absent-request.json"),
            ("input_path", run.root / "review/absent-input.json", "missing_evidence", "review/absent-input.json"),
            ("receipts_path", run.root / "review/absent-receipts.json", "missing_evidence", "review/absent-receipts.json"),
            ("input_path", run.root / "review/ghp_abcdefgh12345678.json", "missing_evidence", "review/evidence.json"),
            ("input_path", self.root / "outside-input.json", "unsafe_path", "review/evidence.json"),
        ):
            with self.subTest(key=key, path=path.name):
                with self.assertRaises(EvidenceAssemblyError) as caught:
                    assemble_review_evidence(**dict(arguments, **{key: path}))
                self.assertEqual({"stage": "lane_input", "reason": reason, "path": role}, caught.exception.detail())
        external = self.root / "external-input.json"
        external.write_text("{}\n")
        (run.root / "review/linked-input.json").symlink_to(external)
        with self.assertRaises(EvidenceAssemblyError) as caught:
            assemble_review_evidence(**dict(arguments, input_path=run.root / "review/linked-input.json"))
        self.assertEqual({"stage": "lane_input", "reason": "unsafe_path", "path": "review/evidence.json"}, caught.exception.detail())

    def test_preservation_diagnostics_use_actual_safe_inputs_and_keep_destination_atomic(self):
        run, paths = self.make_run(run_id="preserve-input-paths")
        first = self.preserve(run, paths)
        destination = Path(first["evidence_path"])
        original = {p.relative_to(destination): p.read_bytes()
                    for p in destination.rglob("*") if p.is_file()}
        for key, path, reason, role in (
            ("request", run.root / "review/absent-final-request.json", "missing_evidence", "review/absent-final-request.json"),
            ("lane_receipts", run.root / "review/absent-pass-lanes.json", "missing_evidence", "review/absent-pass-lanes.json"),
            ("receipts", run.root / "review/absent-final-receipts.json", "missing_evidence", "review/absent-final-receipts.json"),
            ("raw_lane_outputs", run.root / "review/absent-pass-outputs.json", "missing_evidence", "review/absent-pass-outputs.json"),
            ("raw_findings", run.root / "review/absent-pass-findings.json", "missing_evidence", "review/absent-pass-findings.json"),
            ("decisions", run.root / "review/absent-pass-decisions.json", "missing_evidence", "review/absent-pass-decisions.json"),
            ("report", run.root / "review/absent-final-report.md", "missing_evidence", "review/absent-final-report.md"),
            ("report", self.repo / "review/absent-final-report.md", "missing_evidence", "review/absent-final-report.md"),
            ("request", self.root / "secret-foreign-request.json", "unsafe_path", "review/request.json"),
            ("request", run.root / "review/ghp_abcdefgh12345678.json", "missing_evidence", "review/evidence.json"),
        ):
            with self.subTest(key=key, role=role):
                result = self.preserve(run, dict(paths, **{key: path}))
                self.assertEqual("incomplete", result["status"])
                self.assertIn({"stage": "preservation_input", "reason": reason, "path": role}, result["diagnostics"])
                self.assertNotIn(str(self.root), json.dumps(result["diagnostics"]))
                self.assertNotIn("secret-foreign", json.dumps(result["diagnostics"]))
                self.assertEqual(original, {p.relative_to(destination): p.read_bytes()
                                           for p in destination.rglob("*") if p.is_file()})
        # Pass-specific source names still bind canonical retained destinations.
        copied = dict(paths)
        for key in ("request", "lane_receipts", "report"):
            copied[key] = run.root / ("review/final-" + paths[key].name)
            shutil.copyfile(paths[key], copied[key])
        result = self.preserve(run, copied)
        self.assertEqual("complete", result["status"])
        self.assertEqual(first["evidence_path"], result["evidence_path"])
        self.assertEqual(paths["request"].read_bytes(), (destination / "review/request.json").read_bytes())
        self.assertEqual(paths["lane_receipts"].read_bytes(), (destination / "review/review-lane-receipts.json").read_bytes())

    def test_missing_router_directory_names_its_relative_path(self):
        run, paths = self.make_run("dm-review", "absent-router")
        shutil.rmtree(paths["router"])
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertIn({"stage": "preservation_input", "reason": "missing_evidence",
                       "path": "receipts/private/router"}, result["diagnostics"])

    def test_mismatched_lane_output_digest_cannot_complete_closeout(self):
        run, paths = self.make_run("dm-review", "mismatched-lane-digest")
        lane_document = json.loads(paths["lane_receipts"].read_text(encoding="utf-8"))
        lane_document["lanes"][0]["raw_output_digest"] = "sha256:" + "0" * 64
        paths["lane_receipts"].write_text(
            json.dumps(lane_document) + "\n", encoding="utf-8",
        )
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertTrue(result["missing"])

    def test_symlinked_review_evidence_reference_cannot_complete_closeout(self):
        run, paths = self.make_run("dm-review", "symlink-evidence-ref")
        external = self.root / "external-review-evidence.md"
        external.write_text("external evidence\n", encoding="utf-8")
        (run.root / "review" / "linked-evidence.md").symlink_to(external)
        lane_document = json.loads(paths["lane_receipts"].read_text(encoding="utf-8"))
        lane_document["lanes"][0]["evidence_refs"] = ["review/linked-evidence.md"]
        paths["lane_receipts"].write_text(
            json.dumps(lane_document) + "\n", encoding="utf-8",
        )
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertIn("digest_mismatch", result["missing"])
        self.assertFalse(Path(result["evidence_path"], "review/linked-evidence.md").exists())

    def test_report_link_escape_and_foreign_owned_run_remain_rejected(self):
        run, paths = self.make_run("dm-review", "report-escape")
        (run.root / "outside-report-target.md").write_text("outside\n", encoding="utf-8")
        paths["report"].write_text(
            "[Outside](../../../outside-report-target.md).\n", encoding="utf-8",
        )
        with self.assertRaises(ReviewCloseoutValidationError) as caught:
            self.preserve(run, paths)
        error = caught.exception.to_dict()["error"]
        self.assertEqual("unsafe_payload", error["code"])
        self.assertEqual("review_report_link_escapes_scope", error["details"]["reason_code"])
        self.assertNotIn("path", error["details"])

        foreign = self.root / "foreign-run-root"
        foreign.mkdir()
        with self.assertRaises(OSError):
            preserve_review_evidence(
                run_root=foreign,
                repository_root=self.repo,
                request_path=paths["request"],
                receipts_path=paths["receipts"],
                lane_receipts_path=paths["lane_receipts"],
                raw_lane_outputs_path=paths["raw_lane_outputs"],
                raw_findings_path=paths["raw_findings"],
                decisions_path=paths["decisions"],
                private_router_directory=paths["router"],
                report_path=paths["report"],
            )

    def test_nul_encoded_report_link_has_closed_unsafe_target_error(self):
        run, paths = self.make_run("dm-review", "report-nul-link")
        paths["report"].write_text(
            "[Invalid](%00target.md).\n", encoding="utf-8",
        )
        with self.assertRaises(ReviewCloseoutValidationError) as caught:
            self.preserve(run, paths)
        error = caught.exception.to_dict()["error"]
        self.assertEqual("unsafe_payload", error["code"])
        self.assertEqual(
            "review_report_link_target_unsafe",
            error["details"]["reason_code"],
        )
        self.assertEqual("report.md", error["details"]["field"])
        self.assertNotIn("path", error["details"])

    def test_source_binding_rejects_changed_head_without_rewriting_the_request(self):
        run, paths = self.make_run("dm-review", "stale-source")
        before = paths["request"].read_bytes()
        (self.repo / "source.txt").write_text("new HEAD\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "new head"), check=True)
        with self.assertRaisesRegex(ValueError, "source scope is stale"):
            bind_review_source(
                run_root=run.root, repository_root=self.repo, request_path=paths["request"],
            )
        self.assertEqual(before, paths["request"].read_bytes())

    def test_bind_review_source_cli_persists_identity_before_dispatch(self):
        run, paths = self.make_run("dm-review", "bind-cli")
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request.pop("source_repository")
        request.pop("source_head")
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        environment = os.environ.copy()
        references = Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references"
        environment["PYTHONPATH"] = str(references) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            (
                sys.executable, "-m", "workflow_kernel", "bind-review-source",
                "--run-root", str(run.root), "--repository-root", str(self.repo),
                "--request", str(paths["request"]),
            ), env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        bound = json.loads(paths["request"].read_text(encoding="utf-8"))
        repository, head = source_identity(self.repo)
        self.assertEqual(repository, result["source_repository"])
        self.assertEqual(head, result["source_head"])
        self.assertEqual(repository, bound["source_repository"])
        self.assertEqual(head, bound["source_head"])

    def test_mismatched_browser_cases_cannot_complete_closeout(self):
        run, paths = self.make_run()
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request["required_lanes"] = ["security", "visual"]
        request["requested_lanes"] = ["security", "visual"]
        request["required_browser_cases"] = ["home", "settings"]
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        repository, head = source_identity(self.repo)
        outputs = json.loads(paths["raw_lane_outputs"].read_text(encoding="utf-8"))
        visual_output = {"reviewer": "visual", "lane": "visual", "findings": []}
        visual_digest = _document_digest(visual_output)
        outputs["outputs"].append(visual_output)
        paths["raw_lane_outputs"].write_text(json.dumps(outputs) + "\n", encoding="utf-8")
        lane_document = json.loads(paths["lane_receipts"].read_text(encoding="utf-8"))
        visual_receipt = dict(lane_document["lanes"][0])
        visual_receipt.update({
            "reviewer": "visual", "lane": "visual",
            "raw_output_digest": visual_digest,
            "raw_output_ref": (
                "contribution-inputs/raw-lane-output-sha256-"
                + visual_digest.removeprefix("sha256:") + ".json"
            ),
        })
        lane_document["lanes"].append(visual_receipt)
        paths["lane_receipts"].write_text(json.dumps(lane_document) + "\n", encoding="utf-8")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[1]["requested_lanes"] = ["security", "visual"]
        receipts[1]["source_repository"] = repository
        receipts[1]["source_head"] = head
        receipts[2]["expected_lanes"] = ["security", "visual"]
        receipts[2]["completed_lanes"] = ["security", "visual"]
        receipts[2]["source_repository"] = repository
        receipts[2]["source_head"] = head
        receipts[2]["required_browser_cases"] = ["home", "settings"]
        receipts.append({
            "run_id": request["run_id"], "sequence": 3,
            "stage": "browser_verification", "status": "completed",
            "node_id": "visual", "occurred_at": "2026-09-01T00:02:00Z",
            "authoritative_receipt": "review/browser.json", "host": "codex",
            "source_repository": repository, "source_head": head,
            "case_ids": ["home"], "evidence_refs": ["browser/case-home.json"],
        })
        (self.repo / "browser").mkdir(parents=True, exist_ok=True)
        (self.repo / "browser/case-home.json").write_text("{}\n", encoding="utf-8")
        review_directory = paths["request"].parent
        (review_directory / "browser.json").write_text("{}\n", encoding="utf-8")
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_browser_case_relabel_without_new_aggregate_is_rejected(self):
        run, paths = self.make_run("dm-review", "browser-after-coverage")
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request["required_browser_cases"] = ["home"]
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[2]["required_browser_cases"] = ["home"]
        receipts.append({
            "run_id": request["run_id"], "sequence": 3,
            "stage": "browser_verification", "status": "completed",
            "node_id": "visual", "occurred_at": "2026-09-01T00:02:00Z",
            "authoritative_receipt": "review/browser.json", "host": "codex",
            "source_repository": request["source_repository"],
            "source_head": request["source_head"],
            "case_ids": ["home"], "evidence_refs": ["browser/case-home.json"],
        })
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        (paths["request"].parent / "browser.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "browser").mkdir()
        (self.repo / "browser/case-home.json").write_text("{}\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])

    def test_optional_contribution_cost_and_observation_outputs_do_not_gate_coverage(self):
        run, paths = self.make_run()
        self.assertFalse(validate_optional_contribution_coverage([]))
        request = ReviewRequest.from_mapping(json.loads(paths["request"].read_text()))
        receipts = json.loads(paths["receipts"].read_text())
        self.assertIsNone(_validated_existing_review_contributions(request, receipts, self.state))
        # No cost summary, shadow comparison, or observation index is required
        # by the source coverage validator.
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_failed_optional_contribution_receipt_does_not_downgrade_coverage(self):
        run, paths = self.make_run()
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts.append({"sequence": 3, "stage": "finding_contribution", "status": "failed"})
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        retained_receipts = json.loads(
            (Path(result["evidence_path"]) / "review/authoritative-receipts.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(receipts, retained_receipts)

    def test_unvalidated_later_coverage_cannot_override_incomplete_coverage(self):
        run, paths = self.make_run("dm-review", "malformed-recheck")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[2]["completed_lanes"] = []
        receipts[2]["unavailable_lanes"] = ["security"]
        receipts.append({"stage": "finding_contribution", "status": "failed"})
        receipts.append({
            "stage": "coverage_matrix", "expected_lanes": ["security"],
            "completed_lanes": ["security"], "degraded_lanes": [],
            "unavailable_lanes": [], "source_repository": receipts[2]["source_repository"],
            "source_head": receipts[2]["source_head"], "required_browser_cases": [],
        })
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_valid_recheck_after_optional_contribution_can_complete(self):
        run, paths = self.make_run("dm-review", "valid-recheck")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[2]["completed_lanes"] = []
        receipts[2]["unavailable_lanes"] = ["security"]
        receipts.append({"stage": "finding_contribution", "status": "failed"})
        final = dict(receipts[2])
        final.update({
            "sequence": 4, "occurred_at": "2026-09-01T00:03:00Z",
            "completed_lanes": ["security"], "unavailable_lanes": [],
        })
        receipts.append(final)
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_broken_report_link_blocks_successful_preservation_and_keeps_source(self):
        run, paths = self.make_run()
        paths["report"].write_text(
            "## CLEAN\n\n[Missing evidence](review/missing.md).\n",
            encoding="utf-8",
        )
        with self.assertRaises(ReviewCloseoutValidationError) as caught:
            self.preserve(run, paths)
        error = caught.exception.to_dict()["error"]
        self.assertEqual("missing_evidence", error["code"])
        self.assertEqual("review_report_link_missing", error["details"]["reason_code"])
        self.assertEqual("report.md", error["details"]["field"])
        self.assertEqual("review/missing.md", error["details"]["path"])
        self.assertEqual(ErrorMessage.REVIEW_REPORT_LINK_MISSING.value, error["message"])
        self.assertTrue(paths["report"].is_file())
        with self.assertRaisesRegex(ValueError, "durably validated"):
            run.finish("succeeded", retain_diagnostics=True)

    def test_report_links_resolve_from_retained_scope_root_and_retry_idempotently(self):
        run, paths = self.make_run("dm-review", "retained-report-layout")
        review_source = run.root / "review"
        for name, text in (
            ("pattern-review.md", "Pattern lane output.\n"),
            ("simplicity-review.md", "Simplicity lane output.\n"),
        ):
            (review_source / name).write_text(text, encoding="utf-8")
        record = json.loads((run.root / paths["record_ref"]).read_text())
        output_ref = record["bindings"]["raw/security.md"]["retained_ref"]
        prompt_ref = record["bindings"]["review/prompt.md"]["retained_ref"]
        paths["report"].write_text(f"[Output]({output_ref}) and [Prompt]({prompt_ref}).\n")

        first = self.preserve(run, paths)
        self.assertEqual("complete", first["status"], first)
        report = Path(first["evidence_path"]) / "report.md"
        report_bytes = report.read_bytes()
        second = self.preserve(run, paths)
        self.assertEqual("complete", second["status"], second)
        self.assertEqual(report_bytes, report.read_bytes())

    def test_cli_reports_missing_retained_link_with_closed_sanitized_details(self):
        run, paths = self.make_run("dm-review", "cli-report-link")
        paths["report"].write_text(
            "[Missing](review/pattern-review.md).\n", encoding="utf-8",
        )
        environment = os.environ.copy()
        references = Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references"
        environment["PYTHONPATH"] = str(references) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            (
                sys.executable, "-m", "workflow_kernel", "preserve-review-evidence",
                "--run-root", str(run.root), "--repository-root", str(self.repo),
                "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
                "--lane-receipts", str(paths["lane_receipts"]),
                "--raw-lane-outputs", str(paths["raw_lane_outputs"]),
                "--raw-findings", str(paths["raw_findings"]),
                "--decisions", str(paths["decisions"]),
                "--private-router-directory", str(paths["router"]),
                "--report", str(paths["report"]),
            ), env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(2, completed.returncode)
        error = json.loads(completed.stderr)["error"]
        self.assertEqual("missing_evidence", error["code"])
        self.assertEqual(ErrorMessage.REVIEW_REPORT_LINK_MISSING.value, error["message"])
        self.assertEqual("review_report_link_missing", error["details"]["reason_code"])
        self.assertEqual("report.md", error["details"]["field"])
        self.assertEqual("review/pattern-review.md", error["details"]["path"])
        self.assertNotIn("Traceback", completed.stderr)

    def test_corrected_source_report_can_be_preserved_after_link_failure(self):
        run, paths = self.make_run("dm-review", "corrected-report")
        paths["report"].write_text("[Missing](review/missing.md).\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "retained review report link is missing"):
            self.preserve(run, paths)
        paths["report"].write_text("[Request](review/request.json).\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertEqual(paths["report"].read_bytes(), (Path(result["evidence_path"]) / "report.md").read_bytes())

    def test_indexed_router_receipt_must_survive_preservation_and_finish(self):
        run, paths = self.make_run("dm-review", "router-index")
        paths["router"].joinpath("security.json").unlink()
        paths["router"].joinpath("unrelated.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(EvidenceAssemblyError) as caught:
            self.preserve(run, paths)
        self.assertEqual({"stage": "preservation_input", "reason": "missing_evidence",
                          "path": "receipts/private/router/security.json"}, caught.exception.detail())
        self.assertTrue(run.root.is_dir())
        paths["router"].joinpath("unrelated.json").unlink()
        paths["router"].joinpath("security.json").write_text(json.dumps({
            "schemaVersion": 1, "receiptId": "dispatch-" + "a" * 24,
            "requested": {}, "attempts": [], "served": None, "fallback": False,
        }) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        Path(result["evidence_path"], "receipts/private/router/security.json").unlink()
        with self.assertRaisesRegex(ValueError, "not durably validated"):
            run.finish("succeeded", retain_diagnostics=True)

    def test_reference_style_report_link_must_resolve(self):
        run, paths = self.make_run("dm-review", "reference-link")
        paths["report"].write_text(
            "[Lane outputs][lane]\n\n[lane]: review/missing.json\n", encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "retained review report link is missing"):
            self.preserve(run, paths)

    def test_retained_recovery_retry_reuses_exact_sources_without_lane_rerun(self):
        run, paths = self.make_run("dm-review", "report-retry")
        paths["report"].write_text(
            "## CLEAN\n\n[Missing evidence](review/missing.md).\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "retained review report"):
            self.preserve(run, paths)
        evidence = next((run.root / "diagnostic/review").iterdir())
        retained = run.finish(
            "failed", retain_diagnostics=True,
            reason="report link validation failed", contains="required source evidence and retry report",
        )
        self.assertEqual("retained", retained.status)
        evidence_request = evidence / "review/request.json"
        paths.update({
            "request": evidence_request,
            "receipts": evidence / "review/authoritative-receipts.json",
            "lane_receipts": evidence / "review/review-lane-receipts.json",
            "raw_lane_outputs": evidence / "review/raw-lane-outputs.json",
            "raw_findings": evidence / "review/raw-finding-inventory.json",
            "decisions": evidence / "review/synthesis-decisions.json",
            "router": evidence / "receipts/private/router",
            "report": evidence / "report.md",
        })
        paths["report"].write_text(
            "## CLEAN\n\n[Lane outputs](review/raw-lane-outputs.json).\n",
            encoding="utf-8",
        )
        before = paths["raw_lane_outputs"].read_bytes()
        retry = self.preserve(run, paths)
        self.assertEqual("complete", retry["status"], retry)
        self.assertEqual(before, (evidence / "review/raw-lane-outputs.json").read_bytes())
        receipt_values = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        self.assertEqual(3, len(receipt_values))
        finished = ExactOwnedRun.open(run.root).finish("succeeded", retain_diagnostics=True)
        self.assertEqual("retained", finished.status)
        self.assertTrue((evidence / "report.md").is_file())

    def test_aggregate_only_head_rewrite_cannot_relabel_old_lane_output(self):
        run, paths = self.make_run("dm-review", "rechecked")
        (self.repo / "source.txt").write_text("repaired source\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "repair"), check=True)
        repository, head = source_identity(self.repo)
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request["source_repository"] = repository
        request["source_head"] = head
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[1]["source_repository"] = repository
        receipts[1]["source_head"] = head
        receipts[2]["source_repository"] = repository
        receipts[2]["source_head"] = head
        receipts[2]["required_browser_cases"] = []
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        with self.assertRaisesRegex(ValueError, "durably validated"):
            run.finish("succeeded", retain_diagnostics=True)

    def test_supported_cli_seals_and_reports_the_durable_evidence_path(self):
        run, paths = self.make_run("dm-review", "cli-closeout")
        environment = os.environ.copy()
        references = Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references"
        environment["PYTHONPATH"] = str(references) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            (
                sys.executable, "-m", "workflow_kernel", "preserve-review-evidence",
                "--run-root", str(run.root), "--repository-root", str(self.repo),
                "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
                "--lane-receipts", str(paths["lane_receipts"]),
                "--raw-lane-outputs", str(paths["raw_lane_outputs"]),
                "--raw-findings", str(paths["raw_findings"]),
                "--decisions", str(paths["decisions"]),
                "--private-router-directory", str(paths["router"]),
                "--report", str(paths["report"]),
            ), env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("complete", result["status"])
        self.assertTrue(Path(result["evidence_path"], "review/authoritative-receipts.json").is_file())

    def test_pipeline_and_loop_owners_use_the_same_single_closeout(self):
        for workflow in ("dm-review-loop", "pipeline"):
            with self.subTest(workflow=workflow):
                run, paths = self.make_run(workflow, "owner-" + workflow)
                result = self.preserve(run, paths)
                self.assertEqual("complete", result["status"])
                first = run.finish("succeeded", retain_diagnostics=True, reason="review evidence sealed", contains="required review evidence")
                second = ExactOwnedRun.open(run.root).finish("succeeded")
                self.assertEqual(first.to_dict(), second.to_dict())
                self.assertEqual(1, len(list((run.root / "diagnostic").glob("review/*"))))

    def test_unrelated_files_and_author_worktrees_survive_exact_review_cleanup(self):
        run, paths = self.make_run()
        unrelated = self.root / "unrelated.txt"
        author_worktree = self.root / "author-worktree"
        unrelated.write_text("preserve", encoding="utf-8")
        subprocess.run(
            ("git", "-C", str(self.repo), "worktree", "add", "--quiet", "--detach", str(author_worktree), "HEAD"),
            check=True,
        )
        (author_worktree / "uncommitted.txt").write_text("author", encoding="utf-8")
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        run.finish("succeeded", retain_diagnostics=True, reason="review evidence sealed", contains="required review evidence")
        self.assertEqual("preserve", unrelated.read_text(encoding="utf-8"))
        self.assertEqual("author", (author_worktree / "uncommitted.txt").read_text(encoding="utf-8"))
        worktrees = subprocess.run(
            ("git", "-C", str(self.repo), "worktree", "list", "--porcelain"),
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn(str(author_worktree), worktrees)
        subprocess.run(
            ("git", "-C", str(self.repo), "worktree", "remove", "--force", str(author_worktree)),
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
